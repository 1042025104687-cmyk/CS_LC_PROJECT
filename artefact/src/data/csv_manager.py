# CSV logging and export

from __future__ import annotations

import os
from datetime import datetime
import pandas as pd

CSV_COLUMNS = ["timestamp", "temperature", "light", "wind_speed", "risk_level", "source"]


class CsvManager:

    def __init__(self, csv_path="data/sensor_log.csv"):
        self._csv_path = csv_path
        self._ensure_file()

    def set_active_file(self, csv_path):
        self._csv_path = csv_path

    @property
    def active_path(self):
        return self._csv_path

    def append_row(self, timestamp, temperature, light, risk_level, source="sensor", wind_speed=None):
        row = pd.DataFrame([{
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature": temperature,
            "light": light,
            "wind_speed": wind_speed if wind_speed is not None else "",
            "risk_level": risk_level,
            "source": source,
        }])
        row.to_csv(self._csv_path, mode="a", header=False, index=False)

    def load_history(self):
        return self.load_file(self._csv_path)

    @staticmethod
    def load_file(csv_path):
        try:
            if not os.path.exists(csv_path):
                return pd.DataFrame(columns=CSV_COLUMNS)

            with open(csv_path, encoding="utf-8") as fh:
                first_line = fh.readline().strip()
                if not first_line:
                    return pd.DataFrame(columns=CSV_COLUMNS)

                header_fields = first_line.split(",")
                max_fields = len(header_fields)
                for line in fh:
                    n = len(line.strip().split(","))
                    if n > max_fields:
                        max_fields = n
                        break

            KNOWN_HEADERS = {
                4: ["timestamp", "temperature", "light", "risk_level"],
                5: ["timestamp", "temperature", "light", "risk_level", "source"],
                6: ["timestamp", "temperature", "light", "wind_speed", "risk_level", "source"],
            }

            col_names = KNOWN_HEADERS.get(max_fields, header_fields)

            if max_fields > len(header_fields):
                df = pd.read_csv(csv_path, names=col_names, skiprows=1, engine="python")
            else:
                df = pd.read_csv(csv_path)

            if df.empty:
                return pd.DataFrame(columns=CSV_COLUMNS)

            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

            if "wind_speed" not in df.columns:
                pos = df.columns.get_loc("light") + 1 if "light" in df.columns else len(df.columns)
                df.insert(pos, "wind_speed", float("nan"))

            if "source" not in df.columns:
                df["source"] = "sensor"

            return df

        except (pd.errors.EmptyDataError, FileNotFoundError):
            return pd.DataFrame(columns=CSV_COLUMNS)

    def export_range(self, start, end, output_path, csv_path=None):
        df = self.load_file(csv_path) if csv_path else self.load_history()
        if df.empty:
            return
        mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
        df.loc[mask].to_csv(output_path, index=False)

    def _ensure_file(self):
        directory = os.path.dirname(self._csv_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self._csv_path):
            pd.DataFrame(columns=CSV_COLUMNS).to_csv(self._csv_path, index=False)