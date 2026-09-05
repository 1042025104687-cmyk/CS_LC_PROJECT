"""
Tests for data_processor.py – parsing and DataFrame management.
"""

import pytest
from src.data.processor import DataProcessor


class TestParseLine:
    """Validate raw serial line parsing."""

    def test_valid_line(self):
        dp = DataProcessor()
        result = dp.parse_line("23.5,147")
        assert result is not None
        assert result["temperature"] == 23.5
        assert result["light"] == 147

    def test_valid_line_with_spaces(self):
        dp = DataProcessor()
        result = dp.parse_line("  30.0 , 200 ")
        assert result is not None
        assert result["temperature"] == 30.0
        assert result["light"] == 200

    def test_integer_temperature(self):
        dp = DataProcessor()
        result = dp.parse_line("25,100")
        assert result is not None
        assert result["temperature"] == 25.0

    def test_boundary_temperature_low(self):
        dp = DataProcessor()
        result = dp.parse_line("-40,100")
        assert result is not None
        assert result["temperature"] == -40.0

    def test_boundary_temperature_high(self):
        dp = DataProcessor()
        result = dp.parse_line("80,100")
        assert result is not None
        assert result["temperature"] == 80.0

    def test_temperature_out_of_range_high(self):
        dp = DataProcessor()
        result = dp.parse_line("81,100")
        assert result is None

    def test_temperature_out_of_range_low(self):
        dp = DataProcessor()
        result = dp.parse_line("-41,100")
        assert result is None

    def test_light_boundary_low(self):
        dp = DataProcessor()
        result = dp.parse_line("20,0")
        assert result is not None
        assert result["light"] == 0

    def test_light_boundary_high(self):
        dp = DataProcessor()
        result = dp.parse_line("20,255")
        assert result is not None
        assert result["light"] == 255

    def test_light_out_of_range(self):
        dp = DataProcessor()
        result = dp.parse_line("20,256")
        assert result is None

    def test_light_negative(self):
        dp = DataProcessor()
        result = dp.parse_line("20,-1")
        assert result is None

    def test_malformed_no_comma(self):
        dp = DataProcessor()
        assert dp.parse_line("hello") is None

    def test_three_fields_with_wind(self):
        dp = DataProcessor()
        result = dp.parse_line("25,150,20.5")
        assert result is not None
        assert result["temperature"] == 25.0
        assert result["light"] == 150
        assert result["wind_speed"] == 20.5

    def test_two_fields_wind_is_none(self):
        dp = DataProcessor()
        result = dp.parse_line("25,150")
        assert result is not None
        assert result["wind_speed"] is None

    def test_malformed_too_many_fields(self):
        dp = DataProcessor()
        assert dp.parse_line("20,100,10,extra") is None

    def test_wind_out_of_range(self):
        dp = DataProcessor()
        assert dp.parse_line("25,150,201") is None

    def test_malformed_non_numeric(self):
        dp = DataProcessor()
        assert dp.parse_line("abc,def") is None

    def test_empty_string(self):
        dp = DataProcessor()
        assert dp.parse_line("") is None

    def test_timestamp_is_set(self):
        dp = DataProcessor()
        result = dp.parse_line("25,150")
        assert result is not None
        assert "timestamp" in result


class TestProcessLine:
    """Validate that process_line parses AND stores in the DataFrame."""

    def test_process_adds_to_dataframe(self):
        dp = DataProcessor()
        dp.process_line("25,150")
        df = dp.get_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["temperature"] == 25.0
        assert df.iloc[0]["light"] == 150

    def test_process_multiple_lines(self):
        dp = DataProcessor()
        dp.process_line("20,100")
        dp.process_line("25,150")
        dp.process_line("30,200")
        df = dp.get_dataframe()
        assert len(df) == 3

    def test_process_invalid_line_ignored(self):
        dp = DataProcessor()
        dp.process_line("25,150")
        dp.process_line("invalid")
        df = dp.get_dataframe()
        assert len(df) == 1

    def test_latest_record(self):
        dp = DataProcessor()
        dp.process_line("20,100")
        dp.process_line("30,200")
        latest = dp.get_latest()
        assert latest["temperature"] == 30.0
        assert latest["light"] == 200

    def test_clear(self):
        dp = DataProcessor()
        dp.process_line("25,150")
        dp.clear()
        assert dp.get_latest() is None
        assert len(dp.get_dataframe()) == 0


class TestBufferLimit:
    """Ensure the rolling buffer caps at MAX_BUFFER."""

    def test_buffer_caps_at_limit(self):
        from src.data.processor import MAX_BUFFER
        dp = DataProcessor()
        for i in range(MAX_BUFFER + 50):
            temp = 20 + (i % 30)
            dp.process_line(f"{temp},100")
        df = dp.get_dataframe()
        assert len(df) == MAX_BUFFER

