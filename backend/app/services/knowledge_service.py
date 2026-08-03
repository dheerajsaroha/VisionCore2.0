"""
knowledge_service.py — Enterprise Knowledge Platform
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Enterprise knowledge management platform:
- Knowledge collections (tenant-scoped)
- Document ingestion and management
- Metadata extraction and search
- Collection-level permissions
- Knowledge freshness tracking
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import (
    DocumentChunk,
    DocumentIngestionRequest,
    KnowledgeCollection,
    VectorDocument,
)
from app.services.document_ingestion import document_ingestion_pipeline
from app.services.embedding_service import embedding_service
from app.services.vector_store_service import vector_store_manager, VectorStoreType
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Enterprise Knowledge Platform.

    Manages:
    - Knowledge collections (grouped documents)
    - Document ingestion pipeline
    - Chunking and embedding
    - Vector indexing
    - Tenant-scoped isolation
    - Knowledge freshness tracking
    """

    def __init__(self):
        self._collections: dict[str, KnowledgeCollection] = {}
        self._documents: dict[str, dict] = {}  # document_id -> metadata
        self._collection_documents: dict[str, list[str]] = defaultdict(list)
        self._default_chunk_size = 1000
        self._default_chunk_overlap = 200

    # =========================================================================
    #  Collection Management
    # =========================================================================

    async def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> KnowledgeCollection:
        """Create a new knowledge collection."""
        collection_id = f"kc-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        collection = KnowledgeCollection(
            id=collection_id,
            name=name,
            description=description or "",
            tenant_id=tenant_id,
            document_count=0,
            chunk_count=0,
            created_at=now,
            updated_at=now,
        )
        self._collections[collection_id] = collection

        logger.info(f"Knowledge collection created: {name} ({collection_id})")
        return collection

    async def get_collection(self, collection_id: str) -> Optional[KnowledgeCollection]:
        """Get a knowledge collection by ID."""
        return self._collections.get(collection_id)

    async def get_collections(
        self, tenant_id: Optional[str] = None
    ) -> list[KnowledgeCollection]:
        """Get all collections, optionally filtered by tenant."""
        if tenant_id:
            return [c for c in self._collections.values() if c.tenant_id == tenant_id]
        return list(self._collections.values())

    async def delete_collection(
        self, collection_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Delete a collection and its documents."""
        collection = self._collections.get(collection_id)
        if not collection:
            return False
        if tenant_id and collection.tenant_id != tenant_id:
            return False

        # Delete documents from vector store
        for doc_id in self._collection_documents.get(collection_id, []):
            await vector_store_manager.delete_document(
                doc_id, collection=collection_id, tenant_id=tenant_id
            )

        # Remove from tracking
        del self._collections[collection_id]
        self._collection_documents.pop(collection_id, None)

        logger.info(f"Knowledge collection deleted: {collection_id}")
        return True

    # =========================================================================
    #  Document Ingestion
    # =========================================================================

    async def ingest_document(
        self,
        filename: str,
        content_type: str,
        content: str,
        collection_id: str = "default",
        metadata: Optional[dict] = None,
        tenant_id: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> dict:
        """
        Ingest a document into the knowledge platform.

        Steps:
        1. Validate collection exists (create default if needed)
        2. Run ingestion pipeline to get chunks
        3. Generate embeddings for each chunk
        4. Index chunks in vector store
        5. Track document metadata
        """
        # Ensure collection exists
        collection = self._collections.get(collection_id)
        if not collection:
            if collection_id == "default":
                collection = await self.create_collection(
                    name="Default Collection",
                    description="Default knowledge collection",
                    tenant_id=tenant_id,
                )
                collection_id = collection.id
            else:
                raise ValueError(f"Collection not found: {collection_id}")

        # Create ingestion request
        request = DocumentIngestionRequest(
            filename=filename,
            content_type=content_type,
            content=content,
            collection=collection_id,
            metadata=metadata,
            tenant_id=tenant_id,
            chunk_size=chunk_size or self._default_chunk_size,
            chunk_overlap=chunk_overlap or self._default_chunk_overlap,
        )

        # Run ingestion pipeline
        chunks = await document_ingestion_pipeline.ingest(request)

        if not chunks:
            raise ValueError("No chunks produced from document")

        # Generate embeddings for chunks
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await embedding_service.generate_embedding_document(
            chunks=chunk_texts,
            organization_id=tenant_id,
        )

        # Index chunks in vector store
        doc_ids = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vec_doc = VectorDocument(
                id=chunk.document_id + f"-chunk-{i}",
                text=chunk.text,
                embedding=embedding,
                metadata=chunk.metadata,
                tenant_id=tenant_id,
                collection=collection_id,
                chunk_index=i,
            )
            await vector_store_manager.index_document(vec_doc)
            doc_ids.append(vec_doc.id)

        # Track document
        document_id = chunks[0].document_id
        doc_metadata = {
            "id": document_id,
            "filename": filename,
            "content_type": content_type,
            "collection_id": collection_id,
            "tenant_id": tenant_id,
            "chunk_count": len(chunks),
            "char_count": sum(len(c.text) for c in chunks),
            "metadata": metadata or {},
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        self._documents[document_id] = doc_metadata
        self._collection_documents[collection_id].append(document_id)

        # Update collection stats
        collection.document_count += 1
        collection.chunk_count += len(chunks)
        collection.updated_at = datetime.now(timezone.utc).isoformat()

        # Audit
        audit_service.record(
            module="ai",
            action="document_ingested",
            entity_type="knowledge_document",
            entity_id=document_id,
            summary=f"Document ingested: {filename} ({len(chunks)} chunks) into {collection_id}",
            details={
                "filename": filename,
                "content_type": content_type,
                "chunk_count": len(chunks),
                "collection_id": collection_id,
            },
            organization_id=tenant_id,
        )

        logger.info(f"Document ingested: {filename} -> {document_id} ({len(chunks)} chunks)")
        return doc_metadata

    async def ingest_batch(
        self,
        documents: list[dict],
        collection_id: str = "default",
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Ingest multiple documents in batch."""
        results = []
        for doc in documents:
            result = await self.ingest_document(
                filename=doc.get("filename", "unknown"),
                content_type=doc.get("content_type", "text/plain"),
                content=doc.get("content", ""),
                collection_id=collection_id,
                metadata=doc.get("metadata"),
                tenant_id=tenant_id,
                chunk_size=doc.get("chunk_size"),
                chunk_overlap=doc.get("chunk_overlap"),
            )
            results.append(result)
        return results

    # =========================================================================
    #  Document Management
    # =========================================================================

    async def get_document(self, document_id: str) -> Optional[dict]:
        """Get document metadata."""
        return self._documents.get(document_id)

    async def get_documents(
        self,
        collection_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Get all documents, optionally filtered."""
        docs = list(self._documents.values())
        if collection_id:
            docs = [d for d in docs if d.get("collection_id") == collection_id]
        if tenant_id:
            docs = [d for d in docs if d.get("tenant_id") == tenant_id]
        return sorted(docs, key=lambda d: d.get("ingested_at", ""), reverse=True)

    async def delete_document(
        self, document_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Delete a document and its chunks from vector store."""
        doc = self._documents.get(document_id)
        if not doc:
            return False
        if tenant_id and doc.get("tenant_id") != tenant_id:
            return False

        # Delete from vector store
        collection_id = doc.get("collection_id", "default")
        await vector_store_manager.delete_collection(
            collection=collection_id, tenant_id=tenant_id
        )

        # Remove from tracking
        del self._documents[document_id]
        if collection_id in self._collection_documents:
            self._collection_documents[collection_id] = [
                d for d in self._collection_documents[collection_id]
                if d != document_id
            ]

        # Update collection stats
        collection = self._collections.get(collection_id)
        if collection:
            collection.document_count = max(0, collection.document_count - 1)
            collection.chunk_count = max(0, collection.chunk_count - doc.get("chunk_count", 0))

        logger.info(f"Document deleted: {document_id}")
        return True

    # =========================================================================
    #  Knowledge Stats
    # =========================================================================

    async def get_stats(self, tenant_id: Optional[str] = None) -> dict:
        """Get knowledge platform statistics."""
        collections = await self.get_collections(tenant_id)
        documents = await self.get_documents(tenant_id=tenant_id)

        total_chunks = sum(c.chunk_count for c in collections)
        total_chars = sum(d.get("char_count", 0) for d in documents)

        return {
            "total_collections": len(collections),
            "total_documents": len(documents),
            "total_chunks": total_chunks,
            "total_chars": total_chars,
            "collections": [
                {
                    "id": c.id,
                    "name": c.name,
                    "document_count": c.document_count,
                    "chunk_count": c.chunk_count,
                    "created_at": c.created_at,
                }
                for c in collections
            ],
        }


# Singleton
knowledge_service = KnowledgeService()

