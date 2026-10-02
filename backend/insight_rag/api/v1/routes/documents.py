from pathlib import Path
from uuid import uuid4
import hashlib
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from insight_rag.core.config import settings
from insight_rag.core.db import get_db
from insight_rag.models.chunk import Chunk
from insight_rag.models.document import Document
from insight_rag.models.knowledge_base import KnowledgeBase
from insight_rag.models.multimodal_asset import MultimodalAsset
from insight_rag.schemas.document import DocumentOut, EmbedResponse
from insight_rag.services.chunker import rough_token_count, split_text
from insight_rag.services.indexing_service import delete_document_embeddings, index_document
from insight_rag.services.multimodal_service import IMAGE_EXTENSIONS, create_image_asset_from_upload, extract_pdf_image_assets
from insight_rag.services.parser import SUPPORTED_EXTENSIONS, clean_extracted_text, is_noise_chunk, parse_document, split_pdf_pages
from insight_rag.services.storage_service import ObjectStorageService

router = APIRouter()
logger = logging.getLogger(__name__)


def _create_chunks_for_document(
    db: Session,
    doc: Document,
    kb: KnowledgeBase,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> int:
    logger.info("document.parse_text.start document_id=%s filename=%s", doc.id, doc.filename)
    raw_text = parse_document(Path(doc.storage_path))
    size = chunk_size or kb.chunk_size
    overlap = chunk_overlap or kb.chunk_overlap
    raw_length = len(raw_text)
    cleaned_length = 0
    discarded_chunks = 0
    chunk_rows: list[dict] = []

    if doc.file_type == "pdf":
        pages = split_pdf_pages(raw_text)
        logger.info("Parsed PDF document_id=%s pages=%s raw_length=%s", doc.id, len(pages), raw_length)
        for page_number, page_text in pages:
            cleaned_page = clean_extracted_text(page_text)
            cleaned_length += len(cleaned_page)
            for content in split_text(cleaned_page, size, overlap):
                if is_noise_chunk(content):
                    discarded_chunks += 1
                    continue
                chunk_rows.append({"content": content, "page_number": page_number})
    else:
        cleaned_text = clean_extracted_text(raw_text)
        cleaned_length = len(cleaned_text)
        for content in split_text(cleaned_text, size, overlap):
            if is_noise_chunk(content):
                discarded_chunks += 1
                continue
            chunk_rows.append({"content": content, "page_number": None})

    if not chunk_rows:
        raise ValueError("Document did not produce any valid chunks after cleaning")

    for index, row in enumerate(chunk_rows):
        content = row["content"]
        db.add(
            Chunk(
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                content=content,
                chunk_text=content,
                chunk_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                chunk_index=index,
                page_number=row["page_number"],
                token_count=rough_token_count(content),
                source_type="table" if doc.file_type == "xlsx" else "text",
                meta={"filename": doc.filename, "file_type": doc.file_type, "page_number": row["page_number"]},
            )
        )

    logger.info(
        "document.parse_text.done document_id=%s raw_length=%s cleaned_length=%s discarded_noise_chunks=%s valid_chunks=%s",
        doc.id,
        raw_length,
        cleaned_length,
        discarded_chunks,
        len(chunk_rows),
    )
    return len(chunk_rows)


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    knowledge_base_id: int = Form(...),
    file: UploadFile = File(...),
    chunk_size: int | None = Form(None),
    chunk_overlap: int | None = Form(None),
    db: Session = Depends(get_db),
):
    kb = db.get(KnowledgeBase, knowledge_base_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    original_name = file.filename or "upload"
    ext = Path(original_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f"{uuid4().hex}{ext}"
    file_bytes = await file.read()
    storage_path.write_bytes(file_bytes)
    logger.info(
        "document.upload.saved knowledge_base_id=%s filename=%s bytes=%s path=%s",
        knowledge_base_id,
        original_name,
        len(file_bytes),
        storage_path,
    )

    doc = Document(
        knowledge_base_id=knowledge_base_id,
        filename=original_name,
        file_type=ext.lstrip("."),
        storage_path=str(storage_path),
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        if ext in IMAGE_EXTENSIONS:
            logger.info("document.upload.image_asset.start document_id=%s", doc.id)
            create_image_asset_from_upload(db, doc, file_bytes, original_name, file.content_type)
        else:
            _create_chunks_for_document(db, doc, kb, chunk_size, chunk_overlap)
            if ext == ".pdf":
                logger.info("document.upload.pdf_images.start document_id=%s", doc.id)
                extract_pdf_image_assets(db, doc)
                logger.info("document.upload.pdf_images.done document_id=%s", doc.id)
        doc.status = "parsed"
        doc.error_message = None
        db.commit()
        db.refresh(doc)
    except Exception as exc:
        db.rollback()
        logger.exception("document.upload.parse_failed document_id=%s filename=%s", doc.id, original_name)
        doc = db.get(Document, doc.id)
        if not doc:
            raise HTTPException(status_code=400, detail=f"Document upload failed before parsing: {exc}") from exc
        doc.status = "parse_failed"
        doc.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(knowledge_base_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Document)
    if knowledge_base_id:
        query = query.filter(Document.knowledge_base_id == knowledge_base_id)
    return query.order_by(Document.created_at.desc()).all()


@router.post("/{document_id}/reparse", response_model=DocumentOut)
def reparse_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).with_for_update().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    kb = db.get(KnowledgeBase, doc.knowledge_base_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    if not Path(doc.storage_path).exists():
        raise HTTPException(status_code=404, detail="Stored file not found")

    try:
        logger.info("document.reparse.delete_embeddings.start document_id=%s", document_id)
        delete_document_embeddings(db, document_id)
    except Exception:
        logger.exception("Failed to delete old document embeddings document_id=%s", document_id)
    db.query(Chunk).filter(Chunk.document_id == document_id).delete(synchronize_session=False)
    _delete_multimodal_assets(db, document_id)
    db.flush()

    try:
        logger.info("document.reparse.start document_id=%s", document_id)
        _create_chunks_for_document(db, doc, kb)
        if doc.file_type == "pdf":
            logger.info("document.reparse.pdf_images.start document_id=%s", document_id)
            extract_pdf_image_assets(db, doc)
            logger.info("document.reparse.pdf_images.done document_id=%s", document_id)
        doc.status = "parsed"
        doc.error_message = None
        db.commit()
        db.refresh(doc)
        return doc
    except Exception as exc:
        db.rollback()
        logger.exception("document.reparse.failed document_id=%s", document_id)
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=409,
                detail="Document was deleted while reparse was running. Refresh the document list and upload again.",
            ) from exc
        doc.status = "parse_failed"
        doc.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=f"reparse failed: {exc}") from exc


@router.post("/{document_id}/embed", response_model=EmbedResponse)
async def embed_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        count = await index_document(db, document_id)
        return EmbedResponse(document_id=document_id, embedded_chunks=count)
    except Exception as exc:
        doc.status = "embed_failed"
        doc.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).with_for_update().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        delete_document_embeddings(db, document_id)
    except Exception:
        logger.exception("Failed to delete document embeddings document_id=%s", document_id)

    path = Path(doc.storage_path)
    if path.exists() and path.is_file():
        path.unlink()

    _delete_multimodal_assets(db, document_id)
    db.delete(doc)
    db.commit()
    return {"message": "deleted"}


