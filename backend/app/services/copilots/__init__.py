"""
copilots/__init__.py — Domain Copilot Package
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

All domain copilots implement the BaseCopilot interface:
- HRCopilot
- RecruitmentCopilot
- PolicyCopilot
- PerformanceCopilot
- AssetCopilot
- OperationsCopilot
- ExecutiveCopilot
"""
from app.services.copilots.hr_copilot import HRCopilot
from app.services.copilots.recruitment_copilot import RecruitmentCopilot
from app.services.copilots.policy_copilot import PolicyCopilot
from app.services.copilots.performance_copilot import PerformanceCopilot
from app.services.copilots.asset_copilot import AssetCopilot
from app.services.copilots.operations_copilot import OperationsCopilot
from app.services.copilots.executive_copilot import ExecutiveCopilot

__all__ = [
    "HRCopilot",
    "RecruitmentCopilot",
    "PolicyCopilot",
    "PerformanceCopilot",
    "AssetCopilot",
    "OperationsCopilot",
    "ExecutiveCopilot",
]
