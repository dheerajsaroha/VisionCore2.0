"""
openai_provider.py — OpenAI / Azure OpenAI Provider
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator, Optional

import httpx

from app.schema.ai import AICompletionRequest, AICompletionResponse, AIStreamChunk
from app.services.ai_provider_manager import AIProviderBase, AIProviderConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProviderBase):
    """Provider for OpenAI and Azure OpenAI API."""

    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
        self._model_map = {
            "gpt-4": {"context_window": 8192, "max_output": 4096},
            "gpt-4-turbo": {"context_window": 128000, "max_output": 4096},
            "gpt-4o": {"context_window": 128000, "max_output": 16384},
            "gpt-4o-mini": {"context_window": 128000, "max_output": 16384},
            "gpt-3.5-turbo": {"context_window": 16384, "max_output": 4096},
            "text-embedding-3-small": {"context_window": 8191, "max_output": 1},
            "text-embedding-3-large": {"context_window": 8191, "max_output": 1},
        }
        self._api_base = (config.api_base_url or "https://api.openai.com/v1").rstrip("/")
        self._api_key = config.api_key
        self._organization = config.organization_id
        self._default_model = config.default_model or "gpt-4o-mini"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2048,
            "stream": False,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._organization:
            headers["OpenAI-Organization"] = self._organization

        start_time = time.time()
        response = await self._client.post(
            f"{self._api_base}/chat/completions",
            json=payload,
            headers=headers,
        )
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            error_body = response.text[:500]
            self._last_error = f"OpenAI API error {response.status_code}: {error_body}"
            self._status = "error"
            raise ValueError(self._last_error)

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        cost = self._calculate_cost(prompt_tokens, completion_tokens, model)

        return AICompletionResponse(
            id=data["id"],
            model=data["model"],
            provider=self.config.name,
            content=choice["message"]["content"],
            finish_reason=choice["finish_reason"],
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": usage.get("total_tokens", 0),
            },
            cost_usd=cost,
            latency_ms=round(latency_ms, 2),
        )

    async def complete_stream(self, request: AICompletionRequest):
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2048,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with self._client.stream(
            "POST",
            f"{self._api_base}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        finish = chunk["choices"][0].get("finish_reason")
                        yield AIStreamChunk(
                            id=chunk["id"],
                            content=content,
                            finish_reason=finish,
                        )
                    except (json.JSONDecodeError, KeyError):
                        continue

    async def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        model = model or "text-embedding-3-small"
        payload = {
            "model": model,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        response = await self._client.post(
            f"{self._api_base}/embeddings",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            raise ValueError(f"Embedding API error: {response.text[:200]}")

        data = response.json()
        return data["data"][0]["embedding"]

    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        model = model or "text-embedding-3-small"
        payload = {
            "model": model,
            "input": texts,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        response = await self._client.post(
            f"{self._api_base}/embeddings",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            raise ValueError(f"Batch embedding API error: {response.text[:200]}")

        data = response.json()
        # Sort by index to preserve order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [d["embedding"] for d in sorted_data]

    async def health_check(self) -> dict:
        try:
            response = await self._client.get(f"{self._api_base}/models", headers={
                "Authorization": f"Bearer {self._api_key}",
            }, timeout=10)
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "openai",
                "status": "active" if response.status_code == 200 else "error",
                "latency_ms": response.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "openai",
                "status": "error",
                "error": str(e),
            }
