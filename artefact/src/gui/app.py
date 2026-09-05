# Main application controller

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from src.io.serial_manager import SerialManager
from src.data.processor import DataProcessor
from src.core.risk_engine import RiskEngine
from src.core.alert_manager import AlertManager
from src.data.csv_manager import CsvManager
from src.config.settings import SettingsManager
from src.io.simulator import Simulator
from src.core.feedback_engine import FeedbackEngine
from src.data.session_manager import SessionManager
from src.core.wildfire_model import WildfireModel

from src.gui.frames.dashboard import DashboardFrame
from src.gui.frames.graph import GraphFrame
from src.gui.frames.alerts import AlertsFrame
from src.gui.frames.settings import SettingsFrame
from src.gui.frames.feedback import FeedbackFrame
from src.gui.frames.history import HistoryFrame
from src.gui.frames.model import ModelFrame


class App:

    TITLE = "Drought Risk Prevention System"
    MIN_SIZE = (950, 680)

    def __init__(self):
        self.settings = SettingsManager()
        self.serial = SerialManager()
        self.processor = DataProcessor()
        self.risk_engine = RiskEngine(self.settings)
        self.alert_mgr = AlertManager(max_alerts=self.settings.get("max_alerts"))
        self.csv_mgr = CsvManager(csv_path=self.settings.get("csv_path"))
        self.simulator = Simulator(self.settings, callback=self._on_serial_line)
        self.feedback_engine = FeedbackEngine(self.settings)
        self.wildfire_model = WildfireModel(
            default_wind=self.settings.get("default_wind_speed"),
            settings_manager=self.settings,
        )
        self.session_mgr = SessionManager(sessions_dir=self.settings.get("sessions_dir"))
        self.session_mgr.recover_orphaned_sessions()

        self._data_lock = threading.Lock()
        self._pending_lines = []

        self.root = tk.Tk()
        self.root.title(self.TITLE)
        self.root.minsize(*self.MIN_SIZE)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.dashboard = DashboardFrame(self.notebook)
        self.graph = GraphFrame(self.notebook)
        self.alerts_view = AlertsFrame(self.notebook)
        self.feedback_view = FeedbackFrame(self.notebook)
        self.history_view = HistoryFrame(
            self.notebook, self.session_mgr,
            risk_engine=self.risk_engine, settings=self.settings,
        )
        self.model_view = ModelFrame(self.notebook, self.settings)
        self.settings_view = SettingsFrame(self.notebook, self.settings, self.serial)

        self.notebook.add(self.dashboard, text="  📊 Dashboard  ")
        self.notebook.add(self.graph, text="  📈 Trends  ")
        self.notebook.add(self.alerts_view, text="  🔔 Alerts  ")
        self.notebook.add(self.feedback_view, text="  💡 Advice  ")
        self.notebook.add(self.model_view, text="  🔥 Model  ")
        self.notebook.add(self.history_view, text="  📜 History  ")
        self.notebook.add(self.settings_view, text="  ⚙ Settings  ")

        self.settings_view.connect_btn.config(command=self._connect)
        self.settings_view.disconnect_btn.config(command=self._disconnect)
        self.alerts_view.clear_btn.config(command=self._clear_alerts)
        self.feedback_view.clear_btn.config(command=self._clear_advice)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._current_risk = "LOW"
        self._poll_interval = self.settings.get("polling_interval_normal_ms")
        self.root.after(self._poll_interval, self._poll)
        self.root.after(500, self._auto_connect)

    def _auto_connect(self):
        if self.serial.is_connected or self.simulator.is_running:
            return

        ports = SerialManager.list_ports()
        if not ports:
            return

        saved_port = self.settings.get("com_port")
        port = saved_port if saved_port in ports else ports[0]

        self.settings_view.port_combo["values"] = ports
        self.settings_view.port_combo.set(port)

        try:
            baud = int(self.settings_view.baud_var.get())
            self.session_mgr.start_session("sensor")
            self.csv_mgr.set_active_file(self.session_mgr.active_csv_path())
            self.alert_mgr.clear_history()
            self.feedback_engine.clear_history()
            self.processor.clear()
            self.risk_engine.reset()
            self.wildfire_model.reset_weights()

            self.serial.connect(port, baud, callback=self._on_serial_line)
            self.settings_view.update_connection_status(True)
            self.dashboard.show_simulation_banner(False)
        except Exception:
            if self.session_mgr.is_active:
                self.session_mgr.end_session()

    def _connect(self):
        if self.settings_view.simulate_var.get():
            scenario = self.settings_view.sim_scenario_var.get()
            self.session_mgr.start_session("simulation", scenario)
            self.csv_mgr.set_active_file(self.session_mgr.active_csv_path())
            self.alert_mgr.clear_history()
            self.feedback_engine.clear_history()
            self.processor.clear()
            self.risk_engine.reset()
            self.wildfire_model.reset_weights()

            self.simulator.start()
            self.settings_view.update_connection_status(True)
            self.dashboard.show_simulation_banner(True)
            return

        port = self.settings_view.port_combo.get()
        if not port:
            messagebox.showwarning("Connection", "Please select a COM port.")
            return

        try:
            baud = int(self.settings_view.baud_var.get())
            self.session_mgr.start_session("sensor")
            self.csv_mgr.set_active_file(self.session_mgr.active_csv_path())
            self.alert_mgr.clear_history()
            self.feedback_engine.clear_history()
            self.processor.clear()
            self.risk_engine.reset()
            self.wildfire_model.reset_weights()

            self.serial.connect(port, baud, callback=self._on_serial_line)
            self.settings_view.update_connection_status(True)
            self.dashboard.show_simulation_banner(False)
        except Exception as e:
            self.session_mgr.end_session()
            messagebox.showerror("Connection Error", str(e))

    def _disconnect(self):
        self.simulator.stop()
        self.serial.disconnect()

        if self.session_mgr.is_active:
            self.session_mgr.end_session(
                alerts=self.alert_mgr.history_to_dicts(),
                advice=self.feedback_engine.history_to_dicts(),
            )

        self.settings_view.update_connection_status(False)
        self.dashboard.show_simulation_banner(False)

    def _on_serial_line(self, line):
        with self._data_lock:
            self._pending_lines.append(line)


    def _poll(self):
        with self._data_lock:
            lines = list(self._pending_lines)
            self._pending_lines.clear()

        new_record = None
        for line in lines:
            if record := self.processor.process_line(line):
                new_record = record

                wind = record.get("wind_speed") or self.settings.get("default_wind_speed")
                record["wind_speed"] = wind

                risk = self.risk_engine.calculate_risk(record["temperature"], record["light"])
                self.serial.send(f"RISK:{risk}\n")
                self.alert_mgr.evaluate(risk, record["temperature"], record["light"])

                source = "simulation" if self.simulator.is_running else "sensor"
                self.csv_mgr.append_row(
                    record["timestamp"], record["temperature"], record["light"],
                    risk, source, wind_speed=record["wind_speed"],
                )
                self.session_mgr.increment_readings()

        if lines and self.session_mgr.is_active:
            self.session_mgr.update_session_meta(
                alerts=self.alert_mgr.history_to_dicts(),
                advice=self.feedback_engine.history_to_dicts(),
            )

        if new_record:
            risk = self.risk_engine.calculate_risk(new_record["temperature"], new_record["light"])
            colour = RiskEngine.risk_colour(risk)
            self._current_risk = risk

            new_interval = (self.settings.get("polling_interval_fast_ms")
                            if risk in ("HIGH", "CRITICAL")
                            else self.settings.get("polling_interval_normal_ms"))
            if new_interval != self._poll_interval:
                self._poll_interval = new_interval

            self.serial.send(f"RATE:{self._poll_interval}\n")
            self.wildfire_model.adapt_weights(self.processor.get_dataframe())
            self.risk_engine.auto_adjust_thresholds()

            advice_items = self.feedback_engine.generate_advice(
                risk, new_record, self.processor.get_dataframe()
            )
            model_result = self.wildfire_model.predict(
                new_record["temperature"], new_record["light"], new_record.get("wind_speed"),
            )

            adaptive_status = {
                "weights": self.wildfire_model.get_weights(),
                "escalated": self.risk_engine.is_escalated,
            }

            self.dashboard.update_readings(
                new_record, risk, colour, advice_items,
                poll_interval=self._poll_interval, adaptive_status=adaptive_status,
            )
            self.model_view.update_live_prediction(model_result)
            self.alerts_view.refresh(self.alert_mgr.get_history())

            current_tab = self.notebook.index(self.notebook.select())
            if current_tab == 3:
                self.feedback_view.refresh(self.feedback_engine.get_history())

        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:
            self.graph.update_graph(self.processor.get_dataframe())

        self.root.after(self._poll_interval, self._poll)

    def _clear_alerts(self):
        self.alert_mgr.clear_history()
        self.alerts_view.refresh([])

    def _clear_advice(self):
        self.feedback_engine.clear_history()
        self.feedback_view.refresh([])

    def _on_tab_changed(self, _event):
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 5:
            self.history_view.refresh_session_list()

    def _on_close(self):
        if self.session_mgr.is_active:
            self.session_mgr.end_session(
                alerts=self.alert_mgr.history_to_dicts(),
                advice=self.feedback_engine.history_to_dicts(),
            )
        self.simulator.stop()
        self.serial.disconnect()
        self.root.destroy()

    def run(self):
        self.root.mainloop()