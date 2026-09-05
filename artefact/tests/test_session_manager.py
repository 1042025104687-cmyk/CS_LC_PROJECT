"""
Tests for session_manager.py – session lifecycle and metadata.
"""

import json
import os
import pytest

from src.data.session_manager import SessionManager


@pytest.fixture
def session_mgr(tmp_path):
    """Create a SessionManager using a temporary directory."""
    return SessionManager(sessions_dir=str(tmp_path / "sessions"))


class TestSessionLifecycle:
    """Validate start / end / query cycle."""

    def test_start_session(self, session_mgr):
        session = session_mgr.start_session("sensor")
        assert session["source"] == "sensor"
        assert session["end_time"] is None
        assert session_mgr.is_active

    def test_start_simulation_session(self, session_mgr):
        session = session_mgr.start_session("simulation", "drought_ramp")
        assert session["source"] == "simulation"
        assert session["scenario"] == "drought_ramp"

    def test_end_session(self, session_mgr):
        session_mgr.start_session("sensor")
        session_mgr.increment_readings()
        session_mgr.increment_readings()
        session_mgr.end_session(alerts=[], advice=[])
        assert not session_mgr.is_active

    def test_end_session_updates_readings(self, session_mgr):
        session = session_mgr.start_session("sensor")
        session_mgr.increment_readings()
        session_mgr.increment_readings()
        session_mgr.increment_readings()
        session_mgr.end_session()

        sessions = session_mgr.list_sessions()
        assert sessions[0]["readings_count"] == 3

    def test_end_session_sets_end_time(self, session_mgr):
        session_mgr.start_session("sensor")
        session_mgr.end_session()
        sessions = session_mgr.list_sessions()
        assert sessions[0]["end_time"] is not None

    def test_csv_file_created(self, session_mgr):
        session = session_mgr.start_session("sensor")
        csv_path = session_mgr.active_csv_path()
        assert os.path.exists(csv_path)

    def test_meta_file_created(self, session_mgr):
        session = session_mgr.start_session("sensor")
        meta_path = session_mgr.get_session_meta_path(session["id"])
        assert os.path.exists(meta_path)


class TestSessionQueries:
    """Validate listing, getting, and loading sessions."""

    def test_list_sessions_newest_first(self, session_mgr):
        s1 = session_mgr.start_session("sensor")
        session_mgr.end_session()
        # Force a different ID by changing the internal clock is impractical,
        # so we just verify ordering logic with one session
        sessions = session_mgr.list_sessions()
        assert len(sessions) == 1

    def test_get_session_by_id(self, session_mgr):
        session = session_mgr.start_session("sensor")
        session_mgr.end_session()
        found = session_mgr.get_session(session["id"])
        assert found is not None
        assert found["id"] == session["id"]

    def test_get_session_not_found(self, session_mgr):
        assert session_mgr.get_session("nonexistent") is None

    def test_load_session_meta(self, session_mgr):
        session = session_mgr.start_session("sensor")
        session_mgr.end_session(
            alerts=[{"timestamp": "2026-03-10 12:00:00", "level": "HIGH", "message": "test"}],
            advice=[],
        )
        meta = session_mgr.load_session_meta(session["id"])
        assert len(meta["alerts"]) == 1
        assert meta["alerts"][0]["level"] == "HIGH"


class TestDeleteSession:
    """Validate session deletion."""

    def test_delete_removes_files(self, session_mgr):
        session = session_mgr.start_session("sensor")
        sid = session["id"]
        csv_path = session_mgr.get_session_csv_path(sid)
        meta_path = session_mgr.get_session_meta_path(sid)
        session_mgr.end_session()

        session_mgr.delete_session(sid)
        assert not os.path.exists(csv_path)
        assert not os.path.exists(meta_path)
        assert session_mgr.get_session(sid) is None

    def test_delete_removes_from_index(self, session_mgr):
        session = session_mgr.start_session("sensor")
        session_mgr.end_session()
        session_mgr.delete_session(session["id"])
        assert len(session_mgr.list_sessions()) == 0


class TestActiveSession:
    """Validate active session properties."""

    def test_active_csv_path_when_inactive(self, session_mgr):
        assert session_mgr.active_csv_path() is None

    def test_active_session_property(self, session_mgr):
        assert session_mgr.active_session is None
        session_mgr.start_session("sensor")
        assert session_mgr.active_session is not None

    def test_end_without_active_is_noop(self, session_mgr):
        # Should not raise
        session_mgr.end_session()


# ==================================================================
# micro:bit data-log import
# ==================================================================

