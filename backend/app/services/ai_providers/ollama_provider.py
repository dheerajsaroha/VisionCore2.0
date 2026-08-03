"""
ollama_provider.py — Ollama Local Provider
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


class OllamaProvider(AIProviderBase):
    """Provider for local Ollama models."""

    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
        self._api_base = (config.api_base_url or "http://localhost:11434").rstrip("/")
        self._default_model = config.default_model or "llama3"

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model_id or self._default_model
        system_prompt = request.system_prompt

        payload = {
            "model": model,
            "prompt": request.prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature or 0.7,
                "num_predict": request.max_tokens or 2048,
            },
        }
        if request.stop_sequences:
            payload["options"]["stop"] = request.stop_sequences

        headers = {"Content-Type": "application/json"}

        start_time = time.time()
        response = await self._client.post(
            f"{self._api_base}/api/generate",
            json=payload,
            headers=headers,
        )
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            error_body = response.text[:500]
            self._last_error = f"Ollama API error {response.status_code}: {error_body}"
            self._status = "error"
            raise ValueError(self._last_error)

        data = response.json()

        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": (data.get("prompt_eval_count", 0) + data.get("eval_count", 0)),
        }

        return AICompletionResponse(
            id=data.get("created_at", ""),
            model=data.get("model", model),
            provider=self.config.name,
            content=data.get("response", ""),
            finish_reason="stop",
            usage=usage,
            cost_usd=0.0,  # Local models are free
            latency_ms=round(latency_ms, 2),
        )

    async def complete_stream(self, request: AICompletionRequest):
        model = request.model_id or self._default_model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": True,
            "options": {
                "temperature": request.temperature or 0.7,
                "num_predict": request.max_tokens or 2048,
            },
        }
        headers = {"Content-Type": "application/json"}

        async with self._client.stream(
            "POST",
            f"{self._api_base}/api/generate",
            json=payload,
            headers=headers,
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("response", "")
                    done = chunk.get("done", False)
                    yield AIStreamChunk(
                        id=chunk.get("created_at", ""),
                        content=content,
                        finish_reason="stop" if done else None,
                    )
                except json.JSONDecodeError:
                    continue

    async def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        model = model or "nomic-embed-text"
        payload = {
            "model": model,
            "prompt": text,
        }
        headers = {"Content-Type": "application/json"}

        response = await self._client.post(
            f"{self._api_base}/api/embeddings",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            raise ValueError(f"Ollama embedding error: {response.text[:200]}")

        data = response.json()
        return data.get("embedding", [])

    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        results = []
        for text in texts:
            embedding = await self.generate_embedding(text, model)
            results.append(embedding)
        return results

    async def health_check(self) -> dict:
        try:
            response = await self._client.get(
                f"{self._api_base}/api/tags",
                timeout=10,
            )
            data = response.json()
            models = data.get("models", [])
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "ollama",
                "status": "active" if response.status_code == 200 else "error",
                "models_available": len(models),
                "latency_ms": response.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "ollama",
                "status": "error",
                "error": str(e),
            }
