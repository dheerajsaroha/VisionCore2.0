"""
rag_service.py — Enterprise Retrieval-Augmented Generation (RAG) Framework
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Reusable RAG framework:
- Hybrid search (semantic + keyword)
- Permission-aware retrieval with tenant isolation
- Metadata filtering
- Citation generation with source attribution
- Re-ranking pipeline
- Knowledge freshness tracking
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, AsyncIterator

from app.schema.ai import (
    AICompletionRequest,
    RAGCitation,
    RAGQuery,
    RAGResponse,
    RAGStrategy,
    AIStreamChunk,
)
from app.services.ai_provider_manager import ai_provider_manager
from app.services.ai_cost_tracker import ai_cost_tracker
from app.services.audit_service import audit_service
from app.services.knowledge_search import knowledge_search
from app.services.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class RAGService:
    """
    Enterprise RAG (Retrieval-Augmented Generation) service.

    Features:
    - Hybrid search with configurable strategy
    - Semantic retrieval with embeddings
    - Metadata filtering for precision
    - Citation generation with source attribution
    - Tenant isolation for multi-tenant environments
    - Permission-aware retrieval
    - Knowledge freshness tracking
    - Re-ranking for improved relevance
    """

    def __init__(self):
        self._pipeline = RAGPipeline()

    async def query(self, request: RAGQuery) -> RAGResponse:
        """
        Execute a RAG query.

        Steps:
        1. Retrieve relevant documents from knowledge base
        2. Re-rank results for relevance
        3. Generate citations
        4. Build augmented prompt with context
        5. Send to AI provider for answer generation
        6. Track usage and cost
        7. Return response with citations
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())

        logger.info(f"RAG query [{query_id}]: {request.query[:100]}...")

        # Step 1: Retrieve documents
        search_response = await knowledge_search.search(
            query=request.query,
            collections=request.collections,
            top_k=request.top_k,
            strategy=request.strategy,
            filters=request.filters,
            tenant_id=request.tenant_id,
        )

        documents = search_response.results

        if not documents:
            logger.info(f"No documents found for RAG query [{query_id}]")
            return RAGResponse(
                id=query_id,
                query=request.query,
                answer="I couldn't find any relevant information in the knowledge base to answer your question.",
                citations=[],
                model="none",
                provider="none",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                cost_usd=0.0,
                latency_ms=round((time.time() - start_time) * 1000, 2),
            )

        # Step 2: Re-rank results
        reranked = await self._pipeline.rerank(request.query, documents)

        # Step 3: Build context and citations
        context_parts = []
        citations = []
        for i, doc in enumerate(reranked):
            context_parts.append(f"[Document {i + 1}]\n{doc.text}")
            citations.append(RAGCitation(
                document_id=doc.id,
                chunk_index=doc.metadata.get("chunk_index", 0) if doc.metadata else 0,
                text=doc.text[:500] + "..." if len(doc.text) > 500 else doc.text,
                score=doc.score,
                source=doc.metadata.get("filename", "unknown") if doc.metadata else "unknown",
                metadata=doc.metadata,
            ))

        context = "\n\n".join(context_parts)

        # Step 4: Build prompt
        system_prompt = request.system_prompt or self._build_system_prompt(request)
        augmented_prompt = self._build_augmented_prompt(request.query, context, request.include_citations)

        # Step 5: Generate answer
        completion_request = AICompletionRequest(
            prompt=augmented_prompt,
            system_prompt=system_prompt,
            model_id=request.model_id,
            temperature=request.temperature or 0.3,
            max_tokens=request.max_tokens or 2048,
            organization_id=request.tenant_id,
            user_id=request.user_id,
        )

        try:
            completion = await ai_provider_manager.complete(completion_request)
        except Exception as e:
            logger.error(f"RAG completion failed: {e}")
            return RAGResponse(
                id=query_id,
                query=request.query,
                answer=f"I retrieved relevant information but encountered an error generating the answer: {str(e)}",
                citations=citations,
                model="none",
                provider="none",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                cost_usd=0.0,
                latency_ms=round((time.time() - start_time) * 1000, 2),
            )

        # Step 6: Track cost
        ai_cost_tracker.track_rag(
            provider=completion.provider,
            model=completion.model,
            total_tokens=completion.usage.get("total_tokens", 0),
            cost_usd=completion.cost_usd,
            documents_retrieved=len(documents),
            organization_id=request.tenant_id,
            user_id=request.user_id,
        )

        # Step 7: Audit
        audit_service.record(
            module="ai",
            action="rag_query",
            entity_type="rag_query",
            entity_id=query_id,
            summary=f"RAG query: {request.query[:100]}... ({len(documents)} docs retrieved)",
            details={
                "strategy": request.strategy.value if request.strategy else "hybrid",
                "collections": request.collections,
                "documents_retrieved": len(documents),
                "citations": len(citations),
                "model": completion.model,
                "provider": completion.provider,
                "tokens": completion.usage,
                "cost": completion.cost_usd,
            },
            organization_id=request.tenant_id,
            actor_user_id=request.user_id,
        )

        latency_ms = (time.time() - start_time) * 1000

        return RAGResponse(
            id=query_id,
            query=request.query,
            answer=completion.content,
            citations=citations,
            model=completion.model,
            provider=completion.provider,
            usage=completion.usage,
            cost_usd=completion.cost_usd,
            latency_ms=round(latency_ms, 2),
        )

    async def query_stream(self, request: RAGQuery) -> AsyncIterator[AIStreamChunk]:
        """
        Execute a RAG query with streaming response.

        Yields content chunks as they are generated from the AI provider.
        """
        search_response = await knowledge_search.search(
            query=request.query,
            collections=request.collections,
            top_k=request.top_k,
            strategy=request.strategy,
            filters=request.filters,
            tenant_id=request.tenant_id,
        )

        documents = search_response.results
        reranked = await self._pipeline.rerank(request.query, documents)
        context_parts = [f"[Document {i + 1}]\n{d.text}" for i, d in enumerate(reranked)]
        context = "\n\n".join(context_parts)
        augmented_prompt = self._build_augmented_prompt(request.query, context, request.include_citations)

        completion_request = AICompletionRequest(
            prompt=augmented_prompt,
            system_prompt=self._build_system_prompt(request),
            model_id=request.model_id,
            temperature=request.temperature or 0.3,
            max_tokens=request.max_tokens or 2048,
            stream=True,
            organization_id=request.tenant_id,
            user_id=request.user_id,
        )

        async for chunk in ai_provider_manager.complete_stream(completion_request):
            yield chunk

    # =========================================================================
    #  Prompt Building
    # =========================================================================

    @staticmethod
    def _build_system_prompt(request: RAGQuery) -> str:
        """Build the system prompt for RAG."""
        strategy_desc = {
            RAGStrategy.HYBRID: "semantic and keyword",
            RAGStrategy.SEMANTIC: "semantic",
            RAGStrategy.KEYWORD: "keyword",
        }
        return (
            "You are an enterprise AI assistant with access to a knowledge base. "
            "Answer the user's question based STRICTLY on the provided context documents. "
            f"Search strategy used: {strategy_desc.get(request.strategy, 'hybrid')} search. "
            "If the context doesn't contain enough information to answer, say so clearly. "
            "Do not make up information or use external knowledge. "
            "Always cite the source documents you used to form your answer. "
            "Be concise, accurate, and helpful."
        )

    @staticmethod
    def _build_augmented_prompt(query: str, context: str,
                                include_citations: bool = True) -> str:
        """Build the augmented prompt with context."""
        parts = ["Context documents:", context, ""]
        if include_citations:
            parts.append("When answering, reference the documents by number like [Document 1].")
        parts.append(f"Question: {query}")
        parts.append("Answer:")
        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Get RAG service statistics."""
        return {
            "pipeline": self._pipeline.get_stats(),
        }


# Singleton
rag_service = RAGService()

