"""
anthropic_provider.py — Anthropic Claude Provider
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

import httpx

from app.schema.ai import AICompletionRequest, AICompletionResponse, AIStreamChunk
from app.services.ai_provider_manager import AIProviderBase, AIProviderConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProviderBase):
    """Provider for Anthropic Claude API."""

    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
        self._model_map = {
            "claude-3-opus": {"context_window": 200000, "max_output": 4096},
            "claude-3-sonnet": {"context_window": 200000, "max_output": 4096},
            "claude-3-haiku": {"context_window": 200000, "max_output": 4096},
            "claude-3-5-sonnet": {"context_window": 200000, "max_output": 8192},
        }
        self._api_base = (config.api_base_url or "https://api.anthropic.com/v1").rstrip("/")
        self._api_key = config.api_key
        self._default_model = config.default_model or "claude-3-5-sonnet-20241022"
        self._api_version = "2023-06-01"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        payload = {
            "model": model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2048,
        }
        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._api_version,
            "Content-Type": "application/json",
        }

        start_time = time.time()
        response = await self._client.post(
            f"{self._api_base}/messages",
            json=payload,
            headers=headers,
        )
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            error_body = response.text[:500]
            self._last_error = f"Anthropic API error {response.status_code}: {error_body}"
            self._status = "error"
            raise ValueError(self._last_error)

        data = response.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        cost = self._calculate_cost(input_tokens, output_tokens, model)

        return AICompletionResponse(
            id=data["id"],
            model=data["model"],
            provider=self.config.name,
            content=content,
            finish_reason=data.get("stop_reason", "end_turn"),
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            cost_usd=cost,
            latency_ms=round(latency_ms, 2),
        )

    async def complete_stream(self, request: AICompletionRequest):
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        payload = {
            "model": model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2048,
            "stream": True,
        }

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._api_version,
            "Content-Type": "application/json",
        }

        async with self._client.stream(
            "POST",
            f"{self._api_base}/messages",
            json=payload,
            headers=headers,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    try:
                        chunk = json.loads(chunk_data)
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {})
                            yield AIStreamChunk(
                                id=chunk.get("id", ""),
                                content=delta.get("text", ""),
                                finish_reason=chunk.get("stop_reason"),
                            )
                    except json.JSONDecodeError:
                        continue

    async def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        raise NotImplementedError("Anthropic does not support embeddings via API")

    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not support embeddings via API")

    async def health_check(self) -> dict:
        try:
            response = await self._client.get(
                f"{self._api_base}/models",
                headers={"x-api-key": self._api_key, "anthropic-version": self._api_version},
                timeout=10,
            )
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "anthropic",
                "status": "active" if response.status_code == 200 else "error",
                "latency_ms": response.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "anthropic",
                "status": "error",
                "error": str(e),
            }
