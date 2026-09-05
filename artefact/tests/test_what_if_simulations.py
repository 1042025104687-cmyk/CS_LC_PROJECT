"""
Tests for what-if simulations — Stress Test and Trend Test.

Validates both the WildfireModel static predictions and the adaptive
RiskEngine integration side-by-side, ensuring:

1. **Stress Test (Extreme)**: forcing extreme values triggers
   High/Extreme immediately in the model and HIGH/CRITICAL in
   the RiskEngine.
2. **Trend Test (Loop)**: simulating days of gradual change produces
   monotonically rising scores, and the adaptive RiskEngine
   demonstrates dampened drift (transitions later than the model).
"""

import pytest
import pandas as pd

from src.core.wildfire_model import WildfireModel
from src.core.risk_engine import RiskEngine
from src.config.settings import SettingsManager


# ==================================================================
# Fixtures
# ==================================================================

@pytest.fixture
def model():
    """Create a WildfireModel with default parameters."""
    return WildfireModel()


@pytest.fixture
def settings():
    """Create a SettingsManager with default settings."""
    s = SettingsManager()
    s.reset_defaults()
    return s


@pytest.fixture
def static_engine(settings):
    """RiskEngine with adaptive features disabled (sensitivity=0)."""
    settings.set("adaptive_sensitivity", 0.0)
    return RiskEngine(settings)


@pytest.fixture
def adaptive_engine(settings):
    """RiskEngine with high adaptive sensitivity."""
    settings.set("adaptive_sensitivity", 1.0)
    return RiskEngine(settings)


# ==================================================================
# Stress Test – basic model behaviour
# ==================================================================

class TestStressTestModel:
    """Validate stress_test() model-only output (no RiskEngine)."""

    def test_drought_triggers_high_or_extreme(self, model):
        """Drought extreme values must produce High or Extreme."""
        result = model.stress_test("drought")
        assert result["risk_category"] in ("High", "Extreme")
        assert result["risk_score"] >= 50

    def test_heatwave_triggers_high_or_extreme(self, model):
        """Heatwave extreme values must produce High or Extreme."""
        result = model.stress_test("heatwave")
        assert result["risk_category"] in ("High", "Extreme")
        assert result["risk_score"] >= 50

    def test_calm_triggers_low(self, model):
        """Calm scenario must produce Low category."""
        result = model.stress_test("calm")
        assert result["risk_category"] == "Low"
        assert result["risk_score"] < 25

    def test_returns_required_keys(self, model):
        result = model.stress_test("drought")
        for key in ("scenario", "temperature", "light", "wind_speed",
                     "risk_score", "risk_category", "prediction", "risk_level"):
            assert key in result

    def test_risk_level_none_without_engine(self, model):
        """Without a RiskEngine, risk_level should be None."""
        result = model.stress_test("drought")
        assert result["risk_level"] is None

    def test_unknown_scenario_raises(self, model):
        with pytest.raises(ValueError, match="Unknown scenario"):
            model.stress_test("blizzard")

    def test_inputs_match_scenario(self, model):
        """Returned inputs must match the STRESS_SCENARIOS definition."""
        for name, (exp_t, exp_l, exp_w) in WildfireModel.STRESS_SCENARIOS.items():
            result = model.stress_test(name)
            assert result["temperature"] == exp_t
            assert result["light"] == exp_l
            assert result["wind_speed"] == exp_w


# ==================================================================
# Stress Test – RiskEngine integration
# ==================================================================

