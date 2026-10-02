from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil

from sqlalchemy.orm import Session

from insight_rag.models.chunk import Chunk
from insight_rag.models.document import Document
from insight_rag.models.multimodal_asset import MultimodalAsset
from insight_rag.services.chunker import rough_token_count
from insight_rag.services.llm import caption_image_bytes, ocr_image_bytes
from insight_rag.services.storage_service import ObjectStorageService, image_object_key_for_pdf, image_object_key_for_upload

try:
    import fitz
except Exception:  # pragma: no cover - optional parser dependency.
    fitz = None


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ASSET_TYPES = {"image", "figure", "chart", "diagram", "table_image"}


def extract_pdf_image_assets(
    db: Session,
    doc: Document,
    storage: ObjectStorageService | None = None,
    tmp_root: str | Path = "storage/tmp",
) -> list[MultimodalAsset]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed")
    storage = storage or ObjectStorageService()
    assets: list[MultimodalAsset] = []
    tmp_dir = Path(tmp_root) / "documents" / str(doc.id) / "images"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        with fitz.open(doc.storage_path) as pdf:
            for page_index, page in enumerate(pdf, start=1):
                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    xref = image_info[0]
                    extracted = pdf.extract_image(xref)
                    data = extracted.get("image") or b""
                    if not data:
                        continue
                    pix = fitz.Pixmap(pdf, xref)
                    png_data = pix.tobytes("png")
                    width, height = pix.width, pix.height
                    pix = None
                    tmp_path = tmp_dir / f"page_{page_index}_image_{image_index}.png"
                    tmp_path.write_bytes(png_data)
                    assets.append(
                        create_pdf_image_asset(
                            db,
                            doc,
                            tmp_path.read_bytes(),
                            page_number=page_index,
                            image_index=image_index,
                            ext="png",
                            storage=storage,
                            width=width,
                            height=height,
                        )
                    )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return assets


def create_image_asset_from_upload(
    db: Session,
    doc: Document,
    data: bytes,
    original_filename: str,
    content_type: str | None,
    storage: ObjectStorageService | None = None,
) -> MultimodalAsset:
    ext = Path(original_filename).suffix.lower().lstrip(".") or "png"
    asset_seed = hashlib.sha256(data).hexdigest()[:24]
    object_key = image_object_key_for_upload(doc.knowledge_base_id, asset_seed, ext)
    return _create_image_asset(
        db,
        doc,
        data,
        object_key,
        original_filename=original_filename,
        content_type=content_type or f"image/{ext}",
        asset_type="image",
        page_number=None,
        image_index=None,
        storage=storage,
    )


def create_pdf_image_asset(
    db: Session,
    doc: Document,
    data: bytes,
    page_number: int,
    image_index: int,
    ext: str = "png",
    storage: ObjectStorageService | None = None,
    width: int | None = None,
    height: int | None = None,
) -> MultimodalAsset:
    object_key = image_object_key_for_pdf(doc.knowledge_base_id, doc.id, page_number, image_index, ext)
    return _create_image_asset(
        db,
        doc,
        data,
        object_key,
        original_filename=f"page_{page_number}_image_{image_index}.{ext}",
        content_type=f"image/{ext}",
        asset_type="figure",
        page_number=page_number,
        image_index=image_index,
        storage=storage,
        width=width,
        height=height,
    )


def _create_image_asset(
    db: Session,
    doc: Document,
    data: bytes,
    object_key: str,
    original_filename: str,
    content_type: str | None,
    asset_type: str,
    page_number: int | None,
    image_index: int | None,
    storage: ObjectStorageService | None,
    width: int | None = None,
    height: int | None = None,
) -> MultimodalAsset:
    storage = storage or ObjectStorageService()
    stored = storage.upload_bytes(data, object_key, content_type)
    ocr_text = ocr_image_bytes(data, content_type or "image/png")
    caption = caption_image_bytes(data, content_type or "image/png")
    caption = _enrich_caption(caption, asset_type, page_number, image_index)
    asset_type = _infer_asset_type(caption, ocr_text, asset_type)
    asset = MultimodalAsset(
        knowledge_base_id=doc.knowledge_base_id,
        document_id=doc.id,
        asset_type=asset_type,
        original_filename=original_filename,
        content_type=content_type,
        bucket=stored.bucket,
        object_key=stored.object_key,
        public_url=stored.url,
        image_url=stored.url,
        page_number=page_number,
        image_index=image_index,
        width=width,
        height=height,
        file_size=stored.size_bytes,
        ocr_text=ocr_text,
        image_caption=caption,
    )
    db.add(asset)
    db.flush()
    asset.ocr_chunk_id = _create_asset_chunk(db, doc, asset, ocr_text, "ocr") if ocr_text else None
    asset.caption_chunk_id = _create_asset_chunk(db, doc, asset, caption, "image_caption") if caption else None
    return asset


def _create_asset_chunk(db: Session, doc: Document, asset: MultimodalAsset, text: str, source_type: str) -> int:
    content = text.strip()
    chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        content=content,
        chunk_text=content,
        chunk_hash=hashlib.sha256(f"{asset.object_key}:{source_type}:{content}".encode("utf-8")).hexdigest(),
        chunk_index=_next_chunk_index(db, doc.id),
        page_number=asset.page_number,
        source_type=source_type,
        token_count=rough_token_count(content),
        meta={
            "filename": doc.filename,
            "asset_type": asset.asset_type,
            "object_key": asset.object_key,
            "public_url": asset.public_url,
            "image_url": asset.image_url or asset.public_url,
            "page_number": asset.page_number,
            "image_index": asset.image_index,
            "figure": _figure_label(asset.image_caption, asset.ocr_text, asset.image_index),
            "width": asset.width,
            "height": asset.height,
        },
    )
    db.add(chunk)
    db.flush()
    return chunk.id


def _next_chunk_index(db: Session, document_id: int) -> int:
    current = db.query(Chunk).filter(Chunk.document_id == document_id).count()
    return int(current)


def _infer_asset_type(caption: str, ocr_text: str, default: str) -> str:
    text = f"{caption}\n{ocr_text}".lower()
    if "table" in text or "表" in text:
        return "table_image"
    if "chart" in text or "plot" in text or "axis" in text or "柱状" in text or "折线" in text:
        return "chart"
    if "diagram" in text or "architecture" in text or "flow" in text or "流程" in text:
        return "diagram"
    if "figure" in text or "fig." in text or "图" in text:
        return "figure"
    return default if default in ASSET_TYPES else "image"


def _enrich_caption(caption: str, asset_type: str, page_number: int | None, image_index: int | None) -> str:
    prefix = f"{asset_type}"
    if page_number is not None:
        prefix += f" on page {page_number}"
    if image_index is not None:
        prefix += f", image {image_index}"
    return f"{prefix}: {caption.strip()}" if caption.strip() else prefix


def _figure_label(caption: str | None, ocr_text: str | None, image_index: int | None) -> str | None:
    text = f"{caption or ''}\n{ocr_text or ''}"
    match = re.search(r"\b(?:Figure|Fig\.)\s*([0-9]+[A-Za-z]?)\b|图\s*([0-9]+[A-Za-z]?)", text, re.IGNORECASE)
    if match:
        return f"Figure {match.group(1) or match.group(2)}"
    if image_index is not None:
        return f"Image {image_index}"
    return None

