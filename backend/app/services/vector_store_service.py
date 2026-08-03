"""
vector_store_service.py — Enterprise Vector Store Abstraction
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Abstract vector store interface supporting:
- Chroma (local, embedded)
- Pinecone (cloud)
- Qdrant (cloud/local)
- pgvector (PostgreSQL)
- Weaviate
- Milvus

Provides:
- Document indexing with metadata and tenant isolation
- Similarity search with filtering
- Collection management
- Tenant-scoped namespacing
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import (
    VectorDocument,
    VectorSearchQuery,
    VectorSearchResult,
    VectorSearchResponse,
    VectorStoreConfig,
    VectorStoreType,
)

logger = logging.getLogger(__name__)


# =============================================================================
#  Abstract Vector Store
# =============================================================================

class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations."""

    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self._index_name = config.index_name
        self._dimension = config.dimension
        self._metric = config.metric
        self._tenant_namespace = config.tenant_namespace

    @abstractmethod
    async def index_document(self, doc: VectorDocument) -> str:
        """Index a single document."""
        pass

    @abstractmethod
    async def index_documents(self, docs: list[VectorDocument]) -> list[str]:
        """Index multiple documents."""
        pass

    @abstractmethod
    async def search(self, query: VectorSearchQuery) -> VectorSearchResponse:
        """Search for similar documents."""
        pass

    @abstractmethod
    async def delete_document(self, doc_id: str, collection: str = "default",
                              tenant_id: Optional[str] = None) -> bool:
        """Delete a document by ID."""
        pass

    @abstractmethod
    async def delete_collection(self, collection: str,
                                tenant_id: Optional[str] = None) -> bool:
        """Delete an entire collection."""
        pass

    @abstractmethod
    async def collection_stats(self, collection: str = "default",
                               tenant_id: Optional[str] = None) -> dict:
        """Get collection statistics."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check vector store health."""
        pass

    def _namespace(self, collection: str, tenant_id: Optional[str] = None) -> str:
        """Build namespaced collection name for tenant isolation."""
        if self._tenant_namespace and tenant_id:
            return f"{tenant_id}:{collection}"
        return collection


# =============================================================================
#  Chroma Vector Store (Local)
# =============================================================================

