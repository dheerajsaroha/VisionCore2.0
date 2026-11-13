# backend/app/tasks.py
"""Asynchronous inference task definitions.
We use Celery with Redis as the broker (already required for rate‑limit fallback).
The tasks are deliberately lightweight examples – real AI inference would be more complex.
"""
from __future__ import annotations

from celery import Celery
from typing import Any, Dict

# Celery app – configuration is read from environment via the existing .env
celery_app = Celery(
    "visioncore",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

# Example task: process a single video frame (base64‑encoded image) and return a mock embedding.
@celery_app.task(name="process_frame")
def process_frame(frame_data: str) -> Dict[str, Any]:
    """Placeholder image‑processing task.
    In production this would decode the base64 image, run the face model, optionally
    perform liveness checks, and store the resulting embedding.
    """
    # Simulate some CPU work – in real life this would be OpenCV + model inference.
    import time
    time.sleep(0.2)  # pretend the model takes ~200 ms
    # Return a fake 128‑dim embedding (list of floats).
    fake_embedding = [0.0] * 128
    return {"status": "ok", "embedding": fake_embedding}
