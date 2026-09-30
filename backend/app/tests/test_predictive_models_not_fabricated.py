"""
Regression tests for the AI predictive models.

These models are rule-based heuristics, but they were dressed up as trained
models: every `predict()` reported a fabricated training-set size
(`data_points=500` ... `5000`), a `confidence_score` of `constant + random
jitter` that changed on every identical call, and `forecast()` returned a
`±10%` band advertised as a 90% confidence interval.

They also crashed: `ForecastResult.created_at` is a required field that no
`forecast()` supplied, so every forecast raised a pydantic ValidationError and
the endpoint returned 500.
"""
from __future__ import annotations

import pytest

from app.schema.ai import PredictiveModelType
from app.services.predictive_service import predictive_service


def _model(name: str):
    return predictive_service.get_model(name)


class TestPredictionsAreDeterministic:
    @pytest.mark.parametrize("model_type", list(PredictiveModelType))
    def test_identical_inputs_give_identical_output(self, model_type):
        """`constant + random.uniform(...)` made confidence vary per call."""
        import asyncio

        model = _model(model_type.value)
        first = asyncio.run(model.predict({"current_headcount": 120}))
        second = asyncio.run(model.predict({"current_headcount": 120}))
        assert first.confidence_score == second.confidence_score, (
            f"{model_type.value} confidence is not deterministic: "
            f"{first.confidence_score} vs {second.confidence_score}"
        )
        assert first.prediction == second.prediction

    @pytest.mark.parametrize("model_type", list(PredictiveModelType))
    def test_data_points_counts_supplied_inputs_not_a_training_set(self, model_type):
        """The old code hardcoded `data_points=1000` and similar."""
        import asyncio

        model = _model(model_type.value)
        assert asyncio.run(model.predict({})).data_points == 0
        three = asyncio.run(model.predict({"a": 1, "b": 2, "c": 3}))
        assert three.data_points == 3, (
            f"{model_type.value} reported data_points={three.data_points}; it "
            "must reflect the caller's inputs, not an invented training set"
        )


class TestForecastsDoNotFabricateIntervals:
    def test_confidence_interval_is_not_asserted_without_an_error_estimate(self):
        import asyncio

        for model_type in PredictiveModelType:
            model = _model(model_type.value)
            try:
                result = asyncio.run(model.forecast({}, 3))
            except NotImplementedError:
                continue
            assert result.confidence_interval == 0.0, (
                f"{model_type.value} claims a "
                f"{result.confidence_interval} confidence interval from a "
                "hardcoded band"
            )
            for point in result.forecast:
                assert point.lower_bound is None, (
                    f"{model_type.value} published a lower bound without "
                    "computing one"
                )
                assert point.upper_bound is None

    def test_forecast_includes_created_at(self):
        """Every forecast 500'd: `created_at` is required and was never set."""
        import asyncio

        for model_type in PredictiveModelType:
            model = _model(model_type.value)
            try:
                result = asyncio.run(model.forecast({}, 3))
            except NotImplementedError:
                continue
            assert result.created_at, f"{model_type.value} forecast has no created_at"

    def test_unsupported_forecast_is_a_client_error_not_a_server_fault(self):
        """The base class always defines forecast(), so the hasattr guard never
        fired and NotImplementedError surfaced as HTTP 500."""
        import asyncio

        unsupported = []
        for model_type in PredictiveModelType:
            model = _model(model_type.value)
            try:
                asyncio.run(model.forecast({}, 3))
            except NotImplementedError:
                unsupported.append(model_type)
        assert unsupported, "expected some models to not support forecasting"

        for model_type in unsupported:
            with pytest.raises(ValueError):
                asyncio.run(
                    predictive_service.forecast(
                        model_type=model_type, params={}, days_ahead=3
                    )
                )
