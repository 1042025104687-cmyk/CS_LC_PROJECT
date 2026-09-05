"""
Tests for alert_manager.py – alert generation and history.
"""

import pytest
from unittest.mock import patch
from src.core.alert_manager import AlertManager, Alert, alert_to_dict, alert_from_dict
from datetime import datetime


class TestEvaluate:
    """Validate alert creation based on risk level."""

    def test_low_risk_no_alert(self):
        mgr = AlertManager()
        result = mgr.evaluate("LOW", 20.0, 80)
        assert result is None
        assert len(mgr.get_history()) == 0

    def test_moderate_risk_no_alert(self):
        mgr = AlertManager()
        result = mgr.evaluate("MODERATE", 25.0, 120)
        assert result is None

    @patch("src.core.alert_manager.winsound")
    def test_high_risk_creates_alert(self, mock_winsound):
        mgr = AlertManager()
        result = mgr.evaluate("HIGH", 35.0, 200)
        assert result is not None
        assert result.level == "HIGH"
        assert len(mgr.get_history()) == 1

    @patch("src.core.alert_manager.winsound")
    def test_critical_risk_creates_alert(self, mock_winsound):
        mgr = AlertManager()
        result = mgr.evaluate("CRITICAL", 45.0, 250)
        assert result is not None
        assert result.level == "CRITICAL"
        assert "CRITICAL" in result.message

    @patch("src.core.alert_manager.winsound")
    def test_critical_triggers_beep(self, mock_winsound):
        mgr = AlertManager()
        mgr.evaluate("CRITICAL", 45.0, 250)
        mock_winsound.Beep.assert_called_once_with(1000, 500)

    @patch("src.core.alert_manager.winsound")
    def test_high_does_not_beep(self, mock_winsound):
        mgr = AlertManager()
        mgr.evaluate("HIGH", 35.0, 200)
        mock_winsound.Beep.assert_not_called()


class TestHistory:
    """Validate alert history management."""

    @patch("src.core.alert_manager.winsound")
    def test_history_accumulates(self, mock_winsound):
        mgr = AlertManager()
        mgr.evaluate("HIGH", 35.0, 200)
        mgr.evaluate("CRITICAL", 45.0, 250)
        assert len(mgr.get_history()) == 2

    @patch("src.core.alert_manager.winsound")
    def test_clear_history(self, mock_winsound):
        mgr = AlertManager()
        mgr.evaluate("HIGH", 35.0, 200)
        mgr.clear_history()
        assert len(mgr.get_history()) == 0

    @patch("src.core.alert_manager.winsound")
    def test_history_capped(self, mock_winsound):
        mgr = AlertManager(max_alerts=5)
        for _ in range(10):
            mgr.evaluate("HIGH", 35.0, 200)
        assert len(mgr.get_history()) == 5

    @patch("src.core.alert_manager.winsound")
    def test_history_to_dicts(self, mock_winsound):
        mgr = AlertManager()
        mgr.evaluate("HIGH", 35.0, 200)
        dicts = mgr.history_to_dicts()
        assert len(dicts) == 1
        assert dicts[0]["level"] == "HIGH"
        assert "timestamp" in dicts[0]
        assert "message" in dicts[0]


class TestSerialisation:
    """Validate Alert serialisation and deserialisation."""

    def test_roundtrip(self):
        alert = Alert(
            timestamp=datetime(2026, 3, 10, 12, 30, 0),
            level="HIGH",
            message="Test alert",
        )
        d = alert_to_dict(alert)
        restored = alert_from_dict(d)
        assert restored.level == alert.level
        assert restored.message == alert.message
        assert restored.timestamp == alert.timestamp

    def test_dict_format(self):
        alert = Alert(
            timestamp=datetime(2026, 1, 15, 9, 0, 0),
            level="CRITICAL",
            message="Danger!",
        )
        d = alert_to_dict(alert)
        assert d["timestamp"] == "2026-01-15 09:00:00"
        assert d["level"] == "CRITICAL"
        assert d["message"] == "Danger!"