class ChromaVectorStore(BaseVectorStore):
    """ChromaDB vector store (local, embedded)."""

    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._client = None
        self._collections: dict[str, Any] = {}

    async def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                persist_directory = self.config.connection_string or "./chroma_data"
                self._client = chromadb.PersistentClient(path=persist_directory)
            except ImportError:
                logger.warning("chromadb not installed, using ephemeral client")
                import chromadb
                self._client = chromadb.EphemeralClient()
        return self._client

    async def _get_collection(self, namespace: str):
        client = await self._get_client()
        if namespace not in self._collections:
            try:
                self._collections[namespace] = client.get_collection(namespace)
            except Exception:
                self._collections[namespace] = client.create_collection(
                    name=namespace,
                    metadata={"hnsw:space": self._metric},
                )
        return self._collections[namespace]

    async def index_document(self, doc: VectorDocument) -> str:
        namespace = self._namespace(doc.collection, doc.tenant_id)
        collection = await self._get_collection(namespace)
        collection.add(
            ids=[doc.id],
            embeddings=[doc.embedding] if doc.embedding else None,
            documents=[doc.text],
            metadatas=[{
                **doc.metadata,
                "tenant_id": doc.tenant_id or "",
                "chunk_index": doc.chunk_index,
            }],
        )
        return doc.id

    async def index_documents(self, docs: list[VectorDocument]) -> list[str]:
        if not docs:
            return []
        namespace = self._namespace(docs[0].collection, docs[0].tenant_id)
        collection = await self._get_collection(namespace)
        ids = [d.id for d in docs]
        embeddings = [d.embedding for d in docs if d.embedding] or None
        documents = [d.text for d in docs]
        metadatas = [{
            **d.metadata,
            "tenant_id": d.tenant_id or "",
            "chunk_index": d.chunk_index,
        } for d in docs]
        collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        return ids

    async def search(self, query: VectorSearchQuery) -> VectorSearchResponse:
        namespace = self._namespace(query.collection, query.tenant_id)
        collection = await self._get_collection(namespace)

        where_filter = None
        if query.filters:
            where_filter = {}
            for k, v in query.filters.items():
                if isinstance(v, str):
                    where_filter[k] = v
                elif isinstance(v, (int, float)):
                    where_filter[k] = v

        start_time = time.time()
        results = collection.query(
            query_texts=[query.query],
            n_results=query.top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        latency_ms = (time.time() - start_time) * 1000

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                score = 1.0 - (results["distances"][0][i] if results.get("distances") else 0)
                if score >= query.threshold:
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    search_results.append(VectorSearchResult(
                        id=doc_id,
                        score=round(score, 4),
                        text=results["documents"][0][i] if results.get("documents") else "",
                        metadata=metadata,
                        tenant_id=metadata.get("tenant_id"),
                        collection=query.collection,
                    ))

        return VectorSearchResponse(
            query=query.query,
            results=search_results,
            total=len(search_results),
            latency_ms=round(latency_ms, 2),
        )

    async def delete_document(self, doc_id: str, collection: str = "default",
                              tenant_id: Optional[str] = None) -> bool:
        namespace = self._namespace(collection, tenant_id)
        col = await self._get_collection(namespace)
        col.delete(ids=[doc_id])
        return True

    async def delete_collection(self, collection: str = "default",
                                tenant_id: Optional[str] = None) -> bool:
        namespace = self._namespace(collection, tenant_id)
        client = await self._get_client()
        client.delete_collection(namespace)
        self._collections.pop(namespace, None)
        return True

    async def collection_stats(self, collection: str = "default",
                               tenant_id: Optional[str] = None) -> dict:
        namespace = self._namespace(collection, tenant_id)
        col = await self._get_collection(namespace)
        count = col.count()
        return {"name": namespace, "document_count": count, "type": "chroma"}

    async def health_check(self) -> dict:
        try:
            client = await self._get_client()
            heartbeat = client.heartbeat()
            return {
                "type": "chroma",
                "status": "healthy",
                "latency_ms": 0,
            }
        except Exception as e:
            return {"type": "chroma", "status": "error", "error": str(e)}


# =============================================================================
#  pgvector Vector Store (PostgreSQL)
# =============================================================================

class PGVectorStore(BaseVectorStore):
    """pgvector extension for PostgreSQL."""

    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._pool = None
        self._connection_string = config.connection_string or "postgresql://localhost:5432/vectordb"

    async def _get_pool(self):
        if self._pool is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
                self._engine = create_async_engine(self._connection_string, echo=False)
            except ImportError:
                raise ImportError("sqlalchemy[asyncio] required for pgvector")
        return self._engine

    async def _ensure_table(self, namespace: str):
        engine = await self._get_pool()
        safe_name = namespace.replace(":", "_").replace("-", "_")
        async with engine.connect() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {safe_name} (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding vector({self._dimension}),
                    metadata JSONB DEFAULT '{{}}',
                    tenant_id TEXT DEFAULT '',
                    chunk_index INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.commit()

    async def index_document(self, doc: VectorDocument) -> str:
        namespace = self._namespace(doc.collection, doc.tenant_id)
        await self._ensure_table(namespace)
        safe_name = namespace.replace(":", "_").replace("-", "_")
        engine = await self._get_pool()
        async with engine.connect() as conn:
            await conn.execute(
                f"INSERT INTO {safe_name} (id, text, embedding, metadata, tenant_id, chunk_index) "
                f"VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO UPDATE SET text=$2, embedding=$3",
                doc.id, doc.text, doc.embedding, json.dumps(doc.metadata),
                doc.tenant_id or "", doc.chunk_index
            )
            await conn.commit()
        return doc.id

    async def index_documents(self, docs: list[VectorDocument]) -> list[str]:
        if not docs:
            return []
        namespace = self._namespace(docs[0].collection, docs[0].tenant_id)
        await self._ensure_table(namespace)
        safe_name = namespace.replace(":", "_").replace("-", "_")
        engine = await self._get_pool()
        async with engine.connect() as conn:
            for doc in docs:
                await conn.execute(
                    f"INSERT INTO {safe_name} (id, text, embedding, metadata, tenant_id, chunk_index) "
                    f"VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO UPDATE SET text=$2, embedding=$3",
                    doc.id, doc.text, doc.embedding, json.dumps(doc.metadata),
                    doc.tenant_id or "", doc.chunk_index
                )
            await conn.commit()
        return [d.id for d in docs]

    async def search(self, query: VectorSearchQuery) -> VectorSearchResponse:
        namespace = self._namespace(query.collection, query.tenant_id)
        await self._ensure_table(namespace)
        safe_name = namespace.replace(":", "_").replace("-", "_")
        engine = await self._get_pool()

        start_time = time.time()
        async with engine.connect() as conn:
            filter_clause = ""
            if query.filters:
                for k, v in query.filters.items():
                    filter_clause += f" AND metadata->>'{k}' = '{v}'"
            if query.tenant_id:
                filter_clause += f" AND tenant_id = '{query.tenant_id}'"

            results = await conn.execute(f"""
                SELECT id, text, metadata, tenant_id, 
                       1 - (embedding <=> $1::vector) AS score
                FROM {safe_name}
                WHERE 1=1 {filter_clause}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, query.embedding or [0.0]*self._dimension, query.top_k)
            rows = results.fetchall()

        latency_ms = (time.time() - start_time) * 1000
        search_results = []
        for row in rows:
            score = float(row[4]) if row[4] else 0.0
            if score >= query.threshold:
                search_results.append(VectorSearchResult(
                    id=row[0], score=round(score, 4), text=row[1],
                    metadata=row[2], tenant_id=row[3], collection=query.collection,
                ))

        return VectorSearchResponse(
            query=query.query, results=search_results,
            total=len(search_results), latency_ms=round(latency_ms, 2),
        )

    async def delete_document(self, doc_id: str, collection: str = "default",
                              tenant_id: Optional[str] = None) -> bool:
        namespace = self._namespace(collection, tenant_id)
        safe_name = namespace.replace(":", "_").replace("-", "_")
        engine = await self._get_pool()
        async with engine.connect() as conn:
            await conn.execute(f"DELETE FROM {safe_name} WHERE id = $1", doc_id)
            await conn.commit()
        return True

    async def delete_collection(self, collection: str = "default",
                                tenant_id: Optional[str] = None) -> bool:
        namespace = self._namespace(collection, tenant_id)
        safe_name = namespace.replace(":", "_").replace("-", "_")
        engine = await self._get_pool()
        async with engine.connect() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {safe_name}")
            await conn.commit()
        return True

    async def collection_stats(self, collection: str = "default",
                               tenant_id: Optional[str] = None) -> dict:
        namespace = self._namespace(collection, tenant_id)
        safe_name = namespace.replace(":", "_").replace("-", "_")
        engine = await self._get_pool()
        async with engine.connect() as conn:
            result = await conn.execute(f"SELECT COUNT(*) FROM {safe_name}")
            count = result.scalar() or 0
        return {"name": namespace, "document_count": count, "type": "pgvector"}

    async def health_check(self) -> dict:
        try:
            engine = await self._get_pool()
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")
            return {"type": "pgvector", "status": "healthy"}
        except Exception as e:
            return {"type": "pgvector", "status": "error", "error": str(e)}


# =============================================================================
#  Vector Store Manager
# =============================================================================

class VectorStoreManager:
    """
    Central vector store manager.

    Manages:
    - Multiple vector store backends (Chroma, pgvector, Pinecone, Qdrant, etc.)
    - Automatic client initialization
    - Tenant-scoped collections
    - Document indexing and search
    """

    def __init__(self):
        self._stores: dict[str, BaseVectorStore] = {}
        self._default_store_type = VectorStoreType.CHROMA

    def configure(self, config: VectorStoreConfig) -> BaseVectorStore:
        """Configure and initialize a vector store backend."""
        store: BaseVectorStore
        if config.store_type == VectorStoreType.CHROMA:
            store = ChromaVectorStore(config)
        elif config.store_type == VectorStoreType.PGVECTOR:
            store = PGVectorStore(config)
        elif config.store_type == VectorStoreType.PINECONE:
            from app.services.vector_stores.pinecone_store import PineconeVectorStore
            store = PineconeVectorStore(config)
        elif config.store_type == VectorStoreType.QDRANT:
            from app.services.vector_stores.qdrant_store import QdrantVectorStore
            store = QdrantVectorStore(config)
        elif config.store_type == VectorStoreType.WEAVIATE:
            from app.services.vector_stores.weaviate_store import WeaviateVectorStore
            store = WeaviateVectorStore(config)
        elif config.store_type == VectorStoreType.MILVUS:
            from app.services.vector_stores.milvus_store import MilvusVectorStore
            store = MilvusVectorStore(config)
        else:
            raise ValueError(f"Unsupported vector store type: {config.store_type}")

        store_key = f"{config.store_type.value}:{config.index_name}"
        self._stores[store_key] = store
        logger.info(f"Vector store configured: {config.store_type.value} ({config.index_name})")
        return store

    def get_store(self, store_type: Optional[VectorStoreType] = None,
                  index_name: str = "default") -> BaseVectorStore:
        """Get a configured vector store by type and index."""
        st = store_type or self._default_store_type
        store_key = f"{st.value}:{index_name}"
        if store_key in self._stores:
            return self._stores[store_key]
        # Auto-configure with default
        config = VectorStoreConfig(store_type=st, index_name=index_name)
        return self.configure(config)

    async def index_document(self, doc: VectorDocument,
                             store_type: Optional[VectorStoreType] = None) -> str:
        """Index a document in the vector store."""
        store = self.get_store(store_type)
        return await store.index_document(doc)

    async def index_documents(self, docs: list[VectorDocument],
                              store_type: Optional[VectorStoreType] = None) -> list[str]:
        """Index multiple documents."""
        store = self.get_store(store_type)
        return await store.index_documents(docs)

    async def search(self, query: VectorSearchQuery,
                     store_type: Optional[VectorStoreType] = None) -> VectorSearchResponse:
        """Search the vector store."""
        store = self.get_store(store_type, query.collection)
        return await store.search(query)

    async def delete_document(self, doc_id: str, collection: str = "default",
                              tenant_id: Optional[str] = None,
                              store_type: Optional[VectorStoreType] = None) -> bool:
        store = self.get_store(store_type, collection)
        return await store.delete_document(doc_id, collection, tenant_id)

    async def delete_collection(self, collection: str = "default",
                                tenant_id: Optional[str] = None,
                                store_type: Optional[VectorStoreType] = None) -> bool:
        store = self.get_store(store_type, collection)
        return await store.delete_collection(collection, tenant_id)

    def get_stats(self) -> dict:
        """Get vector store manager statistics."""
        return {
            "stores_configured": len(self._stores),
            "store_types": list(self._stores.keys()),
        }


# Singleton
vector_store_manager = VectorStoreManager()

