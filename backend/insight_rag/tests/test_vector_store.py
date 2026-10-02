from __future__ import annotations

from types import SimpleNamespace
import pytest

from insight_rag.services import vector_store as vector_module
from insight_rag.services.vector_store import MilvusVectorStore, OUTDATED_SCHEMA_MESSAGE, format_milvus_value


class FakeMilvusClient:
    def __init__(self):
        self.collections = set()
        self.rows = {}
        self.loaded = set()
        self.last_filter = ""
        self.schema_override = None
        self.field_types = {
            "id": "VARCHAR",
            "knowledge_base_id": "VARCHAR",
            "document_id": "VARCHAR",
            "chunk_id": "VARCHAR",
            "chunk_hash": "VARCHAR",
            "source_type": "VARCHAR",
            "embedding": "FLOAT_VECTOR",
        }

    def has_collection(self, name):
        return name in self.collections

    def create_collection(self, collection_name, schema=None):
        self.collections.add(collection_name)

    def create_index(self, collection_name, index_params):
        self.collections.add(collection_name)

    def upsert(self, collection_name, data):
        self.collections.add(collection_name)
        for row in data:
            self.rows[row["id"]] = row

    def flush(self, collection_name):
        self.collections.add(collection_name)

    def describe_collection(self, collection_name):
        if self.schema_override is not None:
            return self.schema_override
        return {
            "fields": [
                {"name": name, "type": field_type}
                for name, field_type in self.field_types.items()
            ]
        }

    def get_collection(self, collection_name):
        client = self

        class FakeCollection:
            def load(self):
                client.loaded.add(collection_name)

        return FakeCollection()

    def search(self, collection_name, data, filter, limit, anns_field, output_fields, search_params):
        if collection_name not in self.loaded:
            raise RuntimeError("collection not loaded")
        self.last_filter = filter
        if 'knowledge_base_id == "' in filter:
            kb_id = filter.split('knowledge_base_id == "')[1].split('"')[0]
        else:
            kb_id = filter.split("knowledge_base_id == ")[1].split()[0]
        matches = [row for row in self.rows.values() if str(row["knowledge_base_id"]) == str(kb_id)]
        return [[{"id": row["id"], "distance": 0.9, "entity": row} for row in matches[:limit]]]

    def delete(self, collection_name, filter):
        if "chunk_id in" in filter:
            ids = {item.strip().strip('"') for item in filter.split("[")[1].split("]")[0].split(",")}
            self.rows = {key: row for key, row in self.rows.items() if str(row["chunk_id"]) not in ids}
        elif "document_id ==" in filter:
            document_id = int(filter.rsplit(" ", 1)[1])
            self.rows = {key: row for key, row in self.rows.items() if row["document_id"] != document_id}


class FakeMilvusFactory:
    @staticmethod
    def create_schema(auto_id=False, enable_dynamic_field=False):
        return SimpleNamespace(add_field=lambda *args, **kwargs: None)

    @staticmethod
    def prepare_index_params():
        return SimpleNamespace(add_index=lambda *args, **kwargs: None)


def test_vector_store_create_upsert_search_delete_health(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="test_chunks", embedding_dim=4, client=fake)

    store.create_collection_if_not_exists()
    vector_ids = store.upsert_embeddings(
        [
            {
                "knowledge_base_id": 1,
                "document_id": 10,
                "chunk_id": 100,
                "chunk_hash": "abc",
                "source_type": "text",
                "embedding": [0.1, 0.2, 0.3, 0.4],
            }
        ]
    )

    assert vector_ids == ["kb1_chunk100"]
    hits = store.search([0.1, 0.2, 0.3, 0.4], knowledge_base_id=1, top_k=5)
    assert hits[0].chunk_id == 100
    assert hits[0].knowledge_base_id == 1
    assert fake.last_filter == 'knowledge_base_id == "1"'
    assert store.health_check()["status"] == "ok"
    store.delete_by_chunk_ids([100])
    assert store.search([0.1, 0.2, 0.3, 0.4], knowledge_base_id=1, top_k=5) == []


def test_create_collection_loads_collection(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)

    store.create_collection_if_not_exists()

    assert "insightrag_chunks" in fake.collections
    assert "insightrag_chunks" in fake.loaded


def test_search_auto_loads_collection(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)
    store.upsert_embeddings(
        [
            {
                "knowledge_base_id": 7,
                "document_id": 70,
                "chunk_id": 700,
                "chunk_hash": "hash",
                "source_type": "text",
                "embedding": [0.1, 0.2, 0.3, 0.4],
            }
        ]
    )
    fake.loaded.clear()

    hits = store.search([0.1, 0.2, 0.3, 0.4], knowledge_base_id=7, top_k=5)

    assert "insightrag_chunks" in fake.loaded
    assert hits[0].chunk_id == 700


