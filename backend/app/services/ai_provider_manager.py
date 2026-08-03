"""
ai_provider_manager.py — Enterprise AI Provider Manager
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Central orchestrator for all AI operations:
- Multi-provider AI completions (OpenAI, Azure, Anthropic, Gemini, Ollama, Custom)
- Embedding generation
- Model registry and capability management
- Prompt template management with versioning
- Usage tracking and cost management
- Provider failover and load balancing
- Rate limiting per provider/model
- Audit logging for AI operations
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import (
    AICompletionRequest,
    AICompletionResponse,
    AIProviderConfig,
    AIProviderResponse,
    AIProviderType,
    AIModelRegistration,
    AIModelResponse,
    AIStreamChunk,
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelCapability,
    PromptTemplate,
    TenantAIConfig,
)
from app.services.audit_service import audit_service
from app.services.config_center import config_center

logger = logging.getLogger(__name__)


# =============================================================================
#  Abstract Provider Base
# =============================================================================

class AIProviderBase(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.provider_id = f"prov-{uuid.uuid4().hex[:12]}"
        self._models: dict[str, dict] = {}
        self._total_requests = 0
        self._total_tokens = 0
        self._total_cost_usd = 0.0
        self._last_error: Optional[str] = None
        self._status = "active"

    @abstractmethod
    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """Send a completion request to the provider."""
        pass

    @abstractmethod
    async def complete_stream(self, request: AICompletionRequest):
        """Stream a completion response."""
        pass

    @abstractmethod
    async def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        """Generate an embedding vector for text."""
        pass

    @abstractmethod
    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check provider health and return status."""
        pass

    def get_stats(self) -> dict:
        """Get provider statistics."""
        return {
            "provider_id": self.provider_id,
            "name": self.config.name,
            "type": self.config.provider_type.value,
            "status": self._status,
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost_usd, 6),
            "models_count": len(self._models),
            "last_error": self._last_error,
        }

    def _track_usage(self, tokens: int, cost: float) -> None:
        """Track usage statistics."""
        self._total_requests += 1
        self._total_tokens += tokens
        self._total_cost_usd += cost

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, model_id: str) -> float:
        """Calculate cost for a request based on model pricing."""
        model = self._models.get(model_id, {})
        input_cost = model.get("cost_per_1k_input_tokens", 0.0) * (prompt_tokens / 1000)
        output_cost = model.get("cost_per_1k_output_tokens", 0.0) * (completion_tokens / 1000)
        return input_cost + output_cost


# =============================================================================
#  AI Provider Manager
# =============================================================================