class TestStressTestRiskEngine:
    """Validate stress_test() with a RiskEngine provided."""

    def test_static_engine_drought_high_or_critical(self, model, static_engine):
        """Static engine should return HIGH or CRITICAL for drought."""
        result = model.stress_test("drought", risk_engine=static_engine)
        assert result["risk_level"] in ("HIGH", "CRITICAL")

    def test_static_engine_calm_is_low(self, model, static_engine):
        """Static engine should return LOW for calm."""
        result = model.stress_test("calm", risk_engine=static_engine)
        assert result["risk_level"] == "LOW"

    def test_adaptive_engine_spike_from_low_baseline(self, model, adaptive_engine):
        """A spike from a cold baseline should be amplified to CRITICAL."""
        # Build a low baseline (10 LOW readings)
        for _ in range(10):
            adaptive_engine.calculate_risk(15.0, 50)

        result = model.stress_test("drought", risk_engine=adaptive_engine)
        assert result["risk_level"] == "CRITICAL"

    def test_risk_level_populated(self, model, static_engine):
        result = model.stress_test("heatwave", risk_engine=static_engine)
        assert result["risk_level"] is not None
        assert result["risk_level"] in RiskEngine.LEVELS


# ==================================================================
# Trend Test – basic model behaviour
# ==================================================================

class TestTrendTestModel:
    """Validate trend_test() model-only output (no RiskEngine)."""

    def test_returns_dataframe(self, model):
        df = model.trend_test(days=10, scenario="drought_ramp")
        assert isinstance(df, pd.DataFrame)

    def test_row_count_matches_days(self, model):
        for days in (7, 30, 60):
            df = model.trend_test(days=days, scenario="drought_ramp")
            assert len(df) == days

    def test_has_required_columns(self, model):
        df = model.trend_test(days=10, scenario="drought_ramp")
        for col in ("day", "temperature", "light", "wind_speed",
                     "model_score", "model_category", "risk_level"):
            assert col in df.columns

    def test_day_column_sequential(self, model):
        df = model.trend_test(days=20, scenario="drought_ramp")
        assert df["day"].tolist() == list(range(1, 21))

    def test_scores_non_decreasing_drought(self, model):
        """Drought ramp should produce monotonically non-decreasing scores."""
        df = model.trend_test(days=30, scenario="drought_ramp")
        scores = df["model_score"].tolist()
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"Score decreased at day {i + 1}: {scores[i]} < {scores[i - 1]}"
            )

    def test_scores_non_decreasing_deforestation(self, model):
        """Deforestation scenario should also be non-decreasing."""
        df = model.trend_test(days=30, scenario="deforestation")
        scores = df["model_score"].tolist()
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_final_score_higher_than_first(self, model):
        df = model.trend_test(days=30, scenario="drought_ramp")
        assert df["model_score"].iloc[-1] > df["model_score"].iloc[0]

    def test_drought_reaches_extreme(self, model):
        """Over 30 days of drought ramp, final category should be Extreme."""
        df = model.trend_test(days=30, scenario="drought_ramp")
        assert df["model_category"].iloc[-1] == "Extreme"

    def test_drought_starts_low_or_moderate(self, model):
        """Day 1 of drought ramp starts from safe conditions."""
        df = model.trend_test(days=30, scenario="drought_ramp")
        assert df["model_category"].iloc[0] in ("Low", "Moderate")

    def test_risk_level_none_without_engine(self, model):
        df = model.trend_test(days=10, scenario="drought_ramp")
        assert df["risk_level"].isna().all()

    def test_unknown_scenario_raises(self, model):
        with pytest.raises(ValueError, match="Unknown scenario"):
            model.trend_test(days=10, scenario="tsunami")

    def test_single_day(self, model):
        """Edge case: 1 day should still produce a valid row."""
        df = model.trend_test(days=1, scenario="drought_ramp")
        assert len(df) == 1
        assert df["day"].iloc[0] == 1


# ==================================================================
# Trend Test – RiskEngine integration
# ==================================================================

