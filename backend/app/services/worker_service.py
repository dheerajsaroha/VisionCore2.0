"""
worker_service.py — Distributed Worker Management Service
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Worker pool management
- Worker heartbeat and health monitoring
- Distributed job execution coordination
- Worker capacity management
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WorkerStatus:
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    DOWN = "down"


class WorkerService:
    """
    Distributed worker management service.

    Manages:
    - Worker registration and lifecycle
    - Worker capacity and load balancing
    - Job assignment to workers
    - Worker health monitoring
    """

    def __init__(self):
        self._workers: dict[str, dict] = {}
        self._max_workers: int = 100
        self._worker_timeout_seconds: int = 30

    def register_worker(
        self,
        worker_id: str,
        host: str = "",
        port: int = 0,
        max_concurrent_jobs: int = 5,
        labels: Optional[dict] = None,
    ) -> dict:
        """Register a new worker."""
        worker = {
            "id": worker_id,
            "host": host,
            "port": port,
            "status": WorkerStatus.IDLE,
            "max_concurrent_jobs": max_concurrent_jobs,
            "current_jobs": [],
            "total_jobs_processed": 0,
            "labels": labels or {},
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
        }
        self._workers[worker_id] = worker
        logger.info(f"Worker registered: {worker_id} (capacity={max_concurrent_jobs})")
        return worker

    def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker."""
        if worker_id in self._workers:
            del self._workers[worker_id]
            return True
        return False

    def get_worker(self, worker_id: str) -> Optional[dict]:
        """Get worker details."""
        return self._workers.get(worker_id)

    def list_workers(self, status: str = "") -> list[dict]:
        """List all workers."""
        workers = list(self._workers.values())
        if status:
            workers = [w for w in workers if w["status"] == status]
        return workers

    def update_heartbeat(self, worker_id: str, stats: Optional[dict] = None) -> bool:
        """Update worker heartbeat."""
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        worker["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        if stats:
            worker["cpu_usage"] = stats.get("cpu_usage", worker["cpu_usage"])
            worker["memory_usage"] = stats.get("memory_usage", worker["memory_usage"])
        return True

    def assign_job(self, worker_id: str, job_id: str) -> bool:
        """Assign a job to a worker."""
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        if len(worker["current_jobs"]) >= worker["max_concurrent_jobs"]:
            return False
        worker["current_jobs"].append(job_id)
        worker["status"] = WorkerStatus.BUSY
        worker["total_jobs_processed"] += 1
        return True

    def complete_job(self, worker_id: str, job_id: str) -> bool:
        """Mark a job as completed on a worker."""
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        if job_id in worker["current_jobs"]:
            worker["current_jobs"].remove(job_id)
        if not worker["current_jobs"]:
            worker["status"] = WorkerStatus.IDLE
        return True

    def get_available_worker(self) -> Optional[dict]:
        """Get an available worker for job assignment."""
        for worker in self._workers.values():
            if worker["status"] == WorkerStatus.IDLE:
                return worker
            if (worker["status"] == WorkerStatus.BUSY
                    and len(worker["current_jobs"]) < worker["max_concurrent_jobs"]):
                return worker
        return None

    def get_worker_count(self) -> dict:
        """Get worker count statistics."""
        workers = self._workers.values()
        return {
            "total": len(workers),
            "idle": len([w for w in workers if w["status"] == WorkerStatus.IDLE]),
            "busy": len([w for w in workers if w["status"] == WorkerStatus.BUSY]),
            "draining": len([w for w in workers if w["status"] == WorkerStatus.DRAINING]),
            "total_capacity": sum(w["max_concurrent_jobs"] for w in workers),
            "current_load": sum(len(w["current_jobs"]) for w in workers),
        }

    def get_stats(self) -> dict:
        """Get worker service statistics."""
        return self.get_worker_count()


# Singleton
worker_service = WorkerService()
