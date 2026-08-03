"""
ai.py — AI Platform Schemas for Enterprise AI Platform
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Defines Pydantic models for:
- AI Providers, Models, and Prompts
- AI Requests and Responses
- Embedding and Vector Store operations
- RAG queries
- Copilot interactions
- Predictive analytics
- AI Governance
- Usage tracking
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
#  Enums
# =============================================================================

class AIProviderType(str, Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    CUSTOM_REST = "custom_rest"


class ModelCapability(str, Enum):
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    CODE_GENERATION = "code_generation"
    FUNCTION_CALLING = "function_calling"


class EmbeddingProvider(str, Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class VectorStoreType(str, Enum):
    CHROMA = "chroma"
    PINECONE = "pinecone"
    QDRANT = "qdrant"
    PGVECTOR = "pgvector"
    WEAVIATE = "weaviate"
    MILVUS = "milvus"


class RAGStrategy(str, Enum):
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    KEYWORD = "keyword"


class CopilotDomain(str, Enum):
    HR = "hr"
    RECRUITMENT = "recruitment"
    POLICY = "policy"
    PERFORMANCE = "performance"
    ASSET = "asset"
    OPERATIONS = "operations"
    EXECUTIVE = "executive"


class PredictiveModelType(str, Enum):
    ATTRITION = "attrition"
    LEAVE_FORECAST = "leave_forecast"
    ATTENDANCE_ANOMALY = "attendance_anomaly"
    PAYROLL_ANOMALY = "payroll_anomaly"
    PERFORMANCE_TREND = "performance_trend"
    PROMOTION_READINESS = "promotion_readiness"
    ASSET_FAILURE = "asset_failure"
    CAPACITY_FORECAST = "capacity_forecast"


class AISafetyPolicy(str, Enum):
    STRICT = "strict"
    MODERATE = "moderate"
    RELAXED = "relaxed"


# =============================================================================
#  AI Provider Schemas
# =============================================================================

class AIProviderConfig(BaseModel):
    """Schema for AI provider configuration."""
    name: str = Field(..., min_length=1, max_length=200)
    provider_type: AIProviderType
    api_key: str = Field(..., description="API key for the provider")
    api_base_url: Optional[str] = Field(None, description="Custom API base URL")
    organization_id: Optional[str] = Field(None, description="Organization ID for Azure")
    default_model: Optional[str] = Field(None, description="Default model to use")
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=60, ge=1, le=300)
    rate_limit_rpm: Optional[int] = Field(None, description="Rate limit requests per minute")
    is_active: bool = True
    extra_params: Optional[dict[str, Any]] = None


class AIProviderResponse(BaseModel):
    """Schema for AI provider response."""
    id: str
    name: str
    provider_type: AIProviderType
    api_base_url: Optional[str] = None
    default_model: Optional[str] = None
    is_active: bool
    status: str  # active, error, rate_limited
    models_count: int = 0
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    created_at: str
    updated_at: str


class AIModelRegistration(BaseModel):
    """Schema for registering an AI model."""
    name: str = Field(..., min_length=1, max_length=200)
    provider_id: str
    capabilities: list[ModelCapability]
    context_window: int = Field(default=4096, ge=512, le=1000000)
    max_output_tokens: int = Field(default=2048, ge=64, le=100000)
    cost_per_1k_input_tokens: float = Field(default=0.0, ge=0.0)
    cost_per_1k_output_tokens: float = Field(default=0.0, ge=0.0)
    is_active: bool = True
    metadata: Optional[dict[str, Any]] = None


class AIModelResponse(BaseModel):
    """Schema for AI model response."""
    id: str
    name: str
    provider_id: str
    provider_name: str
    capabilities: list[ModelCapability]
    context_window: int
    max_output_tokens: int
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    is_active: bool
    total_requests: int = 0
    created_at: str


class PromptTemplate(BaseModel):
    """Schema for a prompt template."""
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(default="1.0", description="Semantic version")
    template: str = Field(..., description="Prompt template with {variables}")
    variables: list[str] = Field(default_factory=list, description="Template variables")
    model_id: Optional[str] = Field(None, description="Preferred model for this prompt")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=16, le=100000)
    stop_sequences: Optional[list[str]] = None
    safety_policy: AISafetyPolicy = AISafetyPolicy.MODERATE
    category: str = Field(default="general", description="Prompt category")
    is_active: bool = True


# =============================================================================
#  AI Request/Response Schemas
# =============================================================================

class AICompletionRequest(BaseModel):
    """Schema for an AI completion request."""
    prompt: str = Field(..., min_length=1, max_length=100000)
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=16, le=100000)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    stop_sequences: Optional[list[str]] = None
    stream: bool = False
    organization_id: Optional[str] = None
    user_id: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


class AICompletionResponse(BaseModel):
    """Schema for an AI completion response."""
    id: str
    model: str
    provider: str
    content: str
    finish_reason: str = "stop"
    usage: dict = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AIStreamChunk(BaseModel):
    """Schema for a streaming AI response chunk."""
    id: str
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None


# =============================================================================
#  Embedding Schemas
# =============================================================================

class EmbeddingRequest(BaseModel):
    """Schema for an embedding request."""
    text: str = Field(..., min_length=1, max_length=100000)
    model: Optional[str] = None
    provider: Optional[str] = None
    organization_id: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Schema for an embedding response."""
    id: str
    model: str
    provider: str
    embedding: list[float]
    dimensions: int
    usage: dict = Field(default_factory=lambda: {"prompt_tokens": 0, "total_tokens": 0})
    latency_ms: float = 0.0


