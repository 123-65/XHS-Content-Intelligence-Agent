from __future__ import annotations


def test_upload_image_to_minio_or_mock_storage(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "local_public_base_url", "http://local.test")
    storage = ObjectStorageService(provider="local")
    stored = storage.upload_bytes(b"image-bytes", "knowledge-bases/1/uploads/images/a.png", "image/png")

    assert stored.provider == "local"
    assert stored.size_bytes == 11
    assert storage.object_exists(stored.object_key)


def test_object_key_is_stable_and_traceable():
    from insight_rag.services.storage_service import image_object_key_for_pdf, image_object_key_for_upload

    assert image_object_key_for_pdf(1, 23, 5, 1) == "knowledge-bases/1/documents/23/images/page_5/image_1.png"
    assert image_object_key_for_upload(1, "asset-1", "jpg") == "knowledge-bases/1/uploads/images/asset-1.jpg"


def test_delete_object(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    storage = ObjectStorageService(provider="local")
    stored = storage.upload_bytes(b"data", "knowledge-bases/1/uploads/images/delete.png")
    assert storage.object_exists(stored.object_key)

    storage.delete_object(stored.object_key)

    assert not storage.object_exists(stored.object_key)


def test_get_object_url(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "local_public_base_url", "http://localhost/assets")
    storage = ObjectStorageService(provider="local")

    assert storage.get_object_url("knowledge-bases/1/uploads/images/a.png") == "http://localhost/assets/knowledge-bases/1/uploads/images/a.png"

