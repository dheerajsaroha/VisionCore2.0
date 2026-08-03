"""
goal_scoring_engine.py — Goal Scoring & OKR Engine Service
Sprint 4 — Entity 1: Performance Management System
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.all_models import Goal, GoalProgress, User


class GoalScoringEngine:
    """Enterprise goal scoring with OKR framework, cascade tracking,
    stretch goal recognition, and progress analytics."""

    @staticmethod
    def compute_goal_score(completion_pct: float) -> float:
        """
        Convert goal completion percentage to a 1.0-5.0 score.
        - 0-20% → 1.0-2.0
        - 21-50% → 2.0-3.0
        - 51-80% → 3.0-4.0
        - 81-100%+ → 4.0-5.0
        """
        pct = min(150.0, max(0.0, completion_pct))
        if pct <= 20:
            return round(1.0 + (pct / 20.0) * 1.0, 2)
        elif pct <= 50:
            return round(2.0 + ((pct - 20) / 30.0) * 1.0, 2)
        elif pct <= 80:
            return round(3.0 + ((pct - 50) / 30.0) * 1.0, 2)
        else:
            score = 4.0 + min(1.0, (pct - 80) / 20.0)
            return round(min(5.0, score), 2)

    @staticmethod
    def calculate_user_goal_score(db: Session, user_id: int, org_id: UUID,
                                   cycle_id: Optional[int] = None) -> Optional[float]:
        """Calculate average goal score for a user across all goals or a specific cycle."""
        q = db.query(Goal).filter(Goal.organization_id == org_id, Goal.user_id == user_id)
        if cycle_id:
            q = q.filter(Goal.cycle_id == cycle_id)

        goals = q.all()
        if not goals:
            return None

        scores = [GoalScoringEngine.compute_goal_score(float(g.completion_pct)) for g in goals]
        return round(sum(scores) / len(scores), 2)

    @staticmethod
    def get_goal_cascade_tree(db: Session, org_id: UUID, root_goal_id: int) -> Dict[str, Any]:
        """Build a cascade tree of goals (parent → children)."""
        root = db.query(Goal).filter(Goal.id == root_goal_id, Goal.organization_id == org_id).first()
        if not root:
            return {}

        children = db.query(Goal).filter(
            Goal.organization_id == org_id,
            Goal.parent_goal_id == root_goal_id
        ).all()

        child_trees = []
        for child in children:
            child_trees.append(GoalScoringEngine.get_goal_cascade_tree(db, org_id, child.id))

        return {
            "id": root.id,
            "title": root.title,
            "goal_type": root.goal_type,
            "goal_framework": root.goal_framework,
            "completion_pct": float(root.completion_pct),
            "status": root.status,
            "user_id": root.user_id,
            "children": child_trees
        }

    @staticmethod
    def get_org_goal_summary(db: Session, org_id: UUID,
                              cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Aggregate goal statistics across the organization."""
        q = db.query(Goal).filter(Goal.organization_id == org_id)
        if cycle_id:
            q = q.filter(Goal.cycle_id == cycle_id)

        goals = q.all()
        if not goals:
            return {"total_goals": 0, "avg_completion": 0.0, "completed": 0, "active": 0}

        completed = sum(1 for g in goals if g.status == "completed")
        active = sum(1 for g in goals if g.status == "active")
        avg_pct = round(sum(float(g.completion_pct) for g in goals) / len(goals), 1)

        return {
            "total_goals": len(goals),
            "avg_completion": avg_pct,
            "completed": completed,
            "active": active,
            "okr_count": sum(1 for g in goals if g.goal_framework == "okr"),
            "smart_count": sum(1 for g in goals if g.goal_framework == "smart"),
            "stretch_count": sum(1 for g in goals if g.goal_framework == "stretch")
        }

    @staticmethod
    def get_stretch_goal_candidates(db: Session, org_id: UUID) -> List[Dict[str, Any]]:
        """Identify goals that exceed target (stretch performance)."""
        goals = db.query(Goal).filter(
            Goal.organization_id == org_id,
            Goal.completion_pct >= 100.0,
            Goal.status == "completed"
        ).all()

        return [{
            "id": g.id,
            "title": g.title,
            "completion_pct": float(g.completion_pct),
            "goal_framework": g.goal_framework,
            "user_id": g.user_id
        } for g in goals]


goal_scoring_engine = GoalScoringEngine()

