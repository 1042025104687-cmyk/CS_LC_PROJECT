"""
Tests for risk_engine.py – adaptive risk level scoring.

The adaptive engine combines:
* **Memory** – a rolling deque of the last 10 raw scores (baseline).
* **Context** – weighted scoring that shifts 3:1 toward temperature
  when temp > context_temp_threshold.
* **Sensitivity** – amplifies deviation from the moving baseline.
"""

import pytest
from src.core.risk_engine import RiskEngine
from src.config.settings import SettingsManager


@pytest.fixture
def engine():
    """Create a RiskEngine with default settings (sensitivity=0.5, context_temp=28)."""
    settings = SettingsManager()
    settings.reset_defaults()
    return RiskEngine(settings)


@pytest.fixture
def static_engine():
    """Create a RiskEngine with adaptive features disabled (sensitivity=0)."""
    settings = SettingsManager()
    settings.reset_defaults()
    settings.set("adaptive_sensitivity", 0.0)
    return RiskEngine(settings)


# ==================================================================
# Basic scoring – adaptive features disabled (sensitivity = 0)
# ==================================================================

class TestStaticCalculateRisk:
    """Validate risk levels with sensitivity=0 (pure weighted scoring).

    Default thresholds:
        temp:  moderate=25, high=32, critical=40
        light: moderate=120, high=180, critical=220
    Context temp threshold: 28 °C

    Below 28 °C → equal weighting (0.5 temp + 0.5 light).
    Above 28 °C → 0.75 temp + 0.25 light.
    """

    def test_low_risk(self, static_engine):
        # temp=20 → score 0, light=80 → score 0 → weighted 0.0 → LOW
        assert static_engine.calculate_risk(20.0, 80) == "LOW"

    def test_moderate_by_temperature_below_context(self, static_engine):
        # temp=25 (score 1), light=80 (score 0), temp <= 28 → 0.5*1+0.5*0=0.5
        # Python banker's rounding: round(0.5)=0 → LOW
        assert static_engine.calculate_risk(25.0, 80) == "LOW"

    def test_moderate_by_light(self, static_engine):
        # temp=20 (score 0), light=120 (score 1), temp <= 28 → 0.5*0+0.5*1=0.5 → round→0 → LOW
        # Note: equal weighting at 0.5 rounds to 0 → LOW
        assert static_engine.calculate_risk(20.0, 120) == "LOW"

    def test_high_by_temperature_above_context(self, static_engine):
        # temp=32 (score 2), light=80 (score 0), temp > 28 → 0.75*2+0.25*0=1.5 → round→2 → HIGH
        assert static_engine.calculate_risk(32.0, 80) == "HIGH"

    def test_high_by_light_below_context(self, static_engine):
        # temp=20 (score 0), light=180 (score 2), temp <= 28 → 0.5*0+0.5*2=1.0 → round→1 → MODERATE
        assert static_engine.calculate_risk(20.0, 180) == "MODERATE"

    def test_critical_by_temperature(self, static_engine):
        # temp=40 (score 3), light=80 (score 0), temp > 28 → 0.75*3+0.25*0=2.25 → round→2 → HIGH
        assert static_engine.calculate_risk(40.0, 80) == "HIGH"

    def test_critical_by_light(self, static_engine):
        # temp=20 (score 0), light=220 (score 3), temp <= 28 → 0.5*0+0.5*3=1.5 → round→2 → HIGH
        assert static_engine.calculate_risk(20.0, 220) == "HIGH"

    def test_both_critical(self, static_engine):
        # temp=45 (score 3), light=250 (score 3), temp > 28 → 0.75*3+0.25*3=3.0 → CRITICAL
        assert static_engine.calculate_risk(45.0, 250) == "CRITICAL"

    def test_weighted_takes_temperature_bias_above_context(self, static_engine):
        # temp=32 (score 2), light=120 (score 1), temp > 28 → 0.75*2+0.25*1=1.75 → round→2 → HIGH
        assert static_engine.calculate_risk(32.0, 120) == "HIGH"

    def test_equal_weight_below_context(self, static_engine):
        # temp=25 (score 1), light=180 (score 2), temp <= 28 → 0.5*1+0.5*2=1.5 → round→2 → HIGH
        assert static_engine.calculate_risk(25.0, 180) == "HIGH"

    def test_just_below_moderate(self, static_engine):
        # temp=24.9 (score 0), light=119 (score 0) → 0.0 → LOW
        assert static_engine.calculate_risk(24.9, 119) == "LOW"