def test_search_filters_by_knowledge_base_id(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)
    store.upsert_embeddings(
        [
            {
                "knowledge_base_id": 1,
                "document_id": 10,
                "chunk_id": 100,
                "chunk_hash": "hash-1",
                "source_type": "text",
                "embedding": [0.1, 0.2, 0.3, 0.4],
            },
            {
                "knowledge_base_id": 2,
                "document_id": 20,
                "chunk_id": 200,
                "chunk_hash": "hash-2",
                "source_type": "text",
                "embedding": [0.1, 0.2, 0.3, 0.4],
            },
        ]
    )

    hits = store.search([0.1, 0.2, 0.3, 0.4], knowledge_base_id=2, top_k=5)

    assert [hit.chunk_id for hit in hits] == [200]
    assert fake.last_filter == 'knowledge_base_id == "2"'


def test_format_milvus_value_handles_numeric_and_string_types():
    assert format_milvus_value(1, "INT64") == "1"
    assert format_milvus_value("abc", "VARCHAR") == '"abc"'
    assert format_milvus_value('a"b', "STRING") == '"a\\"b"'


def test_upsert_converts_knowledge_base_id_to_string(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)

    store.upsert_embeddings(
        [
            {
                "knowledge_base_id": "1",
                "document_id": "10",
                "chunk_id": "100",
                "chunk_hash": "hash",
                "source_type": "text",
                "embedding": ["0.1", 0.2, 0.3, 0.4],
            }
        ]
    )

    row = fake.rows["kb1_chunk100"]
    assert row["knowledge_base_id"] == "1"
    assert row["document_id"] == "10"
    assert row["chunk_id"] == "100"
    assert row["embedding"] == [0.1, 0.2, 0.3, 0.4]


def test_search_expr_for_string_knowledge_base_id(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)
    store.upsert_embeddings(
        [
            {
                "knowledge_base_id": "2",
                "document_id": "20",
                "chunk_id": "200",
                "chunk_hash": "hash",
                "source_type": "text",
                "embedding": [0.1, 0.2, 0.3, 0.4],
            }
        ]
    )

    store.search([0.1, 0.2, 0.3, 0.4], knowledge_base_id=2, top_k=5)

    assert fake.last_filter == 'knowledge_base_id == "2"'


def test_normalize_milvus_item_matches_schema(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)
    store.create_collection_if_not_exists()

    row = store.normalize_milvus_item(
        {
            "id": 123,
            "knowledge_base_id": "3",
            "document_id": "30",
            "chunk_id": "300",
            "chunk_hash": 456,
            "source_type": None,
            "embedding": ["1", 2, 3.5, 4],
        }
    )

    assert row == {
        "id": "123",
        "knowledge_base_id": "3",
        "document_id": "30",
        "chunk_id": "300",
        "chunk_hash": "456",
        "source_type": "text",
        "embedding": [1.0, 2.0, 3.5, 4.0],
    }


def test_milvus_schema_uses_varchar_ids(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)

    store.create_collection_if_not_exists()

    field_types = store._collection_field_types()
    assert field_types["knowledge_base_id"] == "VARCHAR"
    assert field_types["document_id"] == "VARCHAR"
    assert field_types["chunk_id"] == "VARCHAR"


def test_normalize_milvus_item_converts_ids_to_string(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)
    store.create_collection_if_not_exists()

    row = store.normalize_milvus_item(
        {
            "id": 900,
            "knowledge_base_id": 9,
            "document_id": 90,
            "chunk_id": 900,
            "chunk_hash": "hash",
            "source_type": "text",
            "embedding": [1, 2, 3, 4],
        }
    )

    assert row["id"] == "900"
    assert row["knowledge_base_id"] == "9"
    assert row["document_id"] == "90"
    assert row["chunk_id"] == "900"


def test_search_expr_uses_quoted_string_kb_id(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)
    store.upsert_embeddings(
        [
            {
                "knowledge_base_id": 4,
                "document_id": 40,
                "chunk_id": 400,
                "chunk_hash": "hash",
                "source_type": "text",
                "embedding": [0.1, 0.2, 0.3, 0.4],
            }
        ]
    )

    store.search([0.1, 0.2, 0.3, 0.4], knowledge_base_id=4, top_k=5)

    assert fake.last_filter == 'knowledge_base_id == "4"'


def test_outdated_int64_schema_raises_clear_error(monkeypatch):
    monkeypatch.setattr(vector_module, "MilvusClient", FakeMilvusFactory)
    monkeypatch.setattr(vector_module, "DataType", SimpleNamespace(VARCHAR="varchar", INT64="int64", FLOAT_VECTOR="vector"))
    fake = FakeMilvusClient()
    fake.collections.add("insightrag_chunks")
    fake.schema_override = {
        "fields": [
            {"name": "id", "type": "VARCHAR"},
            {"name": "knowledge_base_id", "type": "INT64"},
            {"name": "document_id", "type": "VARCHAR"},
            {"name": "chunk_id", "type": "VARCHAR"},
            {"name": "chunk_hash", "type": "VARCHAR"},
            {"name": "source_type", "type": "VARCHAR"},
            {"name": "embedding", "type": "FLOAT_VECTOR"},
        ]
    }
    store = MilvusVectorStore(collection_name="insightrag_chunks", embedding_dim=4, client=fake)

    with pytest.raises(RuntimeError, match="Milvus collection schema is outdated") as exc_info:
        store.create_collection_if_not_exists()

    assert OUTDATED_SCHEMA_MESSAGE in str(exc_info.value)

