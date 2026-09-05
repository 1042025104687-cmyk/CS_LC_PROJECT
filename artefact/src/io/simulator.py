# Fake sensor data generator for testing without hardware

from __future__ import annotations

import math
import random
import threading
import time

from src.io.data_source import DataSource


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _add_noise(value, noise):
    return value + random.gauss(0, noise)


class Simulator(DataSource):
    """Fake sensor data generator implementing DataSource protocol."""
    
    SCENARIOS = ["random", "drought_ramp", "heatwave", "day_night_cycle", "calm", "stress_extreme", "trend_drought"]

    def __init__(self, settings_manager, callback=None):
        self._settings = settings_manager
        self._callback = callback
        self._running = False
        self._thread = None
        self._tick = 0

    def start(self, callback=None):
        if callback is not None:
            self._callback = callback
        if self._running:
            return
        self._running = True
        self._tick = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def is_active(self) -> bool:
        return self._running

    @property
    def is_running(self):
        """Alias for is_active for backwards compatibility."""
        return self._running

    def _loop(self):
        while self._running:
            speed = self._settings.get("sim_speed_sec")
            temp, light, wind = self._generate()
            self._callback(f"{temp},{light},{wind}")
            self._tick += 1
            time.sleep(speed)

    def _generate(self):
        scenario = self._settings.get("sim_scenario")
        noise = self._settings.get("sim_noise")

        # Dispatch to scenario
        scenarios = {
            "drought_ramp": self._scenario_drought_ramp,
            "heatwave": self._scenario_heatwave,
            "day_night_cycle": self._scenario_day_night,
            "calm": self._scenario_calm,
            "stress_extreme": self._scenario_stress_extreme,
            "trend_drought": self._scenario_trend_drought,
        }
        temp, light, wind = scenarios.get(scenario, self._scenario_random)()

        # Apply noise and clamp
        temp = _clamp(round(_add_noise(temp, noise), 1),
                      self._settings.get("sim_temp_min"), self._settings.get("sim_temp_max"))
        light = _clamp(int(round(_add_noise(light, noise * 10))),
                       self._settings.get("sim_light_min"), self._settings.get("sim_light_max"))
        wind = _clamp(round(_add_noise(wind, noise * 2), 1),
                      self._settings.get("sim_wind_min"), self._settings.get("sim_wind_max"))
        return temp, light, wind

    def _scenario_random(self):
        return (
            round(random.uniform(self._settings.get("sim_temp_min"), self._settings.get("sim_temp_max")), 1),
            random.randint(self._settings.get("sim_light_min"), self._settings.get("sim_light_max")),
            round(random.uniform(self._settings.get("sim_wind_min"), self._settings.get("sim_wind_max")), 1),
        )

    def _scenario_drought_ramp(self):
        t_min, t_max = self._settings.get("sim_temp_min"), self._settings.get("sim_temp_max")
        l_min, l_max = self._settings.get("sim_light_min"), self._settings.get("sim_light_max")
        w_min, w_max = self._settings.get("sim_wind_min"), self._settings.get("sim_wind_max")
        progress = min(self._tick / 120.0, 1.0)
        return (
            round(t_min + (t_max - t_min) * progress, 1),
            int(l_min + (l_max - l_min) * progress),
            round(w_min + (w_max - w_min) * progress, 1),
        )

    def _scenario_heatwave(self):
        t_max = self._settings.get("sim_temp_max")
        base_temp = t_max - 8
        temp = base_temp + 5 * math.sin(self._tick * 0.15)
        if random.random() < 0.05:
            temp += random.uniform(3, 7)
        light = 180 + 30 * math.sin(self._tick * 0.1)
        wind = 25.0 + 10 * math.sin(self._tick * 0.2)
        if random.random() < 0.1:
            wind += random.uniform(5, 15)
        return round(temp, 1), int(light), round(wind, 1)

    def _scenario_day_night(self):
        phase = (self._tick % 60) / 60.0 * 2 * math.pi
        light = 135 + 115 * math.sin(phase)
        temp = 22 + 12 * math.sin(phase - 0.3)
        wind = 15.0 + 10 * math.sin(phase + 0.8)
        return round(temp, 1), int(light), round(wind, 1)

    def _scenario_calm(self):
        return (
            round(20.0 + 2 * math.sin(self._tick * 0.05), 1),
            int(80 + 15 * math.sin(self._tick * 0.08)),
            round(8.0 + 3 * math.sin(self._tick * 0.04), 1),
        )

    def _scenario_stress_extreme(self):
        return (
            round(float(self._settings.get("sim_temp_max")), 1),
            int(self._settings.get("sim_light_max")),
            round(float(self._settings.get("sim_wind_max")), 1),
        )

    def _scenario_trend_drought(self):
        t_min, t_max = self._settings.get("sim_temp_min"), self._settings.get("sim_temp_max")
        l_min, l_max = self._settings.get("sim_light_min"), self._settings.get("sim_light_max")
        w_min, w_max = self._settings.get("sim_wind_min"), self._settings.get("sim_wind_max")
        progress = min(self._tick / 300.0, 1.0)
        return (
            round(t_min + (t_max - t_min) * progress, 1),
            int(l_min + (l_max - l_min) * progress),
            round(w_min + (w_max - w_min) * progress, 1),
        )