class TestTrendTestRiskEngine:
    """Validate trend_test() with a RiskEngine provided."""

    def test_risk_level_populated(self, model, static_engine):
        df = model.trend_test(days=15, scenario="drought_ramp",
                              risk_engine=static_engine)
        assert df["risk_level"].notna().all()

    def test_all_levels_valid(self, model, static_engine):
        df = model.trend_test(days=30, scenario="drought_ramp",
                              risk_engine=static_engine)
        valid = set(RiskEngine.LEVELS)
        for lvl in df["risk_level"]:
            assert lvl in valid

    def test_engine_reset_called(self, model, adaptive_engine):
        """Engine history should be empty at the start of each run,
        so two consecutive calls produce identical results."""
        df1 = model.trend_test(days=20, scenario="drought_ramp",
                               risk_engine=adaptive_engine)
        df2 = model.trend_test(days=20, scenario="drought_ramp",
                               risk_engine=adaptive_engine)
        assert df1["risk_level"].tolist() == df2["risk_level"].tolist()

    def test_adaptive_dampens_slow_drift(self, model):
        """With high sensitivity, the adaptive engine should reach HIGH
        on a *later* day than the model reaches High, because the
        rolling baseline rises with the gradual trend."""
        settings = SettingsManager()
        settings.reset_defaults()
        settings.set("adaptive_sensitivity", 1.0)
        engine = RiskEngine(settings)

        df = model.trend_test(days=30, scenario="drought_ramp",
                              risk_engine=engine)

        # Find first day model_category hits "High" or "Extreme"
        model_high = df.loc[
            df["model_category"].isin(["High", "Extreme"]), "day"
        ]
        # Find first day risk_level hits "HIGH" or "CRITICAL"
        engine_high = df.loc[
            df["risk_level"].isin(["HIGH", "CRITICAL"]), "day"
        ]

        assert len(model_high) > 0, "Model should reach High in 30 days"
        assert len(engine_high) > 0, "Engine should reach HIGH in 30 days"

        day_model = model_high.iloc[0]
        day_engine = engine_high.iloc[0]

        # Adaptive engine should lag behind or match the model
        assert day_engine >= day_model, (
            f"Expected adaptive engine ({day_engine}) to lag the model "
            f"({day_model}) during slow drift"
        )

    def test_static_engine_same_day_as_model(self, model):
        """With sensitivity=0 (static mode), the engine and model should
        transition to high risk around the same time."""
        settings = SettingsManager()
        settings.reset_defaults()
        settings.set("adaptive_sensitivity", 0.0)
        engine = RiskEngine(settings)

        df = model.trend_test(days=30, scenario="drought_ramp",
                              risk_engine=engine)

        model_high = df.loc[
            df["model_category"].isin(["High", "Extreme"]), "day"
        ]
        engine_high = df.loc[
            df["risk_level"].isin(["HIGH", "CRITICAL"]), "day"
        ]

        if len(model_high) > 0 and len(engine_high) > 0:
            # Should be within a reasonable range of each other
            # (the two systems use different scoring — continuous 0–100
            #  vs. categorical 0–3 — so exact alignment is not expected)
            delta = abs(int(engine_high.iloc[0]) - int(model_high.iloc[0]))
            assert delta <= 8, (
                f"Static engine should transition near the model; "
                f"delta was {delta} days"
            )


# ==================================================================
# Combined Stress + Trend integration
# ==================================================================

class TestCombinedSimulations:
    """Cross-scenario validation between stress and trend tests."""

    def test_stress_drought_score_near_trend_final(self, model):
        """The stress-test drought score should be close to (or above)
        the final day score of a drought_ramp trend test, since both
        use similar extreme inputs."""
        stress = model.stress_test("drought")
        trend = model.trend_test(days=30, scenario="drought_ramp")
        # Stress test forces 48°C / 250 / 45 km/h → should be ≥ trend end
        assert stress["risk_score"] >= trend["model_score"].iloc[-1] - 5

    def test_deforestation_trend_reaches_high(self, model):
        """Deforestation scenario should eventually reach High."""
        df = model.trend_test(days=30, scenario="deforestation")
        high_cats = df.loc[df["model_category"].isin(["High", "Extreme"])]
        assert len(high_cats) > 0, (
            "Deforestation over 30 days should reach High risk"
        )


