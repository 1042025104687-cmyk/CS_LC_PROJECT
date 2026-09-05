# Wildfire risk prediction using weighted sensor inputs

from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from src.core.risk_engine import RiskEngine
    from src.config.settings import SettingsManager


class WildfireModel:
    """
    Weighted linear model: combines temp, light, wind into 0-100 risk score.
    Higher score = higher fire probability.
    """

    # Score thresholds for risk categories:
    # 0-24 = Low, 25-49 = Moderate, 50-74 = High, 75-100 = Extreme
    _THRESHOLDS = [(75, "Extreme"), (50, "High"), (25, "Moderate"), (0, "Low")]

    def __init__(self, *, w_temp=0.45, w_light=0.35, w_wind=0.20,
                 temp_min=-10.0, temp_max=50.0, light_min=0, light_max=255,
                 wind_min=0.0, wind_max=50.0, default_wind=15.0,
                 settings_manager=None):
        self._settings = settings_manager

        if settings_manager is not None:
            w_temp = float(settings_manager.get("w_temp"))
            w_light = float(settings_manager.get("w_light"))
            w_wind = float(settings_manager.get("w_wind"))

        self.w_temp = w_temp
        self.w_light = w_light
        self.w_wind = w_wind
        self._default_w_temp = w_temp
        self._default_w_light = w_light
        self._default_w_wind = w_wind

        self.temp_min = temp_min
        self.temp_max = temp_max
        self.light_min = light_min
        self.light_max = light_max
        self.wind_min = wind_min
        self.wind_max = wind_max
        self.default_wind = default_wind

    def predict(self, temperature, light, wind_speed=None):
        """
        Calculate fire risk from three sensor inputs.
        Returns a score from 0 to 100 and a category (Low/Moderate/High/Extreme).
        """
        # If no wind data, use a default value
        if wind_speed is None or (isinstance(wind_speed, float) and math.isnan(wind_speed)):
            wind_speed = self.default_wind

        # Step 1: Scale each input from 0 to 1 (normalisation)
        norm_temp = self._normalise(temperature, self.temp_min, self.temp_max)   # e.g. 30°C → 0.67
        norm_light = self._normalise(light, self.light_min, self.light_max)      # e.g. 200 → 0.78
        norm_wind = self._normalise(wind_speed, self.wind_min, self.wind_max)    # e.g. 25 km/h → 0.50

        # Step 2: Multiply each normalised value by its weight, then sum
        # Weights: temp=0.45, light=0.35, wind=0.20 (must add to 1.0)
        # Multiply by 100 to get a score from 0 to 100
        raw_score = (self.w_temp * norm_temp + self.w_light * norm_light + self.w_wind * norm_wind) * 100.0

        # Step 3: Clamp the score between 0 and 100
        risk_score = self._clamp(round(raw_score, 1), 0.0, 100.0)

        # Step 4: Convert score to a category (Low, Moderate, High, Extreme)
        risk_category = self._categorise(risk_score)

        return {
            "risk_score": risk_score,
            "risk_category": risk_category,
            "prediction": f"{risk_category} Probability of Fire (score {risk_score:.0f}/100)",
        }

    def get_weights(self):
        return {"w_temp": round(self.w_temp, 4), "w_light": round(self.w_light, 4), "w_wind": round(self.w_wind, 4)}

    def reset_weights(self):
        self.w_temp = self._default_w_temp
        self.w_light = self._default_w_light
        self.w_wind = self._default_w_wind

    def adapt_weights(self, df, min_rows=10):
        """Shift weights toward the sensor with highest recent variance."""
        if self._settings is None or not self._settings.get("weight_adapt_enabled"):
            return
        if df is None or df.empty or len(df) < min_rows:
            return

        max_shift = float(self._settings.get("weight_adapt_max_shift"))
        recent = df.tail(min_rows)

        norm_temp = recent["temperature"].apply(lambda v: self._normalise(v, self.temp_min, self.temp_max))
        norm_light = recent["light"].apply(lambda v: self._normalise(v, self.light_min, self.light_max))

        if "wind_speed" in recent.columns:
            norm_wind = pd.to_numeric(recent["wind_speed"], errors="coerce").fillna(self.default_wind)
            norm_wind = norm_wind.apply(lambda v: self._normalise(v, self.wind_min, self.wind_max))
        else:
            norm_wind = pd.Series(self._normalise(self.default_wind, self.wind_min, self.wind_max), index=recent.index)

        var_temp = float(norm_temp.var(ddof=0))
        var_light = float(norm_light.var(ddof=0))
        var_wind = float(norm_wind.var(ddof=0))
        total_var = var_temp + var_light + var_wind

        if total_var < 1e-12:
            return

        # Target weights proportional to variance
        target_temp = var_temp / total_var
        target_light = var_light / total_var
        target_wind = var_wind / total_var

        def bounded_shift(default, target):
            return max(-max_shift, min(max_shift, target - default))

        new_temp = max(0.0, self._default_w_temp + bounded_shift(self._default_w_temp, target_temp))
        new_light = max(0.0, self._default_w_light + bounded_shift(self._default_w_light, target_light))
        new_wind = max(0.0, self._default_w_wind + bounded_shift(self._default_w_wind, target_wind))

        total = new_temp + new_light + new_wind
        if total > 0:
            self.w_temp = new_temp / total
            self.w_light = new_light / total
            self.w_wind = new_wind / total

    def predict_from_dataframe(self, df, temp_col="temperature", light_col="light", wind_col="wind_speed"):
        out = df.copy()
        if wind_col in out.columns:
            winds = pd.to_numeric(out[wind_col], errors="coerce").fillna(self.default_wind)
        else:
            winds = pd.Series(self.default_wind, index=out.index)

        scores, categories, predictions = [], [], []
        for temp, light, wind in zip(out[temp_col], out[light_col], winds):
            result = self.predict(temp, light, wind)
            scores.append(result["risk_score"])
            categories.append(result["risk_category"])
            predictions.append(result["prediction"])

        out["model_score"] = scores
        out["model_category"] = categories
        out["model_prediction"] = predictions
        return out

    def what_if(self, df, temp_offset=0.0, light_offset=0.0, wind_offset=0.0):
        """Re-run model with adjusted inputs for scenario analysis."""
        adjusted = df.copy()
        adjusted["temperature"] = adjusted["temperature"] + temp_offset
        adjusted["light"] = adjusted["light"] + light_offset
        if "wind_speed" in adjusted.columns:
            adjusted["wind_speed"] = adjusted["wind_speed"] + wind_offset
        return self.predict_from_dataframe(adjusted)

    # Stress test scenarios: (temp, light, wind)
    STRESS_SCENARIOS = {
        "drought": (48.0, 250, 45.0),
        "heatwave": (50.0, 200, 30.0),
        "calm": (10.0, 40, 5.0),
    }

    def stress_test(self, scenario="drought", risk_engine=None):
        if scenario not in self.STRESS_SCENARIOS:
            raise ValueError(f"Unknown scenario {scenario!r}. Choose from {list(self.STRESS_SCENARIOS)}")

        temp, light, wind = self.STRESS_SCENARIOS[scenario]
        result = self.predict(temp, light, wind)

        risk_level = None
        if risk_engine is not None:
            risk_level = risk_engine.calculate_risk(temp, light)

        return {"scenario": scenario, "temperature": temp, "light": light, "wind_speed": wind,
                **result, "risk_level": risk_level}

    # Trend scenarios for gradual change simulation
    TREND_SCENARIOS = {
        "drought_ramp": {"temp": (20.0, 48.0), "light": (80, 250), "wind": (10.0, 40.0)},
        "deforestation": {"temp": (22.0, 35.0), "light": (60, 240), "wind": (8.0, 40.0)},
    }

    def trend_test(self, days=30, scenario="drought_ramp", risk_engine=None):
        if scenario not in self.TREND_SCENARIOS:
            raise ValueError(f"Unknown scenario {scenario!r}. Choose from {list(self.TREND_SCENARIOS)}")

        cfg = self.TREND_SCENARIOS[scenario]
        t_start, t_end = cfg["temp"]
        l_start, l_end = cfg["light"]
        w_start, w_end = cfg["wind"]

        if risk_engine is not None:
            risk_engine.reset()

        rows = []
        for day in range(1, days + 1):
            progress = (day - 1) / max(days - 1, 1)
            temp = round(t_start + (t_end - t_start) * progress, 1)
            light = int(l_start + (l_end - l_start) * progress)
            wind = round(w_start + (w_end - w_start) * progress, 1)

            result = self.predict(temp, light, wind)
            risk_level = risk_engine.calculate_risk(temp, light) if risk_engine else None

            rows.append({
                "day": day, "temperature": temp, "light": light, "wind_speed": wind,
                "model_score": result["risk_score"], "model_category": result["risk_category"],
                "risk_level": risk_level,
            })

        return pd.DataFrame(rows)

    @staticmethod
    def _normalise(value, lo, hi):
        if hi == lo:
            return 0.0
        return max(0.0, min(1.0, (value - lo) / (hi - lo)))

    @staticmethod
    def _clamp(value, lo, hi):
        return max(lo, min(hi, value))

    def _categorise(self, score):
        for threshold, label in self._THRESHOLDS:
            if score >= threshold:
                return label
        return "Low"