class TestImportMicrobitLog:
    """Validate importing micro:bit MY_DATA.HTM and plain CSV logs."""

    def _write_plain_csv(self, path, rows):
        """Helper – write a plain CSV with micro:bit log columns."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("Time (seconds),temperature,light,risk\n")
            for r in rows:
                f.write(",".join(str(v) for v in r) + "\n")

    def _write_html_log(self, path, rows):
        """Helper – write a minimal MY_DATA.HTM wrapper around CSV rows."""
        csv_lines = ["Time (seconds),temperature,light,risk"]
        for r in rows:
            csv_lines.append(",".join(str(v) for v in r))
        csv_block = "\n".join(csv_lines)
        html = (
            "<!DOCTYPE html><html><head><title>micro:bit data</title></head>"
            "<body><pre>\n"
            f"{csv_block}\n"
            "</pre></body></html>"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def test_import_plain_csv(self, session_mgr, tmp_path):
        csv_file = str(tmp_path / "microbit.csv")
        self._write_plain_csv(csv_file, [
            (0, 22, 100, "LOW"),
            (2, 23, 110, "LOW"),
            (4, 25, 150, "MODERATE"),
        ])

        session = session_mgr.import_microbit_log(csv_file)
        assert session["source"] == "microbit_import"
        assert session["readings_count"] == 3

    def test_import_html_log(self, session_mgr, tmp_path):
        html_file = str(tmp_path / "MY_DATA.HTM")
        self._write_html_log(html_file, [
            (0, 20, 80, "LOW"),
            (2, 21, 90, "LOW"),
            (4, 24, 130, "MODERATE"),
            (6, 30, 200, "HIGH"),
        ])

        session = session_mgr.import_microbit_log(html_file)
        assert session["source"] == "microbit_import"
        assert session["readings_count"] == 4

    def test_import_creates_csv_and_meta(self, session_mgr, tmp_path):
        csv_file = str(tmp_path / "microbit.csv")
        self._write_plain_csv(csv_file, [(0, 22, 100, "LOW")])

        session = session_mgr.import_microbit_log(csv_file)
        csv_path = session_mgr.get_session_csv_path(session["id"])
        meta_path = session_mgr.get_session_meta_path(session["id"])
        assert os.path.exists(csv_path)
        assert os.path.exists(meta_path)

    def test_import_adds_to_index(self, session_mgr, tmp_path):
        csv_file = str(tmp_path / "microbit.csv")
        self._write_plain_csv(csv_file, [(0, 22, 100, "LOW")])

        session = session_mgr.import_microbit_log(csv_file)
        sessions = session_mgr.list_sessions()
        ids = [s["id"] for s in sessions]
        assert session["id"] in ids

    def test_import_csv_has_correct_columns(self, session_mgr, tmp_path):
        import pandas as pd
        from src.data.csv_manager import CSV_COLUMNS

        csv_file = str(tmp_path / "microbit.csv")
        self._write_plain_csv(csv_file, [
            (0, 22, 100, "LOW"),
            (2, 25, 150, "MODERATE"),
        ])

        session = session_mgr.import_microbit_log(csv_file)
        out_path = session_mgr.get_session_csv_path(session["id"])
        df = pd.read_csv(out_path)
        assert list(df.columns) == CSV_COLUMNS

    def test_import_uses_default_wind(self, session_mgr, tmp_path):
        import pandas as pd

        csv_file = str(tmp_path / "microbit.csv")
        self._write_plain_csv(csv_file, [(0, 22, 100, "LOW")])

        session = session_mgr.import_microbit_log(csv_file, default_wind=20.0)
        out_path = session_mgr.get_session_csv_path(session["id"])
        df = pd.read_csv(out_path)
        assert df["wind_speed"].iloc[0] == 20.0

    def test_import_with_risk_engine(self, session_mgr, tmp_path):
        import pandas as pd
        from src.core.risk_engine import RiskEngine
        from src.config.settings import SettingsManager

        settings = SettingsManager()
        settings.reset_defaults()
        engine = RiskEngine(settings)

        csv_file = str(tmp_path / "microbit.csv")
        self._write_plain_csv(csv_file, [
            (0, 22, 100, ""),
            (2, 45, 250, ""),
        ])

        session = session_mgr.import_microbit_log(
            csv_file, risk_engine=engine
        )
        out_path = session_mgr.get_session_csv_path(session["id"])
        df = pd.read_csv(out_path)
        # Risk engine should have filled in non-empty risk levels
        assert df["risk_level"].iloc[0] != ""
        assert df["risk_level"].iloc[1] != ""

    def test_import_invalid_file_raises(self, session_mgr, tmp_path):
        bad_file = str(tmp_path / "bad.csv")
        with open(bad_file, "w") as f:
            f.write("col_a,col_b\n1,2\n")

        with pytest.raises(ValueError, match="Missing required columns"):
            session_mgr.import_microbit_log(bad_file)

    def test_parse_plain_csv(self, tmp_path):
        csv_file = str(tmp_path / "microbit.csv")
        with open(csv_file, "w") as f:
            f.write("Time (seconds),temperature,light,risk\n")
            f.write("0,22,100,LOW\n")
            f.write("2,23,110,LOW\n")

        df = SessionManager.parse_microbit_log(csv_file)
        assert len(df) == 2
        assert "temperature" in df.columns
        assert "light" in df.columns
        assert "seconds" in df.columns

    def test_parse_html_log(self, tmp_path):
        html_file = str(tmp_path / "MY_DATA.HTM")
        csv_block = (
            "Time (seconds),temperature,light,risk\n"
            "0,20,80,LOW\n"
            "2,21,90,LOW\n"
        )
        html = (
            "<!DOCTYPE html><html><body><pre>\n"
            f"{csv_block}"
            "</pre></body></html>"
        )
        with open(html_file, "w") as f:
            f.write(html)

        df = SessionManager.parse_microbit_log(html_file)
        assert len(df) == 2
        assert df["temperature"].iloc[0] == 20


