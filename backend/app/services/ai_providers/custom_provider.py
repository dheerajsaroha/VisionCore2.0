"""
custom_provider.py — Custom REST API Provider
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


class CustomRESTProvider(AIProviderBase):
    """Provider for custom REST API endpoints."""

    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
        )
        self._api_base = (config.api_base_url or "").rstrip("/")
        self._api_key = config.api_key
        self._default_model = config.default_model or "default"
        self._default_endpoint = "/v1/chat/completions"
        self._extra_params = config.extra_params or {}

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model_id or self._default_model
        endpoint = self._extra_params.get("completion_endpoint", self._default_endpoint)
        system_prompt = request.system_prompt or ""

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2048,
        }

        # Merge any extra params
        payload.update(self._extra_params.get("default_payload", {}))

        headers = {
            "Content-Type": "application/json",
        }
        auth_type = self._extra_params.get("auth_type", "bearer")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"
        elif auth_type == "api-key":
            headers["X-API-Key"] = self._api_key
        elif auth_type == "header":
            header_name = self._extra_params.get("auth_header_name", "Authorization")
            headers[header_name] = self._api_key

        start_time = time.time()
        response = await self._client.post(
            f"{self._api_base}{endpoint}",
            json=payload,
            headers=headers,
        )
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            error_body = response.text[:500]
            self._last_error = f"Custom API error {response.status_code}: {error_body}"
            self._status = "error"
            raise ValueError(self._last_error)

        data = response.json()

        # Try to extract content from common response formats
        content = ""
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"]
            elif "text" in choice:
                content = choice["text"]
        elif "response" in data:
            content = data["response"]
        elif "output" in data:
            content = data["output"]
        else:
            content = str(data)

        usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

        return AICompletionResponse(
            id=data.get("id", f"custom-{int(time.time())}"),
            model=data.get("model", model),
            provider=self.config.name,
            content=content,
            finish_reason=data.get("choices", [{}])[0].get("finish_reason", "stop") if "choices" in data else "stop",
            usage=usage,
            cost_usd=0.0,
            latency_ms=round(latency_ms, 2),
        )

    async def complete_stream(self, request: AICompletionRequest):
        model = request.model_id or self._default_model
        endpoint = self._extra_params.get("completion_endpoint", self._default_endpoint)
        system_prompt = request.system_prompt or ""

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

        headers = {"Content-Type": "application/json"}
        auth_type = self._extra_params.get("auth_type", "bearer")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"
        elif auth_type == "api-key":
            headers["X-API-Key"] = self._api_key

        async with self._client.stream(
            "POST",
            f"{self._api_base}{endpoint}",
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
                        if "choices" in chunk:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            finish = chunk["choices"][0].get("finish_reason")
                            yield AIStreamChunk(
                                id=chunk.get("id", ""),
                                content=content,
                                finish_reason=finish,
                            )
                        elif "response" in chunk:
                            yield AIStreamChunk(
                                id=chunk.get("id", ""),
                                content=chunk.get("response", ""),
                            )
                    except (json.JSONDecodeError, KeyError):
                        continue

    async def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        model = model or self._default_model
        endpoint = self._extra_params.get("embedding_endpoint", "/v1/embeddings")

        payload = {
            "model": model,
            "input": text,
        }

        headers = {"Content-Type": "application/json"}
        auth_type = self._extra_params.get("auth_type", "bearer")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = await self._client.post(
            f"{self._api_base}{endpoint}",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            raise ValueError(f"Custom embedding error: {response.text[:200]}")

        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0].get("embedding", [])
        return data.get("embedding", [])

    async def generate_embeddings_batch(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        endpoint = self._extra_params.get("embedding_endpoint", "/v1/embeddings")
        payload = {
            "model": model or self._default_model,
            "input": texts,
        }
        headers = {"Content-Type": "application/json"}
        auth_type = self._extra_params.get("auth_type", "bearer")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = await self._client.post(
            f"{self._api_base}{endpoint}",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            raise ValueError(f"Batch embedding error: {response.text[:200]}")

        data = response.json()
        if "data" in data:
            sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
            return [d["embedding"] for d in sorted_data]
        return data.get("embeddings", [])

    async def health_check(self) -> dict:
        try:
            health_endpoint = self._extra_params.get("health_endpoint", "/health")
            response = await self._client.get(
                f"{self._api_base}{health_endpoint}",
                timeout=10,
            )
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "custom_rest",
                "status": "active" if response.status_code == 200 else "error",
                "latency_ms": response.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "provider_id": self.provider_id,
                "name": self.config.name,
                "type": "custom_rest",
                "status": "error",
                "error": str(e),
            }