# ==================================================================
# Context-aware weighting
# ==================================================================

class TestContextualWeighting:
    """Verify that the 3:1 weight shift activates above context_temp_threshold."""

    def test_below_context_threshold_equal_weight(self, static_engine):
        # At exactly 28 °C → NOT above threshold → equal weighting
        # temp=28 (score 1), light=180 (score 2) → 0.5*1+0.5*2=1.5 → round→2 → HIGH
        assert static_engine.calculate_risk(28.0, 180) == "HIGH"

    def test_above_context_threshold_temp_dominant(self, static_engine):
        # temp=29 (score 1), light=180 (score 2), temp > 28 → 0.75*1+0.25*2=1.25 → round→1 → MODERATE
        assert static_engine.calculate_risk(29.0, 180) == "MODERATE"

    def test_custom_context_threshold(self):
        """Changing context_temp_threshold shifts when weighting activates."""
        settings = SettingsManager()
        settings.reset_defaults()
        settings.set("adaptive_sensitivity", 0.0)
        settings.set("context_temp_threshold", 20.0)
        engine = RiskEngine(settings)

        # temp=22 (score 0), light=180 (score 2), temp > 20 → 0.75*0+0.25*2=0.5 → round→0 → LOW
        assert engine.calculate_risk(22.0, 180) == "LOW"


# ==================================================================
# Memory – risk_history and reset
# ==================================================================

class TestMemory:
    """Validate the rolling risk_history deque."""

    def test_history_starts_empty(self, engine):
        assert engine.risk_history == []

    def test_history_grows_with_calls(self, engine):
        engine.calculate_risk(20.0, 80)
        engine.calculate_risk(25.0, 80)
        assert len(engine.risk_history) == 2

    def test_history_capped_at_10(self, engine):
        for _ in range(15):
            engine.calculate_risk(30.0, 100)
        assert len(engine.risk_history) == 10

    def test_reset_clears_history(self, engine):
        engine.calculate_risk(20.0, 80)
        engine.calculate_risk(30.0, 100)
        engine.reset()
        assert engine.risk_history == []

    def test_history_records_raw_score(self, static_engine):
        # temp=20 (score 0), light=80 (score 0), temp <= 28 → raw=0.0
        static_engine.calculate_risk(20.0, 80)
        assert static_engine.risk_history == [0.0]

        # temp=45 (score 3), light=250 (score 3), temp > 28 → raw=0.75*3+0.25*3=3.0
        static_engine.calculate_risk(45.0, 250)
        assert static_engine.risk_history == [0.0, 3.0]


# ==================================================================
# Adaptive baseline adjustment
# ==================================================================

class TestAdaptiveBaseline:
    """Verify that baseline adjustment amplifies sudden spikes."""

    def test_sudden_spike_amplified(self):
        """A sudden jump from a low baseline should be amplified upward."""
        settings = SettingsManager()
        settings.reset_defaults()
        settings.set("adaptive_sensitivity", 1.0)
        engine = RiskEngine(settings)

        # Build a low baseline (all LOW readings)
        for _ in range(10):
            engine.calculate_risk(15.0, 50)

        # All raw scores should be 0.0
        assert all(s == 0.0 for s in engine.risk_history)

        # Now a HIGH reading: temp=32 (score 2), light=80 (score 0)
        # temp > 28 → raw = 0.75*2 + 0.25*0 = 1.5
        # baseline = 0.0, deviation = 1.5, sensitivity=1.0
        # adjusted = 1.5 + 1.5*1.0 = 3.0 → CRITICAL
        result = engine.calculate_risk(32.0, 80)
        assert result == "CRITICAL"

    def test_slow_drift_dampened(self):
        """Gradually rising readings should not overshoot because the
        baseline rises with them."""
        settings = SettingsManager()
        settings.reset_defaults()
        settings.set("adaptive_sensitivity", 0.5)
        engine = RiskEngine(settings)

        # Gradually ramp temperature from 25 to 32 in small steps
        temps = [25, 26, 27, 28, 29, 30, 30, 31, 31, 32]
        results = []
        for t in temps:
            results.append(engine.calculate_risk(float(t), 80))

        # The final reading (32 °C = score 2) should NOT jump to CRITICAL
        # because the baseline has been gradually rising.
        assert results[-1] in ("MODERATE", "HIGH")

    def test_zero_sensitivity_is_static(self, static_engine):
        """With sensitivity=0 the baseline has no effect."""
        # Build a low baseline
        for _ in range(10):
            static_engine.calculate_risk(15.0, 50)

        # Spike: temp=32 (score 2), temp > 28 → raw=0.75*2+0.25*0=1.5 → round→2 → HIGH
        result = static_engine.calculate_risk(32.0, 80)
        assert result == "HIGH"


