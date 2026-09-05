# Generates mitigation advice based on sensor readings and trends

from __future__ import annotations

from datetime import datetime
from collections import namedtuple
import numpy as np
import pandas as pd

Advice = namedtuple("Advice", ["timestamp", "urgency", "message"])


def advice_to_dict(advice):
    return {
        "timestamp": advice.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "urgency": advice.urgency,
        "message": advice.message,
    }


def advice_from_dict(d):
    return Advice(
        timestamp=datetime.strptime(d["timestamp"], "%Y-%m-%d %H:%M:%S"),
        urgency=d["urgency"],
        message=d["message"],
    )


class FeedbackEngine:
    INFO = "INFO"
    WARNING = "WARNING"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"

    def __init__(self, settings_manager):
        self._settings = settings_manager
        self._history = []
        self._max_history = 200

    def generate_advice(self, risk_level, record, df):
        temp = record["temperature"]
        light = record["light"]
        now = record["timestamp"]

        window = self._settings.get("trend_window")
        temp_trend = self._compute_trend(df, "temperature", window)
        light_trend = self._compute_trend(df, "light", window)

        advice_items = []
        advice_items.extend(self._risk_advice(risk_level, now))
        advice_items.extend(self._temperature_advice(temp, temp_trend, risk_level, now))
        advice_items.extend(self._light_advice(light, light_trend, risk_level, now))
        advice_items.extend(self._combined_trend_advice(temp_trend, light_trend, risk_level, now))
        advice_items.extend(self._deescalation_advice(temp_trend, light_trend, risk_level, now))

        for item in advice_items:
            self._add_to_history(item)

        return advice_items

    def get_history(self):
        return list(self._history)

    def history_to_dicts(self):
        return [advice_to_dict(a) for a in self._history]

    def clear_history(self):
        self._history.clear()

    def _compute_trend(self, df, column, window):
        if df.empty or len(df) < 3:
            return self.STABLE

        recent = df[column].tail(window)
        if len(recent) < 3:
            return self.STABLE

        # Use numpy for slope calculation
        x = np.arange(len(recent))
        slope, _ = np.polyfit(x, recent.values, 1)

        if slope > 0.3:
            return self.RISING
        elif slope < -0.3:
            return self.FALLING
        return self.STABLE

    def _risk_advice(self, risk_level, now):
        items = []
        if risk_level == "LOW":
            items.append(Advice(now, self.INFO, "✅ Conditions are safe — no action required."))
        elif risk_level == "MODERATE":
            items.append(Advice(now, self.WARNING, "⚠️ Mild risk detected — stay alert and monitor readings."))
            items.append(Advice(now, self.INFO, "💧 Consider pre-positioning water reserves as a precaution."))
        elif risk_level == "HIGH":
            items.append(Advice(now, self.URGENT, "🔶 Significant risk — activate fire watch protocols."))
            items.append(Advice(now, self.URGENT, "🚿 Increase irrigation to vulnerable vegetation."))
            items.append(Advice(now, self.WARNING, "📋 Review and brief emergency response procedures."))
        elif risk_level == "CRITICAL":
            items.append(Advice(now, self.CRITICAL, "🔴 EXTREME DANGER — initiate emergency response NOW."))
            items.append(Advice(now, self.CRITICAL, "🚒 Alert fire services and begin evacuation of at-risk zones."))
            items.append(Advice(now, self.URGENT, "💧 Deploy maximum irrigation and wet-down perimeters."))
            items.append(Advice(now, self.URGENT, "📡 Broadcast public safety warnings immediately."))
        return items

    def _temperature_advice(self, temp, trend, risk_level, now):
        items = []
        crit = self._settings.get("temp_critical")
        high = self._settings.get("temp_high")
        mod = self._settings.get("temp_moderate")

        if temp >= crit:
            items.append(Advice(now, self.CRITICAL, f"🌡️ Temperature {temp:.1f}°C exceeds critical threshold ({crit}°C)."))
            if trend == self.RISING:
                items.append(Advice(now, self.CRITICAL, "📈 Temperature still RISING — conditions worsening rapidly."))
        elif temp >= high:
            items.append(Advice(now, self.URGENT, f"🌡️ Temperature {temp:.1f}°C is dangerously high (threshold {high}°C)."))
            if trend == self.RISING:
                items.append(Advice(now, self.URGENT, "📈 Temperature trending upward — prepare for escalation."))
        elif temp >= mod and trend == self.RISING:
            items.append(Advice(now, self.WARNING, "🌡️ Temperature rising toward high-risk zone — begin precautions."))
        return items

    def _light_advice(self, light, trend, risk_level, now):
        items = []
        crit = self._settings.get("light_critical")
        high = self._settings.get("light_high")

        if light >= crit:
            items.append(Advice(now, self.CRITICAL, f"☀️ Light level {light} exceeds critical threshold ({crit})."))
            items.append(Advice(now, self.URGENT, "🏗️ Deploy shade covers or reflective barriers on crops."))
        elif light >= high:
            items.append(Advice(now, self.URGENT, f"☀️ Light level {light} is high — solar drying risk increases."))
            if trend == self.RISING:
                items.append(Advice(now, self.WARNING, "📈 Light intensity rising — expect further soil moisture loss."))
        return items

    def _combined_trend_advice(self, temp_trend, light_trend, risk_level, now):
        items = []
        if temp_trend == self.RISING and light_trend == self.RISING:
            if risk_level in ("HIGH", "CRITICAL"):
                items.append(Advice(now, self.CRITICAL, "⚠️ Both temperature AND light rising — compound risk accelerating. Escalate response."))
            elif risk_level == "MODERATE":
                items.append(Advice(now, self.WARNING, "📊 Both readings trending up — conditions may deteriorate. Increase monitoring frequency."))
        return items

    def _deescalation_advice(self, temp_trend, light_trend, risk_level, now):
        items = []
        if temp_trend == self.FALLING and light_trend == self.FALLING:
            if risk_level in ("HIGH", "CRITICAL"):
                items.append(Advice(now, self.INFO, "📉 Both readings falling — conditions may be improving. Maintain current response until confirmed."))
            elif risk_level == "MODERATE":
                items.append(Advice(now, self.INFO, "📉 Readings trending down — situation stabilising."))
        elif temp_trend == self.FALLING and risk_level in ("MODERATE", "HIGH"):
            items.append(Advice(now, self.INFO, "🌡️📉 Temperature dropping — positive sign. Continue monitoring."))
        elif light_trend == self.FALLING and risk_level in ("MODERATE", "HIGH"):
            items.append(Advice(now, self.INFO, "☀️📉 Light intensity decreasing — solar stress easing."))
        return items

    def _add_to_history(self, advice):
        self._history.append(advice)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]