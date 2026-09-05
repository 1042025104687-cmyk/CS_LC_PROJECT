# Wildfire model analysis tab

import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import pandas as pd

from src.data.csv_manager import CsvManager
from src.core.wildfire_model import WildfireModel
from src.core.risk_engine import RiskEngine


class ModelFrame(ttk.Frame):

    WHAT_IF_SCENARIOS = [
        ("Baseline",       0,   0,  0, "#3498db"),
        ("Temp +5 °C",     5,   0,  0, "#e74c3c"),
        ("Light +50",      0,  50,  0, "#f39c12"),
        ("Wind +10 km/h",  0,   0, 10, "#2ecc71"),
    ]

    def __init__(self, parent, settings_manager, **kwargs):
        super().__init__(parent, **kwargs)
        self._settings = settings_manager
        self._model = WildfireModel(default_wind=settings_manager.get("default_wind_speed"))
        self._risk_engine = RiskEngine(settings_manager)
        self._df = None
        self._build_widgets()

    def _build_widgets(self):
        ttk.Label(
            self, text="🔥 Wildfire Risk Model", font=("Helvetica", 18, "bold")
        ).pack(pady=(15, 5))
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # ---- Toolbar ----
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=20, pady=5)

        self.analyse_btn = ttk.Button(
            toolbar, text="📂 Analyse Historical CSV", command=self._analyse_csv
        )
        self.analyse_btn.pack(side="left", padx=(0, 10))

        for label, t_off, l_off, w_off, colour in self.WHAT_IF_SCENARIOS[1:]:
            btn = ttk.Button(
                toolbar,
                text=f"🔮 What-If: {label}",
                command=lambda to=t_off, lo=l_off, wo=w_off, c=colour, lb=label:
                    self._run_what_if(to, lo, wo, c, lb),
            )
            btn.pack(side="left", padx=5)

        self.clear_btn = ttk.Button(
            toolbar, text="🗑 Clear", command=self._clear
        )
        self.clear_btn.pack(side="right")

        # ---- Simulation toolbar (Stress Test + Trend Test) ----
        sim_toolbar = ttk.Frame(self)
        sim_toolbar.pack(fill="x", padx=20, pady=(0, 5))

        ttk.Label(sim_toolbar, text="⚡ Stress Test:").pack(side="left")
        self._stress_var = tk.StringVar(value="drought")
        stress_combo = ttk.Combobox(
            sim_toolbar, textvariable=self._stress_var,
            values=list(WildfireModel.STRESS_SCENARIOS), state="readonly", width=12,
        )
        stress_combo.pack(side="left", padx=(4, 2))
        ttk.Button(
            sim_toolbar, text="Run", command=self._run_stress_test,
        ).pack(side="left", padx=(0, 20))

        ttk.Label(sim_toolbar, text="📈 Trend Test:").pack(side="left")
        self._trend_var = tk.StringVar(value="drought_ramp")
        trend_combo = ttk.Combobox(
            sim_toolbar, textvariable=self._trend_var,
            values=list(WildfireModel.TREND_SCENARIOS), state="readonly", width=14,
        )
        trend_combo.pack(side="left", padx=(4, 2))

        ttk.Label(sim_toolbar, text="Days:").pack(side="left", padx=(8, 2))
        self._trend_days_var = tk.IntVar(value=30)
        ttk.Spinbox(
            sim_toolbar, from_=7, to=365, textvariable=self._trend_days_var,
            width=5,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            sim_toolbar, text="Run", command=self._run_trend_test,
        ).pack(side="left")

        # ---- Summary statistics panel ----
        stats_frame = ttk.LabelFrame(self, text="Model Summary", padding=10)
        stats_frame.pack(fill="x", padx=20, pady=(10, 5))

        self.stats_text = tk.Text(
            stats_frame, height=10, wrap="word", font=("Consolas", 10),
            state="disabled", relief="flat", bg="#f4f4f4",
        )
        self.stats_text.pack(fill="x")

        # ---- Chart ----
        self._fig = Figure(figsize=(9, 3.5), dpi=100)
        self._fig.set_tight_layout(True)
        self._ax = self._fig.add_subplot(111)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=10)

        # ---- Live prediction label (updated from app.py polling loop) ----
        live_frame = ttk.LabelFrame(self, text="Live Model Prediction", padding=10)
        live_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.live_score_label = ttk.Label(
            live_frame, text="-- / 100", font=("Helvetica", 22, "bold")
        )
        self.live_score_label.pack(side="left", padx=(10, 20))

        self.live_category_label = ttk.Label(
            live_frame, text="Waiting for data…", font=("Helvetica", 14)
        )
        self.live_category_label.pack(side="left")

        self.live_prediction_label = ttk.Label(
            live_frame, text="", font=("Helvetica", 11), foreground="grey"
        )
        self.live_prediction_label.pack(side="right", padx=10)

    # ------------------------------------------------------------------
    # Public: update from live polling loop
    # ------------------------------------------------------------------

    def update_live_prediction(self, result: dict):
        """Called from app.py with the latest model prediction dict."""
        score = result["risk_score"]
        cat = result["risk_category"]
        pred = result["prediction"]

        colour = self._category_colour(cat)
        self.live_score_label.config(text=f"{score:.0f} / 100", foreground=colour)
        self.live_category_label.config(text=cat, foreground=colour)
        self.live_prediction_label.config(text=pred)

    # ------------------------------------------------------------------
    # Historical analysis
    # ------------------------------------------------------------------

    def _analyse_csv(self):
        """Load the main sensor_log.csv and run the model on it."""
        csv_path = self._settings.get("csv_path")
        df = CsvManager.load_file(csv_path)
        if df.empty:
            self._show_stats("No historical data found.")
            return

        self._df = df
        result_df = self._model.predict_from_dataframe(df)

        # Draw baseline chart
        self._ax.clear()
        self._plot_series(
            result_df, "Baseline", self.WHAT_IF_SCENARIOS[0][4]
        )
        self._ax.legend(loc="upper left", fontsize=8)
        self._ax.set_title("Wildfire Risk Score Over Time")
        self._ax.set_ylabel("Risk Score (0–100)")
        self._ax.set_xlabel("Time")
        self._ax.set_ylim(-5, 105)
        self._draw_threshold_lines()
        self._canvas.draw_idle()

        # Summary stats
        self._show_summary(result_df)

    def _run_what_if(self, temp_offset, light_offset, wind_offset,
                     colour, label):
        """Run a what-if simulation and overlay on the chart."""
        if self._df is None:
            self._analyse_csv()
            if self._df is None:
                return

        result_df = self._model.what_if(
            self._df,
            temp_offset=temp_offset,
            light_offset=light_offset,
            wind_offset=wind_offset,
        )
        self._plot_series(result_df, label, colour)
        self._ax.legend(loc="upper left", fontsize=8)
        self._canvas.draw_idle()

        # Show comparison stats
        baseline = self._model.predict_from_dataframe(self._df)
        self._show_comparison(baseline, result_df, label)

    # ------------------------------------------------------------------
    # Stress Test simulation
    # ------------------------------------------------------------------

    def _run_stress_test(self):
        """Run a single-shot stress test and display the result."""
        scenario = self._stress_var.get()
        self._risk_engine.reset()
        result = self._model.stress_test(scenario, risk_engine=self._risk_engine)

        # Plot a single marker point on the chart
        self._ax.axhline(
            y=result["risk_score"], color="#e74c3c", linestyle=":",
            linewidth=1, alpha=0.6,
        )
        self._ax.plot(
            [0], [result["risk_score"]], marker="*", markersize=14,
            color="#e74c3c", label=f"Stress: {scenario}",
            zorder=5,
        )
        self._ax.legend(loc="upper left", fontsize=8)
        self._canvas.draw_idle()

        # Display stats
        lines = [
            f"  ⚡ STRESS TEST — {scenario.upper()}",
            f"  {'─' * 40}",
            f"  Inputs:  Temp={result['temperature']}°C  "
            f"Light={result['light']}  Wind={result['wind_speed']} km/h",
            "",
            f"  Model score    : {result['risk_score']:.0f} / 100",
            f"  Model category : {result['risk_category']}",
            f"  Prediction     : {result['prediction']}",
        ]
        if result["risk_level"] is not None:
            lines.append(f"  RiskEngine level (adaptive): {result['risk_level']}")
        self._show_stats("\n".join(lines))

    # ------------------------------------------------------------------
    # Trend Test simulation
    # ------------------------------------------------------------------

    _RISK_LEVEL_MAP = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}

    def _run_trend_test(self):
        """Run a multi-day trend test and plot dual-axis results."""
        scenario = self._trend_var.get()
        days = self._trend_days_var.get()
        df = self._model.trend_test(
            days=days, scenario=scenario, risk_engine=self._risk_engine,
        )

        # --- Chart: model_score on left y-axis, risk_level on right ---
        # Remove any previous twinx axes
        for ax in self._fig.axes[1:]:
            ax.remove()
        self._ax.clear()

        # Model score line (left axis, 0–100)
        self._ax.plot(
            df["day"], df["model_score"],
            label="Model Score (0–100)", color="#3498db",
            linewidth=1.5, alpha=0.9,
        )
        self._ax.set_xlabel("Day")
        self._ax.set_ylabel("Model Risk Score (0–100)", color="#3498db")
        self._ax.set_ylim(-5, 105)
        self._ax.tick_params(axis="y", labelcolor="#3498db")
        self._draw_threshold_lines()

        # Risk-level line (right axis, 0–3)
        if df["risk_level"].notna().any():
            ax2 = self._ax.twinx()
            numeric_levels = df["risk_level"].map(self._RISK_LEVEL_MAP)
            ax2.plot(
                df["day"], numeric_levels,
                label="RiskEngine Level (0–3)", color="#e74c3c",
                linewidth=1.5, linestyle="--", alpha=0.85,
            )
            ax2.set_ylabel("RiskEngine Level (0–3)", color="#e74c3c")
            ax2.set_ylim(-0.3, 3.5)
            ax2.set_yticks([0, 1, 2, 3])
            ax2.set_yticklabels(["LOW", "MOD", "HIGH", "CRIT"])
            ax2.tick_params(axis="y", labelcolor="#e74c3c")
            ax2.legend(loc="upper right", fontsize=8)

        self._ax.set_title(f"Trend Test: {scenario} ({days} days)")
        self._ax.legend(loc="upper left", fontsize=8)
        self._ax.grid(True, alpha=0.3)
        self._canvas.draw_idle()

        # --- Summary stats ---
        scores = df["model_score"]
        first_high_model = df.loc[
            df["model_category"].isin(["High", "Extreme"]), "day"
        ]
        day_model_high = int(first_high_model.iloc[0]) if len(first_high_model) else None

        lines = [
            f"  📈 TREND TEST — {scenario.upper()} over {days} days",
            f"  {'─' * 48}",
            f"  Model score Day 1  : {scores.iloc[0]:.1f}",
            f"  Model score Day {days:<3}: {scores.iloc[-1]:.1f}",
            f"  Model mean score   : {scores.mean():.1f}",
            f"  Day model first reached High+: "
            f"{'Day ' + str(day_model_high) if day_model_high else 'never'}",
        ]

        if df["risk_level"].notna().any():
            first_high_engine = df.loc[
                df["risk_level"].isin(["HIGH", "CRITICAL"]), "day"
            ]
            day_engine_high = (
                int(first_high_engine.iloc[0]) if len(first_high_engine) else None
            )
            lines.append(
                f"  Day RiskEngine first reached HIGH+: "
                f"{'Day ' + str(day_engine_high) if day_engine_high else 'never'}"
            )
            if day_model_high and day_engine_high and day_engine_high > day_model_high:
                lines.append(
                    f"  → Adaptive dampening: RiskEngine lagged by "
                    f"{day_engine_high - day_model_high} day(s)"
                )

        self._show_stats("\n".join(lines))

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _plot_series(self, df: pd.DataFrame, label: str, colour: str):
        if "timestamp" in df.columns:
            self._ax.plot(
                df["timestamp"], df["model_score"],
                label=label, color=colour, linewidth=1.2, alpha=0.85,
            )
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            self._ax.tick_params(axis="x", rotation=30, labelsize=7)
        else:
            self._ax.plot(
                df["model_score"].values,
                label=label, color=colour, linewidth=1.2, alpha=0.85,
            )
        self._ax.grid(True, alpha=0.3)

    def _draw_threshold_lines(self):
        for threshold, lbl in WildfireModel._THRESHOLDS[:-1]:
            self._ax.axhline(
                y=threshold, color="grey", linestyle="--",
                linewidth=0.8, alpha=0.5,
            )
            self._ax.text(
                self._ax.get_xlim()[0], threshold + 1.5,
                f"  {lbl}", fontsize=7, color="grey",
            )

    # ------------------------------------------------------------------
    # Statistics display
    # ------------------------------------------------------------------

    def _show_summary(self, df: pd.DataFrame):
        scores = df["model_score"]
        cats = df["model_category"]

        lines = [
            f"  Readings analysed : {len(df)}",
            f"  Mean risk score   : {scores.mean():.1f}",
            f"  Min / Max score   : {scores.min():.1f} / {scores.max():.1f}",
            "",
            "  Category distribution:",
        ]
        for cat in ["Low", "Moderate", "High", "Extreme"]:
            count = (cats == cat).sum()
            pct = count / len(df) * 100 if len(df) else 0
            lines.append(f"    {cat:10s}: {count:5d}  ({pct:5.1f}%)")

        self._show_stats("\n".join(lines))

    def _show_comparison(self, baseline_df: pd.DataFrame,
                         whatif_df: pd.DataFrame, label: str):
        b_mean = baseline_df["model_score"].mean()
        w_mean = whatif_df["model_score"].mean()
        delta = w_mean - b_mean

        lines = [
            f"  What-If: {label}",
            f"  Baseline mean score : {b_mean:.1f}",
            f"  What-if mean score  : {w_mean:.1f}",
            f"  Change              : {delta:+.1f}",
            "",
            "  What-if category distribution:",
        ]
        cats = whatif_df["model_category"]
        for cat in ["Low", "Moderate", "High", "Extreme"]:
            count = (cats == cat).sum()
            pct = count / len(whatif_df) * 100 if len(whatif_df) else 0
            lines.append(f"    {cat:10s}: {count:5d}  ({pct:5.1f}%)")

        self._show_stats("\n".join(lines))

    def _show_stats(self, text: str):
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("end", text)
        self.stats_text.config(state="disabled")

    def _clear(self):
        self._df = None
        # Remove any twinx axes created by trend tests
        for ax in self._fig.axes[1:]:
            ax.remove()
        self._ax.clear()
        self._ax.set_title("Wildfire Risk Score Over Time")
        self._ax.set_ylabel("Risk Score (0–100)")
        self._canvas.draw_idle()
        self._show_stats("")

    # ------------------------------------------------------------------
    # Colour helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _category_colour(category: str) -> str:
        return {
            "Low": "#2ecc71",
            "Moderate": "#f1c40f",
            "High": "#e67e22",
            "Extreme": "#e74c3c",
        }.get(category, "#95a5a6")

