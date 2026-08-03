"""
business_rules_engine.py — Enterprise Configurable Business Rules Engine
VisionCore 3.0 Enterprise Platform Services Layer

Provides:
- Rule definition DSL: IF <conditions> THEN <actions>
- Condition types: equals, not_equals, greater_than, less_than, contains, in_set, between, regex
- Action types: set_field, reject, approve, send_notification, trigger_event, flag_for_review
- Priority-based rule ordering (highest priority evaluated first)
- Simulation mode (evaluate rules without executing actions)
- Rule versioning & effective dates
- Named rule sets (groupings for domain areas)
- Full audit trail per rule evaluation
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Rule DSL Types
# ---------------------------------------------------------------------------

class ConditionOperator(Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN_SET = "in_set"
    NOT_IN_SET = "not_in_set"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    REGEX_MATCH = "regex_match"


class ActionType(Enum):
    SET_FIELD = "set_field"
    REJECT = "reject"
    APPROVE = "approve"
    SEND_NOTIFICATION = "send_notification"
    TRIGGER_EVENT = "trigger_event"
    FLAG_FOR_REVIEW = "flag_for_review"
    CALCULATE = "calculate"
    LOG = "log"


@dataclass
class Condition:
    field: str
    operator: ConditionOperator
    value: Any
    value_high: Optional[Any] = None  # Used for BETWEEN operator


@dataclass
class Action:
    action_type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BusinessRule:
    id: str
    name: str
    description: str
    rule_set: str                           # Domain grouping e.g. 'leave', 'payroll', 'attendance'
    conditions: List[Condition]             # ALL conditions must match (AND logic)
    actions: List[Action]
    priority: int = 50                      # Higher number = evaluated first
    is_active: bool = True
    version: int = 1
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    organization_id: Optional[str] = None  # None = global rule
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RuleEvaluationResult:
    rule_id: str
    rule_name: str
    matched: bool
    actions_executed: List[str] = field(default_factory=list)
    context_after: Dict[str, Any] = field(default_factory=dict)
    simulation: bool = False


@dataclass
class RuleSetEvaluationReport:
    rule_set: str
    total_rules: int
    matched_rules: int
    results: List[RuleEvaluationResult]
    final_context: Dict[str, Any]
    simulation: bool = False
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BusinessRulesEngine:
    """
    Configurable Business Rules Engine.
    Evaluates condition-action rules across platform domains with priority ordering and simulation mode.
    """

    def __init__(self):
        self._rules: Dict[str, BusinessRule] = {}
        self._action_handlers: Dict[ActionType, Callable[[Action, Dict[str, Any]], None]] = {}
        self._register_default_action_handlers()
        self._register_platform_rules()

    # ------------------------------------------------------------------
    #  Rule Management
    # ------------------------------------------------------------------

    def register_rule(self, rule: BusinessRule) -> BusinessRule:
        """Register or update a business rule."""
        self._rules[rule.id] = rule
        logger.info(f"Rule '{rule.name}' (ID={rule.id}) registered in rule set '{rule.rule_set}' [Priority={rule.priority}]")
        return rule

    def create_rule(
        self,
        name: str,
        description: str,
        rule_set: str,
        conditions: List[Condition],
        actions: List[Action],
        priority: int = 50,
        organization_id: Optional[str] = None,
        effective_from: Optional[str] = None,
        effective_until: Optional[str] = None,
    ) -> BusinessRule:
        """Create and register a new business rule."""
        rule = BusinessRule(
            id=f"rule-{uuid.uuid4().hex[:12]}",
            name=name,
            description=description,
            rule_set=rule_set,
            conditions=conditions,
            actions=actions,
            priority=priority,
            organization_id=organization_id,
            effective_from=effective_from,
            effective_until=effective_until,
        )
        return self.register_rule(rule)

    def deactivate_rule(self, rule_id: str) -> bool:
        """Deactivate a rule without deleting it."""
        if rule_id in self._rules:
            self._rules[rule_id].is_active = False
            return True
        return False

    def get_rules_for_set(self, rule_set: str, organization_id: Optional[str] = None) -> List[BusinessRule]:
        """Get all active rules for a rule set, sorted by priority desc."""
        rules = [
            r for r in self._rules.values()
            if r.rule_set == rule_set
            and r.is_active
            and (r.organization_id is None or r.organization_id == organization_id)
        ]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    # ------------------------------------------------------------------
    #  Rule Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        rule_set: str,
        context: Dict[str, Any],
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
        simulation: bool = False,
    ) -> RuleSetEvaluationReport:
        """Evaluate all rules for a rule set against the given context."""
        rules = self.get_rules_for_set(rule_set, organization_id)
        effective_context = dict(context)
        results: List[RuleEvaluationResult] = []
        matched = 0

        for rule in rules:
            result = self._evaluate_single_rule(rule, effective_context, simulation)
            if result.matched:
                matched += 1
                effective_context = result.context_after
            results.append(result)

        report = RuleSetEvaluationReport(
            rule_set=rule_set,
            total_rules=len(rules),
            matched_rules=matched,
            results=results,
            final_context=effective_context,
            simulation=simulation,
        )

        # Audit
        if not simulation:
            try:
                audit_service.record(
                    actor_user_id=user_id,
                    organization_id=organization_id or "",
                    module="rules_engine",
                    action="evaluate_rule_set",
                    entity_type="rule_evaluation",
                    entity_id=rule_set,
                    summary=f"Rule set '{rule_set}' evaluated: {matched}/{len(rules)} rules matched",
                    details={"rule_set": rule_set, "matched": matched, "total": len(rules)},
                )
            except Exception:
                pass

        return report

    def simulate(
        self,
        rule_set: str,
        context: Dict[str, Any],
        organization_id: Optional[str] = None,
    ) -> RuleSetEvaluationReport:
        """Simulation mode: evaluate without executing side-effect actions."""
        return self.evaluate(rule_set, context, organization_id, simulation=True)

    # ------------------------------------------------------------------
    #  Private: Single Rule Evaluation
    # ------------------------------------------------------------------

    def _evaluate_single_rule(
        self,
        rule: BusinessRule,
        context: Dict[str, Any],
        simulation: bool,
    ) -> RuleEvaluationResult:
        # Check effective dates
        now_str = datetime.now(timezone.utc).isoformat()
        if rule.effective_from and now_str < rule.effective_from:
            return RuleEvaluationResult(rule_id=rule.id, rule_name=rule.name, matched=False, simulation=simulation)
        if rule.effective_until and now_str > rule.effective_until:
            return RuleEvaluationResult(rule_id=rule.id, rule_name=rule.name, matched=False, simulation=simulation)

        # Evaluate all conditions (AND logic)
        for condition in rule.conditions:
            if not self._check_condition(condition, context):
                return RuleEvaluationResult(rule_id=rule.id, rule_name=rule.name, matched=False, simulation=simulation)

        # All conditions matched — execute actions
        actions_executed: List[str] = []
        updated_context = dict(context)

        if not simulation:
            for action in rule.actions:
                try:
                    handler = self._action_handlers.get(action.action_type)
                    if handler:
                        handler(action, updated_context)
                    actions_executed.append(action.action_type.value)
                except Exception as e:
                    logger.error(f"Rule action '{action.action_type.value}' failed for rule '{rule.name}': {e}")
        else:
            actions_executed = [a.action_type.value for a in rule.actions]

        return RuleEvaluationResult(
            rule_id=rule.id, rule_name=rule.name, matched=True,
            actions_executed=actions_executed, context_after=updated_context,
            simulation=simulation
        )

    def _check_condition(self, condition: Condition, context: Dict[str, Any]) -> bool:
        """Evaluate a single condition against the context."""
        value = context.get(condition.field)
        op = condition.operator
        target = condition.value

        try:
            if op == ConditionOperator.EQUALS:
                return value == target
            elif op == ConditionOperator.NOT_EQUALS:
                return value != target
            elif op == ConditionOperator.GREATER_THAN:
                return float(value) > float(target)
            elif op == ConditionOperator.LESS_THAN:
                return float(value) < float(target)
            elif op == ConditionOperator.GREATER_THAN_OR_EQUAL:
                return float(value) >= float(target)
            elif op == ConditionOperator.LESS_THAN_OR_EQUAL:
                return float(value) <= float(target)
            elif op == ConditionOperator.CONTAINS:
                return str(target).lower() in str(value).lower()
            elif op == ConditionOperator.NOT_CONTAINS:
                return str(target).lower() not in str(value).lower()
            elif op == ConditionOperator.IN_SET:
                return value in (target if isinstance(target, (list, set, tuple)) else [target])
            elif op == ConditionOperator.NOT_IN_SET:
                return value not in (target if isinstance(target, (list, set, tuple)) else [target])
            elif op == ConditionOperator.BETWEEN:
                return float(target) <= float(value) <= float(condition.value_high)
            elif op == ConditionOperator.IS_NULL:
                return value is None or value == ""
            elif op == ConditionOperator.IS_NOT_NULL:
                return value is not None and value != ""
            elif op == ConditionOperator.REGEX_MATCH:
                return bool(re.match(str(target), str(value)))
        except (TypeError, ValueError):
            return False
        return False

    # ------------------------------------------------------------------
    #  Action Handlers
    # ------------------------------------------------------------------

    def _register_default_action_handlers(self) -> None:
        def set_field_handler(action: Action, context: Dict[str, Any]) -> None:
            field_name = action.params.get("field")
            field_value = action.params.get("value")
            if field_name:
                context[field_name] = field_value
                logger.debug(f"Rule Action SET_FIELD: {field_name} = {field_value}")

        def reject_handler(action: Action, context: Dict[str, Any]) -> None:
            reason = action.params.get("reason", "Rule-based rejection")
            context["__status__"] = "rejected"
            context["__rejection_reason__"] = reason
            logger.debug(f"Rule Action REJECT: {reason}")

        def approve_handler(action: Action, context: Dict[str, Any]) -> None:
            context["__status__"] = "approved"
            logger.debug("Rule Action APPROVE")

        def flag_handler(action: Action, context: Dict[str, Any]) -> None:
            context["__flagged__"] = True
            context["__flag_reason__"] = action.params.get("reason", "Flagged for review")
            logger.debug("Rule Action FLAG_FOR_REVIEW")

        def log_handler(action: Action, context: Dict[str, Any]) -> None:
            logger.info(f"Rule Engine LOG: {action.params.get('message', 'Rule matched')}")

        self._action_handlers[ActionType.SET_FIELD] = set_field_handler
        self._action_handlers[ActionType.REJECT] = reject_handler
        self._action_handlers[ActionType.APPROVE] = approve_handler
        self._action_handlers[ActionType.FLAG_FOR_REVIEW] = flag_handler
        self._action_handlers[ActionType.LOG] = log_handler

    def _register_platform_rules(self) -> None:
        """Seed canonical platform-level default business rules."""
        # Leave: Reject same-day leave requests if balance < 1
        self.create_rule(
            name="Reject Same-Day Leave Request With Zero Balance",
            description="Automatically reject a same-day leave request if leave balance is zero.",
            rule_set="leave",
            conditions=[
                Condition(field="days_requested", operator=ConditionOperator.EQUALS, value=0),
                Condition(field="leave_balance", operator=ConditionOperator.LESS_THAN, value=1),
            ],
            actions=[Action(ActionType.REJECT, params={"reason": "Insufficient leave balance for same-day request"})],
            priority=90,
        )
        # Payroll: Flag large adjustment for review
        self.create_rule(
            name="Flag Payroll Adjustment Over 50%",
            description="Flag any payroll adjustment exceeding 50% of base salary for supervisor review.",
            rule_set="payroll",
            conditions=[
                Condition(field="adjustment_percentage", operator=ConditionOperator.GREATER_THAN, value=50.0),
            ],
            actions=[Action(ActionType.FLAG_FOR_REVIEW, params={"reason": "Payroll adjustment exceeds 50% threshold"})],
            priority=80,
        )
        # Attendance: Auto-approve remote check-in for verified devices
        self.create_rule(
            name="Auto-Approve Remote Check-In For Trusted Devices",
            description="Automatically approve attendance for check-ins from pre-verified trusted devices.",
            rule_set="attendance",
            conditions=[
                Condition(field="device_trust_level", operator=ConditionOperator.EQUALS, value="trusted"),
                Condition(field="liveness_verified", operator=ConditionOperator.EQUALS, value=True),
            ],
            actions=[Action(ActionType.APPROVE)],
            priority=75,
        )


# Singleton
business_rules_engine = BusinessRulesEngine()
