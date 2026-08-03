"""
knowledge_search.py — Enterprise Knowledge Search with Tenant Isolation
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Semantic search across knowledge collections:
- Vector similarity search
- Hybrid search (keyword + semantic)
- Tenant-scoped isolation
- Collection-level filtering
- Metadata filtering
- Relevance scoring
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from app.schema.ai import (
    RAGStrategy,
    VectorSearchQuery,
    VectorSearchResult,
    VectorSearchResponse,
)
from app.services.embedding_service import embedding_service
from app.services.vector_store_service import vector_store_manager, VectorStoreType

logger = logging.getLogger(__name__)


class KnowledgeSearch:
    """
    Semantic search service for the Knowledge Platform.

    Provides:
    - Pure semantic search (vector similarity)
    - Keyword search fallback
    - Hybrid search combining both
    - Tenant-scoped isolation
    - Collection-level filtering
    - Metadata filtering
    - Relevance scoring with threshold
    """

    def __init__(self):
        self._default_top_k = 10
        self._default_threshold = 0.0

    async def search(
        self,
        query: str,
        collections: list[str] | None = None,
        top_k: int = 10,
        threshold: float = 0.0,
        strategy: RAGStrategy = RAGStrategy.HYBRID,
        filters: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> VectorSearchResponse:
        """
        Search across knowledge collections.

        Args:
            query: Search query text
            collections: List of collection names to search (default: all)
            top_k: Maximum number of results
            threshold: Minimum relevance score (0.0 - 1.0)
            strategy: Search strategy (hybrid, semantic, keyword)
            filters: Metadata filters
            tenant_id: Tenant ID for isolation

        Returns:
            VectorSearchResponse with results
        """
        start_time = time.time()

        if strategy == RAGStrategy.SEMANTIC:
            results = await self._semantic_search(
                query, collections, top_k, threshold, filters, tenant_id
            )
        elif strategy == RAGStrategy.KEYWORD:
            results = await self._keyword_search(
                query, collections, top_k, threshold, filters, tenant_id
            )
        else:  # HYBRID
            results = await self._hybrid_search(
                query, collections, top_k, threshold, filters, tenant_id
            )

        latency_ms = (time.time() - start_time) * 1000

        return VectorSearchResponse(
            query=query,
            results=results,
            total=len(results),
            latency_ms=round(latency_ms, 2),
        )

    async def _semantic_search(
        self,
        query: str,
        collections: list[str] | None,
        top_k: int,
        threshold: float,
        filters: dict | None,
        tenant_id: str | None,
    ) -> list[VectorSearchResult]:
        """Pure semantic search using vector embeddings."""
        collections_to_search = collections or ["default"]
        all_results: list[VectorSearchResult] = []

        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(
            query, organization_id=tenant_id
        )

        for collection in collections_to_search:
            search_query = VectorSearchQuery(
                query=query,
                embedding=query_embedding.embedding,
                top_k=top_k,
                threshold=threshold,
                filters=filters,
                tenant_id=tenant_id,
                collection=collection,
                include_metadata=True,
            )
            response = await vector_store_manager.search(search_query)
            all_results.extend(response.results)

        # Sort by score descending
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]

    async def _keyword_search(
        self,
        query: str,
        collections: list[str] | None,
        top_k: int,
        threshold: float,
        filters: dict | None,
        tenant_id: str | None,
    ) -> list[VectorSearchResult]:
        """Keyword-based search fallback."""
        # For pure keyword, we still use vector store but with query text
        collections_to_search = collections or ["default"]
        all_results: list[VectorSearchResult] = []

        for collection in collections_to_search:
            search_query = VectorSearchQuery(
                query=query,
                embedding=None,
                top_k=top_k,
                threshold=threshold,
                filters=filters,
                tenant_id=tenant_id,
                collection=collection,
                include_metadata=True,
            )
            response = await vector_store_manager.search(search_query)
            all_results.extend(response.results)

        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]

    async def _hybrid_search(
        self,
        query: str,
        collections: list[str] | None,
        top_k: int,
        threshold: float,
        filters: dict | None,
        tenant_id: str | None,
    ) -> list[VectorSearchResult]:
        """
        Hybrid search combining semantic and keyword results.

        Uses reciprocal rank fusion (RRF) to combine results.
        """
        semantic_results = await self._semantic_search(
            query, collections, top_k * 2, threshold, filters, tenant_id
        )
        keyword_results = await self._keyword_search(
            query, collections, top_k * 2, threshold, filters, tenant_id
        )

        # Reciprocal Rank Fusion
        rrf_scores: dict[str, dict] = {}
        k = 60  # RRF constant

        for rank, result in enumerate(semantic_results):
            doc_id = result.id
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {
                    "result": result,
                    "rrf_score": 0.0,
                    "semantic_rank": rank + 1,
                    "keyword_rank": None,
                }
            rrf_scores[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)

        for rank, result in enumerate(keyword_results):
            doc_id = result.id
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {
                    "result": result,
                    "rrf_score": 0.0,
                    "semantic_rank": None,
                    "keyword_rank": rank + 1,
                }
            rrf_scores[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)
            rrf_scores[doc_id]["keyword_rank"] = rank + 1

        # Sort by RRF score
        fused = sorted(
            rrf_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        results = []
        for entry in fused[:top_k]:
            result = entry["result"]
            # Boost score slightly if found in both searches
            boost = 1.1 if entry["semantic_rank"] and entry["keyword_rank"] else 1.0
            result.score = round(min(result.score * boost, 1.0), 4)
            results.append(result)

        return results

    async def search_collection(
        self,
        query: str,
        collection_id: str,
        top_k: int = 10,
        tenant_id: str | None = None,
    ) -> list[VectorSearchResult]:
        """Search within a specific collection."""
        response = await self.search(
            query=query,
            collections=[collection_id],
            top_k=top_k,
            tenant_id=tenant_id,
        )
        return response.results

    async def search_by_metadata(
        self,
        query: str,
        filters: dict[str, Any],
        collections: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> list[VectorSearchResult]:
        """Search with strict metadata filtering."""
        response = await self.search(
            query=query,
            collections=collections,
            filters=filters,
            tenant_id=tenant_id,
        )
        return response.results


# Singleton
knowledge_search = KnowledgeSearch()

