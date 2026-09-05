"""
Tests for settings_manager.py – persistent configuration.
"""

import json
import os
import pytest

from src.config.settings import SettingsManager
from src.config.defaults import DEFAULTS
from src.config.settings import CONFIG_FILE


class TestDefaults:
    """Validate that sensible defaults are loaded."""

    def test_get_default_values(self):
        settings = SettingsManager()
        assert settings.get("polling_interval_ms") == 500
        assert settings.get("temp_moderate") == 25
        assert settings.get("temp_high") == 32
        assert settings.get("temp_critical") == 40
        # Adaptive risk engine defaults
        assert settings.get("adaptive_sensitivity") == 0.5
        assert settings.get("context_temp_threshold") == 28.0
        # Dynamic sampling rate defaults
        assert settings.get("polling_interval_normal_ms") == 2000
        assert settings.get("polling_interval_fast_ms") == 500

    def test_get_unknown_key_returns_none(self):
        settings = SettingsManager()
        assert settings.get("nonexistent_key") is None


class TestSetAndGet:
    """Validate in-memory setting changes."""

    def test_set_and_get(self):
        settings = SettingsManager()
        settings.set("temp_moderate", 30)
        assert settings.get("temp_moderate") == 30

    def test_set_new_key(self):
        settings = SettingsManager()
        settings.set("custom_key", "custom_value")
        assert settings.get("custom_key") == "custom_value"


class TestResetDefaults:
    """Validate resetting to factory defaults."""

    def test_reset_restores_defaults(self):
        settings = SettingsManager()
        settings.set("temp_moderate", 99)
        settings.reset_defaults()
        assert settings.get("temp_moderate") == DEFAULTS["temp_moderate"]


class TestAsDict:
    """Validate the merged dict output."""

    def test_as_dict_includes_defaults(self):
        settings = SettingsManager()
        d = settings.as_dict()
        for key in DEFAULTS:
            assert key in d

    def test_as_dict_reflects_overrides(self):
        settings = SettingsManager()
        settings.set("temp_moderate", 99)
        d = settings.as_dict()
        assert d["temp_moderate"] == 99

