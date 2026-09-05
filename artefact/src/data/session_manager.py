# Session management - tracks data collection sessions with metadata

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
import pandas as pd

SESSIONS_INDEX = "sessions.json"


class SessionManager:

    def __init__(self, sessions_dir="data/sessions"):
        self._sessions_dir = sessions_dir
        self._index_path = os.path.join(sessions_dir, SESSIONS_INDEX)
        self._active_session = None
        self._readings_count = 0
        os.makedirs(self._sessions_dir, exist_ok=True)
        self._ensure_index()

    def start_session(self, source, scenario=""):
        now = datetime.now()
        session_id = now.strftime("%Y-%m-%d_%H-%M-%S")

        session = {
            "id": session_id,
            "start_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": None,
            "source": source,
            "scenario": scenario if source == "simulation" else "",
            "readings_count": 0,
            "csv_file": f"{session_id}.csv",
            "meta_file": f"{session_id}_meta.json",
        }

        self._active_session = session
        self._readings_count = 0

        csv_path = self.active_csv_path()
        from src.data.csv_manager import CSV_COLUMNS
        pd.DataFrame(columns=CSV_COLUMNS).to_csv(csv_path, index=False)

        self._write_meta({"session": session, "alerts": [], "advice": []})

        index = self._load_index()
        index.append(session)
        self._save_index(index)

        return session

    def end_session(self, alerts=None, advice=None):
        if self._active_session is None:
            return

        self._active_session["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._active_session["readings_count"] = self._readings_count

        self._write_meta({"session": self._active_session, "alerts": alerts or [], "advice": advice or []})

        index = self._load_index()
        for i, s in enumerate(index):
            if s["id"] == self._active_session["id"]:
                index[i] = self._active_session
                break
        self._save_index(index)

        self._active_session = None
        self._readings_count = 0

    def increment_readings(self):
        self._readings_count += 1

    def update_session_meta(self, alerts=None, advice=None):
        if self._active_session is None:
            return
        self._active_session["readings_count"] = self._readings_count
        self._write_meta({"session": self._active_session, "alerts": alerts or [], "advice": advice or []})

    def list_sessions(self):
        index = self._load_index()
        if self._active_session is not None:
            active_id = self._active_session["id"]
            for i, s in enumerate(index):
                if s["id"] == active_id:
                    index[i] = dict(s, readings_count=self._readings_count)
                    break
        return list(reversed(index))

    def get_session(self, session_id):
        for s in self._load_index():
            if s["id"] == session_id:
                return s
        return None

    def get_session_csv_path(self, session_id):
        return os.path.join(self._sessions_dir, f"{session_id}.csv")

    def get_session_meta_path(self, session_id):
        return os.path.join(self._sessions_dir, f"{session_id}_meta.json")

    def load_session_meta(self, session_id):
        path = self.get_session_meta_path(session_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"session": {}, "alerts": [], "advice": []}

    def delete_session(self, session_id):
        csv_path = self.get_session_csv_path(session_id)
        meta_path = self.get_session_meta_path(session_id)
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        index = [s for s in self._load_index() if s["id"] != session_id]
        self._save_index(index)
        self._save_index(index)

    def recover_orphaned_sessions(self):
        index = self._load_index()
        changed = False
        for session in index:
            if session.get("end_time") is None:
                session["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                csv_path = self.get_session_csv_path(session["id"])
                try:
                    with open(csv_path, "r", encoding="utf-8") as f:
                        session["readings_count"] = max(0, sum(1 for _ in f) - 1)
                except FileNotFoundError:
                    session["readings_count"] = 0
                changed = True
        if changed:
            self._save_index(index)

    def active_csv_path(self):
        if self._active_session is None:
            return None
        return os.path.join(self._sessions_dir, self._active_session["csv_file"])

    @property
    def active_session(self):
        return self._active_session

    @property
    def is_active(self):
        return self._active_session is not None

    @staticmethod
    def parse_microbit_log(file_path):
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()

        is_html = bool(re.search(r"<meta|<script|<html|<!doctype|FS_START", content[:2048], re.IGNORECASE))

        if is_html:
            header_pattern = re.compile(r"Time \(seconds\)[^\n]*", re.IGNORECASE)
            matches = list(header_pattern.finditer(content))
            if not matches:
                raise ValueError("Could not find CSV header in HTML file.")

            csv_start = matches[-1].start()
            csv_line_re = re.compile(r"^[\d.\-]+,")
            raw_csv_lines = []
            for line in content[csv_start:].splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if not raw_csv_lines and stripped.lower().startswith("time"):
                    raw_csv_lines.append(stripped)
                    continue
                if csv_line_re.match(stripped):
                    raw_csv_lines.append(stripped)
                elif raw_csv_lines:
                    break

            if len(raw_csv_lines) < 2:
                raise ValueError("No data rows found in micro:bit log.")

            from io import StringIO
            df = pd.read_csv(StringIO("\n".join(raw_csv_lines)))
        else:
            df = pd.read_csv(file_path, encoding_errors="replace")

        df.columns = [c.strip().lower() for c in df.columns]

        for col in df.columns:
            if "time" in col and "second" in col:
                df = df.rename(columns={col: "seconds"})
                break

        if "temperature" not in df.columns or "light" not in df.columns:
            raise ValueError(f"Missing required columns. Found: {', '.join(df.columns)}")

        return df

    def import_microbit_log(self, file_path, risk_engine=None, default_wind=15.0):
        from src.data.csv_manager import CSV_COLUMNS

        raw_df = self.parse_microbit_log(file_path)

        if "seconds" in raw_df.columns:
            try:
                elapsed = pd.to_numeric(raw_df["seconds"], errors="coerce")
                total_secs = elapsed.max() - elapsed.min()
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                anchor = file_mtime - timedelta(seconds=float(total_secs))
                timestamps = [anchor + timedelta(seconds=float(s)) for s in elapsed]
            except Exception:
                timestamps = [datetime.now()] * len(raw_df)
        else:
            timestamps = [datetime.now() + timedelta(seconds=i) for i in range(len(raw_df))]

        now = datetime.now()
        session_id = now.strftime("%Y-%m-%d_%H-%M-%S")

        session = {
            "id": session_id,
            "start_time": timestamps[0].strftime("%Y-%m-%d %H:%M:%S") if timestamps else now.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": timestamps[-1].strftime("%Y-%m-%d %H:%M:%S") if timestamps else now.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "microbit_import",
            "scenario": "",
            "readings_count": len(raw_df),
            "csv_file": f"{session_id}.csv",
            "meta_file": f"{session_id}_meta.json",
        }

        rows = []
        for i, (_, row) in enumerate(raw_df.iterrows()):
            temp = float(row["temperature"])
            light = int(row["light"])

            if risk_engine is not None:
                risk = risk_engine.calculate_risk(temp, light)
            elif "risk" in raw_df.columns and pd.notna(row.get("risk")):
                risk = str(row["risk"]).strip().upper()
            else:
                risk = ""

            rows.append({
                "timestamp": timestamps[i].strftime("%Y-%m-%d %H:%M:%S"),
                "temperature": temp,
                "light": light,
                "wind_speed": default_wind,
                "risk_level": risk,
                "source": "microbit_import",
            })

        out_df = pd.DataFrame(rows, columns=CSV_COLUMNS)
        csv_path = os.path.join(self._sessions_dir, session["csv_file"])
        out_df.to_csv(csv_path, index=False)

        meta = {"session": session, "alerts": [], "advice": []}
        meta_path = os.path.join(self._sessions_dir, session["meta_file"])
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        index = self._load_index()
        index.append(session)
        self._save_index(index)

        return session

    def _ensure_index(self):
        if not os.path.exists(self._index_path):
            self._save_index([])

    def _load_index(self):
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_index(self, index):
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    def _write_meta(self, meta):
        if self._active_session is None:
            return
        path = os.path.join(self._sessions_dir, self._active_session["meta_file"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)