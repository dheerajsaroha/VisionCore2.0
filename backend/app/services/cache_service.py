"""
cache_service.py — Distributed Cache Management Service
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Cache management API
- Cache statistics
- Tenant namespace management
- Cache warming configuration
- Distributed lock management
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheService:
    """
    Distributed cache management service.
    
    Manages:
    - Cache key namespaces per tenant
    - Cache warming schedules
    - Cache statistics and monitoring
    - Distributed lock state
    """

    def __init__(self):
        self._warming_schedules: dict[str, dict] = {}
        self._lock_registry: dict[str, dict] = {}
        self._statistics: dict[str, Any] = {
            "total_gets": 0,
            "total_sets": 0,
            "total_deletes": 0,
            "total_hits": 0,
            "total_misses": 0,
            "total_locks_acquired": 0,
            "total_locks_released": 0,
            "total_locks_contended": 0,
            "cache_evictions": 0,
            "warming_jobs": 0,
        }

    # =========================================================================
    #  Cache Key Helpers
    # =========================================================================

    def tenant_key(self, org_id: str, key: str) -> str:
        """Generate a tenant-scoped cache key."""
        return f"tenant:{org_id}:{key}"

    def global_key(self, key: str) -> str:
        """Generate a global cache key."""
        return f"global:{key}"

    def lock_key(self, resource: str) -> str:
        """Generate a distributed lock key."""
        return f"lock:{resource}"

    # =========================================================================
    #  Cache Warming
    # =========================================================================

    def add_warming_schedule(
        self,
        name: str,
        key_pattern: str,
        ttl_seconds: int = 300,
        interval_seconds: int = 60,
        tenant_id: str = "",
    ) -> dict:
        """Add a cache warming schedule."""
        schedule = {
            "id": str(uuid.uuid4()),
            "name": name,
            "key_pattern": key_pattern,
            "ttl_seconds": ttl_seconds,
            "interval_seconds": interval_seconds,
            "tenant_id": tenant_id,
            "enabled": True,
            "last_warmed": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._warming_schedules[schedule["id"]] = schedule
        self._statistics["warming_jobs"] += 1
        return schedule

    def remove_warming_schedule(self, schedule_id: str) -> bool:
        """Remove a cache warming schedule."""
        if schedule_id in self._warming_schedules:
            del self._warming_schedules[schedule_id]
            self._statistics["warming_jobs"] -= 1
            return True
        return False

    def get_warming_schedules(self, tenant_id: str = "") -> list[dict]:
        """Get all warming schedules."""
        schedules = list(self._warming_schedules.values())
        if tenant_id:
            schedules = [s for s in schedules if s["tenant_id"] == tenant_id or not s["tenant_id"]]
        return schedules

    def record_warmed(self, schedule_id: str) -> None:
        """Record that a warming schedule was executed."""
        schedule = self._warming_schedules.get(schedule_id)
        if schedule:
            schedule["last_warmed"] = datetime.now(timezone.utc).isoformat()

    # =========================================================================
    #  Distributed Locking
    # =========================================================================

    def acquire_lock(
        self,
        resource: str,
        holder: str = "",
        ttl_seconds: int = 30,
        retry_interval: float = 0.1,
        max_retries: int = 10,
    ) -> Optional[dict]:
        """Acquire a distributed lock."""
        lock_id = str(uuid.uuid4())
        lock_key = self.lock_key(resource)

        for attempt in range(max_retries):
            if lock_key not in self._lock_registry:
                lock = {
                    "id": lock_id,
                    "resource": resource,
                    "holder": holder or lock_id,
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                    "ttl_seconds": ttl_seconds,
                    "expires_at": time.time() + ttl_seconds,
                }
                self._lock_registry[lock_key] = lock
                self._statistics["total_locks_acquired"] += 1
                return lock

            # Check if existing lock is expired
            existing = self._lock_registry.get(lock_key)
            if existing and time.time() > existing.get("expires_at", 0):
                del self._lock_registry[lock_key]
                self._statistics["cache_evictions"] += 1
                continue

            self._statistics["total_locks_contended"] += 1
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                return None

        return None

    def release_lock(self, resource: str, holder: str = "") -> bool:
        """Release a distributed lock."""
        lock_key = self.lock_key(resource)
        lock = self._lock_registry.get(lock_key)
        if lock and (not holder or lock["holder"] == holder):
            del self._lock_registry[lock_key]
            self._statistics["total_locks_released"] += 1
            return True
        return False

    def get_lock(self, resource: str) -> Optional[dict]:
        """Get lock status for a resource."""
        lock_key = self.lock_key(resource)
        lock = self._lock_registry.get(lock_key)
        if lock and time.time() > lock.get("expires_at", 0):
            del self._lock_registry[lock_key]
            self._statistics["cache_evictions"] += 1
            return None
        return lock

    def get_active_locks(self) -> list[dict]:
        """Get all active distributed locks."""
        active = []
        for key, lock in list(self._lock_registry.items()):
            if time.time() <= lock.get("expires_at", 0):
                active.append(lock)
            else:
                del self._lock_registry[key]
                self._statistics["cache_evictions"] += 1
        return active

    # =========================================================================
    #  Statistics
    # =========================================================================

    def record_get(self, hit: bool) -> None:
        """Record a cache get operation."""
        self._statistics["total_gets"] += 1
        if hit:
            self._statistics["total_hits"] += 1
        else:
            self._statistics["total_misses"] += 1

    def record_set(self) -> None:
        """Record a cache set operation."""
        self._statistics["total_sets"] += 1

    def record_delete(self) -> None:
        """Record a cache delete operation."""
        self._statistics["total_deletes"] += 1

    def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = dict(self._statistics)
        total_ops = stats["total_gets"] + stats["total_sets"]
        stats["total_operations"] = total_ops
        stats["hit_ratio"] = round(
            stats["total_hits"] / max(stats["total_gets"], 1) * 100, 1
        )
        stats["active_warming_schedules"] = len(self._warming_schedules)
        stats["active_locks"] = len(self.get_active_locks())
        return stats

    def reset_stats(self) -> None:
        """Reset all statistics."""
        for key in self._statistics:
            self._statistics[key] = 0


# Singleton
cache_service = CacheService()