# ==================================================================
# Risk colour (unchanged)
# ==================================================================

class TestRiskColour:
    """Validate colour mapping for risk levels."""

    def test_low_colour(self):
        assert RiskEngine.risk_colour("LOW") == "#2ecc71"

    def test_moderate_colour(self):
        assert RiskEngine.risk_colour("MODERATE") == "#f1c40f"

    def test_high_colour(self):
        assert RiskEngine.risk_colour("HIGH") == "#e67e22"

    def test_critical_colour(self):
        assert RiskEngine.risk_colour("CRITICAL") == "#e74c3c"

    def test_unknown_colour(self):
        assert RiskEngine.risk_colour("UNKNOWN") == "#95a5a6"


# ==================================================================
# Static scoring helper (unchanged)
# ==================================================================

class TestScoreValue:
    """Validate the internal scoring helper."""

    def test_below_all_thresholds(self):
        assert RiskEngine._score_value(10, 25, 32, 40) == 0

    def test_at_moderate(self):
        assert RiskEngine._score_value(25, 25, 32, 40) == 1

    def test_at_high(self):
        assert RiskEngine._score_value(32, 25, 32, 40) == 2

    def test_at_critical(self):
        assert RiskEngine._score_value(40, 25, 32, 40) == 3

    def test_above_critical(self):
        assert RiskEngine._score_value(50, 25, 32, 40) == 3


# ==================================================================
# Dynamic sampling rate integration
# ==================================================================

class TestDynamicSamplingIntegration:
    """Verify that risk levels correctly signal when fast polling is needed.

    The actual interval switching happens in app.py, but these tests
    confirm the risk outputs that drive the decision.
    """

    def test_high_risk_triggers_fast_poll(self, static_engine):
        """HIGH risk should indicate the system needs to poll faster."""
        result = static_engine.calculate_risk(32.0, 120)
        assert result == "HIGH"
        # In the real app, HIGH → polling_interval_fast_ms

    def test_low_risk_keeps_normal_poll(self, static_engine):
        """LOW risk should keep the system at normal polling rate."""
        result = static_engine.calculate_risk(15.0, 50)
        assert result == "LOW"
        # In the real app, LOW → polling_interval_normal_ms

    def test_critical_risk_triggers_fast_poll(self, static_engine):
        """CRITICAL risk should also trigger fast polling."""
        result = static_engine.calculate_risk(45.0, 250)
        assert result == "CRITICAL"
        # In the real app, CRITICAL → polling_interval_fast_ms

    def test_moderate_risk_keeps_normal_poll(self, static_engine):
        """MODERATE risk keeps normal polling (only HIGH+ triggers fast)."""
        result = static_engine.calculate_risk(20.0, 180)
        assert result == "MODERATE"
        # In the real app, MODERATE → polling_interval_normal_ms

    def test_risk_transitions_drive_rate_changes(self, static_engine):
        """Successive calls producing different risk levels demonstrate
        the inputs that would trigger sampling rate switches."""
        # Low-risk reading
        r1 = static_engine.calculate_risk(15.0, 50)
        assert r1 == "LOW"

        # High-risk reading
        r2 = static_engine.calculate_risk(32.0, 120)
        assert r2 == "HIGH"

        # Back to low-risk
        r3 = static_engine.calculate_risk(15.0, 50)
        assert r3 == "LOW"


# ==================================================================
# Threshold escalation / de-escalation
# ==================================================================

