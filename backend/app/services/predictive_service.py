"""
predictive_service.py — Enterprise Predictive Intelligence Engine
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Central predictive intelligence service:
- Model registry and lifecycle management
- Prediction execution with explanation
- Confidence scoring
- Model training triggers
- Scheduled predictions
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from app.schema.ai import (
    ForecastResult,
    PredictiveModelType,
    PredictionResult,
)
from app.services.predictive_models import (
    AttritionModel,
    LeaveForecastModel,
    AttendanceAnomalyModel,
    PayrollAnomalyModel,
    PerformanceTrendModel,
    PromotionReadinessModel,
    AssetFailureModel,
    CapacityForecastModel,
)
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class PredictiveService:
    """
    Enterprise predictive intelligence service.

    Manages:
    - Model registry for all predictive models
    - Prediction execution with confidence scoring
    - Forecast generation for time-series models
    - Model statistics and training data tracking
    - Scheduled prediction jobs
    """

    def __init__(self):
        self._models: dict[PredictiveModelType, Any] = {
            PredictiveModelType.ATTRITION: AttritionModel(),
            PredictiveModelType.LEAVE_FORECAST: LeaveForecastModel(),
            PredictiveModelType.ATTENDANCE_ANOMALY: AttendanceAnomalyModel(),
            PredictiveModelType.PAYROLL_ANOMALY: PayrollAnomalyModel(),
            PredictiveModelType.PERFORMANCE_TREND: PerformanceTrendModel(),
            PredictiveModelType.PROMOTION_READINESS: PromotionReadinessModel(),
            PredictiveModelType.ASSET_FAILURE: AssetFailureModel(),
            PredictiveModelType.CAPACITY_FORECAST: CapacityForecastModel(),
        }

    def get_models(self) -> list[dict]:
        """Get all registered predictive models."""
        return [
            {
                "type": mt.value,
                "name": model.name,
                "supports_forecast": hasattr(model, "forecast") and callable(getattr(model, "forecast")),
            }
            for mt, model in self._models.items()
        ]

    def get_model(self, model_type: PredictiveModelType) -> Any:
        """Get a predictive model by type."""
        model = self._models.get(model_type)
        if not model:
            raise ValueError(f"Unknown model type: {model_type}")
        return model

    async def predict(
        self,
        model_type: PredictiveModelType,
        params: dict[str, Any],
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> PredictionResult:
        """
        Execute a prediction using the specified model.

        Args:
            model_type: Type of predictive model to use
            params: Input parameters for prediction
            organization_id: Tenant ID
            user_id: User ID

        Returns:
            PredictionResult with prediction, confidence, and explanation
        """
        model = self.get_model(model_type)
        logger.info(f"Running prediction: {model.name} ({model_type.value})")

        result = await model.predict(params)

        # Audit
        audit_service.record(
            module="ai",
            action="prediction",
            entity_type="prediction",
            entity_id=result.id,
            summary=f"Prediction: {model_type.value}",
            details={
                "model_type": model_type.value,
                "model_name": model.name,
                "confidence": result.confidence_score,
                "features": result.features_used,
            },
            organization_id=organization_id or "",
            actor_user_id=user_id,
        )

        return result

    async def forecast(
        self,
        model_type: PredictiveModelType,
        params: dict[str, Any],
        days_ahead: int = 30,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> ForecastResult:
        """
        Generate a forecast using a time-series model.

        Args:
            model_type: Type of predictive model
            params: Input parameters
            days_ahead: Number of days/months to forecast
            organization_id: Tenant ID
            user_id: User ID

        Returns:
            ForecastResult with time-series data points
        """
        model = self.get_model(model_type)
        if not hasattr(model, "forecast"):
            raise ValueError(f"Model {model.name} does not support forecasting")

        logger.info(f"Generating forecast: {model.name} ({days_ahead} steps)")
        try:
            result = await model.forecast(params, days_ahead)
        except NotImplementedError as exc:
            # The base class defines forecast() but raises NotImplementedError,
            # so the hasattr guard above can never fire and this escaped to the
            # router's generic handler as a 500. "This model cannot forecast" is
            # a bad-request condition, not a server fault.
            raise ValueError(f"Model {model.name} does not support forecasting") from exc

        # Audit
        audit_service.record(
            module="ai",
            action="forecast",
            entity_type="forecast",
            entity_id=result.id,
            summary=f"Forecast: {model_type.value} ({days_ahead} periods)",
            details={
                "model_type": model_type.value,
                "model_name": model.name,
                "periods": days_ahead,
                "data_points": len(result.forecast),
            },
            organization_id=organization_id or "",
            actor_user_id=user_id,
        )

        return result

    def get_stats(self) -> dict:
        """Get predictive service statistics."""
        return {
            "total_models": len(self._models),
            "model_types": [mt.value for mt in self._models.keys()],
            "models": [
                {
                    "name": model.name,
                    "type": mt.value,
                    "supports_forecast": hasattr(model, "forecast") and callable(getattr(model, "forecast")),
                }
                for mt, model in self._models.items()
            ],
        }


# Singleton
predictive_service = PredictiveService()

