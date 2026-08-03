"""
azure_provider.py — Azure OpenAI Provider
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework
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


class AzureOpenAIProvider(AIProviderBase):
    """Provider for Azure OpenAI API."""

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
            "gpt-35-turbo": {"context_window": 16384, "max_output": 4096},
            "text-embedding-ada-002": {"context_window": 8191, "max_output": 1},
            "text-embedding-3-small": {"context_window": 8191, "max_output": 1},
            "text-embedding-3-large": {"context_window": 8191, "max_output": 1},
        }
        # Azure endpoint: https://{resource}.openai.azure.com/openai/deployments/{deployment}
        self._api_base = (config.api_base_url or "https://api.openai.azure.com").rstrip("/")
        self._api_key = config.api_key
        self._default_model = config.default_model or "gpt-4o-mini"
        self._api_version = config.extra_params.get("api_version", "2024-02-15-preview") if config.extra_params else "2024-02-15-preview"
        self._deployment = config.extra_params.get("deployment", "") if config.extra_params else ""

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model_id or self._default_model
        deployment = self._deployment or model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        payload = {
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
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

        url = f"{self._api_base}/openai/deployments/{deployment}/chat/completions?api-version={self._api_version}"

        start_time = time.time()
        response = await self._client.post(url, json=payload, headers=headers)
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            error_body = response.text[:500]
            self._last_error = f"Azure OpenAI API error {response.status_code}: {error_body}"
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
            model=data.get("model", model),
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
        deployment = self._deployment or model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2048,
            "stream": True,
        }

        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

        url = f"{self._api_base}/openai/deployments/{deployment}/chat/completions?api-version={self._api_version}"

        async with self._client.stream("POST", url, json=payload, headers=headers) as response:
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
        deployment = self._deployment or model
        payload = {"input": text}
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        url = f"{self._api_base}/openai/deployments/{deployment}/embeddings?api-version={self._api_version}"

        response = await self._client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"Azure Embedding API error: {response.text[:200]}")
        data = response.json()
        return data["data"][0]["embedding"]

    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        model = model or "text-embedding-3-small"
        deployment = self._deployment or model
        payload = {"input": texts}
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        url = f"{self._api_base}/openai/deployments/{deployment}/embeddings?api-version={self._api_version}"

        response = await self._client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"Azure batch embedding error: {response.text[:200]}")
        data = response.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [d["embedding"] for d in sorted_data]

    async def health_check(self) -> dict:
        try:
            deployment = self._deployment or self._default_model
            url = f"{self._api_base}/openai/deployments/{deployment}?api-version={self._api_version}"
            response = await self._client.get(url, headers={"api-key": self._api_key}, timeout=10)
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "azure_openai",
                "status": "active" if response.status_code == 200 else "error",
                "latency_ms": response.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "azure_openai",
                "status": "error",
                "error": str(e),
            }

