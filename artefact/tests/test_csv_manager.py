"""
Tests for csv_manager.py – CSV read/write and export.
"""

import os
import tempfile
import pytest
from datetime import datetime

import pandas as pd

from src.data.csv_manager import CsvManager, CSV_COLUMNS


@pytest.fixture
def tmp_csv(tmp_path):
    """Create a CsvManager pointing at a temporary CSV file."""
    csv_path = str(tmp_path / "test_log.csv")
    return CsvManager(csv_path=csv_path)


class TestAppendAndLoad:
    """Validate writing and reading back rows."""

    def test_append_single_row(self, tmp_csv):
        ts = datetime(2026, 3, 10, 12, 0, 0)
        tmp_csv.append_row(ts, 25.0, 150, "MODERATE", "sensor", wind_speed=15.0)
        df = tmp_csv.load_history()
        assert len(df) == 1
        assert df.iloc[0]["temperature"] == 25.0
        assert df.iloc[0]["light"] == 150
        assert df.iloc[0]["risk_level"] == "MODERATE"
        assert df.iloc[0]["source"] == "sensor"

    def test_append_row_without_wind(self, tmp_csv):
        ts = datetime(2026, 3, 10, 12, 0, 0)
        tmp_csv.append_row(ts, 25.0, 150, "MODERATE", "sensor")
        df = tmp_csv.load_history()
        assert len(df) == 1

    def test_append_multiple_rows(self, tmp_csv):
        for i in range(5):
            ts = datetime(2026, 3, 10, 12, i, 0)
            tmp_csv.append_row(ts, 20.0 + i, 100 + i * 10, "LOW", "simulation",
                               wind_speed=10.0 + i)
        df = tmp_csv.load_history()
        assert len(df) == 5

    def test_columns_match(self, tmp_csv):
        ts = datetime(2026, 3, 10, 12, 0, 0)
        tmp_csv.append_row(ts, 25.0, 150, "MODERATE", "sensor", wind_speed=15.0)
        df = tmp_csv.load_history()
        assert list(df.columns) == CSV_COLUMNS


class TestLoadFile:
    """Validate static file loading."""

    def test_load_nonexistent_file(self):
        df = CsvManager.load_file("nonexistent_file.csv")
        assert df.empty
        assert list(df.columns) == CSV_COLUMNS

    def test_load_empty_file(self, tmp_path):
        empty = tmp_path / "empty.csv"
        pd.DataFrame(columns=CSV_COLUMNS).to_csv(str(empty), index=False)
        df = CsvManager.load_file(str(empty))
        assert df.empty

    def test_load_old_csv_without_wind_column(self, tmp_path):
        """Old CSV files that lack wind_speed should get NaN column added."""
        old_csv = tmp_path / "old.csv"
        old_columns = ["timestamp", "temperature", "light", "risk_level", "source"]
        pd.DataFrame({
            "timestamp": ["2026-03-10 12:00:00"],
            "temperature": [25.0],
            "light": [150],
            "risk_level": ["LOW"],
            "source": ["sensor"],
        }).to_csv(str(old_csv), index=False)
        df = CsvManager.load_file(str(old_csv))
        assert "wind_speed" in df.columns
        assert pd.isna(df.iloc[0]["wind_speed"])


class TestExportRange:
    """Validate date-range filtering and export."""

    def test_export_filters_correctly(self, tmp_csv, tmp_path):
        # Write 5 rows spanning 5 minutes
        for i in range(5):
            ts = datetime(2026, 3, 10, 12, i, 0)
            tmp_csv.append_row(ts, 20.0 + i, 100, "LOW", "sensor")

        output = str(tmp_path / "export.csv")
        start = datetime(2026, 3, 10, 12, 1, 0)
        end = datetime(2026, 3, 10, 12, 3, 0)
        tmp_csv.export_range(start, end, output)

        df = pd.read_csv(output, parse_dates=["timestamp"])
        assert len(df) == 3  # minutes 1, 2, 3


class TestSetActiveFile:
    """Validate switching the active CSV path."""

    def test_set_active_file(self, tmp_path):
        path1 = str(tmp_path / "a.csv")
        path2 = str(tmp_path / "b.csv")
        mgr = CsvManager(csv_path=path1)
        assert mgr.active_path == path1
        mgr.set_active_file(path2)
        assert mgr.active_path == path2

