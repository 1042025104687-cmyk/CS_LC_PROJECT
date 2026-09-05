# Dashboard - live sensor readings and risk gauge

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class DashboardFrame(ttk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_widgets()

    def _build_widgets(self):
        # Simulation banner (hidden by default)
        self.sim_banner = tk.Label(
            self,
            text="⚡ SIMULATION MODE — Data is generated, not from a real sensor",
            font=("Helvetica", 11, "bold"),
            bg="#8e44ad",
            fg="white",
            pady=4,
        )
        # Not packed yet – shown/hidden via show_simulation_banner()

        # Title
        self._title_label = ttk.Label(self, text="Live Dashboard", font=("Helvetica", 18, "bold"))
        self._title_label.pack(
            pady=(15, 5)
        )
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # --- Sensor cards row ---
        cards = ttk.Frame(self)
        cards.pack(pady=15, padx=20, fill="x")
        cards.columnconfigure((0, 1, 2), weight=1)

        # Temperature card
        temp_frame = ttk.LabelFrame(cards, text="Temperature", padding=15)
        temp_frame.grid(row=0, column=0, padx=10, sticky="nsew")
        self.temp_label = ttk.Label(
            temp_frame, text="-- °C", font=("Helvetica", 36, "bold")
        )
        self.temp_label.pack()
        self.temp_status = ttk.Label(temp_frame, text="Waiting for data…")
        self.temp_status.pack(pady=(5, 0))

        # Light card
        light_frame = ttk.LabelFrame(cards, text="Light Level", padding=15)
        light_frame.grid(row=0, column=1, padx=10, sticky="nsew")
        self.light_label = ttk.Label(
            light_frame, text="--", font=("Helvetica", 36, "bold")
        )
        self.light_label.pack()
        self.light_status = ttk.Label(light_frame, text="Waiting for data…")
        self.light_status.pack(pady=(5, 0))

        # Wind Speed card
        wind_frame = ttk.LabelFrame(cards, text="Wind Speed", padding=15)
        wind_frame.grid(row=0, column=2, padx=10, sticky="nsew")
        self.wind_label = ttk.Label(
            wind_frame, text="-- km/h", font=("Helvetica", 36, "bold")
        )
        self.wind_label.pack()
        self.wind_status = ttk.Label(wind_frame, text="Waiting for data…")
        self.wind_status.pack(pady=(5, 0))

        # --- Risk gauge ---
        risk_frame = ttk.LabelFrame(self, text="Drought / Fire Risk", padding=15)
        risk_frame.pack(pady=15, padx=30, fill="x")

        self.risk_label = tk.Label(
            risk_frame,
            text="UNKNOWN",
            font=("Helvetica", 28, "bold"),
            bg="#95a5a6",
            fg="white",
            width=20,
            relief="ridge",
            padx=10,
            pady=10,
        )
        self.risk_label.pack(pady=5)

        self.risk_detail = ttk.Label(risk_frame, text="Connect a micro:bit to begin.")
        self.risk_detail.pack()

        # --- Adaptive Status panel ---
        adapt_frame = ttk.LabelFrame(self, text="Adaptive Status", padding=8)
        adapt_frame.pack(pady=(5, 5), padx=30, fill="x")

        adapt_inner = ttk.Frame(adapt_frame)
        adapt_inner.pack(fill="x")
        adapt_inner.columnconfigure((0, 1, 2), weight=1)

        self.weights_label = ttk.Label(
            adapt_inner, text="Weights: T=0.45  L=0.35  W=0.20",
            font=("Consolas", 10),
        )
        self.weights_label.grid(row=0, column=0, padx=10, sticky="w")

        self.escalation_label = ttk.Label(
            adapt_inner, text="✅ Thresholds normal",
            font=("Helvetica", 10),
        )
        self.escalation_label.grid(row=0, column=1, padx=10)

        self.sampling_label = ttk.Label(
            adapt_inner, text="Sampling: --",
            font=("Helvetica", 10), foreground="grey",
        )
        self.sampling_label.grid(row=0, column=2, padx=10, sticky="e")

        # --- Adaptive Mitigation Advice panel ---
        advice_frame = ttk.LabelFrame(self, text="Mitigation Advice", padding=10)
        advice_frame.pack(pady=10, padx=30, fill="both", expand=True)

        self.advice_text = tk.Text(
            advice_frame,
            height=6,
            wrap="word",
            font=("Helvetica", 10),
            state="disabled",
            relief="flat",
            bg="#f9f9f9",
        )
        advice_scroll = ttk.Scrollbar(
            advice_frame, orient="vertical", command=self.advice_text.yview
        )
        self.advice_text.configure(yscrollcommand=advice_scroll.set)
        self.advice_text.pack(side="left", fill="both", expand=True)
        advice_scroll.pack(side="right", fill="y")

        # Configure colour tags for urgency levels
        self.advice_text.tag_configure("INFO", foreground="#1e8449")
        self.advice_text.tag_configure("WARNING", foreground="#7d6608")
        self.advice_text.tag_configure("URGENT", foreground="#af601a", font=("Helvetica", 10, "bold"))
        self.advice_text.tag_configure("CRITICAL", foreground="#922b21", font=("Helvetica", 10, "bold"))

        # --- Timestamp ---
        self.time_label = ttk.Label(self, text="Last update: --", foreground="grey")
        self.time_label.pack(pady=(5, 5))

    # ------------------------------------------------------------------
    # Public update methods (called from app.py polling loop)
    # ------------------------------------------------------------------

    def update_readings(self, record: dict, risk_level: str, risk_colour: str,
                        advice_items: list | None = None,
                        poll_interval: int | None = None,
                        adaptive_status: dict | None = None):
        """Refresh all displayed values with the latest record."""
        temp = record["temperature"]
        light = record["light"]
        wind = record.get("wind_speed")
        ts = record["timestamp"].strftime("%H:%M:%S")

        self.temp_label.config(text=f"{temp:.1f} °C")
        self.temp_status.config(text=self._temp_description(temp))

        self.light_label.config(text=str(light))
        self.light_status.config(text=self._light_description(light))

        if wind is not None:
            self.wind_label.config(text=f"{wind:.1f} km/h")
            self.wind_status.config(text=self._wind_description(wind))
        else:
            self.wind_label.config(text="-- km/h")
            self.wind_status.config(text="No wind data")

        self.risk_label.config(text=risk_level, bg=risk_colour)
        self.risk_detail.config(text=self._risk_advice(risk_level))

        # Update adaptive status panel
        if adaptive_status is not None:
            w = adaptive_status.get("weights", {})
            self.weights_label.config(
                text=(f"Weights: T={w.get('w_temp', 0.45):.2f}  "
                      f"L={w.get('w_light', 0.35):.2f}  "
                      f"W={w.get('w_wind', 0.20):.2f}")
            )
            if adaptive_status.get("escalated", False):
                self.escalation_label.config(
                    text="⚡ Thresholds ESCALATED",
                    foreground="#c0392b",
                )
            else:
                self.escalation_label.config(
                    text="✅ Thresholds normal",
                    foreground="#1e8449",
                )

        # Show dynamic sampling rate
        if poll_interval is not None:
            rate_str = f"{poll_interval / 1000:.1f}s"
            self.sampling_label.config(text=f"Sampling: every {rate_str}")
            self.time_label.config(
                text=f"Last update: {ts}  ·  Sampling: every {rate_str}"
            )
        else:
            self.time_label.config(text=f"Last update: {ts}")

        # Update the adaptive advice panel
        if advice_items is not None:
            self._update_advice_panel(advice_items)

    def _update_advice_panel(self, advice_items: list):
        """Replace the advice panel content with the latest advice items."""
        self.advice_text.config(state="normal")
        self.advice_text.delete("1.0", "end")

        if not advice_items:
            self.advice_text.insert("end", "No advice at this time.", "INFO")
        else:
            for i, item in enumerate(advice_items):
                prefix = f"[{item.urgency}] "
                self.advice_text.insert("end", prefix, item.urgency)
                self.advice_text.insert("end", item.message)
                if i < len(advice_items) - 1:
                    self.advice_text.insert("end", "\n")

        self.advice_text.config(state="disabled")

    def show_simulation_banner(self, visible: bool):
        """Show or hide the simulation-mode banner at the top of the dashboard."""
        if visible:
            self.sim_banner.pack(fill="x", before=self._title_label)
        else:
            self.sim_banner.pack_forget()

    # ------------------------------------------------------------------
    # Descriptive helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _temp_description(temp: float) -> str:
        if temp >= 40:
            return "Extreme heat!"
        elif temp >= 32:
            return "Very hot"
        elif temp >= 25:
            return "Warm"
        elif temp >= 15:
            return "Mild"
        else:
            return "Cool"

    @staticmethod
    def _light_description(light: int) -> str:
        if light >= 220:
            return "Intense sunlight"
        elif light >= 180:
            return "Bright"
        elif light >= 120:
            return "Moderate"
        elif light >= 60:
            return "Dim"
        else:
            return "Dark"

    @staticmethod
    def _wind_description(wind: float) -> str:
        if wind >= 40:
            return "Gale-force — extreme fire spread risk"
        elif wind >= 25:
            return "Strong wind — high fire spread risk"
        elif wind >= 15:
            return "Moderate breeze"
        elif wind >= 8:
            return "Light breeze"
        else:
            return "Calm"

    @staticmethod
    def _risk_advice(level: str) -> str:
        return {
            "LOW": "Conditions are safe. No action required.",
            "MODERATE": "Mild risk. Keep monitoring.",
            "HIGH": "Significant risk! Monitor closely and prepare.",
            "CRITICAL": "EXTREME DANGER — Immediate preventive action required!",
        }.get(level, "")

