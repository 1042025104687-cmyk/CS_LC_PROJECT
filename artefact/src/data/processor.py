# Parses sensor data and maintains rolling buffer

from __future__ import annotations

from datetime import datetime
import pandas as pd

MAX_BUFFER = 500


class DataProcessor:

    def __init__(self):
        self._df = pd.DataFrame({
            "timestamp": pd.Series(dtype="datetime64[ns]"),
            "temperature": pd.Series(dtype="float64"),
            "light": pd.Series(dtype="int64"),
            "wind_speed": pd.Series(dtype="float64")
        })
        self._latest = None

    def parse_line(self, line):
        try:
            parts = line.split(",")
            if len(parts) not in (2, 3):
                return None

            temp = float(parts[0].strip())
            light = int(parts[1].strip())

            if not (-40 <= temp <= 80) or not (0 <= light <= 255):
                return None

            wind_speed = None
            if len(parts) == 3:
                wind_speed = float(parts[2].strip())
                if not (0 <= wind_speed <= 200):
                    return None

            return {"timestamp": datetime.now(), "temperature": temp, "light": light, "wind_speed": wind_speed}
        except (ValueError, IndexError):
            return None

    def add_record(self, record):
        self._latest = record
        self._df = pd.concat([self._df, pd.DataFrame([record])], ignore_index=True)
        if len(self._df) > MAX_BUFFER:
            self._df = self._df.iloc[-MAX_BUFFER:]

    def process_line(self, line):
        if record := self.parse_line(line):
            self.add_record(record)
            return record
        return None

    def get_latest(self):
        return self._latest

    def get_dataframe(self):
        return self._df.copy()

    def clear(self):
        self._df = pd.DataFrame({
            "timestamp": pd.Series(dtype="datetime64[ns]"),
            "temperature": pd.Series(dtype="float64"),
            "light": pd.Series(dtype="int64"),
            "wind_speed": pd.Series(dtype="float64")
        })
        self._latest = None