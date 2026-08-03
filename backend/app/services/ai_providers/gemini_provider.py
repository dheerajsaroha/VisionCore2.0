"""
gemini_provider.py — Google Gemini Provider
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


class GeminiProvider(AIProviderBase):
    """Provider for Google Gemini API."""

    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
        self._model_map = {
            "gemini-pro": {"context_window": 30720, "max_output": 2048},
            "gemini-pro-vision": {"context_window": 30720, "max_output": 2048},
            "gemini-1.5-pro": {"context_window": 1000000, "max_output": 8192},
            "gemini-1.5-flash": {"context_window": 1000000, "max_output": 8192},
            "gemini-2.0-flash": {"context_window": 1000000, "max_output": 8192},
            "text-embedding-004": {"context_window": 2048, "max_output": 1},
        }
        self._api_base = (config.api_base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self._api_key = config.api_key
        self._default_model = config.default_model or "gemini-1.5-flash"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"[System Instruction]: {system_prompt}\n\nUser: {request.prompt}"}]})
        else:
            contents.append({"role": "user", "parts": [{"text": request.prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature or 0.7,
                "maxOutputTokens": request.max_tokens or 2048,
                "stopSequences": request.stop_sequences or [],
            },
        }

        headers = {"Content-Type": "application/json"}
        url = f"{self._api_base}/models/{model}:generateContent?key={self._api_key}"

        start_time = time.time()
        response = await self._client.post(url, json=payload, headers=headers)
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            error_body = response.text[:500]
            self._last_error = f"Gemini API error {response.status_code}: {error_body}"
            self._status = "error"
            raise ValueError(self._last_error)

        data = response.json()
        candidate = data.get("candidates", [{}])[0]
        content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
        finish_reason = candidate.get("finishReason", "STOP")

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        cost = self._calculate_cost(prompt_tokens, completion_tokens, model)

        return AICompletionResponse(
            id=data.get("id", f"gemini-{int(time.time())}"),
            model=model,
            provider=self.config.name,
            content=content,
            finish_reason=finish_reason.lower() if finish_reason else "stop",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            cost_usd=cost,
            latency_ms=round(latency_ms, 2),
        )

    async def complete_stream(self, request: AICompletionRequest):
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt or "You are a helpful enterprise AI assistant."

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"[System Instruction]: {system_prompt}\n\nUser: {request.prompt}"}]})
        else:
            contents.append({"role": "user", "parts": [{"text": request.prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature or 0.7,
                "maxOutputTokens": request.max_tokens or 2048,
            },
        }

        headers = {"Content-Type": "application/json"}
        url = f"{self._api_base}/models/{model}:streamGenerateContent?key={self._api_key}&alt=sse"

        async with self._client.stream("POST", url, json=payload, headers=headers) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    candidate = chunk.get("candidates", [{}])[0]
                    part = candidate.get("content", {}).get("parts", [{}])[0]
                    content = part.get("text", "")
                    finish = candidate.get("finishReason", "")
                    yield AIStreamChunk(
                        id=chunk.get("id", ""),
                        content=content,
                        finish_reason=finish.lower() if finish else None,
                    )
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

    async def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        model = model or "text-embedding-004"
        payload = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": text}]},
        }
        headers = {"Content-Type": "application/json"}
        url = f"{self._api_base}/models/{model}:embedContent?key={self._api_key}"

        response = await self._client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"Gemini embedding error: {response.text[:200]}")
        data = response.json()
        return data.get("embedding", {}).get("values", [])

    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        model = model or "text-embedding-004"
        payload = {
            "model": f"models/{model}",
            "requests": [
                {"model": f"models/{model}", "content": {"parts": [{"text": text}]}}
                for text in texts
            ],
        }
        headers = {"Content-Type": "application/json"}
        url = f"{self._api_base}/models/{model}:batchEmbedContents?key={self._api_key}"

        response = await self._client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"Gemini batch embedding error: {response.text[:200]}")
        data = response.json()
        return [e.get("values", []) for e in data.get("embeddings", [])]

    async def health_check(self) -> dict:
        try:
            url = f"{self._api_base}/models?key={self._api_key}"
            response = await self._client.get(url, timeout=10)
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "gemini",
                "status": "active" if response.status_code == 200 else "error",
                "latency_ms": response.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "gemini",
                "status": "error",
                "error": str(e),
            }

