"""
Tests for wildfire_model.py – wildfire risk prediction model.
"""

import math
import pytest
import pandas as pd

from src.core.wildfire_model import WildfireModel
from src.config.settings import SettingsManager


@pytest.fixture
def model():
    """Create a WildfireModel with default parameters."""
    return WildfireModel()


# ------------------------------------------------------------------
# Single-point predictions
# ------------------------------------------------------------------

class TestPredict:
    """Validate the core predict() method."""

    def test_returns_required_keys(self, model):
        result = model.predict(25.0, 128, 15.0)
        assert "risk_score" in result
        assert "risk_category" in result
        assert "prediction" in result

    def test_score_clamped_low(self, model):
        """Very cold, dark, no wind → score should be clamped at 0."""
        result = model.predict(-40.0, 0, 0.0)
        assert result["risk_score"] >= 0

    def test_score_clamped_high(self, model):
        """Extreme values → score should be clamped at 100."""
        result = model.predict(80.0, 255, 100.0)
        assert result["risk_score"] <= 100

    def test_low_category(self, model):
        """Cold and dark → Low category."""
        result = model.predict(-5.0, 0, 0.0)
        assert result["risk_category"] == "Low"

    def test_extreme_category(self, model):
        """Hot, bright, windy → Extreme category."""
        result = model.predict(50.0, 255, 50.0)
        assert result["risk_category"] == "Extreme"

    def test_moderate_range(self, model):
        """Mid-range values should give Moderate."""
        result = model.predict(15.0, 80, 10.0)
        assert result["risk_category"] in ("Low", "Moderate")

    def test_prediction_string_contains_category(self, model):
        result = model.predict(35.0, 200, 30.0)
        assert result["risk_category"] in result["prediction"]

    def test_prediction_string_contains_score(self, model):
        result = model.predict(35.0, 200, 30.0)
        score_str = f"{result['risk_score']:.0f}/100"
        assert score_str in result["prediction"]


# ------------------------------------------------------------------
# Wind speed default handling
# ------------------------------------------------------------------

class TestWindDefault:
    """Wind should fall back to default_wind when None or NaN."""

    def test_none_wind_uses_default(self):
        m = WildfireModel(default_wind=20.0)
        r_none = m.predict(30.0, 150, None)
        r_explicit = m.predict(30.0, 150, 20.0)
        assert r_none["risk_score"] == r_explicit["risk_score"]

    def test_nan_wind_uses_default(self):
        m = WildfireModel(default_wind=20.0)
        r_nan = m.predict(30.0, 150, float("nan"))
        r_explicit = m.predict(30.0, 150, 20.0)
        assert r_nan["risk_score"] == r_explicit["risk_score"]


# ------------------------------------------------------------------
# Normalisation
# ------------------------------------------------------------------

class TestNormalise:
    """Validate the internal normalisation helper."""

    def test_min_value_normalises_to_zero(self):
        assert WildfireModel._normalise(0, 0, 100) == 0.0

    def test_max_value_normalises_to_one(self):
        assert WildfireModel._normalise(100, 0, 100) == 1.0

    def test_mid_value(self):
        assert abs(WildfireModel._normalise(50, 0, 100) - 0.5) < 1e-9

    def test_below_min_clamped_to_zero(self):
        assert WildfireModel._normalise(-10, 0, 100) == 0.0

    def test_above_max_clamped_to_one(self):
        assert WildfireModel._normalise(200, 0, 100) == 1.0

    def test_equal_bounds_returns_zero(self):
        assert WildfireModel._normalise(50, 50, 50) == 0.0


# ------------------------------------------------------------------
# Category thresholds
# ------------------------------------------------------------------

class TestCategories:
    """Verify score-to-category mapping boundaries."""

    def test_score_0_is_low(self, model):
        assert model._categorise(0) == "Low"

    def test_score_24_is_low(self, model):
        assert model._categorise(24.9) == "Low"

    def test_score_25_is_moderate(self, model):
        assert model._categorise(25) == "Moderate"

    def test_score_49_is_moderate(self, model):
        assert model._categorise(49.9) == "Moderate"

    def test_score_50_is_high(self, model):
        assert model._categorise(50) == "High"

    def test_score_74_is_high(self, model):
        assert model._categorise(74.9) == "High"

    def test_score_75_is_extreme(self, model):
        assert model._categorise(75) == "Extreme"

    def test_score_100_is_extreme(self, model):
        assert model._categorise(100) == "Extreme"


# ------------------------------------------------------------------
# DataFrame batch prediction
# ------------------------------------------------------------------

