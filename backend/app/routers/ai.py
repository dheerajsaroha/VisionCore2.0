"""
ai.py — AI Platform Router
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Provides REST API endpoints for:
- AI Provider management
- Model registry
- Prompt management
- AI completions
- Embeddings
- RAG queries
- Copilot interactions
- Predictive analytics
- AI Governance
- Usage & Cost tracking
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.all_models import User
from app.schema.ai import (
    AICompletionRequest,
    AICompletionResponse,
    AIProviderConfig,
    AIProviderResponse,
    AIModelRegistration,
    AIModelResponse,
    PromptTemplate,
    EmbeddingRequest,
    EmbeddingResponse,
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    RAGQuery,
    RAGResponse,
    CopilotRequest,
    CopilotResponse,
    PredictionRequest,
    PredictionResult,
    ForecastResult,
    TenantAIConfig,
    AIUsageSummary,
    AIAuditEntry,
)
from app.services.ai_provider_manager import ai_provider_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
#  Health & Stats
# =============================================================================

@router.get("/health", tags=["ai"])
async def ai_health():
    """AI platform health check."""
    stats = ai_provider_manager.get_stats()
    return {
        "status": "healthy",
        "providers": stats["total_providers"],
        "active_providers": stats["active_providers"],
        "models": stats["total_models"],
    }


@router.get("/stats", tags=["ai"])
async def ai_stats():
    """Get AI platform statistics."""
    return ai_provider_manager.get_stats()


# =============================================================================
#  Provider Management
# =============================================================================

@router.get("/providers", tags=["ai"])
async def list_providers():
    """List all registered AI providers."""
    providers = ai_provider_manager.get_providers()
    return [p.get_stats() for p in providers]


@router.get("/providers/{provider_id}", tags=["ai"])
async def get_provider(provider_id: str):
    """Get provider details."""
    provider = ai_provider_manager.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider.get_stats()


@router.post("/providers", tags=["ai"])
async def register_provider(config: AIProviderConfig):
    """Register a new AI provider."""
    try:
        provider = ai_provider_manager.register_provider(config)
        return provider.get_stats()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/providers/{provider_id}", tags=["ai"])
async def remove_provider(provider_id: str):
    """Remove an AI provider."""
    success = ai_provider_manager.remove_provider(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"status": "removed"}


@router.get("/providers/{provider_id}/health", tags=["ai"])
async def check_provider_health(provider_id: str):
    """Check provider health."""
    provider = ai_provider_manager.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        return await provider.health_check()
    except Exception as e:
        return {"provider_id": provider_id, "status": "error", "error": str(e)}


# =============================================================================
#  Model Registry
# =============================================================================

@router.get("/models", tags=["ai"])
async def list_models(capability: Optional[str] = Query(None)):
    """List all registered AI models."""
    return ai_provider_manager.get_models(capability)


@router.get("/models/{model_id}", tags=["ai"])
async def get_model(model_id: str):
    """Get model details."""
    model = ai_provider_manager.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/models", tags=["ai"])
async def register_model(registration: AIModelRegistration):
    """Register a new AI model."""
    return ai_provider_manager.register_model(registration)


# =============================================================================
#  Prompt Management
# =============================================================================

@router.get("/prompts", tags=["ai"])
async def list_prompts(category: Optional[str] = Query(None)):
    """List all prompt templates."""
    return ai_provider_manager.get_prompts(category)


@router.get("/prompts/{prompt_id}", tags=["ai"])
async def get_prompt(prompt_id: str):
    """Get prompt template details."""
    prompt = ai_provider_manager.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@router.post("/prompts", tags=["ai"])
async def register_prompt(template: PromptTemplate):
    """Register a new prompt template."""
    return ai_provider_manager.register_prompt(template)


@router.post("/prompts/{prompt_id}/render", tags=["ai"])
async def render_prompt(prompt_id: str, variables: dict[str, str]):
    """Render a prompt template with variables."""
    result = ai_provider_manager.render_prompt(prompt_id, variables)
    if not result:
        raise HTTPException(status_code=404, detail="Prompt not found or render failed")
    return {"rendered": result}


# =============================================================================
#  Completions
# =============================================================================

@router.post("/complete", tags=["ai"])
async def complete(request: AICompletionRequest):
    """Send an AI completion request."""
    try:
        response = await ai_provider_manager.complete(request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("AI completion failed")
        raise HTTPException(status_code=500, detail=f"AI completion failed: {str(e)}")


# =============================================================================
#  Embeddings
# =============================================================================

@router.post("/embeddings", tags=["ai"])
async def generate_embedding(request: EmbeddingRequest):
    """Generate an embedding for text."""
    try:
        return await ai_provider_manager.generate_embedding(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/embeddings/batch", tags=["ai"])
async def generate_embeddings_batch(request: BatchEmbeddingRequest):
    """Generate embeddings for multiple texts."""
    try:
        return await ai_provider_manager.generate_embeddings_batch(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
#  RAG
# =============================================================================

@router.post("/rag/query", tags=["ai"])
async def rag_query(query: RAGQuery):
    """Execute a RAG query."""
    try:
        from app.services.rag_service import rag_service
        response = await rag_service.query(query)
        return response
    except Exception as e:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")


# =============================================================================
#  Copilot
# =============================================================================

@router.post("/copilot", tags=["ai"])
async def copilot_query(request: CopilotRequest):
    """Send a copilot query."""
    try:
        from app.services.copilot_service import copilot_service
        response = await copilot_service.query(request)
        return response
    except Exception as e:
        logger.exception("Copilot query failed")
        raise HTTPException(status_code=500, detail=f"Copilot query failed: {str(e)}")


@router.get("/copilot/conversations", tags=["ai"])
async def list_copilot_conversations(domain: Optional[str] = Query(None)):
    """List copilot conversations."""
    from app.services.copilot_service import copilot_service
    from app.schema.ai import CopilotDomain
    domain_enum = CopilotDomain(domain) if domain else None
    return copilot_service.get_conversations(domain=domain_enum)


@router.get("/copilot/conversations/{conversation_id}", tags=["ai"])
async def get_copilot_conversation(conversation_id: str):
    """Get a copilot conversation."""
    from app.services.copilot_service import copilot_service
    conversation = copilot_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


# =============================================================================
#  Predictive Analytics
# =============================================================================

@router.post("/predict", tags=["ai"])
async def predict(request: PredictionRequest):
    """Run a prediction."""
    try:
        from app.services.predictive_service import predictive_service
        result = await predictive_service.predict(
            model_type=request.model_type,
            params=request.params,
            organization_id=request.organization_id,
        )
        return result
    except Exception as e:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict/forecast", tags=["ai"])
async def forecast(model_type: str, params: dict = {}, days_ahead: int = 30):
    """Generate a forecast."""
    try:
        from app.services.predictive_service import predictive_service
        from app.schema.ai import PredictiveModelType
        model_type_enum = PredictiveModelType(model_type)
        result = await predictive_service.forecast(
            model_type=model_type_enum,
            params=params,
            days_ahead=days_ahead,
        )
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid model type: {model_type}")
    except Exception as e:
        logger.exception("Forecast failed")
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")


# =============================================================================
#  AI Governance
# =============================================================================

@router.get("/governance/dashboard", tags=["ai"])
async def get_governance_dashboard():
    """Get AI governance dashboard data."""
    stats = ai_provider_manager.get_stats()
    return {
        "total_requests": stats["total_requests"],
        "total_cost_usd": stats["total_cost_usd"],
        "active_providers": stats["active_providers"],
        "total_models": stats["total_models"],
    }


@router.get("/governance/compliance", tags=["ai"])
async def get_compliance_report(organization_id: Optional[str] = Query(None)):
    """Get AI compliance report."""
    return {
        "organization_id": organization_id,
        "status": "compliant",
        "last_audit": None,
    }


@router.get("/governance/audit", tags=["ai"])
async def search_audit_trail(
    event_type: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Search AI audit trail."""
    return {"entries": [], "total": 0}


# =============================================================================
#  Usage & Cost
# =============================================================================

@router.get("/usage", tags=["ai"])
async def get_usage_summary(
    organization_id: Optional[str] = Query(None),
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
):
    """Get AI usage summary."""
    return ai_provider_manager.get_usage_summary(organization_id, period_start, period_end)


@router.get("/usage/costs", tags=["ai"])
async def get_cost_analytics(organization_id: Optional[str] = Query(None)):
    """Get AI cost analytics."""
    summary = ai_provider_manager.get_usage_summary(organization_id)
    return {
        "total_cost_usd": summary["total_cost_usd"],
        "cost_by_organization": summary["cost_by_organization"],
        "cost_by_provider": summary["requests_by_provider"],
    }


# =============================================================================
#  Tenant Configuration
# =============================================================================

@router.get("/tenant/{org_id}/config", tags=["ai"])
async def get_tenant_config(org_id: str):
    """Get tenant AI configuration."""
    return ai_provider_manager.get_tenant_config(org_id)


@router.put("/tenant/{org_id}/config", tags=["ai"])
async def update_tenant_config(org_id: str, config: TenantAIConfig):
    """Update tenant AI configuration."""
    return ai_provider_manager.update_tenant_config(org_id, config)