class AIProviderManager:
    """
    Central AI provider manager.

    Manages:
    - Provider registration and lifecycle
    - Model registry
    - Prompt template management
    - Request routing with failover
    - Usage tracking and cost management
    - Tenant AI configuration
    """

    def __init__(self):
        self._providers: dict[str, AIProviderBase] = {}
        self._models: dict[str, dict] = {}
        self._prompts: dict[str, PromptTemplate] = {}
        self._tenant_configs: dict[str, TenantAIConfig] = {}
        self._usage_history: list[dict] = []
        self._max_usage_history: int = 100000
        self._rate_limiters: dict[str, dict] = {}

    # =========================================================================
    #  Provider Management
    # =========================================================================

    def register_provider(self, config: AIProviderConfig) -> AIProviderBase:
        """Register a new AI provider."""
        provider = self._create_provider(config)
        self._providers[provider.provider_id] = provider
        logger.info(f"AI provider registered: {config.name} ({config.provider_type.value})")
        return provider

    def _create_provider(self, config: AIProviderConfig) -> AIProviderBase:
        """Factory method to create provider instances."""
        if config.provider_type == AIProviderType.OPENAI:
            from app.services.ai_providers.openai_provider import OpenAIProvider
            return OpenAIProvider(config)
        elif config.provider_type == AIProviderType.ANTHROPIC:
            from app.services.ai_providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(config)
        elif config.provider_type == AIProviderType.OLLAMA:
            from app.services.ai_providers.ollama_provider import OllamaProvider
            return OllamaProvider(config)
        elif config.provider_type == AIProviderType.CUSTOM_REST:
            from app.services.ai_providers.custom_provider import CustomRESTProvider
            return CustomRESTProvider(config)
        else:
            raise ValueError(f"Unsupported provider type: {config.provider_type}")

    def get_provider(self, provider_id: str) -> Optional[AIProviderBase]:
        """Get a provider by ID."""
        return self._providers.get(provider_id)

    def get_providers(self) -> list[AIProviderBase]:
        """Get all registered providers."""
        return list(self._providers.values())

    def get_active_providers(self) -> list[AIProviderBase]:
        """Get all active providers."""
        return [p for p in self._providers.values() if p._status == "active"]

    def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider."""
        if provider_id in self._providers:
            del self._providers[provider_id]
            logger.info(f"AI provider removed: {provider_id}")
            return True
        return False

    # =========================================================================
    #  Model Registry
    # =========================================================================

    def register_model(self, registration: AIModelRegistration) -> dict:
        """Register an AI model."""
        model_id = f"model-{uuid.uuid4().hex[:12]}"
        model = {
            "id": model_id,
            "name": registration.name,
            "provider_id": registration.provider_id,
            "capabilities": [c.value for c in registration.capabilities],
            "context_window": registration.context_window,
            "max_output_tokens": registration.max_output_tokens,
            "cost_per_1k_input_tokens": registration.cost_per_1k_input_tokens,
            "cost_per_1k_output_tokens": registration.cost_per_1k_output_tokens,
            "is_active": registration.is_active,
            "metadata": registration.metadata or {},
            "total_requests": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._models[model_id] = model

        # Also register with provider
        provider = self._providers.get(registration.provider_id)
        if provider:
            provider._models[model_id] = model

        logger.info(f"AI model registered: {registration.name} ({model_id})")
        return model

    def get_model(self, model_id: str) -> Optional[dict]:
        """Get a model by ID."""
        return self._models.get(model_id)

    def get_models(self, capability: Optional[str] = None) -> list[dict]:
        """Get all models, optionally filtered by capability."""
        models = list(self._models.values())
        if capability:
            models = [m for m in models if capability in m.get("capabilities", [])]
        return models

    def get_models_for_provider(self, provider_id: str) -> list[dict]:
        """Get all models for a provider."""
        return [m for m in self._models.values() if m.get("provider_id") == provider_id]

    # =========================================================================
    #  Prompt Template Management
    # =========================================================================

    def register_prompt(self, template: PromptTemplate) -> PromptTemplate:
        """Register a prompt template."""
        prompt_id = f"prompt-{uuid.uuid4().hex[:12]}"
        template_dict = template.model_dump()
        template_dict["id"] = prompt_id
        template_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        template_dict["updated_at"] = template_dict["created_at"]
        self._prompts[prompt_id] = PromptTemplate(**template_dict)
        logger.info(f"Prompt template registered: {template.name} (v{template.version})")
        return self._prompts[prompt_id]

    def get_prompt(self, prompt_id: str) -> Optional[PromptTemplate]:
        """Get a prompt template by ID."""
        return self._prompts.get(prompt_id)

    def get_prompts(self, category: Optional[str] = None) -> list[PromptTemplate]:
        """Get all prompt templates, optionally filtered by category."""
        prompts = list(self._prompts.values())
        if category:
            prompts = [p for p in prompts if p.category == category]
        return prompts

    def render_prompt(self, prompt_id: str, variables: dict[str, str]) -> Optional[str]:
        """Render a prompt template with variables."""
        template = self._prompts.get(prompt_id)
        if not template:
            return None
        try:
            return template.template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing variable in prompt {prompt_id}: {e}")
            return None

    # =========================================================================
    #  Completion Operations
    # =========================================================================

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """
        Send a completion request to the appropriate provider.

        Handles:
        - Model selection (by model_id or provider_id)
        - Provider failover
        - Rate limiting
        - Usage tracking
        - Audit logging
        """
        start_time = time.time()

        # Resolve provider and model
        provider, model = await self._resolve_provider(request)

        if not provider:
            raise ValueError("No available AI provider found")

        # Check rate limits
        await self._check_rate_limits(provider, request.organization_id)

        # Send request
        try:
            response = await provider.complete(request)

            # Track usage
            provider._track_usage(
                response.usage.get("total_tokens", 0),
                response.cost_usd,
            )

            # Update model usage
            if model:
                model_id = model.get("id")
                if model_id in self._models:
                    self._models[model_id]["total_requests"] += 1

            # Record usage history
            self._record_usage(request, response, provider, start_time)

            # Audit
            self._audit_completion(request, response, provider)

            return response

        except Exception as e:
            logger.error(f"AI completion failed: {e}")

            # Try failover provider
            failover_response = await self._try_failover(request, provider)
            if failover_response:
                return failover_response

            raise

    async def complete_stream(self, request: AICompletionRequest):
        """Stream a completion response."""
        provider, model = await self._resolve_provider(request)
        if not provider:
            raise ValueError("No available AI provider found")

        async for chunk in provider.complete_stream(request):
            yield chunk

    async def _resolve_provider(self, request: AICompletionRequest) -> tuple[Optional[AIProviderBase], Optional[dict]]:
        """Resolve the provider and model for a request."""
        model = None
        provider = None

        # If model_id specified, find it
        if request.model_id:
            model = self._models.get(request.model_id)
            if model:
                provider = self._providers.get(model.get("provider_id"))

        # If provider_id specified, use it
        if not provider and request.provider_id:
            provider = self._providers.get(request.provider_id)

        # If no provider, use first active provider with chat capability
        if not provider:
            for p in self.get_active_providers():
                if p._status == "active":
                    provider = p
                    break

        # If no model, use provider's default
        if not model and provider:
            models = self.get_models_for_provider(provider.provider_id)
            if models:
                model = models[0]

        return provider, model

    async def _check_rate_limits(self, provider: AIProviderBase, org_id: Optional[str]) -> None:
        """Check and enforce rate limits."""
        if not provider.config.rate_limit_rpm:
            return

        key = f"{provider.provider_id}:{org_id or 'global'}"
        now = time.time()
        window = 60  # 1 minute window

        if key not in self._rate_limiters:
            self._rate_limiters[key] = {"requests": [], "limit": provider.config.rate_limit_rpm}

        limiter = self._rate_limiters[key]
        # Clean old entries
        limiter["requests"] = [t for t in limiter["requests"] if now - t < window]

        if len(limiter["requests"]) >= limiter["limit"]:
            raise ValueError(f"Rate limit exceeded for provider {provider.config.name}")

        limiter["requests"].append(now)

    async def _try_failover(self, request: AICompletionRequest, failed_provider: AIProviderBase) -> Optional[AICompletionResponse]:
        """Try failover to another provider."""
        for provider in self.get_active_providers():
            if provider.provider_id != failed_provider.provider_id:
                try:
                    logger.info(f"Failing over to provider: {provider.config.name}")
                    return await provider.complete(request)
                except Exception as e:
                    logger.warning(f"Failover provider {provider.config.name} also failed: {e}")
                    continue
        return None

    # =========================================================================
    #  Embedding Operations
    # =========================================================================

    async def generate_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate an embedding for text."""
        start_time = time.time()
        provider = self._get_embedding_provider(request.provider)
        if not provider:
            raise ValueError("No embedding provider available")

        embedding = await provider.generate_embedding(request.text, request.model)
        latency_ms = (time.time() - start_time) * 1000

        return EmbeddingResponse(
            id=str(uuid.uuid4()),
            model=request.model or "default",
            provider=provider.config.name,
            embedding=embedding,
            dimensions=len(embedding),
            latency_ms=round(latency_ms, 2),
        )

    async def generate_embeddings_batch(self, request: BatchEmbeddingRequest) -> BatchEmbeddingResponse:
        """Generate embeddings for multiple texts."""
        start_time = time.time()
        provider = self._get_embedding_provider(request.provider)
        if not provider:
            raise ValueError("No embedding provider available")

        embeddings = await provider.generate_embeddings_batch(request.texts, request.model)
        latency_ms = (time.time() - start_time) * 1000

        return BatchEmbeddingResponse(
            id=str(uuid.uuid4()),
            model=request.model or "default",
            provider=provider.config.name,
            embeddings=embeddings,
            dimensions=len(embeddings[0]) if embeddings else 0,
            usage={"prompt_tokens": 0, "total_tokens": 0},
            latency_ms=round(latency_ms, 2),
        )

    def _get_embedding_provider(self, provider_name: Optional[str] = None) -> Optional[AIProviderBase]:
        """Get a provider capable of embeddings."""
        for provider in self.get_active_providers():
            if provider_name and provider.config.name == provider_name:
                return provider
            if not provider_name:
                # Check if any model has embedding capability
                for model in self.get_models_for_provider(provider.provider_id):
                    if ModelCapability.EMBEDDING.value in model.get("capabilities", []):
                        return provider
        return None

    # =========================================================================
    #  Tenant Configuration
    # =========================================================================

    def get_tenant_config(self, org_id: str) -> TenantAIConfig:
        """Get AI configuration for a tenant."""
        if org_id not in self._tenant_configs:
            # Build from config center
            self._tenant_configs[org_id] = TenantAIConfig(
                organization_id=org_id,
                enabled_providers=config_center.get("ai.enabled_providers", org_id, ["openai"]),
                default_model=config_center.get("ai.default_model", org_id, "gpt-4"),
                safety_policy=config_center.get("ai.safety_policy", org_id, "moderate"),
                max_tokens_per_request=config_center.get("ai.max_tokens_per_request", org_id, 4096),
                rate_limit_rpm=config_center.get("ai.rate_limit_rpm", org_id, 60),
                monthly_budget_usd=config_center.get("ai.monthly_budget_usd", org_id),
                enable_copilots=config_center.get("ai.enable_copilots", org_id, True),
                enable_predictive=config_center.get("ai.enable_predictive", org_id, True),
                enable_rag=config_center.get("ai.enable_rag", org_id, True),
                audit_all_requests=config_center.get("ai.audit_all_requests", org_id, True),
                allowed_copilot_domains=config_center.get("ai.allowed_copilot_domains", org_id, ["hr", "policy", "operations"]),
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
        return self._tenant_configs[org_id]

    def update_tenant_config(self, org_id: str, config: TenantAIConfig) -> TenantAIConfig:
        """Update AI configuration for a tenant."""
        config.updated_at = datetime.now(timezone.utc).isoformat()
        self._tenant_configs[org_id] = config
        return config

    # =========================================================================
    #  Usage Tracking
    # =========================================================================

    def _record_usage(self, request: AICompletionRequest, response: AICompletionResponse,
                      provider: AIProviderBase, start_time: float) -> None:
        """Record usage for analytics."""
        entry = {
            "id": str(uuid.uuid4()),
            "request_id": response.id,
            "provider_id": provider.provider_id,
            "provider_name": provider.config.name,
            "model": response.model,
            "organization_id": request.organization_id,
            "user_id": request.user_id,
            "prompt_tokens": response.usage.get("prompt_tokens", 0),
            "completion_tokens": response.usage.get("completion_tokens", 0),
            "total_tokens": response.usage.get("total_tokens", 0),
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._usage_history.append(entry)
        if len(self._usage_history) > self._max_usage_history:
            self._usage_history = self._usage_history[-self._max_usage_history:]

    def get_usage_summary(self, org_id: Optional[str] = None,
                          period_start: Optional[str] = None,
                          period_end: Optional[str] = None) -> dict:
        """Get AI usage summary."""
        entries = self._usage_history
        if org_id:
            entries = [e for e in entries if e.get("organization_id") == org_id]

        total_requests = len(entries)
        total_tokens = sum(e.get("total_tokens", 0) for e in entries)
        total_cost = sum(e.get("cost_usd", 0) for e in entries)

        # Per-provider breakdown
        by_provider = defaultdict(int)
        by_model = defaultdict(int)
        by_org = defaultdict(float)
        latencies = [e.get("latency_ms", 0) for e in entries if e.get("latency_ms")]

        for e in entries:
            by_provider[e.get("provider_name", "unknown")] += 1
            by_model[e.get("model", "unknown")] += e.get("total_tokens", 0)
            by_org[e.get("organization_id", "unknown")] += e.get("cost_usd", 0)

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "requests_by_provider": dict(by_provider),
            "tokens_by_model": dict(by_model),
            "cost_by_organization": {k: round(v, 4) for k, v in by_org.items()},
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "period_start": period_start or "all",
            "period_end": period_end or "all",
        }

    # =========================================================================
    #  Audit
    # =========================================================================

    def _audit_completion(self, request: AICompletionRequest,
                          response: AICompletionResponse,
                          provider: AIProviderBase) -> None:
        """Audit an AI completion request."""
        audit_service.record(
            module="ai",
            action="completion",
            entity_type="ai_request",
            entity_id=response.id,
            summary=f"AI completion: {response.model} ({provider.config.name})",
            details={
                "provider": provider.config.name,
                "model": response.model,
                "tokens": response.usage,
                "cost": response.cost_usd,
                "latency_ms": response.latency_ms,
            },
            organization_id=request.organization_id,
            actor_user_id=request.user_id,
        )

    # =========================================================================
    #  Health & Stats
    # =========================================================================

    async def health_check_all(self) -> list[dict]:
        """Check health of all providers."""
        results = []
        for provider in self._providers.values():
            try:
                health = await provider.health_check()
                results.append(health)
            except Exception as e:
                results.append({
                    "provider_id": provider.provider_id,
                    "name": provider.config.name,
                    "status": "error",
                    "error": str(e),
                })
        return results

    def get_stats(self) -> dict:
        """Get overall AI platform statistics."""
        provider_stats = [p.get_stats() for p in self._providers.values()]
        return {
            "providers": provider_stats,
            "total_providers": len(self._providers),
            "active_providers": len(self.get_active_providers()),
            "total_models": len(self._models),
            "total_prompts": len(self._prompts),
            "total_requests": sum(p.get("total_requests", 0) for p in provider_stats),
            "total_tokens": sum(p.get("total_tokens", 0) for p in provider_stats),
            "total_cost_usd": round(sum(p.get("total_cost_usd", 0) for p in provider_stats), 4),
            "usage_history_count": len(self._usage_history),
        }


# Singleton
ai_provider_manager = AIProviderManager()