class TestPredictFromDataFrame:
    """Validate batch prediction on a pandas DataFrame."""

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "timestamp": pd.date_range("2026-03-10", periods=5, freq="2s"),
            "temperature": [20.0, 25.0, 35.0, 42.0, 50.0],
            "light": [50, 120, 180, 220, 255],
            "wind_speed": [5.0, 10.0, 20.0, 35.0, 50.0],
        })

    def test_output_has_model_columns(self, model, sample_df):
        result = model.predict_from_dataframe(sample_df)
        assert "model_score" in result.columns
        assert "model_category" in result.columns
        assert "model_prediction" in result.columns

    def test_output_preserves_original_columns(self, model, sample_df):
        result = model.predict_from_dataframe(sample_df)
        for col in sample_df.columns:
            assert col in result.columns

    def test_output_row_count_matches(self, model, sample_df):
        result = model.predict_from_dataframe(sample_df)
        assert len(result) == len(sample_df)

    def test_scores_increase_with_inputs(self, model, sample_df):
        """Scores should generally increase as inputs increase."""
        result = model.predict_from_dataframe(sample_df)
        scores = result["model_score"].tolist()
        # Not strictly monotonic due to rounding, but first < last
        assert scores[0] < scores[-1]

    def test_missing_wind_column_uses_default(self, model):
        """Old CSVs with no wind_speed column should still work."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-03-10", periods=3, freq="2s"),
            "temperature": [20.0, 30.0, 40.0],
            "light": [50, 150, 250],
        })
        result = model.predict_from_dataframe(df)
        assert len(result) == 3
        assert all(result["model_score"] >= 0)

    def test_nan_wind_values_use_default(self, model):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-03-10", periods=3, freq="2s"),
            "temperature": [30.0, 30.0, 30.0],
            "light": [150, 150, 150],
            "wind_speed": [float("nan"), float("nan"), float("nan")],
        })
        result = model.predict_from_dataframe(df)
        # All rows identical → all scores should match
        scores = result["model_score"].unique()
        assert len(scores) == 1


# ------------------------------------------------------------------
# What-if simulations
# ------------------------------------------------------------------

class TestWhatIf:
    """Validate what-if scenario adjustments."""

    @pytest.fixture
    def base_df(self):
        return pd.DataFrame({
            "timestamp": pd.date_range("2026-03-10", periods=5, freq="2s"),
            "temperature": [25.0] * 5,
            "light": [128] * 5,
            "wind_speed": [15.0] * 5,
        })

    def test_temp_increase_raises_score(self, model, base_df):
        baseline = model.predict_from_dataframe(base_df)
        hotter = model.what_if(base_df, temp_offset=10)
        assert hotter["model_score"].mean() > baseline["model_score"].mean()

    def test_light_increase_raises_score(self, model, base_df):
        baseline = model.predict_from_dataframe(base_df)
        brighter = model.what_if(base_df, light_offset=50)
        assert brighter["model_score"].mean() > baseline["model_score"].mean()

    def test_wind_increase_raises_score(self, model, base_df):
        baseline = model.predict_from_dataframe(base_df)
        windier = model.what_if(base_df, wind_offset=15)
        assert windier["model_score"].mean() > baseline["model_score"].mean()

    def test_zero_offsets_unchanged(self, model, base_df):
        baseline = model.predict_from_dataframe(base_df)
        same = model.what_if(base_df, temp_offset=0, light_offset=0, wind_offset=0)
        assert baseline["model_score"].tolist() == same["model_score"].tolist()


# ------------------------------------------------------------------
# Adaptive weight tuning
# ------------------------------------------------------------------

class TestAdaptWeights:
    """Validate the auto-adjusting model weights feature."""

    @pytest.fixture
    def settings(self):
        s = SettingsManager()
        s.reset_defaults()
        return s

    @pytest.fixture
    def adaptive_model(self, settings):
        return WildfireModel(settings_manager=settings)

    def test_get_weights_returns_defaults(self, adaptive_model):
        w = adaptive_model.get_weights()
        assert w == {"w_temp": 0.45, "w_light": 0.35, "w_wind": 0.2}

    def test_weights_read_from_settings(self, settings):
        settings.set("w_temp", 0.50)
        settings.set("w_light", 0.30)
        settings.set("w_wind", 0.20)
        m = WildfireModel(settings_manager=settings)
        assert m.w_temp == 0.50
        assert m.w_light == 0.30
        assert m.w_wind == 0.20

    def test_adapt_shifts_toward_dominant_sensor(self, adaptive_model):
        """Temperature varies a lot, light and wind are constant →
        weight should shift toward temperature."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [20 + i * 2 for i in range(15)],  # varies 20→48
            "light": [128] * 15,                                # constant
            "wind_speed": [15.0] * 15,                          # constant
        }
        df = pd.DataFrame(data)

        adaptive_model.adapt_weights(df, min_rows=10)
        w = adaptive_model.get_weights()
        assert w["w_temp"] > 0.45, "Temperature weight should increase"

    def test_adapt_shifts_toward_light_when_dominant(self, adaptive_model):
        """Light varies a lot, temperature and wind constant →
        weight should shift toward light."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [25.0] * 15,
            "light": [50 + i * 14 for i in range(15)],  # varies 50→246
            "wind_speed": [15.0] * 15,
        }
        df = pd.DataFrame(data)

        adaptive_model.adapt_weights(df, min_rows=10)
        w = adaptive_model.get_weights()
        assert w["w_light"] > 0.35, "Light weight should increase"

    def test_weights_always_sum_to_one(self, adaptive_model):
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [20 + i * 2 for i in range(15)],
            "light": [50 + i * 10 for i in range(15)],
            "wind_speed": [5 + i * 3 for i in range(15)],
        }
        df = pd.DataFrame(data)
        adaptive_model.adapt_weights(df, min_rows=10)
        w = adaptive_model.get_weights()
        assert abs(w["w_temp"] + w["w_light"] + w["w_wind"] - 1.0) < 1e-6

    def test_shift_bounded_by_max_shift(self, settings):
        settings.set("weight_adapt_max_shift", 0.05)
        m = WildfireModel(settings_manager=settings)

        # Only temperature varies → would want to shift heavily, but bounded
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [10 + i * 3 for i in range(15)],
            "light": [128] * 15,
            "wind_speed": [15.0] * 15,
        }
        df = pd.DataFrame(data)
        m.adapt_weights(df, min_rows=10)
        w = m.get_weights()

        # With max_shift=0.15 (default) the weight would shift much further.
        # Here with max_shift=0.05 it's constrained: after normalisation the
        # temp weight should be noticeably lower than the unrestricted case.
        unrestricted_settings = SettingsManager()
        unrestricted_settings.reset_defaults()
        unrestricted_settings.set("weight_adapt_max_shift", 0.30)
        m2 = WildfireModel(settings_manager=unrestricted_settings)
        m2.adapt_weights(df, min_rows=10)
        w2 = m2.get_weights()

        assert w["w_temp"] < w2["w_temp"], (
            "Bounded shift should produce a smaller temp weight than unrestricted"
        )

    def test_reset_weights_restores_defaults(self, adaptive_model):
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [20 + i * 2 for i in range(15)],
            "light": [128] * 15,
            "wind_speed": [15.0] * 15,
        }
        df = pd.DataFrame(data)
        adaptive_model.adapt_weights(df, min_rows=10)

        # Weights have shifted
        assert adaptive_model.w_temp != 0.45

        adaptive_model.reset_weights()
        w = adaptive_model.get_weights()
        assert w == {"w_temp": 0.45, "w_light": 0.35, "w_wind": 0.2}

    def test_adapt_skipped_when_disabled(self, settings):
        settings.set("weight_adapt_enabled", False)
        m = WildfireModel(settings_manager=settings)
        original = m.get_weights()

        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [20 + i * 2 for i in range(15)],
            "light": [128] * 15,
            "wind_speed": [15.0] * 15,
        }
        df = pd.DataFrame(data)
        m.adapt_weights(df, min_rows=10)
        assert m.get_weights() == original

    def test_adapt_skipped_when_too_few_rows(self, adaptive_model):
        original = adaptive_model.get_weights()
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=5, freq="s"),
            "temperature": [20 + i * 2 for i in range(5)],
            "light": [128] * 5,
            "wind_speed": [15.0] * 5,
        }
        df = pd.DataFrame(data)
        adaptive_model.adapt_weights(df, min_rows=10)
        assert adaptive_model.get_weights() == original

    def test_adapt_no_change_when_all_constant(self, adaptive_model):
        """When all sensors are constant (zero variance), weights stay put."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [25.0] * 15,
            "light": [128] * 15,
            "wind_speed": [15.0] * 15,
        }
        df = pd.DataFrame(data)
        original = adaptive_model.get_weights()
        adaptive_model.adapt_weights(df, min_rows=10)
        assert adaptive_model.get_weights() == original

    def test_model_without_settings_ignores_adapt(self):
        """A model created without settings_manager should not crash on adapt."""
        m = WildfireModel()
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=15, freq="s"),
            "temperature": [20 + i * 2 for i in range(15)],
            "light": [128] * 15,
            "wind_speed": [15.0] * 15,
        }
        df = pd.DataFrame(data)
        m.adapt_weights(df)  # Should not raise
        assert m.w_temp == 0.45  # Unchanged


