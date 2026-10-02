from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from insight_rag.core.config import settings

try:
    from pymilvus import Collection, DataType, MilvusClient, connections
except Exception:  # pragma: no cover - Milvus is optional in offline tests.
    Collection = None
    DataType = None
    MilvusClient = None
    connections = None


@dataclass
class VectorSearchHit:
    chunk_id: int
    document_id: int
    knowledge_base_id: int
    chunk_hash: str
    source_type: str
    score: float
    milvus_vector_id: str


def format_milvus_value(value: Any, field_type: str) -> str:
    normalized = field_type.upper()
    if normalized in {"INT64", "INT32", "FLOAT", "DOUBLE"}:
        return str(value)
    if normalized in {"VARCHAR", "STRING"}:
        escaped = str(value).replace('"', '\\"')
        return f'"{escaped}"'
    raise ValueError(f"Unsupported Milvus field type: {field_type}")


OUTDATED_SCHEMA_MESSAGE = (
    "Milvus collection schema is outdated. "
    "Please drop collection insightrag_chunks and rebuild it."
)


class MilvusVectorStore:
    """Milvus-only vector storage.

    PostgreSQL owns chunk text and citation metadata. Milvus stores only vector
    data plus the identifiers needed to filter and join back to PostgreSQL.
    """

    def __init__(
        self,
        collection_name: str | None = None,
        embedding_dim: int | None = None,
        client: Any | None = None,
    ) -> None:
        self.collection_name = collection_name or settings.active_milvus_collection
        self.embedding_dim = embedding_dim or settings.active_embedding_dim
        self._client = client
        self._alias = f"insightrag_{self.collection_name}"
        self._field_types: dict[str, str] | None = None

    def connect(self) -> Any:
        if self._client is not None:
            return self._client
        if MilvusClient is None:
            raise RuntimeError("pymilvus is not installed. Install pymilvus to use MilvusVectorStore.")
        if connections is not None:
            connections.connect(
                alias=self._alias,
                host=settings.milvus_host,
                port=str(settings.milvus_port),
                user=settings.milvus_user or "",
                password=settings.milvus_password or "",
                db_name=settings.milvus_db_name,
            )
        self._client = MilvusClient(
            uri=settings.milvus_uri,
            user=settings.milvus_user or None,
            password=settings.milvus_password or None,
            db_name=settings.milvus_db_name,
        )
        return self._client

    def create_collection_if_not_exists(self) -> None:
        client = self.connect()
        if client.has_collection(self.collection_name):
            self.check_collection_schema()
            self.ensure_collection_loaded()
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("knowledge_base_id", DataType.VARCHAR, max_length=64)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
        schema.add_field("chunk_hash", DataType.VARCHAR, max_length=128)
        schema.add_field("source_type", DataType.VARCHAR, max_length=32)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        client.create_collection(collection_name=self.collection_name, schema=schema)
        self._safe_create_index()
        self.ensure_collection_loaded()

    def create_index(self) -> None:
        client = self.connect()
        index_params = MilvusClient.prepare_index_params()
        index_type = settings.milvus_index_type.upper()
        metric_type = settings.milvus_metric_type.upper()
        params = {"M": 16, "efConstruction": 200} if index_type == "HNSW" else {"nlist": 128}
        index_params.add_index(
            field_name="embedding",
            index_type=index_type,
            metric_type=metric_type,
            params=params,
        )
        client.create_index(collection_name=self.collection_name, index_params=index_params)

    def ensure_collection_loaded(self) -> Any:
        client = self.connect()
        if not client.has_collection(self.collection_name):
            self.create_collection_if_not_exists()
        else:
            self.check_collection_schema()
        collection = self._collection()
        try:
            collection.load()
        except Exception as exc:
            raise RuntimeError(f"Milvus collection `{self.collection_name}` exists but failed to load: {exc}") from exc
        return collection

    def check_collection_schema(self) -> None:
        field_types = self._collection_field_types(refresh=True)
        required = {
            "id": "VARCHAR",
            "knowledge_base_id": "VARCHAR",
            "document_id": "VARCHAR",
            "chunk_id": "VARCHAR",
            "chunk_hash": "VARCHAR",
            "source_type": "VARCHAR",
            "embedding": "FLOAT_VECTOR",
        }
        for field, expected in required.items():
            actual = field_types.get(field)
            if field in {"knowledge_base_id", "document_id", "chunk_id"} and actual in {"INT64", "INT32"}:
                raise RuntimeError(OUTDATED_SCHEMA_MESSAGE)
            if actual != expected:
                raise RuntimeError(OUTDATED_SCHEMA_MESSAGE)

    def upsert_embeddings(self, items: list[dict[str, Any]]) -> list[str]:
        self.create_collection_if_not_exists()
        rows: list[dict[str, Any]] = []
        vector_ids: list[str] = []
        for item in items:
            vector_id = self._vector_id(item["knowledge_base_id"], item["chunk_id"])
            vector_ids.append(vector_id)
            rows.append(self.normalize_milvus_item({**item, "id": vector_id}))
        if rows:
            client = self.connect()
            client.upsert(collection_name=self.collection_name, data=rows)
            client.flush(collection_name=self.collection_name)
            self._safe_create_index()
            self.ensure_collection_loaded()
        return vector_ids

    def normalize_milvus_item(self, item: dict[str, Any]) -> dict[str, Any]:
        try:
            embedding = [float(value) for value in item["embedding"]]
            if len(embedding) != self.embedding_dim:
                raise ValueError(
                    f"embedding dimension mismatch: expected {self.embedding_dim}, got {len(embedding)}"
                )
            return {
                "id": str(item["id"]),
                "knowledge_base_id": str(item["knowledge_base_id"]),
                "document_id": str(item["document_id"]),
                "chunk_id": str(item["chunk_id"]),
                "chunk_hash": str(item["chunk_hash"]),
                "source_type": str(item.get("source_type") or "text"),
                "embedding": embedding,
            }
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Invalid Milvus item for collection `{self.collection_name}`: {exc}") from exc

    def search(
        self,
        query_embedding: list[float],
        knowledge_base_id: int,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        try:
            self.ensure_collection_loaded()
        except Exception as exc:
            raise RuntimeError(f"Milvus collection `{self.collection_name}` is not searchable: {exc}") from exc
        expr = self._build_filter(knowledge_base_id, filters)
        result = self._search_with_expr(query_embedding, expr, top_k)
        hits: list[VectorSearchHit] = []
        for point in result[0] if result else []:
            entity = point.get("entity", {})
            hits.append(
                VectorSearchHit(
                    chunk_id=int(entity["chunk_id"]),
                    document_id=int(entity["document_id"]),
                    knowledge_base_id=int(entity["knowledge_base_id"]),
                    chunk_hash=str(entity.get("chunk_hash") or ""),
                    source_type=str(entity.get("source_type") or ""),
                    score=float(point.get("distance", 0.0)),
                    milvus_vector_id=str(point.get("id") or entity.get("id") or ""),
                )
            )
        return hits

    def delete_by_chunk_ids(self, chunk_ids: list[int]) -> None:
        if not chunk_ids:
            return
        self.create_collection_if_not_exists()
        ids = ", ".join(format_milvus_value(str(chunk_id), "VARCHAR") for chunk_id in chunk_ids)
        self.connect().delete(collection_name=self.collection_name, filter=f"chunk_id in [{ids}]")

    def delete_by_document_id(self, document_id: int) -> None:
        self.create_collection_if_not_exists()
        value = format_milvus_value(str(document_id), "VARCHAR")
        self.connect().delete(collection_name=self.collection_name, filter=f"document_id == {value}")

    def delete_by_knowledge_base_id(self, knowledge_base_id: int) -> None:
        self.create_collection_if_not_exists()
        value = format_milvus_value(str(knowledge_base_id), "VARCHAR")
        self.connect().delete(collection_name=self.collection_name, filter=f"knowledge_base_id == {value}")

    def health_check(self) -> dict[str, Any]:
        try:
            client = self.connect()
            collection_exists = client.has_collection(self.collection_name)
            loaded = False
            if collection_exists:
                self.ensure_collection_loaded()
                loaded = True
            return {
                "status": "ok",
                "collection": self.collection_name,
                "available": collection_exists,
                "loaded": loaded,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _build_filter(self, knowledge_base_id: int, filters: dict[str, Any] | None) -> str:
        clauses = [f"knowledge_base_id == {format_milvus_value(str(knowledge_base_id), 'VARCHAR')}"]
        filters = filters or {}
        if filters.get("document_id") is not None:
            value = format_milvus_value(str(filters["document_id"]), "VARCHAR")
            clauses.append(f"document_id == {value}")
        if filters.get("chunk_id") is not None:
            value = format_milvus_value(str(filters["chunk_id"]), "VARCHAR")
            clauses.append(f"chunk_id == {value}")
        if filters.get("source_types"):
            values = ", ".join(format_milvus_value(str(value), "VARCHAR") for value in filters["source_types"])
            clauses.append(f"source_type in [{values}]")
        elif filters.get("source_type"):
            source_type = str(filters["source_type"]).replace('"', "")
            clauses.append(f'source_type == "{source_type}"')
        return " and ".join(clauses)

    @staticmethod
    def _vector_id(knowledge_base_id: int, chunk_id: int) -> str:
        return f"kb{int(knowledge_base_id)}_chunk{int(chunk_id)}"

    def _collection(self) -> Any:
        client = self.connect()
        if hasattr(client, "get_collection"):
            return client.get_collection(self.collection_name)
        if Collection is not None:
            return Collection(self.collection_name, using=self._alias)
        if hasattr(client, "load_collection"):
            return _ClientCollectionAdapter(client, self.collection_name)
        raise RuntimeError("Milvus client cannot load collections")

    def _safe_create_index(self) -> None:
        try:
            self.create_index()
        except Exception as exc:
            message = str(exc).lower()
            if "index" not in message or ("exist" not in message and "already" not in message):
                raise

    def _search_with_expr(self, query_embedding: list[float], expr: str, top_k: int) -> Any:
        return self.connect().search(
            collection_name=self.collection_name,
            data=[query_embedding],
            filter=expr,
            limit=top_k,
            anns_field="embedding",
            output_fields=["knowledge_base_id", "document_id", "chunk_id", "chunk_hash", "source_type"],
            search_params={"metric_type": settings.milvus_metric_type.upper()},
        )

    def _collection_field_types(self, refresh: bool = False) -> dict[str, str]:
        if self._field_types and not refresh:
            return self._field_types
        client = self.connect()
        field_types = {
            "id": "VARCHAR",
            "knowledge_base_id": "VARCHAR",
            "document_id": "VARCHAR",
            "chunk_id": "VARCHAR",
            "chunk_hash": "VARCHAR",
            "source_type": "VARCHAR",
            "embedding": "FLOAT_VECTOR",
        }
        try:
            description = client.describe_collection(collection_name=self.collection_name)
            fields = description.get("fields", []) if isinstance(description, dict) else getattr(description, "fields", [])
            for field in fields:
                name = field.get("name") if isinstance(field, dict) else getattr(field, "name", None)
                dtype = self._field_dtype(field)
                if name in field_types and dtype is not None:
                    field_types[name] = self._normalize_field_type(dtype)
        except Exception:
            collection = self._collection()
            schema = getattr(collection, "schema", None)
            fields = getattr(schema, "fields", []) if schema is not None else []
            for field in fields:
                name = getattr(field, "name", None)
                dtype = self._field_dtype(field)
                if name in field_types and dtype is not None:
                    field_types[name] = self._normalize_field_type(dtype)
        self._field_types = field_types
        return field_types

    @staticmethod
    def _normalize_field_type(dtype: Any) -> str:
        if DataType is not None:
            if dtype == getattr(DataType, "VARCHAR", None):
                return "VARCHAR"
            if dtype == getattr(DataType, "FLOAT_VECTOR", None):
                return "FLOAT_VECTOR"
            if dtype == getattr(DataType, "INT64", None):
                return "INT64"
            if dtype == getattr(DataType, "INT32", None):
                return "INT32"
            if dtype == getattr(DataType, "FLOAT", None):
                return "FLOAT"
            if dtype == getattr(DataType, "DOUBLE", None):
                return "DOUBLE"

        text = str(dtype).upper()

        numeric_map = {
            "21": "VARCHAR",
            "101": "FLOAT_VECTOR",
            "5": "INT64",
            "4": "INT32",
            "10": "FLOAT",
            "11": "DOUBLE",
        }

        if text in numeric_map:
            return numeric_map[text]

        for candidate in ("FLOAT_VECTOR", "INT64", "INT32", "FLOAT", "DOUBLE", "VARCHAR", "STRING"):
            if candidate in text:
                return candidate

        return text.rsplit(".", 1)[-1]

    @staticmethod
    def _field_dtype(field: Any) -> Any:
        if isinstance(field, dict):
            return field.get("type") or field.get("data_type") or field.get("dtype")
        return getattr(field, "dtype", None) or getattr(field, "type", None) or getattr(field, "data_type", None)


class _ClientCollectionAdapter:
    def __init__(self, client: Any, collection_name: str) -> None:
        self.client = client
        self.collection_name = collection_name

    def load(self) -> None:
        self.client.load_collection(collection_name=self.collection_name)


def get_vector_store() -> MilvusVectorStore:
    return MilvusVectorStore()


def health_check() -> dict[str, Any]:
    return get_vector_store().health_check()

