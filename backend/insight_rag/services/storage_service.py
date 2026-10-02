from __future__ import annotations

import logging
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from insight_rag.core.config import settings

try:
    import boto3
    from botocore.client import Config as BotoConfig
except Exception:  # pragma: no cover - optional in offline tests.
    boto3 = None
    BotoConfig = None

try:
    import oss2
except Exception:  # pragma: no cover - optional in offline tests.
    oss2 = None


logger = logging.getLogger(__name__)


@dataclass
class StoredObject:
    provider: str
    bucket: str
    object_key: str
    url: str
    content_type: str | None
    size_bytes: int


class ObjectStorageService:
    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or settings.storage_provider).strip().lower()

    def upload_file(self, local_path: str | Path, object_key: str, content_type: str | None = None) -> StoredObject:
        path = Path(local_path)
        data = path.read_bytes()
        return self.upload_bytes(data, object_key, content_type or mimetypes.guess_type(path.name)[0])

    def upload_bytes(self, data: bytes, object_key: str, content_type: str | None = None) -> StoredObject:
        content_type = content_type or "application/octet-stream"
        try:
            if self.provider == "oss":
                return self._upload_oss(data, object_key, content_type)
            if self.provider == "minio":
                return self._upload_minio(data, object_key, content_type)
            return self._upload_local(data, object_key, content_type)
        except Exception as exc:
            if self.provider != "local":
                logger.warning("Object storage provider=%s unavailable, falling back to local storage: %s", self.provider, exc)
                return ObjectStorageService(provider="local").upload_bytes(data, object_key, content_type)
            raise

    def delete_object(self, object_key: str) -> None:
        if self.provider == "oss":
            self._oss_bucket().delete_object(object_key)
            return
        if self.provider == "minio":
            self._s3_client().delete_object(Bucket=settings.minio_bucket, Key=object_key)
            return
        path = self._local_path(object_key)
        if path.exists():
            path.unlink()

    def get_object_url(self, object_key: str) -> str:
        if self.provider == "oss":
            return self._join_url(settings.oss_public_base_url, object_key)
        if self.provider == "minio":
            return self._join_url(settings.minio_public_base_url, object_key)
        return self._join_url(settings.local_public_base_url, object_key)

    def get_url(self, object_key: str) -> str:
        return self.get_object_url(object_key)

    def object_exists(self, object_key: str) -> bool:
        if self.provider == "oss":
            return self._oss_bucket().object_exists(object_key)
        if self.provider == "minio":
            try:
                self._s3_client().head_object(Bucket=settings.minio_bucket, Key=object_key)
                return True
            except Exception:
                return False
        return self._local_path(object_key).exists()

    def _upload_local(self, data: bytes, object_key: str, content_type: str | None) -> StoredObject:
        path = self._local_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject("local", "local", object_key, self.get_object_url(object_key), content_type, len(data))

    def _upload_minio(self, data: bytes, object_key: str, content_type: str | None) -> StoredObject:
        client = self._s3_client()
        try:
            client.create_bucket(Bucket=settings.minio_bucket)
        except Exception as exc:
            message = str(exc).lower()
            if "bucketalready" not in message and "already owned" not in message:
                raise
        client.put_object(Bucket=settings.minio_bucket, Key=object_key, Body=data, ContentType=content_type)
        return StoredObject("minio", settings.minio_bucket, object_key, self.get_object_url(object_key), content_type, len(data))

    def _upload_oss(self, data: bytes, object_key: str, content_type: str | None) -> StoredObject:
        bucket = self._oss_bucket()
        headers = {"Content-Type": content_type} if content_type else None
        bucket.put_object(object_key, data, headers=headers)
        return StoredObject("oss", settings.oss_bucket, object_key, self.get_object_url(object_key), content_type, len(data))

    def _s3_client(self) -> Any:
        if boto3 is None or BotoConfig is None:
            raise RuntimeError("boto3 is not installed")
        return boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=BotoConfig(signature_version="s3v4"),
        )

    def _oss_bucket(self) -> Any:
        if oss2 is None:
            raise RuntimeError("oss2 is not installed")
        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        return oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket)

    def _local_path(self, object_key: str) -> Path:
        root = Path(settings.local_storage_dir)
        path = (root / object_key).resolve()
        root_resolved = root.resolve()
        if root_resolved not in path.parents and path != root_resolved:
            raise ValueError(f"Invalid object_key outside storage root: {object_key}")
        return path

    @staticmethod
    def _join_url(base: str, object_key: str) -> str:
        return f"{base.rstrip('/')}/{object_key.lstrip('/')}"


def image_object_key_for_pdf(knowledge_base_id: int, document_id: int, page_number: int, image_index: int, ext: str = "png") -> str:
    ext = ext.lower().lstrip(".") or "png"
    return (
        f"{settings.storage_prefix}/{knowledge_base_id}/documents/{document_id}/"
        f"images/page_{page_number}/image_{image_index}.{ext}"
    )


def image_object_key_for_upload(knowledge_base_id: int, asset_id: int | str, ext: str = "png") -> str:
    ext = ext.lower().lstrip(".") or "png"
    return f"{settings.storage_prefix}/{knowledge_base_id}/uploads/images/{asset_id}.{ext}"


def get_storage_service() -> ObjectStorageService:
    return ObjectStorageService()

