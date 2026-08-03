"""
copilot_service.py — Enterprise AI Copilot Framework
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Central copilot orchestration service:
- Domain-specific copilot routing
- Conversation context management
- RAG-enhanced responses
- Action suggestions and workflow triggers
- Multi-turn conversation support
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import (
    AICompletionRequest,
    Conversation,
    ConversationMessage,
    CopilotDomain,
    CopilotRequest,
    CopilotResponse,
)
from app.services.ai_provider_manager import ai_provider_manager
from app.services.ai_cost_tracker import ai_cost_tracker
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class BaseCopilot:
    """Base class for all domain copilots."""

    def __init__(self, domain: CopilotDomain, name: str, description: str):
        self.domain = domain
        self.name = name
        self.description = description
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the base system prompt for this copilot."""
        return (
            f"You are the {self.name}, an enterprise AI assistant specializing in {self.description}. "
            "You help users with questions, tasks, and recommendations. "
            "Be concise, accurate, and professional. "
            "If you need more information, ask clarifying questions. "
            "Always consider company policies and best practices."
        )

    async def process(
        self,
        request: CopilotRequest,
        context: Optional[dict] = None,
    ) -> Optional[CopilotResponse]:
        """Process a copilot request. Override in subclasses."""
        return None

    def get_capabilities(self) -> list[str]:
        """Get copilot capabilities."""
        return [
            "Q&A",
            "Summarization",
            "Recommendations",
            "Workflow assistance",
            "Natural language analytics",
            "Draft generation",
        ]


