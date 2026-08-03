"""
ha_service.py — Enterprise High Availability Service
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Horizontal scaling readiness verification
- Session sharing configuration
- Load balancing readiness
- Failover configuration
- Leader election abstraction
- Graceful shutdown handling
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    ACTIVE = "active"
    STANDBY = "standby"
    DRAINING = "draining"
    DOWN = "down"
    LEADER = "leader"


class NodeRole(Enum):
    PRIMARY = "primary"
    REPLICA = "replica"
    WORKER = "worker"


class HAService:
    """
    Enterprise high availability service.

    Manages:
    - Node registration and health
    - Leader election
    - Failover coordination
    - Session sharing configuration
    - Load balancing state
    """

    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._current_leader: Optional[str] = None
        self._leader_term: int = 0
        self._failover_history: list[dict] = []
        self._load_balancer_config: dict = {
            "algorithm": "round_robin",
            "health_check_interval": 10,
            "health_check_timeout": 5,
            "unhealthy_threshold": 3,
            "session_sticky": True,
            "session_cookie_name": "VC_SESSION",
        }

    # =========================================================================
    #  Node Management
    # =========================================================================

    def register_node(
        self,
        node_id: str,
        host: str = "",
        port: int = 0,
        role: str = "replica",
        labels: Optional[dict] = None,
    ) -> dict:
        """Register a node in the cluster."""
        node = {
            "id": node_id,
            "host": host,
            "port": port,
            "role": role,
            "status": NodeStatus.ACTIVE.value,
            "labels": labels or {},
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "health_score": 1.0,
            "active_connections": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
        }
        self._nodes[node_id] = node
        logger.info(f"Node registered: {node_id} (role={role}, host={host}:{port})")
        return node

    def unregister_node(self, node_id: str) -> bool:
        """Unregister a node from the cluster."""
        if node_id in self._nodes:
            if self._current_leader == node_id:
                self._current_leader = None
            del self._nodes[node_id]
            # Trigger leader election if leader is gone
            if node_id == self._current_leader:
                self._elect_leader()
            return True
        return False

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get node details."""
        return self._nodes.get(node_id)

    def list_nodes(self, role: str = "", status: str = "") -> list[dict]:
        """List all cluster nodes."""
        nodes = list(self._nodes.values())
        if role:
            nodes = [n for n in nodes if n["role"] == role]
        if status:
            nodes = [n for n in nodes if n["status"] == status]
        return nodes

    def update_node_heartbeat(self, node_id: str, health: Optional[dict] = None) -> bool:
        """Update node heartbeat."""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        if health:
            node["health_score"] = health.get("score", node["health_score"])
            node["cpu_usage"] = health.get("cpu_usage", node["cpu_usage"])
            node["memory_usage"] = health.get("memory_usage", node["memory_usage"])
            node["active_connections"] = health.get("connections", node["active_connections"])
        return True

    def set_node_status(self, node_id: str, status: str) -> bool:
        """Set node status (active, draining, down, standby)."""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node["status"] = status
        if status == NodeStatus.DOWN.value:
            self._handle_node_failure(node_id)
        return True

    # =========================================================================
    #  Leader Election
    # =========================================================================

    def _elect_leader(self) -> Optional[str]:
        """Elect a new leader from available nodes."""
        candidates = [
            n for n in self._nodes.values()
            if n["status"] == NodeStatus.ACTIVE.value
            and n["role"] != NodeRole.WORKER.value
        ]

        if not candidates:
            self._current_leader = None
            return None

        # Prefer primary role, then highest health score
        primaries = [n for n in candidates if n["role"] == NodeRole.PRIMARY.value]
        if primaries:
            leader = max(primaries, key=lambda n: n["health_score"])
        else:
            leader = max(candidates, key=lambda n: n["health_score"])

        self._current_leader = leader["id"]
        self._leader_term += 1
        leader["status"] = NodeStatus.LEADER.value

        logger.info(
            f"Leader elected: {leader['id']} (term={self._leader_term})"
        )
        return leader["id"]

    def get_leader(self) -> Optional[dict]:
        """Get the current leader node."""
        if not self._current_leader:
            self._elect_leader()
        leader = self._nodes.get(self._current_leader or "")
        if leader and leader["status"] == NodeStatus.ACTIVE.value:
            return leader
        # Leader is unhealthy, re-elect
        self._elect_leader()
        return self._nodes.get(self._current_leader or "")

    def get_leader_term(self) -> int:
        """Get current leader term."""
        return self._leader_term

    # =========================================================================
    #  Failover Handling
    # =========================================================================

    def _handle_node_failure(self, node_id: str) -> None:
        """Handle a node failure."""
        node = self._nodes.get(node_id)
        if not node:
            return

        self._failover_history.append({
            "node_id": node_id,
            "previous_role": node["role"],
            "previous_status": node["status"],
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "action_taken": "re_elect_leader" if node_id == self._current_leader else "mark_down",
        })

        # If leader failed, trigger re-election
        if node_id == self._current_leader:
            self._elect_leader()

        logger.warning(f"Node failure handled: {node_id}")

    def get_failover_history(self, limit: int = 50) -> list[dict]:
        """Get failover history."""
        return sorted(
            self._failover_history,
            key=lambda f: f["failed_at"],
            reverse=True,
        )[:limit]

    # =========================================================================
    #  Session Sharing
    # =========================================================================

    def get_session_config(self) -> dict:
        """Get session sharing configuration."""
        return {
            "backend": "redis",
            "prefix": "session:",
            "ttl_seconds": 3600,
            "sticky": self._load_balancer_config["session_sticky"],
            "cookie_name": self._load_balancer_config["session_cookie_name"],
        }

    def update_session_config(self, config: dict) -> dict:
        """Update session sharing configuration."""
        self._load_balancer_config.update(config)
        return self.get_session_config()

    # =========================================================================
    #  Load Balancer Configuration
    # =========================================================================

    def get_lb_config(self) -> dict:
        """Get load balancer configuration."""
        return dict(self._load_balancer_config)

    def update_lb_config(self, config: dict) -> dict:
        """Update load balancer configuration."""
        self._load_balancer_config.update(config)
        return self.get_lb_config()

    def get_healthy_nodes(self) -> list[dict]:
        """Get all healthy nodes for load balancing."""
        now = datetime.now(timezone.utc)
        healthy = []
        for node in self._nodes.values():
            if node["status"] not in (NodeStatus.ACTIVE.value, NodeStatus.LEADER.value):
                continue
            last_hb = datetime.fromisoformat(node["last_heartbeat"])
            if (now - last_hb).total_seconds() > self._load_balancer_config["health_check_interval"] * 3:
                continue
            healthy.append(node)
        return healthy

    # =========================================================================
    #  Graceful Shutdown
    # =========================================================================

    def prepare_shutdown(self, node_id: str) -> dict:
        """Prepare a node for graceful shutdown."""
        node = self._nodes.get(node_id)
        if not node:
            return {"error": "Node not found"}

        node["status"] = NodeStatus.DRAINING.value
        node["drain_started_at"] = datetime.now(timezone.utc).isoformat()

        # If leader, trigger re-election
        if node_id == self._current_leader:
            self._elect_leader()

        return {
            "node_id": node_id,
            "status": NodeStatus.DRAINING.value,
            "active_connections": node["active_connections"],
            "drain_started_at": node["drain_started_at"],
            "message": "Node is draining connections before shutdown",
        }

    def complete_shutdown(self, node_id: str) -> dict:
        """Complete node shutdown."""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            node["status"] = NodeStatus.DOWN.value
            node["shutdown_at"] = datetime.now(timezone.utc).isoformat()
            return {
                "node_id": node_id,
                "status": NodeStatus.DOWN.value,
                "message": "Node shutdown complete",
            }
        return {"error": "Node not found"}

    # =========================================================================
    #  Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """Get HA statistics."""
        nodes = self._nodes.values()
        return {
            "total_nodes": len(nodes),
            "active_nodes": len([n for n in nodes if n["status"] == NodeStatus.ACTIVE.value]),
            "standby_nodes": len([n for n in nodes if n["status"] == NodeStatus.STANDBY.value]),
            "draining_nodes": len([n for n in nodes if n["status"] == NodeStatus.DRAINING.value]),
            "down_nodes": len([n for n in nodes if n["status"] == NodeStatus.DOWN.value]),
            "current_leader": self._current_leader,
            "leader_term": self._leader_term,
            "failover_count": len(self._failover_history),
            "load_balancer": self._load_balancer_config["algorithm"],
            "session_sharing": self._load_balancer_config["session_sticky"],
        }


# Singleton
ha_service = HAService()
