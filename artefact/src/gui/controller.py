# Application controller - coordinates data flow and business logic

from __future__ import annotations

import threading
from typing import Callable, Optional, Any

from src.config import SettingsManager
from src.core import RiskEngine, AlertManager, FeedbackEngine, WildfireModel
from src.data import DataProcessor, CsvManager, SessionManager
from src.io import SerialManager, Simulator


class Controller:
    """
    Orchestrates data flow between I/O, processing, and risk engines.
    
    Extracts business logic coordination from the GUI App, making it
    testable and allowing the App to focus purely on UI concerns.
    """

    def __init__(
        self,
        on_reading: Optional[Callable[[dict], None]] = None,
        on_connection_change: Optional[Callable[[bool, bool], None]] = None,
    ):
        """
        Initialize controller with all service dependencies.
        
        Args:
            on_reading: Callback(record_info) when new sensor reading processed
            on_connection_change: Callback(is_connected, is_simulation) on connect/disconnect
        """
        # Callbacks for UI notification
        self._on_reading = on_reading
        self._on_connection_change = on_connection_change

        # Core services
        self.settings = SettingsManager()
        self.processor = DataProcessor()
        self.risk_engine = RiskEngine(self.settings)
        self.alert_mgr = AlertManager(max_alerts=self.settings.get("max_alerts"))
        self.feedback_engine = FeedbackEngine(self.settings)
        self.wildfire_model = WildfireModel(
            default_wind=self.settings.get("default_wind_speed"),
            settings_manager=self.settings,
        )

        # Data persistence
        self.csv_mgr = CsvManager(csv_path=self.settings.get("csv_path"))
        self.session_mgr = SessionManager(sessions_dir=self.settings.get("sessions_dir"))
        self.session_mgr.recover_orphaned_sessions()

        # I/O sources
        self.serial = SerialManager()
        self.simulator = Simulator(self.settings, callback=self._on_data_line)

        # Thread-safe line buffer
        self._data_lock = threading.Lock()
        self._pending_lines: List[str] = []

        # State
        self._current_risk = "LOW"
        self._poll_interval = self.settings.get("polling_interval_normal_ms")
        self._is_simulation = False

    @property
    def current_risk(self) -> str:
        return self._current_risk

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def is_connected(self) -> bool:
        return self.serial.is_connected or self.simulator.is_running

    @property
    def is_simulation(self) -> bool:
        return self._is_simulation

    def list_serial_ports(self) -> List[str]:
        return SerialManager.list_ports()

    def connect_serial(self, port: str, baud: int = 115200) -> None:
        """Connect to a real sensor via serial port."""
        self._reset_for_new_session()
        self.session_mgr.start_session("sensor")
        self.csv_mgr.set_active_file(self.session_mgr.active_csv_path())

        self.serial.connect(port, baud, callback=self._on_data_line)
        self._is_simulation = False

        if self._on_connection_change:
            self._on_connection_change(True, False)

    def connect_simulator(self, scenario: str = "random") -> None:
        """Start the data simulator."""
        self._reset_for_new_session()
        self.session_mgr.start_session("simulation", scenario)
        self.csv_mgr.set_active_file(self.session_mgr.active_csv_path())

        self.simulator.start()
        self._is_simulation = True

        if self._on_connection_change:
            self._on_connection_change(True, True)

    def disconnect(self) -> None:
        """Disconnect from current data source and end session."""
        self.simulator.stop()
        self.serial.disconnect()

        if self.session_mgr.is_active:
            self.session_mgr.end_session(
                alerts=self.alert_mgr.history_to_dicts(),
                advice=self.feedback_engine.history_to_dicts(),
            )

        self._is_simulation = False

        if self._on_connection_change:
            self._on_connection_change(False, False)

    def auto_connect(self) -> bool:
        """
        Attempt to auto-connect to a serial port.
        Returns True if connection established.
        """
        if self.is_connected:
            return True

        ports = self.list_serial_ports()
        if not ports:
            return False

        saved_port = self.settings.get("com_port")
        port = saved_port if saved_port in ports else ports[0]

        try:
            baud = self.settings.get("baud_rate")
            self.connect_serial(port, baud)
            return True
        except Exception:
            if self.session_mgr.is_active:
                self.session_mgr.end_session()
            return False

    def _reset_for_new_session(self) -> None:
        """Clear state for a fresh session."""
        self.alert_mgr.clear_history()
        self.feedback_engine.clear_history()
        self.processor.clear()
        self.risk_engine.reset()
        self.wildfire_model.reset_weights()
        self._current_risk = "LOW"
        self._poll_interval = self.settings.get("polling_interval_normal_ms")

    def _on_data_line(self, line: str) -> None:
        """Callback from serial/simulator - thread-safe buffering."""
        with self._data_lock:
            self._pending_lines.append(line)

    def process_pending_data(self) -> Optional[dict]:
        """
        Process buffered sensor lines and return info about latest reading.
        
        Should be called periodically (e.g., on UI poll timer).
        Returns dict with reading info if new data processed, else None.
        """
        with self._data_lock:
            lines = list(self._pending_lines)
            self._pending_lines.clear()

        if not lines:
            return None

        new_record = None
        for line in lines:
            if record := self.processor.process_line(line):
                new_record = record

                # Ensure wind speed
                wind = record.get("wind_speed") or self.settings.get("default_wind_speed")
                record["wind_speed"] = wind

                # Calculate risk
                risk = self.risk_engine.calculate_risk(
                    record["temperature"], record["light"]
                )

                # Send feedback to device
                self.serial.send(f"RISK:{risk}\n")

                # Generate alerts
                self.alert_mgr.evaluate(risk, record["temperature"], record["light"])

                # Log to CSV
                source = "simulation" if self.simulator.is_running else "sensor"
                self.csv_mgr.append_row(
                    record["timestamp"],
                    record["temperature"],
                    record["light"],
                    risk,
                    source,
                    wind_speed=record["wind_speed"],
                )
                self.session_mgr.increment_readings()

        # Update session metadata
        if lines and self.session_mgr.is_active:
            self.session_mgr.update_session_meta(
                alerts=self.alert_mgr.history_to_dicts(),
                advice=self.feedback_engine.history_to_dicts(),
            )

        if not new_record:
            return None

        # Process the latest reading
        risk = self.risk_engine.calculate_risk(
            new_record["temperature"], new_record["light"]
        )
        colour = RiskEngine.risk_colour(risk)
        self._current_risk = risk

        # Adjust polling interval based on risk
        new_interval = (
            self.settings.get("polling_interval_fast_ms")
            if risk in ("HIGH", "CRITICAL")
            else self.settings.get("polling_interval_normal_ms")
        )
        if new_interval != self._poll_interval:
            self._poll_interval = new_interval
            self.serial.send(f"RATE:{self._poll_interval}\n")

        # Adaptive adjustments
        df = self.processor.get_dataframe()
        self.wildfire_model.adapt_weights(df)
        self.risk_engine.auto_adjust_thresholds()

        # Generate advice
        advice_items = self.feedback_engine.generate_advice(risk, new_record, df)

        # Model prediction
        model_result = self.wildfire_model.predict(
            new_record["temperature"],
            new_record["light"],
            new_record.get("wind_speed"),
        )

        result = {
            "record": new_record,
            "risk": risk,
            "colour": colour,
            "advice": advice_items,
            "model_result": model_result,
            "poll_interval": self._poll_interval,
            "adaptive_status": {
                "weights": self.wildfire_model.get_weights(),
                "escalated": self.risk_engine.is_escalated,
            },
        }

        if self._on_reading:
            self._on_reading(result)

        return result

    def get_dataframe(self):
        """Get current sensor data as DataFrame."""
        return self.processor.get_dataframe()

    def get_alerts(self):
        """Get alert history."""
        return self.alert_mgr.get_history()

    def get_advice(self):
        """Get advice history."""
        return self.feedback_engine.get_history()

    def clear_alerts(self) -> None:
        """Clear alert history."""
        self.alert_mgr.clear_history()

    def clear_advice(self) -> None:
        """Clear advice history."""
        self.feedback_engine.clear_history()

    def shutdown(self) -> None:
        """Clean shutdown - end session and disconnect."""
        if self.session_mgr.is_active:
            self.session_mgr.end_session(
                alerts=self.alert_mgr.history_to_dicts(),
                advice=self.feedback_engine.history_to_dicts(),
            )
        self.simulator.stop()
        self.serial.disconnect()