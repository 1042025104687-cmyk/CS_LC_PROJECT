# Alert system - creates warnings when risk levels are high

from __future__ import annotations

try:
    import winsound
except ImportError:
    class _SilentWinsound:
        """Provide a no-op beep on platforms without Windows audio support."""

        @staticmethod
        def Beep(frequency, duration):
            return None

    winsound = _SilentWinsound()

from collections import namedtuple
from datetime import datetime

Alert = namedtuple("Alert", ["timestamp", "level", "message"])


def alert_to_dict(alert):
    return {
        "timestamp": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "level": alert.level,
        "message": alert.message,
    }


def alert_from_dict(d):
    return Alert(
        timestamp=datetime.strptime(d["timestamp"], "%Y-%m-%d %H:%M:%S"),
        level=d["level"],
        message=d["message"],
    )


class AlertManager:

    def __init__(self, max_alerts=100):
        self._history = []
        self._max_alerts = max_alerts
        self._last_level = "LOW"

    def evaluate(self, risk_level, temperature, light):
        if risk_level in ("HIGH", "CRITICAL"):
            if risk_level == "CRITICAL":
                msg = f"Risk {risk_level}: Temp={temperature}°C, Light={light} — Extreme danger! Immediate action required."
            else:
                msg = f"Risk {risk_level}: Temp={temperature}°C, Light={light} — Conditions are concerning. Monitor closely."

            alert = Alert(timestamp=datetime.now(), level=risk_level, message=msg)
            self._add_alert(alert)

            if risk_level == "CRITICAL":
                try:
                    winsound.Beep(1000, 500)
                except RuntimeError:
                    pass

            self._last_level = risk_level
            return alert

        self._last_level = risk_level
        return None

    def get_history(self):
        return list(self._history)

    def history_to_dicts(self):
        return [alert_to_dict(a) for a in self._history]

    def clear_history(self):
        self._history.clear()

    @property
    def last_level(self):
        return self._last_level

    def _add_alert(self, alert):
        self._history.append(alert)
        if len(self._history) > self._max_alerts:
            self._history = self._history[-self._max_alerts:]
