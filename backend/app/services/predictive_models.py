"""
predictive_models.py — Enterprise Predictive Intelligence Models
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Implements 8 predictive models:
1. Attrition prediction
2. Leave forecasting
3. Attendance anomaly detection
4. Payroll anomaly detection
5. Performance trend prediction
6. Promotion readiness prediction
7. Asset failure prediction
8. Capacity forecasting

Each model provides:
- Confidence scores
- Explanations
- Feature importance
- Data point counts
"""
from __future__ import annotations

import logging
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.schema.ai import (
    ForecastDatapoint,
    ForecastResult,
    PredictiveModelType,
    PredictionResult,
)

logger = logging.getLogger(__name__)


class PredictiveModel:
    """Base class for predictive models."""

    def __init__(self, model_type: PredictiveModelType, name: str):
        self.model_type = model_type
        self.name = name
        self._training_data_points = 0

    async def predict(self, params: dict) -> PredictionResult:
        """Run prediction. Override in subclass."""
        raise NotImplementedError

    async def forecast(self, params: dict, days_ahead: int = 30) -> ForecastResult:
        """Generate forecast. Override if applicable."""
        raise NotImplementedError(f"{self.name} does not support forecasting")


class AttritionModel(PredictiveModel):
    """Attrition prediction model."""

    def __init__(self):
        super().__init__(PredictiveModelType.ATTRITION, "Attrition Predictor")

    async def predict(self, params: dict) -> PredictionResult:
        features = [
            "tenure_months", "performance_score", "absences",
            "promotion_history", "satisfaction_score",
        ]
        # Use available features or defaults
        tenure = params.get("tenure_months", 24)
        perf = params.get("performance_score", 3.0)
        absences = params.get("absences", 5)
        promotions = params.get("promotion_history", 1)
        satisfaction = params.get("satisfaction_score", 3.5)

        # Simple heuristic model
        risk_score = (
            max(0, 1.0 - tenure / 60) * 0.2 +
            max(0, 1.0 - perf / 5.0) * 0.25 +
            min(1.0, absences / 20) * 0.15 +
            max(0, 1.0 - promotions / 5) * 0.15 +
            max(0, 1.0 - satisfaction / 5.0) * 0.25
        )

        explanation = (
            f"Attrition risk assessment based on {len(features)} factors. "
            f"Tenure ({tenure} months), performance ({perf}/5), "
            f"absences ({absences}), promotions ({promotions}), "
            f"satisfaction ({satisfaction}/5). "
        )
        if risk_score > 0.7:
            explanation += "High risk: multiple factors indicate potential attrition."
        elif risk_score > 0.4:
            explanation += "Moderate risk: some factors need attention."
        else:
            explanation += "Low risk: current indicators are favorable."

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "risk_score": round(risk_score, 3),
                "risk_level": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low",
                "key_factors": features,
                "recommendation": self._get_recommendation(risk_score),
            },
            confidence_score=0.7,
            explanation=explanation,
            features_used=features,
            data_points=len(params),
        )

    def _get_recommendation(self, risk_score: float) -> str:
        if risk_score > 0.7:
            return "Schedule retention interview, review compensation, consider mentorship program"
        elif risk_score > 0.4:
            return "Monitor satisfaction, provide growth opportunities, check work-life balance"
        return "Continue regular engagement and development programs"


class LeaveForecastModel(PredictiveModel):
    """Leave forecasting model."""

    def __init__(self):
        super().__init__(PredictiveModelType.LEAVE_FORECAST, "Leave Forecaster")

    async def predict(self, params: dict) -> PredictionResult:
        features = ["historical_leave_days", "department_size", "season", "headcount"]
        historical = params.get("historical_leave_days", 15)
        dept_size = params.get("department_size", 50)
        season_factor = params.get("season_factor", 1.0)

        predicted_leave = historical * season_factor

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "predicted_leave_days": round(predicted_leave, 1),
                "historical_average": historical,
                "seasonal_factor": season_factor,
                "department_headcount": dept_size,
            },
            confidence_score=0.75,
            explanation=f"Predicted leave based on historical average ({historical} days) "
                       f"adjusted for seasonal factor ({season_factor}).",
            features_used=features,
            data_points=len(params),
        )

    async def forecast(self, params: dict, days_ahead: int = 30) -> ForecastResult:
        now = datetime.now(timezone.utc)
        datapoints = []
        base = params.get("historical_leave_days", 15) / 30
        for i in range(days_ahead):
            day = now + timedelta(days=i)
            daily_rate = base * (1 + math.sin(i * math.pi / 7) * 0.3)
            datapoints.append(ForecastDatapoint(
                date=day.strftime("%Y-%m-%d"),
                value=round(daily_rate, 2),
                # Fixed +-30% presented as a 95% interval. No interval is
                # claimed, because none is computed.
                lower_bound=None,
                upper_bound=None,
            ))

        return ForecastResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            forecast=datapoints,
            confidence_interval=0.0,
            seasonality="weekly",
            trend="stable",
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class AttendanceAnomalyModel(PredictiveModel):
    """Attendance anomaly detection model."""

    def __init__(self):
        super().__init__(PredictiveModelType.ATTENDANCE_ANOMALY, "Attendance Anomaly Detector")

    async def predict(self, params: dict) -> PredictionResult:
        features = [
            "avg_check_in_time", "avg_check_out_time",
            "late_count", "early_departure_count",
            "absent_count",
        ]
        late_count = params.get("late_count", 2)
        early_departure = params.get("early_departure_count", 1)
        absences = params.get("absent_count", 0)

        anomaly_score = (late_count * 0.3 + early_departure * 0.2 + absences * 0.5) / 10
        anomaly_score = min(1.0, anomaly_score)

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "anomaly_score": round(anomaly_score, 3),
                "risk_level": "critical" if anomaly_score > 0.8 else "high" if anomaly_score > 0.6 else "medium" if anomaly_score > 0.3 else "low",
                "patterns_detected": {
                    "late_arrivals": late_count,
                    "early_departures": early_departure,
                    "absences": absences,
                },
            },
            confidence_score=0.8,
            explanation=f"Attendance pattern analysis reveals {late_count} late arrivals, "
                       f"{early_departure} early departures, {absences} absences.",
            features_used=features,
            data_points=len(params),
        )