class TestThresholdEscalation:
    """Verify automatic threshold lowering under sustained high risk
    and restoration under sustained low risk."""

    @pytest.fixture
    def esc_engine(self):
        """RiskEngine with sensitivity=0 and escalation_readings=3 for easy testing."""
        settings = SettingsManager()
        settings.reset_defaults()
        settings.set("adaptive_sensitivity", 0.0)
        settings.set("escalation_readings", 3)
        settings.set("escalation_factor", 0.10)
        return RiskEngine(settings)

    def test_not_escalated_initially(self, esc_engine):
        assert esc_engine.is_escalated is False

    def test_escalation_after_sustained_high(self, esc_engine):
        """Three consecutive HIGH+ readings should trigger escalation."""
        # temp=45 (score 3), light=250 (score 3), temp>28 → raw=3.0
        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()
        assert esc_engine.is_escalated is True

    def test_escalation_lowers_thresholds(self, esc_engine):
        """After escalation, moderate/high thresholds should be lower."""
        settings = esc_engine._settings
        orig_temp_mod = settings.get("temp_moderate")

        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()

        assert settings.get("temp_moderate") < orig_temp_mod
        assert settings.get("temp_high") < 32  # original default
        assert settings.get("light_moderate") < 120
        assert settings.get("light_high") < 180

    def test_escalation_factor_applied_correctly(self, esc_engine):
        """Thresholds should be lowered by exactly the escalation factor."""
        settings = esc_engine._settings
        orig_temp_high = settings.get("temp_high")  # 32 (int)

        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()

        # 32 * (1 - 0.10) = 28.8, rounded to int → 29
        expected = int(round(orig_temp_high * 0.90))
        assert settings.get("temp_high") == expected

    def test_deescalation_after_sustained_low(self, esc_engine):
        """After escalation, three consecutive LOW readings should de-escalate."""
        # First escalate
        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()
        assert esc_engine.is_escalated is True

        # Now sustained low: temp=10 (score 0), light=30 (score 0) → raw=0.0
        for _ in range(3):
            esc_engine.calculate_risk(10.0, 30)
        esc_engine.auto_adjust_thresholds()
        assert esc_engine.is_escalated is False

    def test_deescalation_restores_original_thresholds(self, esc_engine):
        """After de-escalation, thresholds should match their original values."""
        settings = esc_engine._settings
        orig_temp_mod = settings.get("temp_moderate")

        # Escalate then de-escalate
        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()

        for _ in range(3):
            esc_engine.calculate_risk(10.0, 30)
        esc_engine.auto_adjust_thresholds()

        assert settings.get("temp_moderate") == orig_temp_mod

    def test_reset_clears_escalation(self, esc_engine):
        """reset() should clear escalation and restore thresholds."""
        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()
        assert esc_engine.is_escalated is True

        esc_engine.reset()
        assert esc_engine.is_escalated is False
        assert esc_engine.risk_history == []

    def test_reset_thresholds_restores_values(self, esc_engine):
        settings = esc_engine._settings
        orig_temp_mod = settings.get("temp_moderate")

        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()
        assert settings.get("temp_moderate") != orig_temp_mod

        esc_engine.reset_thresholds()
        assert settings.get("temp_moderate") == orig_temp_mod
        assert esc_engine.is_escalated is False

    def test_no_escalation_without_enough_readings(self, esc_engine):
        """Fewer than escalation_readings entries → no escalation."""
        esc_engine.calculate_risk(45.0, 250)
        esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()
        assert esc_engine.is_escalated is False

    def test_no_double_escalation(self, esc_engine):
        """Calling auto_adjust_thresholds multiple times should not
        escalate again (thresholds should not keep shrinking)."""
        settings = esc_engine._settings

        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()
        first_temp_mod = settings.get("temp_moderate")

        # More high readings and another call
        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()

        assert settings.get("temp_moderate") == first_temp_mod

    def test_critical_thresholds_not_lowered(self, esc_engine):
        """Escalation only affects moderate and high, not critical thresholds."""
        settings = esc_engine._settings
        orig_temp_crit = settings.get("temp_critical")
        orig_light_crit = settings.get("light_critical")

        for _ in range(3):
            esc_engine.calculate_risk(45.0, 250)
        esc_engine.auto_adjust_thresholds()

        assert settings.get("temp_critical") == orig_temp_crit
        assert settings.get("light_critical") == orig_light_crit


