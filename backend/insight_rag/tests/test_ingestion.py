from __future__ import annotations

def test_pdf_removes_trial_watermark_noise():
    from insight_rag.services.chunker import split_text
    from insight_rag.services.parser import clean_extracted_text, is_noise_chunk, split_pdf_pages

    raw = "# Page 5 此为试读,需要完整PDF请访问: www.ertongbook.com"
    valid_chunks = []
    for _page_number, page_text in split_pdf_pages(raw):
        cleaned = clean_extracted_text(page_text)
        for chunk in split_text(cleaned, 800, 120):
            if not is_noise_chunk(chunk):
                valid_chunks.append(chunk)

    assert valid_chunks == []


def test_pdf_extracts_images_and_uploads_to_storage(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.models.multimodal_asset import MultimodalAsset
    from insight_rag.services.multimodal_service import create_pdf_image_asset
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    db, _kb, doc = _sqlite_document_fixture(file_type="pdf")
    asset = create_pdf_image_asset(db, doc, b"png-bytes", page_number=5, image_index=1, storage=ObjectStorageService("local"))
    db.commit()

    assert db.query(MultimodalAsset).count() == 1
    assert asset.object_key.endswith("/documents/1/images/page_5/image_1.png")
    assert asset.public_url


def test_uploaded_image_creates_multimodal_asset(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.models.multimodal_asset import MultimodalAsset
    from insight_rag.services.multimodal_service import create_image_asset_from_upload
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    db, _kb, doc = _sqlite_document_fixture(file_type="png")
    asset = create_image_asset_from_upload(db, doc, b"image-bytes", "地图.png", "image/png", ObjectStorageService("local"))
    db.commit()

    assert db.query(MultimodalAsset).count() == 1
    assert asset.original_filename == "地图.png"
    assert "/uploads/images/" in asset.object_key


def test_image_ocr_and_caption_create_chunks(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.models.chunk import Chunk
    from insight_rag.services.multimodal_service import create_image_asset_from_upload
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    db, _kb, doc = _sqlite_document_fixture(file_type="jpg")
    asset = create_image_asset_from_upload(db, doc, b"image-bytes", "photo.jpg", "image/jpeg", ObjectStorageService("local"))
    db.commit()
    source_types = {chunk.source_type for chunk in db.query(Chunk).all()}

    assert {"ocr", "image_caption"}.issubset(source_types)
    assert asset.ocr_chunk_id is not None
    assert asset.caption_chunk_id is not None


def test_image_chunks_are_written_to_milvus(tmp_path, monkeypatch):
    import asyncio
    from insight_rag.core.config import settings
    from insight_rag.services import indexing_service
    from insight_rag.services.multimodal_service import create_image_asset_from_upload
    from insight_rag.services.storage_service import ObjectStorageService

    class RecordingVectorStore:
        def __init__(self):
            self.upserts = []

        def upsert_embeddings(self, items):
            self.upserts.extend(items)
            return [f"vector-{item['chunk_id']}" for item in items]

    async def fake_embed(texts):
        return [[0.1] * settings.active_embedding_dim for _ in texts]

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    monkeypatch.setattr(indexing_service, "embed_texts", fake_embed)
    db, _kb, doc = _sqlite_document_fixture(file_type="png")
    create_image_asset_from_upload(db, doc, b"image-bytes", "photo.png", "image/png", ObjectStorageService("local"))
    db.commit()
    store = RecordingVectorStore()

    count = asyncio.run(indexing_service.index_document(db, doc.id, vector_store=store))

    assert count == 2
    assert {item["source_type"] for item in store.upserts} == {"ocr", "image_caption"}


def _sqlite_document_fixture(file_type: str = "txt"):
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from insight_rag.core.db import Base
    from insight_rag.models.document import Document
    from insight_rag.models.knowledge_base import KnowledgeBase

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    kb = KnowledgeBase(name=f"kb-ingestion-{file_type}", chunk_size=800, chunk_overlap=120)
    db.add(kb)
    db.commit()
    doc = Document(
        knowledge_base_id=kb.id,
        filename=f"sample.{file_type}",
        file_type=file_type,
        storage_path=str(Path("fixture") / f"sample.{file_type}"),
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    return db, kb, doc

