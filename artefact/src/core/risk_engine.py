# Adaptive risk scoring for drought/fire detection

from __future__ import annotations

from collections import deque


class RiskEngine:
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    LEVELS = [LOW, MODERATE, HIGH, CRITICAL]
    HISTORY_SIZE = 10

    def __init__(self, settings_manager):
        self._settings = settings_manager
        self._risk_history = deque(maxlen=self.HISTORY_SIZE)
        self._escalated = False
        self._capture_original_thresholds()

    @property
    def risk_history(self):
        return list(self._risk_history)

    def reset(self):
        self._risk_history.clear()
        self.reset_thresholds()

    @property
    def is_escalated(self):
        return self._escalated

    def reset_thresholds(self):
        for key, value in self._original_thresholds.items():
            self._settings.set(key, value)
        self._escalated = False

    def auto_adjust_thresholds(self):
        n = int(self._settings.get("escalation_readings"))
        factor = float(self._settings.get("escalation_factor"))

        if len(self._risk_history) < n:
            return

        recent = list(self._risk_history)[-n:]

        # Escalate when sustained high risk
        if all(s >= 2.0 for s in recent) and not self._escalated:
            for key in ("temp_moderate", "temp_high", "light_moderate", "light_high"):
                original = self._original_thresholds[key]
                lowered = original * (1.0 - factor)
                if isinstance(original, int):
                    lowered = int(round(lowered))
                self._settings.set(key, lowered)
            self._escalated = True

        # De-escalate when things calm down
        elif all(s <= 0.5 for s in recent) and self._escalated:
            self.reset_thresholds()

    def _capture_original_thresholds(self):
        self._original_thresholds = {
            "temp_moderate": self._settings.get("temp_moderate"),
            "temp_high": self._settings.get("temp_high"),
            "temp_critical": self._settings.get("temp_critical"),
            "light_moderate": self._settings.get("light_moderate"),
            "light_high": self._settings.get("light_high"),
            "light_critical": self._settings.get("light_critical"),
        }

    def calculate_risk(self, temperature, light):
        # Score each sensor independently (0-3)
        temp_score = self._score_value(
            temperature,
            self._settings.get("temp_moderate"),
            self._settings.get("temp_high"),
            self._settings.get("temp_critical"),
        )
        light_score = self._score_value(
            light,
            self._settings.get("light_moderate"),
            self._settings.get("light_high"),
            self._settings.get("light_critical"),
        )

        # In high heat, weight temperature more heavily
        context_threshold = self._settings.get("context_temp_threshold")
        if temperature > context_threshold:
            raw_score = 0.75 * temp_score + 0.25 * light_score
        else:
            raw_score = 0.50 * temp_score + 0.50 * light_score

        # Adaptive baseline - emphasize sudden changes
        sensitivity = self._settings.get("adaptive_sensitivity")
        if self._risk_history and sensitivity > 0:
            baseline = sum(self._risk_history) / len(self._risk_history)
            deviation = raw_score - baseline
            adjusted_score = raw_score + deviation * sensitivity
        else:
            adjusted_score = raw_score

        self._risk_history.append(raw_score)

        clamped = max(0.0, min(3.0, adjusted_score))
        return self.LEVELS[min(int(round(clamped)), 3)]

    @staticmethod
    def _score_value(value, moderate_thresh, high_thresh, critical_thresh):
        if value >= critical_thresh:
            return 3
        elif value >= high_thresh:
            return 2
        elif value >= moderate_thresh:
            return 1
        return 0

    @staticmethod
    def risk_colour(level):
        return {
            "LOW": "#2ecc71",
            "MODERATE": "#f1c40f",
            "HIGH": "#e67e22",
            "CRITICAL": "#e74c3c",
        }.get(level, "#95a5a6")