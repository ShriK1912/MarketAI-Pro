from __future__ import annotations

from functools import lru_cache
from typing import Any

from sentence_transformers import SentenceTransformer

from config import get_settings
from services.data_loader import load_seed_posts

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None


class InMemoryCollection:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def count(self) -> int:
        return len(self._items)

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
        for item_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            self._items.append(
                {"id": item_id, "document": document, "metadata": metadata, "embedding": embedding}
            )

    def query(self, query_texts: list[str], n_results: int, where: dict[str, Any] | None = None) -> dict[str, list[list[Any]]]:
        del query_texts
        filtered = self._items
        if where and "$and" in where:
            for condition in where["$and"]:
                key, value = next(iter(condition.items()))
                if isinstance(value, dict) and "$gte" in value:
                    filtered = [item for item in filtered if float(item["metadata"].get(key, 0.0)) >= value["$gte"]]
                else:
                    filtered = [item for item in filtered if item["metadata"].get(key) == value]
        top_items = filtered[:n_results]
        return {
            "ids": [[item["id"] for item in top_items]],
            "documents": [[item["document"] for item in top_items]],
            "metadatas": [[item["metadata"] for item in top_items]],
        }


class LocalFallbackEmbedder:
    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 32
            for index, char in enumerate(text.lower()):
                vector[index % 32] += (ord(char) % 31) / 31.0
            if normalize_embeddings:
                norm = sum(value * value for value in vector) ** 0.5 or 1.0
                vector = [value / norm for value in vector]
            vectors.append(vector)
        return vectors


class MemoryService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = chromadb.PersistentClient(path=settings.chroma_dir) if chromadb is not None else None
        try:
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        except Exception:
            self.embedding_model = LocalFallbackEmbedder()
        if self.client is not None:
            self.posts_collection = self.client.get_or_create_collection(name="posts")
            self.brand_collection = self.client.get_or_create_collection(name="brand")
        else:
            self.posts_collection = InMemoryCollection()
            self.brand_collection = InMemoryCollection()

    def pre_warm(self) -> None:
        self.embedding_model.encode(["warm start"], normalize_embeddings=True)
        try:
            if self.posts_collection.count() == 0:
                self.seed_posts()
            if self.brand_collection.count() == 0:
                self.seed_brand()
        except Exception as exc:
            if self._is_dimension_mismatch(exc):
                self.reset_collections()
                self.seed_posts()
                self.seed_brand()
            else:
                raise

    def seed_posts(self) -> None:
        posts = load_seed_posts()
        documents = [item["text"][:320] for item in posts]
        ids = [item["id"] for item in posts]
        metadatas = [
            {
                "platform": item["platform"],
                "engagement_score": float(item["engagement_score"]),
                "tone": item.get("tone", ""),
            }
            for item in posts
        ]
        embeddings = self._encode(documents)
        try:
            self.posts_collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        except Exception as exc:
            if self._is_dimension_mismatch(exc):
                self.reset_collections()
                self.posts_collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
            else:
                raise

    def seed_brand(self) -> None:
        seed_docs = [
            "Brand voice is clear, confident, practical, and grounded in actual product value.",
            "Avoid hype, unsupported claims, and competitor references.",
        ]
        embeddings = self._encode(seed_docs)
        try:
            self.brand_collection.add(
                ids=["brand-001", "brand-002"],
                documents=seed_docs,
                metadatas=[{"type": "voice"}, {"type": "guardrail"}],
                embeddings=embeddings,
            )
        except Exception as exc:
            if self._is_dimension_mismatch(exc):
                self.reset_collections()
                self.brand_collection.add(
                    ids=["brand-001", "brand-002"],
                    documents=seed_docs,
                    metadatas=[{"type": "voice"}, {"type": "guardrail"}],
                    embeddings=embeddings,
                )
            else:
                raise

    def retrieve_similar(self, query: str, platform: str, k: int = 3) -> list[dict[str, Any]]:
        where = {"$and": [{"platform": platform}, {"engagement_score": {"$gte": 0.6}}]}
        try:
            results = self.posts_collection.query(query_texts=[query], n_results=k, where=where)
        except Exception as exc:
            if self._is_dimension_mismatch(exc):
                self.reset_collections()
                self.seed_posts()
                self.seed_brand()
                results = self.posts_collection.query(query_texts=[query], n_results=k, where=where)
            else:
                raise
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        ids = results.get("ids", [[]])[0]
        return [
            {"id": doc_id, "text": doc, "metadata": metadata}
            for doc_id, doc, metadata in zip(ids, documents, metadatas)
        ]

    def top_brand_posts(self) -> list[str]:
        items = load_seed_posts()
        ranked = sorted(items, key=lambda item: item["engagement_score"], reverse=True)
        return [item["text"] for item in ranked[:3]]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.embedding_model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings

    def reset_collections(self) -> None:
        if self.client is None:
            self.posts_collection = InMemoryCollection()
            self.brand_collection = InMemoryCollection()
            return
        try:
            self.client.delete_collection("posts")
        except Exception:
            pass
        try:
            self.client.delete_collection("brand")
        except Exception:
            pass
        self.posts_collection = self.client.get_or_create_collection(name="posts")
        self.brand_collection = self.client.get_or_create_collection(name="brand")

    def _is_dimension_mismatch(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "dimension" in message and ("embedding" in message or "expecting" in message)


@lru_cache
def get_memory_service() -> MemoryService:
    service = MemoryService()
    service.pre_warm()
    return service