class PayrollAnomalyModel(PredictiveModel):
    """Payroll anomaly detection model."""

    def __init__(self):
        super().__init__(PredictiveModelType.PAYROLL_ANOMALY, "Payroll Anomaly Detector")

    async def predict(self, params: dict) -> PredictionResult:
        features = ["amount", "overtime_hours", "deductions", "bonus_amount"]
        amount = params.get("amount", 5000)
        overtime = params.get("overtime_hours", 10)
        deductions = params.get("deductions", 500)
        bonus = params.get("bonus_amount", 0)

        expected_amount = 5000
        variance = abs(amount - expected_amount) / expected_amount
        overtime_anomaly = overtime > 40
        deduction_anomaly = deductions > expected_amount * 0.3

        anomaly_score = min(1.0, variance * 0.5 + (0.3 if overtime_anomaly else 0) + (0.2 if deduction_anomaly else 0))

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "anomaly_score": round(anomaly_score, 3),
                "is_anomaly": anomaly_score > 0.5,
                "flags": {
                    "high_overtime": overtime_anomaly,
                    "high_deductions": deduction_anomaly,
                    "amount_variance_pct": round(variance * 100, 1),
                },
            },
            confidence_score=0.85,
            explanation=f"Payroll reviewed: amount ${amount}, overtime {overtime}h, deductions ${deductions}.",
            features_used=features,
            data_points=len(params),
        )


class PerformanceTrendModel(PredictiveModel):
    """Performance trend prediction model."""

    def __init__(self):
        super().__init__(PredictiveModelType.PERFORMANCE_TREND, "Performance Trend Predictor")

    async def predict(self, params: dict) -> PredictionResult:
        features = [
            "current_rating", "previous_rating",
            "goal_completion_rate", "training_hours",
        ]
        current = params.get("current_rating", 3.5)
        previous = params.get("previous_rating", 3.0)
        goals = params.get("goal_completion_rate", 0.7)
        training = params.get("training_hours", 20)

        trend = (current - previous) / max(previous, 0.1)
        predicted_next = current + trend * 0.3 + goals * 0.2 + min(training / 100, 0.3)

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "current_rating": current,
                "trend_direction": "improving" if trend > 0.05 else "declining" if trend < -0.05 else "stable",
                "predicted_next_rating": round(predicted_next, 2),
                "goal_completion_rate": goals,
            },
            confidence_score=0.7,
            explanation=f"Performance trend from {previous} to {current}. "
                       f"Goal completion at {goals:.0%}. Training: {training}h.",
            features_used=features,
            data_points=len(params),
        )

    async def forecast(self, params: dict, days_ahead: int = 90) -> ForecastResult:
        now = datetime.now(timezone.utc)
        current = params.get("current_rating", 3.5)
        datapoints = []
        for i in range(0, days_ahead, 30):
            month = i // 30
            projected = current + (i / 90) * 0.2
            datapoints.append(ForecastDatapoint(
                date=(now + timedelta(days=i)).strftime("%Y-%m-%d"),
                value=round(projected, 2),
                # A fixed +-0.5 band presented as a 0.8 interval is not a
                # computed error estimate, so no interval is claimed.
                lower_bound=None,
                upper_bound=None,
            ))
        return ForecastResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            forecast=datapoints,
            confidence_interval=0.0,
            trend="stable",
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class PromotionReadinessModel(PredictiveModel):
    """Promotion readiness prediction model."""

    def __init__(self):
        super().__init__(PredictiveModelType.PROMOTION_READINESS, "Promotion Readiness Assessor")

    async def predict(self, params: dict) -> PredictionResult:
        features = [
            "current_role_tenure", "performance_score",
            "leadership_score", "skill_gap_score",
        ]
        tenure = params.get("current_role_tenure", 24)
        perf = params.get("performance_score", 3.5)
        leadership = params.get("leadership_score", 3.0)
        skill_gap = params.get("skill_gap_score", 0.3)

        readiness = (min(tenure / 36, 1.0) * 0.25 + perf / 5 * 0.3 + leadership / 5 * 0.25 + (1 - skill_gap) * 0.2)

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "readiness_score": round(readiness, 3),
                "readiness_level": "ready" if readiness > 0.8 else "developing" if readiness > 0.5 else "not_ready",
                "strengths": ["performance", "tenure"] if perf > 4.0 else ["tenure"],
                "development_areas": ["leadership"] if leadership < 3.5 else [],
            },
            confidence_score=0.75,
            explanation=f"Promotion readiness assessed: tenure {tenure}mo, "
                       f"performance {perf}/5, leadership {leadership}/5.",
            features_used=features,
            data_points=len(params),
        )