class CopilotService:
    """
    Central copilot orchestration service.

    Manages:
    - Domain-specific copilot registration and routing
    - Conversation context management
    - RAG-enhanced responses with knowledge base
    - Action suggestions and workflow triggers
    - Multi-turn conversation tracking
    """

    def __init__(self):
        self._copilots: dict[CopilotDomain, BaseCopilot] = {}
        self._conversations: dict[str, Conversation] = {}
        self._max_conversations: int = 10000
        self._max_messages_per_conversation: int = 100

    def register_copilot(self, copilot: BaseCopilot) -> None:
        """Register a domain copilot."""
        self._copilots[copilot.domain] = copilot
        logger.info(f"Copilot registered: {copilot.name} ({copilot.domain.value})")

    def get_copilot(self, domain: CopilotDomain) -> Optional[BaseCopilot]:
        """Get a copilot by domain."""
        return self._copilots.get(domain)

    def get_copilots(self) -> list[BaseCopilot]:
        """Get all registered copilots."""
        return list(self._copilots.values())

    # =========================================================================
    #  Conversation Management
    # =========================================================================

    def create_conversation(
        self,
        domain: CopilotDomain,
        title: str,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            id=str(uuid.uuid4()),
            domain=domain,
            title=title,
            organization_id=organization_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._conversations[conversation.id] = conversation
        self._trim_conversations()
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    def get_conversations(
        self,
        user_id: Optional[int] = None,
        domain: Optional[CopilotDomain] = None,
        limit: int = 50,
    ) -> list[Conversation]:
        """Get conversations with optional filtering."""
        results = list(self._conversations.values())
        if user_id:
            results = [c for c in results if c.user_id == user_id]
        if domain:
            results = [c for c in results if c.domain == domain]
        return sorted(results, key=lambda c: c.updated_at, reverse=True)[:limit]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Optional[ConversationMessage]:
        """Add a message to a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        if len(conversation.messages) >= self._max_messages_per_conversation:
            conversation.messages = conversation.messages[-self._max_messages_per_conversation + 1:]

        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata,
        )
        conversation.messages.append(message)
        conversation.updated_at = datetime.now(timezone.utc).isoformat()
        return message

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    def _trim_conversations(self) -> None:
        """Trim conversations if over limit."""
        if len(self._conversations) > self._max_conversations:
            sorted_conv = sorted(
                self._conversations.values(),
                key=lambda c: c.updated_at,
            )
            for conv in sorted_conv[:len(sorted_conv) - self._max_conversations]:
                del self._conversations[conv.id]

    # =========================================================================
    #  Query Processing
    # =========================================================================

    async def query(self, request: CopilotRequest) -> CopilotResponse:
        """
        Process a copilot query.

        Steps:
        1. Find the appropriate domain copilot
        2. Build context from conversation history and domain data
        3. Process with RAG enhancement if available
        4. Track conversation
        5. Return response with suggestions and actions
        """
        start_time = time.time()

        # Find copilot
        copilot = self._copilots.get(request.domain)
        if not copilot:
            raise ValueError(f"No copilot registered for domain: {request.domain}")

        # Get or create conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation = self.create_conversation(
                domain=request.domain,
                title=request.query[:80] + ("..." if len(request.query) > 80 else ""),
                organization_id=request.organization_id,
                user_id=request.user_id,
            )
            conversation_id = conversation.id
        else:
            conversation = self._conversations.get(conversation_id)

        # Add user message to conversation
        self.add_message(
            conversation_id,
            role="user",
            content=request.query,
            metadata={"context": request.context},
        )

        # Build context
        context = await self._build_context(request, copilot)

        # Process with copilot
        try:
            response = await copilot.process(request, context)
        except NotImplementedError:
            response = None

        if not response:
            # Fallback to generic AI processing
            response = await self._generic_process(request, copilot, context, start_time)

        # Add assistant message to conversation
        self.add_message(
            conversation_id,
            role="assistant",
            content=response.answer,
            metadata={"suggestions": response.suggestions, "actions": response.actions},
        )

        # Audit
        audit_service.record(
            module="ai",
            action="copilot_query",
            entity_type="copilot_query",
            entity_id=response.id,
            summary=f"Copilot query: {request.domain.value} - {request.query[:80]}...",
            details={
                "domain": request.domain.value,
                "conversation_id": conversation_id,
                "model": response.usage.get("model", "unknown"),
                "tokens": response.usage,
                "cost": response.cost_usd,
            },
            organization_id=request.organization_id or "",
            actor_user_id=request.user_id,
        )

        response.conversation_id = conversation_id
        return response

    async def _build_context(
        self,
        request: CopilotRequest,
        copilot: BaseCopilot,
    ) -> dict:
        """Build enriched context for the copilot."""
        context = request.context or {}

        # Add conversation history
        conversation = self._conversations.get(request.conversation_id or "")
        if conversation:
            context["conversation_history"] = [
                {"role": m.role, "content": m.content}
                for m in conversation.messages[-10:]
            ]

        # Add platform analytics context based on domain
        domain_contexts = {
            CopilotDomain.HR: self._get_hr_context,
            CopilotDomain.RECRUITMENT: self._get_recruitment_context,
            CopilotDomain.POLICY: self._get_policy_context,
            CopilotDomain.PERFORMANCE: self._get_performance_context,
            CopilotDomain.ASSET: self._get_asset_context,
            CopilotDomain.OPERATIONS: self._get_operations_context,
            CopilotDomain.EXECUTIVE: self._get_executive_context,
        }
        context_fn = domain_contexts.get(request.domain)
        if context_fn:
            try:
                domain_data = context_fn(request.organization_id)
                context["domain_data"] = domain_data
            except Exception as e:
                logger.warning(f"Failed to get domain context: {e}")

        return context

    async def _generic_process(
        self,
        request: CopilotRequest,
        copilot: BaseCopilot,
        context: dict,
        start_time: float,
    ) -> CopilotResponse:
        """Generic AI processing fallback."""
        prompt_parts = []
        if context.get("domain_data"):
            prompt_parts.append(f"Domain Context:\n{context.get('domain_data')}")
        if context.get("conversation_history"):
            prompt_parts.append("Conversation History:\n" + "\n".join(
                f"{m['role']}: {m['content']}"
                for m in context["conversation_history"][-5:]
            ))
        prompt_parts.append(f"User Query: {request.query}")
        prompt = "\n\n".join(prompt_parts)

        completion_request = AICompletionRequest(
            prompt=prompt,
            system_prompt=copilot._system_prompt,
            model_id=request.model_id,
            temperature=request.temperature or 0.5,
            max_tokens=2048,
            organization_id=request.organization_id,
            user_id=request.user_id,
        )

        completion = await ai_provider_manager.complete(completion_request)

        # Track cost
        ai_cost_tracker.track_completion(
            provider=completion.provider,
            model=completion.model,
            prompt_tokens=completion.usage.get("prompt_tokens", 0),
            completion_tokens=completion.usage.get("completion_tokens", 0),
            total_tokens=completion.usage.get("total_tokens", 0),
            cost_usd=completion.cost_usd,
            organization_id=request.organization_id,
            user_id=request.user_id,
            request_type=f"copilot_{request.domain.value}",
        )

        latency_ms = (time.time() - start_time) * 1000

        return CopilotResponse(
            id=str(uuid.uuid4()),
            domain=request.domain,
            query=request.query,
            answer=completion.content,
            suggestions=self._generate_suggestions(request.domain, completion.content),
            actions=self._generate_actions(request.domain, completion.content),
            data_sources=[copilot.name],
            usage={
                "model": completion.model,
                "provider": completion.provider,
                **completion.usage,
            },
            cost_usd=completion.cost_usd,
            latency_ms=round(latency_ms, 2),
            conversation_id=request.conversation_id or "",
        )

    # =========================================================================
    #  Domain Context Providers
    # =========================================================================

    def _get_hr_context(self, org_id: Optional[str]) -> dict:
        from app.services.analytics_platform import analytics_platform
        return analytics_platform.get_hr_analytics(org_id or "")

    def _get_recruitment_context(self, org_id: Optional[str]) -> dict:
        entries, _ = audit_service.search(module="recruitment", organization_id=org_id or None, limit=20)
        return {"open_positions": len(entries)}

    def _get_policy_context(self, org_id: Optional[str]) -> dict:
        from app.services.analytics_platform import analytics_platform
        return analytics_platform.get_policy_analytics(org_id or "")

    def _get_performance_context(self, org_id: Optional[str]) -> dict:
        from app.services.analytics_platform import analytics_platform
        return analytics_platform.get_performance_analytics(org_id or "")

    def _get_asset_context(self, org_id: Optional[str]) -> dict:
        from app.services.analytics_platform import analytics_platform
        return analytics_platform.get_asset_analytics(org_id or "")

    def _get_operations_context(self, org_id: Optional[str]) -> dict:
        from app.services.monitor_service import monitor_service
        dashboard = monitor_service.get_dashboard()
        return {
            "health_score": dashboard.get("health_score"),
            "alerts": dashboard.get("alerts", [])[-5:],
        }

    def _get_executive_context(self, org_id: Optional[str]) -> dict:
        from app.services.analytics_platform import analytics_platform
        return analytics_platform.get_executive_dashboard(org_id or "")

    # =========================================================================
    #  Suggestions & Actions
    # =========================================================================

    def _generate_suggestions(self, domain: CopilotDomain, answer: str) -> list[str]:
        """Generate follow-up suggestions based on domain and answer."""
        suggestions_map = {
            CopilotDomain.HR: [
                "Show me leave balances",
                "What are the attendance trends?",
                "Help me draft a HR policy",
            ],
            CopilotDomain.RECRUITMENT: [
                "Show open positions",
                "Summarize candidate pipeline",
                "Schedule an interview",
            ],
            CopilotDomain.POLICY: [
                "Search policies about leave",
                "Summarize compliance requirements",
                "What policies need acknowledgement?",
            ],
            CopilotDomain.PERFORMANCE: [
                "Show performance trends",
                "Identify top performers",
                "Generate review summary",
            ],
            CopilotDomain.ASSET: [
                "Show asset inventory",
                "Assets due for maintenance",
                "License expiry report",
            ],
            CopilotDomain.OPERATIONS: [
                "System health status",
                "Active alerts",
                "Recent incidents",
            ],
            CopilotDomain.EXECUTIVE: [
                "Platform overview",
                "Key metrics summary",
                "Risk assessment",
            ],
        }
        return suggestions_map.get(domain, [])

    def _generate_actions(self, domain: CopilotDomain, answer: str) -> list[dict]:
        """Generate actionable items based on domain and answer."""
        actions_map = {
            CopilotDomain.HR: [
                {"type": "navigate", "label": "Open HR Dashboard", "url": "/dashboard/hr"},
                {"type": "navigate", "label": "View Leave Management", "url": "/dashboard/leave"},
            ],
            CopilotDomain.PERFORMANCE: [
                {"type": "navigate", "label": "Performance Dashboard", "url": "/dashboard/performance"},
                {"type": "navigate", "label": "View Reviews", "url": "/dashboard/performance/reviews"},
            ],
            CopilotDomain.POLICY: [
                {"type": "navigate", "label": "Policy Center", "url": "/dashboard/policies"},
            ],
            CopilotDomain.ASSET: [
                {"type": "navigate", "label": "Asset Management", "url": "/dashboard/assets"},
            ],
            CopilotDomain.OPERATIONS: [
                {"type": "navigate", "label": "Operations Center", "url": "/dashboard/operations"},
            ],
            CopilotDomain.EXECUTIVE: [
                {"type": "navigate", "label": "Analytics Dashboard", "url": "/dashboard/reports"},
                {"type": "navigate", "label": "Platform Overview", "url": "/dashboard"},
            ],
        }
        return actions_map.get(domain, [])

    def get_stats(self) -> dict:
        """Get copilot service statistics."""
        return {
            "copilots_registered": len(self._copilots),
            "active_conversations": len(self._conversations),
            "copilots": [
                {"domain": c.domain.value, "name": c.name}
                for c in self._copilots.values()
            ],
        }


# Singleton
copilot_service = CopilotService()

