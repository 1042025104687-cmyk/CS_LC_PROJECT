# Session browser and historical review

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import shutil

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import pandas as pd

from src.data.csv_manager import CsvManager


class HistoryFrame(ttk.Frame):

    def __init__(self, parent, session_manager, risk_engine=None, settings=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._session_mgr = session_manager
        self._risk_engine = risk_engine
        self._settings = settings
        self._sessions = []
        self._selected_id = None
        self._build_widgets()

    def _build_widgets(self):
        ttk.Label(
            self, text="Session History", font=("Helvetica", 18, "bold")
        ).pack(pady=(15, 5))
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # ---- Top toolbar ----
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=20, pady=5)

        ttk.Label(toolbar, text="Session:").pack(side="left", padx=(0, 5))
        self.session_combo = ttk.Combobox(
            toolbar, state="readonly", width=45
        )
        self.session_combo.pack(side="left", padx=5)
        self.session_combo.bind("<<ComboboxSelected>>", self._on_session_selected)

        self.refresh_btn = ttk.Button(
            toolbar, text="↻ Refresh", command=self.refresh_session_list
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.import_btn = ttk.Button(
            toolbar, text="📥 Import from micro:bit",
            command=self._import_microbit_log
        )
        self.import_btn.pack(side="left", padx=5)

        self.export_btn = ttk.Button(
            toolbar, text="📁 Export CSV", command=self._export_session
        )
        self.export_btn.pack(side="right", padx=5)

        self.delete_btn = ttk.Button(
            toolbar, text="🗑 Delete", command=self._delete_session
        )
        self.delete_btn.pack(side="right", padx=5)

        # ---- Main paned window (top: stats+table, bottom: chart) ----
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=20, pady=5)

        # ---- Upper section: stats + data table ----
        upper = ttk.Frame(paned)
        paned.add(upper, weight=3)

        # Stats panel
        stats_frame = ttk.LabelFrame(upper, text="Session Summary", padding=10)
        stats_frame.pack(fill="x", pady=(0, 5))

        self.stats_label = ttk.Label(
            stats_frame, text="Select a session to view its summary.",
            wraplength=800, justify="left"
        )
        self.stats_label.pack(anchor="w")

        # Alert / advice counts
        self.alert_stats_label = ttk.Label(
            stats_frame, text="", wraplength=800, justify="left"
        )
        self.alert_stats_label.pack(anchor="w", pady=(3, 0))

        # Data table
        table_frame = ttk.Frame(upper)
        table_frame.pack(fill="both", expand=True)

        columns = ("time", "temp", "light", "risk", "source")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=10
        )
        self.tree.heading("time", text="Timestamp")
        self.tree.heading("temp", text="Temp (°C)")
        self.tree.heading("light", text="Light")
        self.tree.heading("risk", text="Risk")
        self.tree.heading("source", text="Source")
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("temp", width=90, anchor="center")
        self.tree.column("light", width=80, anchor="center")
        self.tree.column("risk", width=90, anchor="center")
        self.tree.column("source", width=90, anchor="center")

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Colour-code risk rows
        self.tree.tag_configure("low", background="#d5f5e3")
        self.tree.tag_configure("moderate", background="#fef9e7")
        self.tree.tag_configure("high", background="#fdebd0")
        self.tree.tag_configure("critical", background="#fadbd8")

        # ---- Lower section: chart ----
        lower = ttk.Frame(paned)
        paned.add(lower, weight=2)

        self._fig = Figure(figsize=(8, 3), dpi=100, tight_layout=True)
        self._ax_temp = self._fig.add_subplot(121)
        self._ax_light = self._fig.add_subplot(122)

        self._canvas = FigureCanvasTkAgg(self._fig, master=lower)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Session list management
    # ------------------------------------------------------------------

    def refresh_session_list(self):
        """Reload the session dropdown from SessionManager."""
        self._sessions = self._session_mgr.list_sessions()
        display = []
        for s in self._sessions:
            start = s.get("start_time", "?")
            source = s.get("source", "?")
            count = s.get("readings_count", 0)
            end = s.get("end_time")
            status = "✔" if end else "▶ active"
            label = f"{start}  |  {source}  |  {count} readings  {status}"
            display.append(label)

        self.session_combo["values"] = display
        if display:
            self.session_combo.current(0)
            self._on_session_selected(None)
        else:
            self.session_combo.set("")
            self._clear_display()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_session_selected(self, _event):
        """Load the selected session's data."""
        idx = self.session_combo.current()
        if idx < 0 or idx >= len(self._sessions):
            return

        session = self._sessions[idx]
        self._selected_id = session["id"]

        # Load CSV
        csv_path = self._session_mgr.get_session_csv_path(session["id"])
        df = CsvManager.load_file(csv_path)

        # Load meta (alerts + advice)
        meta = self._session_mgr.load_session_meta(session["id"])

        self._update_stats(session, df, meta)
        self._update_table(df)
        self._update_chart(df)

    def _export_session(self):
        """Export the selected session's CSV to a user-chosen location."""
        if not self._selected_id:
            messagebox.showwarning("Export", "No session selected.")
            return

        src = self._session_mgr.get_session_csv_path(self._selected_id)
        dest = filedialog.asksaveasfilename(
            title="Export Session CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"session_{self._selected_id}.csv",
        )
        if dest:
            shutil.copy2(src, dest)
            messagebox.showinfo("Export", f"Session exported to:\n{dest}")

    def _delete_session(self):
        """Delete the selected session after confirmation."""
        if not self._selected_id:
            messagebox.showwarning("Delete", "No session selected.")
            return

        if messagebox.askyesno(
            "Delete Session",
            f"Permanently delete session {self._selected_id}?\n"
            "This removes all CSV and metadata files.",
        ):
            self._session_mgr.delete_session(self._selected_id)
            self._selected_id = None
            self.refresh_session_list()

    def _import_microbit_log(self):
        """Import a micro:bit MY_DATA.HTM (or CSV) as a new session."""
        file_path = filedialog.askopenfilename(
            title="Select micro:bit data log",
            filetypes=[
                ("micro:bit data log", "*.htm *.html *.csv"),
                ("HTML files", "*.htm *.html"),
                ("CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return

        try:
            # Determine default wind speed from settings if available
            default_wind = 15.0
            if self._settings is not None:
                default_wind = self._settings.get("default_wind_speed")

            session = self._session_mgr.import_microbit_log(
                file_path,
                risk_engine=self._risk_engine,
                default_wind=default_wind,
            )
            count = session.get("readings_count", 0)
            messagebox.showinfo(
                "Import Successful",
                f"Imported {count} readings from micro:bit log.\n"
                f"Session: {session['id']}",
            )
            self.refresh_session_list()

        except ValueError as exc:
            messagebox.showerror("Import Error", str(exc))
        except Exception as exc:
            messagebox.showerror(
                "Import Error",
                f"Failed to import micro:bit log:\n{exc}",
            )

    # ------------------------------------------------------------------
    # Display updaters
    # ------------------------------------------------------------------

    def _update_stats(self, session: dict, df: pd.DataFrame, meta: dict):
        """Update the summary statistics labels."""
        if df.empty:
            self.stats_label.config(
                text=f"Session: {session['id']}  |  Source: {session['source']}  |  No data recorded."
            )
            self.alert_stats_label.config(text="")
            return

        temp_min = df["temperature"].min()
        temp_max = df["temperature"].max()
        temp_mean = df["temperature"].mean()

        light_min = df["light"].min()
        light_max = df["light"].max()
        light_mean = df["light"].mean()

        # Risk distribution
        risk_counts = df["risk_level"].value_counts().to_dict()
        risk_str = "  |  ".join(
            f"{level}: {count}" for level, count in risk_counts.items()
        )

        duration = ""
        if session.get("end_time") and session.get("start_time"):
            try:
                start_dt = datetime.strptime(session["start_time"], "%Y-%m-%d %H:%M:%S")
                end_dt = datetime.strptime(session["end_time"], "%Y-%m-%d %H:%M:%S")
                dur = end_dt - start_dt
                minutes = int(dur.total_seconds() // 60)
                seconds = int(dur.total_seconds() % 60)
                duration = f"  |  Duration: {minutes}m {seconds}s"
            except ValueError:
                pass

        summary = (
            f"Session: {session['id']}  |  Source: {session['source']}"
            f"{duration}  |  Readings: {len(df)}\n"
            f"Temp  →  min: {temp_min:.1f}°C  |  max: {temp_max:.1f}°C  |  "
            f"mean: {temp_mean:.1f}°C\n"
            f"Light →  min: {light_min}  |  max: {light_max}  |  "
            f"mean: {light_mean:.0f}\n"
            f"Risk  →  {risk_str}"
        )
        self.stats_label.config(text=summary)

        # Alert / advice counts from meta
        alerts = meta.get("alerts", [])
        advice = meta.get("advice", [])
        self.alert_stats_label.config(
            text=f"Alerts: {len(alerts)}  |  Advice items: {len(advice)}"
        )

    def _update_table(self, df: pd.DataFrame):
        """Repopulate the treeview with session data rows."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        if df.empty:
            return

        for _, row in df.iterrows():
            ts = str(row["timestamp"])
            risk = str(row.get("risk_level", ""))
            source = str(row.get("source", ""))
            tag = risk.lower() if risk else ""
            self.tree.insert(
                "", "end",
                values=(ts, f"{row['temperature']:.1f}", row["light"], risk, source),
                tags=(tag,),
            )

    def _update_chart(self, df: pd.DataFrame):
        """Redraw the session trend chart."""
        self._ax_temp.clear()
        self._ax_light.clear()

        if df.empty:
            self._ax_temp.set_title("Temperature — no data")
            self._ax_light.set_title("Light — no data")
            self._canvas.draw_idle()
            return

        timestamps = df["timestamp"]
        temps = df["temperature"]
        lights = df["light"]

        self._ax_temp.plot(timestamps, temps, color="#e74c3c", linewidth=1.5)
        self._ax_temp.set_ylabel("°C")
        self._ax_temp.set_title("Temperature")
        self._ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self._ax_temp.tick_params(axis="x", rotation=30, labelsize=7)
        self._ax_temp.grid(True, alpha=0.3)

        self._ax_light.plot(timestamps, lights, color="#f39c12", linewidth=1.5)
        self._ax_light.set_ylabel("Level")
        self._ax_light.set_title("Light Level")
        self._ax_light.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self._ax_light.tick_params(axis="x", rotation=30, labelsize=7)
        self._ax_light.grid(True, alpha=0.3)

        self._canvas.draw_idle()

    def _clear_display(self):
        """Clear all display elements when no session is selected."""
        self.stats_label.config(text="No sessions recorded yet.")
        self.alert_stats_label.config(text="")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._ax_temp.clear()
        self._ax_light.clear()
        self._ax_temp.set_title("Temperature — no data")
        self._ax_light.set_title("Light — no data")
        self._canvas.draw_idle()



