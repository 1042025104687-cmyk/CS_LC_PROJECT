# JSON-based settings persistence

from __future__ import annotations

import json
import os

from src.config.defaults import DEFAULTS

# Config directory is at artefact/config (two levels up from src/config/)
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


class SettingsManager:

    def __init__(self):
        self._settings = {}
        self.load()

    def get(self, key):
        return self._settings.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._settings[key] = value

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=4)

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._settings = dict(DEFAULTS)
        else:
            self._settings = dict(DEFAULTS)

    def reset_defaults(self):
        self._settings = dict(DEFAULTS)
        self.save()

    def as_dict(self):
        merged = dict(DEFAULTS)
        merged.update(self._settings)
        return merged