"""
Tests for feedback_engine.py – adaptive mitigation advice.
"""

import pytest
from datetime import datetime

import pandas as pd

from src.core.feedback_engine import FeedbackEngine, Advice, advice_to_dict, advice_from_dict
from src.config.settings import SettingsManager


@pytest.fixture
def engine():
    """Create a FeedbackEngine with default settings."""
    settings = SettingsManager()
    settings.reset_defaults()
    return FeedbackEngine(settings)


def _make_record(temp: float, light: int) -> dict:
    return {
        "timestamp": datetime(2026, 3, 10, 12, 0, 0),
        "temperature": temp,
        "light": light,
    }


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.Series(dtype="datetime64[ns]"),
        "temperature": pd.Series(dtype="float64"),
        "light": pd.Series(dtype="int64"),
    })


class TestGenerateAdvice:
    """Validate that advice is generated for various risk levels."""

    def test_low_risk_returns_advice(self, engine):
        record = _make_record(20.0, 80)
        items = engine.generate_advice("LOW", record, _empty_df())
        assert len(items) > 0
        # Should contain a safe / info message
        assert any(a.urgency == "INFO" for a in items)

    def test_critical_risk_returns_critical_advice(self, engine):
        record = _make_record(45.0, 250)
        items = engine.generate_advice("CRITICAL", record, _empty_df())
        assert any(a.urgency == "CRITICAL" for a in items)

    def test_high_risk_returns_urgent_advice(self, engine):
        record = _make_record(35.0, 200)
        items = engine.generate_advice("HIGH", record, _empty_df())
        assert any(a.urgency in ("URGENT", "CRITICAL") for a in items)

    def test_moderate_risk_returns_warning(self, engine):
        record = _make_record(26.0, 130)
        items = engine.generate_advice("MODERATE", record, _empty_df())
        assert any(a.urgency == "WARNING" for a in items)


class TestTrendComputation:
    """Validate the internal trend classification helper."""

    def test_stable_with_empty_df(self, engine):
        df = _empty_df()
        assert engine._compute_trend(df, "temperature", 10) == "stable"

    def test_rising_trend(self, engine):
        """A steadily increasing series should be classified as rising."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=10, freq="s"),
            "temperature": [20 + i * 2 for i in range(10)],
            "light": [100] * 10,
        }
        df = pd.DataFrame(data)
        assert engine._compute_trend(df, "temperature", 10) == "rising"

    def test_falling_trend(self, engine):
        """A steadily decreasing series should be classified as falling."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=10, freq="s"),
            "temperature": [40 - i * 2 for i in range(10)],
            "light": [100] * 10,
        }
        df = pd.DataFrame(data)
        assert engine._compute_trend(df, "temperature", 10) == "falling"

    def test_stable_trend(self, engine):
        """A flat series should be classified as stable."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=10, freq="s"),
            "temperature": [25.0] * 10,
            "light": [100] * 10,
        }
        df = pd.DataFrame(data)
        assert engine._compute_trend(df, "temperature", 10) == "stable"

    def test_too_few_rows(self, engine):
        """With fewer than 3 rows, trend should be stable."""
        data = {
            "timestamp": pd.date_range("2026-01-01", periods=2, freq="s"),
            "temperature": [20.0, 30.0],
            "light": [100, 100],
        }
        df = pd.DataFrame(data)
        assert engine._compute_trend(df, "temperature", 10) == "stable"


class TestHistory:
    """Validate advice history management."""

    def test_advice_stored_in_history(self, engine):
        record = _make_record(25.0, 120)
        engine.generate_advice("MODERATE", record, _empty_df())
        history = engine.get_history()
        assert len(history) > 0

    def test_clear_history(self, engine):
        record = _make_record(25.0, 120)
        engine.generate_advice("MODERATE", record, _empty_df())
        engine.clear_history()
        assert len(engine.get_history()) == 0

    def test_history_to_dicts(self, engine):
        record = _make_record(25.0, 120)
        engine.generate_advice("MODERATE", record, _empty_df())
        dicts = engine.history_to_dicts()
        assert len(dicts) > 0
        assert "timestamp" in dicts[0]
        assert "urgency" in dicts[0]
        assert "message" in dicts[0]


class TestSerialisation:
    """Validate Advice serialisation roundtrip."""

    def test_roundtrip(self):
        advice = Advice(
            timestamp=datetime(2026, 3, 10, 12, 0, 0),
            urgency="WARNING",
            message="Stay alert.",
        )
        d = advice_to_dict(advice)
        restored = advice_from_dict(d)
        assert restored.urgency == advice.urgency
        assert restored.message == advice.message
        assert restored.timestamp == advice.timestamp