class BatchEmbeddingRequest(BaseModel):
    """Schema for batch embedding request."""
    texts: list[str] = Field(..., min_length=1, max_length=100)
    model: Optional[str] = None
    provider: Optional[str] = None
    organization_id: Optional[str] = None


class BatchEmbeddingResponse(BaseModel):
    """Schema for batch embedding response."""
    id: str
    model: str
    provider: str
    embeddings: list[list[float]]
    dimensions: int
    usage: dict
    latency_ms: float = 0.0


# =============================================================================
#  Vector Store Schemas
# =============================================================================

class VectorStoreConfig(BaseModel):
    """Schema for vector store configuration."""
    store_type: VectorStoreType
    connection_string: Optional[str] = None
    api_key: Optional[str] = None
    environment: Optional[str] = None
    index_name: str = "default"
    dimension: int = Field(default=1536, ge=64, le=16384)
    metric: str = Field(default="cosine", description="cosine, euclidean, dot_product")
    tenant_namespace: bool = True


class VectorDocument(BaseModel):
    """Schema for a document to be stored in vector store."""
    id: str
    text: str
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tenant_id: Optional[str] = None
    collection: str = "default"
    chunk_index: int = 0


class VectorSearchQuery(BaseModel):
    """Schema for vector search query."""
    query: str
    embedding: Optional[list[float]] = None
    top_k: int = Field(default=10, ge=1, le=200)
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    filters: Optional[dict[str, Any]] = None
    tenant_id: Optional[str] = None
    collection: str = "default"
    include_metadata: bool = True


class VectorSearchResult(BaseModel):
    """Schema for vector search result."""
    id: str
    score: float
    text: str
    metadata: Optional[dict[str, Any]] = None
    tenant_id: Optional[str] = None
    collection: str = "default"


class VectorSearchResponse(BaseModel):
    """Schema for vector search response."""
    query: str
    results: list[VectorSearchResult]
    total: int
    latency_ms: float = 0.0


# =============================================================================
#  Knowledge Platform Schemas
# =============================================================================

class DocumentIngestionRequest(BaseModel):
    """Schema for document ingestion."""
    filename: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(..., description="MIME type")
    content: str = Field(..., description="Base64-encoded content or text")
    collection: str = "default"
    metadata: Optional[dict[str, Any]] = None
    tenant_id: Optional[str] = None
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    chunk_overlap: int = Field(default=200, ge=0, le=2000)


class DocumentChunk(BaseModel):
    """Schema for a document chunk."""
    document_id: str
    chunk_index: int
    text: str
    metadata: dict[str, Any]
    embedding: Optional[list[float]] = None


class KnowledgeCollection(BaseModel):
    """Schema for a knowledge collection."""
    id: str
    name: str
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    document_count: int = 0
    chunk_count: int = 0
    created_at: str
    updated_at: str


# =============================================================================
#  RAG Schemas
# =============================================================================

class RAGQuery(BaseModel):
    """Schema for a RAG query."""
    query: str = Field(..., min_length=1, max_length=10000)
    collections: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = Field(default=5, ge=1, le=50)
    strategy: RAGStrategy = RAGStrategy.HYBRID
    filters: Optional[dict[str, Any]] = None
    tenant_id: Optional[str] = None
    user_id: Optional[int] = None
    model_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=16, le=100000)
    include_citations: bool = True
    system_prompt: Optional[str] = None


class RAGCitation(BaseModel):
    """Schema for a RAG citation."""
    document_id: str
    chunk_index: int
    text: str
    score: float
    source: str
    metadata: Optional[dict[str, Any]] = None