@router.get("/{document_id}/multimodal-summary")
def multimodal_summary(document_id: int, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    assets = db.query(MultimodalAsset).filter(
        MultimodalAsset.document_id == document_id,
        MultimodalAsset.deleted.is_(False),
    )
    return {
        "images": assets.filter(MultimodalAsset.asset_type.in_(["image", "figure", "chart", "diagram"])).count(),
        "tables": assets.filter(MultimodalAsset.asset_type == "table_image").count(),
        "ocr_chunks": db.query(Chunk)
        .filter(Chunk.document_id == document_id, Chunk.source_type == "ocr", Chunk.deleted.is_(False))
        .count(),
        "caption_chunks": db.query(Chunk)
        .filter(Chunk.document_id == document_id, Chunk.source_type == "image_caption", Chunk.deleted.is_(False))
        .count(),
    }


@router.get("/{document_id}/multimodal-debug")
def multimodal_debug(document_id: int, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    assets = (
        db.query(MultimodalAsset)
        .filter(MultimodalAsset.document_id == document_id, MultimodalAsset.deleted.is_(False))
        .order_by(MultimodalAsset.page_number.asc(), MultimodalAsset.image_index.asc(), MultimodalAsset.id.asc())
        .all()
    )
    return [
        {
            "page": asset.page_number,
            "image_index": asset.image_index,
            "ocr": asset.ocr_text,
            "caption": asset.image_caption,
            "oss_url": asset.image_url or asset.public_url,
            "object_key": asset.object_key,
            "asset_type": asset.asset_type,
            "width": asset.width,
            "height": asset.height,
        }
        for asset in assets
    ]


def _delete_multimodal_assets(db: Session, document_id: int) -> None:
    storage = ObjectStorageService()
    assets = db.query(MultimodalAsset).filter(MultimodalAsset.document_id == document_id).all()
    for asset in assets:
        try:
            storage.delete_object(asset.object_key)
        except Exception:
            logger.exception("Failed to delete multimodal object object_key=%s", asset.object_key)
        db.delete(asset)