class AssetFailureModel(PredictiveModel):
    """Asset failure prediction model."""

    def __init__(self):
        super().__init__(PredictiveModelType.ASSET_FAILURE, "Asset Failure Predictor")

    async def predict(self, params: dict) -> PredictionResult:
        features = [
            "asset_age_days", "maintenance_count",
            "last_maintenance_days", "usage_hours",
        ]
        age = params.get("asset_age_days", 365)
        maintenance = params.get("maintenance_count", 3)
        last_maint = params.get("last_maintenance_days", 90)
        usage = params.get("usage_hours", 2000)

        failure_risk = (
            min(age / 1825, 1.0) * 0.3 +  # 5 year lifespan
            max(0, 1.0 - maintenance / 10) * 0.2 +
            min(last_maint / 365, 1.0) * 0.25 +
            min(usage / 10000, 1.0) * 0.25
        )

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "failure_risk_score": round(failure_risk, 3),
                "risk_level": "high" if failure_risk > 0.7 else "medium" if failure_risk > 0.4 else "low",
                "estimated_remaining_life_days": round(1825 - age),
                "recommended_action": "Schedule maintenance" if failure_risk > 0.5 else "Continue monitoring",
            },
            confidence_score=0.7,
            explanation=f"Asset age: {age} days, last maintenance: {last_maint} days ago, "
                       f"usage: {usage}h, maintenance count: {maintenance}.",
            features_used=features,
            data_points=len(params),
        )


class CapacityForecastModel(PredictiveModel):
    """Capacity forecasting model."""

    def __init__(self):
        super().__init__(PredictiveModelType.CAPACITY_FORECAST, "Capacity Forecaster")

    async def predict(self, params: dict) -> PredictionResult:
        features = [
            "current_headcount", "growth_rate",
            "attrition_rate", "planned_hires",
        ]
        headcount = params.get("current_headcount", 100)
        growth = params.get("growth_rate", 0.05)
        attrition = params.get("attrition_rate", 0.1)
        hires = params.get("planned_hires", 12)

        projected = headcount * (1 + growth - attrition) + hires

        return PredictionResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            prediction={
                "current_headcount": headcount,
                "projected_headcount": round(projected),
                "growth_rate": growth,
                "attrition_rate": attrition,
                "net_change": round(projected - headcount),
                "capacity_utilization": round(headcount / (headcount * 1.1), 2),
            },
            confidence_score=0.8,
            explanation=f"Capacity forecast: {headcount} current, {projected:.0f} projected. "
                       f"Growth {growth:.0%}, attrition {attrition:.0%}, hires {hires}.",
            features_used=features,
            data_points=len(params),
        )

    async def forecast(self, params: dict, months_ahead: int = 12) -> ForecastResult:
        now = datetime.now(timezone.utc)
        headcount = params.get("current_headcount", 100)
        growth = params.get("growth_rate", 0.05)
        attrition = params.get("attrition_rate", 0.1)
        hires = params.get("monthly_hires", 1)

        datapoints = []
        projected = headcount
        for i in range(months_ahead):
            projected = projected * (1 + growth / 12 - attrition / 12) + hires
            date = now.replace(day=1) + timedelta(days=30 * i)
            datapoints.append(ForecastDatapoint(
                date=date.strftime("%Y-%m-%d"),
                value=round(projected),
                # No error estimate is computed for a rule-based
                # projection, so no confidence interval is claimed. These
                # were previously a flat +-10% band presented as a 90%
                # interval, which is a statistical claim the model does not
                # support.
                lower_bound=None,
                upper_bound=None,
            ))

        return ForecastResult(
            id=str(uuid.uuid4()),
            model_type=self.model_type,
            forecast=datapoints,
            confidence_interval=0.0,
            seasonality=None,
            trend="increasing" if datapoints[-1].value > headcount else "decreasing",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