class RAGResponse(BaseModel):
    """Schema for a RAG response."""
    id: str
    query: str
    answer: str
    citations: list[RAGCitation] = []
    model: str
    provider: str
    usage: dict
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =============================================================================
#  Copilot Schemas
# =============================================================================

class CopilotRequest(BaseModel):
    """Schema for a copilot request."""
    domain: CopilotDomain
    query: str = Field(..., min_length=1, max_length=10000)
    context: Optional[dict[str, Any]] = None
    organization_id: Optional[str] = None
    user_id: Optional[int] = None
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


class CopilotResponse(BaseModel):
    """Schema for a copilot response."""
    id: str
    domain: CopilotDomain
    query: str
    answer: str
    suggestions: list[str] = []
    actions: list[dict] = []
    data_sources: list[str] = []
    usage: dict
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    conversation_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConversationMessage(BaseModel):
    """Schema for a conversation message."""
    role: str = Field(..., description="user, assistant, system")
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Optional[dict[str, Any]] = None


class Conversation(BaseModel):
    """Schema for a conversation."""
    id: str
    domain: CopilotDomain
    title: str
    messages: list[ConversationMessage] = []
    organization_id: Optional[str] = None
    user_id: Optional[int] = None
    created_at: str
    updated_at: str


# =============================================================================
#  Predictive Schemas
# =============================================================================

class PredictionRequest(BaseModel):
    """Schema for a prediction request."""
    model_type: PredictiveModelType
    organization_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    include_explanation: bool = True


class PredictionResult(BaseModel):
    """Schema for a prediction result."""
    id: str
    model_type: PredictiveModelType
    prediction: Any
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: Optional[str] = None
    features_used: list[str] = []
    data_points: int = 0
    organization_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ForecastDatapoint(BaseModel):
    """Schema for a forecast data point."""
    date: str
    value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastResult(BaseModel):
    """Schema for a forecast result."""
    id: str
    model_type: PredictiveModelType
    forecast: list[ForecastDatapoint]
    confidence_interval: float = 0.95
    seasonality: Optional[str] = None
    trend: str = "stable"  # increasing, decreasing, stable
    organization_id: Optional[str] = None
    created_at: str


# =============================================================================
#  AI Workflow Schemas
# =============================================================================

class AIWorkflowRecommendation(BaseModel):
    """Schema for AI workflow recommendation."""
    request_id: int
    suggested_approvers: list[dict] = []
    suggested_routing: Optional[str] = None
    predicted_priority: str = "normal"
    sla_risk: str = "low"  # low, medium, high
    category: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of: Optional[int] = None
    suggested_resolution: Optional[str] = None
    confidence: float = 0.0


class AIWorkflowAction(BaseModel):
    """Schema for an AI workflow action."""
    action_type: str  # recommend_approver, auto_categorize, predict_priority, detect_duplicate
    source: str = "ai_workflow"
    recommendation: AIWorkflowRecommendation
    applied: bool = False
    overridden_by: Optional[int] = None
    timestamp: str


# =============================================================================
#  AI Governance Schemas
# =============================================================================

class AIAuditEntry(BaseModel):
    """Schema for an AI audit entry."""
    id: str
    event_type: str  # completion, embedding, rag, copilot, prediction
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_text: Optional[str] = None
    response_text: Optional[str] = None
    user_id: Optional[int] = None
    organization_id: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    safety_flagged: bool = False
    safety_action: Optional[str] = None
    status: str = "completed"  # completed, failed, flagged
    error: Optional[str] = None
    timestamp: str


class AIUsageSummary(BaseModel):
    """Schema for AI usage summary."""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    requests_by_provider: dict[str, int] = {}
    tokens_by_model: dict[str, int] = {}
    cost_by_organization: dict[str, float] = {}
    avg_latency_ms: float = 0.0
    period_start: str
    period_end: str


class TenantAIConfig(BaseModel):
    """Schema for tenant AI configuration."""
    organization_id: str
    enabled_providers: list[str] = Field(default_factory=lambda: ["openai"])
    default_model: str = "gpt-4"
    safety_policy: AISafetyPolicy = AISafetyPolicy.MODERATE
    max_tokens_per_request: int = Field(default=4096, ge=64, le=100000)
    rate_limit_rpm: int = Field(default=60, ge=1, le=10000)
    monthly_budget_usd: Optional[float] = None
    enable_copilots: bool = True
    enable_predictive: bool = True
    enable_rag: bool = True
    audit_all_requests: bool = True
    allowed_copilot_domains: list[str] = Field(default_factory=lambda: ["hr", "policy", "operations"])
    created_at: str
    updated_at: str
