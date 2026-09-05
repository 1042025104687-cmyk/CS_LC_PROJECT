# Trend chart using matplotlib

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import pandas as pd
from scipy.interpolate import make_interp_spline


class GraphFrame(ttk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_widgets()

    def _build_widgets(self):
        ttk.Label(self, text="Sensor Trends", font=("Helvetica", 18, "bold")).pack(
            pady=(15, 5)
        )
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # Matplotlib figure with two subplots (temperature + light)
        self._fig = Figure(figsize=(8, 4), dpi=100)
        self._fig.set_tight_layout(True)

        self._ax_temp = self._fig.add_subplot(211)
        self._ax_light = self._fig.add_subplot(212)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=10)

    def _smooth_data(self, timestamps, values, num_points=300):
        """
        Apply cubic spline interpolation to create smooth curves from blocky integer data.
        
        Args:
            timestamps: pandas Series of datetime timestamps
            values: pandas Series of sensor values (integers)
            num_points: number of interpolated points (higher = smoother)
        
        Returns:
            tuple: (smoothed_timestamps, smoothed_values) as numpy arrays
        """
        if len(timestamps) < 4:
            # Need at least 4 points for cubic spline
            return timestamps.values, values.values
        
        # Convert timestamps to numeric (seconds since first reading)
        t_numeric = (timestamps - timestamps.iloc[0]).dt.total_seconds().values
        y_values = values.values.astype(float)
        
        # Remove any duplicate x values (required for interpolation)
        _, unique_idx = np.unique(t_numeric, return_index=True)
        t_numeric = t_numeric[unique_idx]
        y_values = y_values[unique_idx]
        
        if len(t_numeric) < 4:
            return timestamps.values, values.values
        
        # Create smooth interpolation points
        t_smooth = np.linspace(t_numeric.min(), t_numeric.max(), num_points)
        
        try:
            # Cubic spline interpolation (k=3)
            spline = make_interp_spline(t_numeric, y_values, k=3)
            y_smooth = spline(t_smooth)
            
            # Convert back to datetime
            base_time = timestamps.iloc[0]
            t_smooth_dt = pd.to_datetime(base_time) + pd.to_timedelta(t_smooth, unit='s')
            
            return t_smooth_dt, y_smooth
        except Exception:
            # Fallback to original data if interpolation fails
            return timestamps.values, values.values

    def update_graph(self, df):
        self._ax_temp.clear()
        self._ax_light.clear()

        if df.empty:
            self._ax_temp.set_title("Temperature (°C) — no data")
            self._ax_light.set_title("Light Level — no data")
            self._canvas.draw_idle()
            return

        timestamps = df["timestamp"]
        temps = df["temperature"]
        lights = df["light"]

        # Apply smoothing interpolation for cleaner curves
        t_smooth_temp, temps_smooth = self._smooth_data(timestamps, temps)
        t_smooth_light, lights_smooth = self._smooth_data(timestamps, lights)

        # Temperature subplot - smooth line with faint raw data points
        self._ax_temp.plot(t_smooth_temp, temps_smooth, color="#e74c3c", linewidth=1.5, label="Smoothed")
        self._ax_temp.scatter(timestamps, temps, color="#e74c3c", s=8, alpha=0.3, label="Raw")
        self._ax_temp.set_ylabel("°C")
        self._ax_temp.set_title("Temperature")
        self._ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self._ax_temp.tick_params(axis="x", rotation=30, labelsize=7)
        self._ax_temp.grid(True, alpha=0.3)

        # Light subplot - smooth line with faint raw data points
        self._ax_light.plot(t_smooth_light, lights_smooth, color="#f39c12", linewidth=1.5, label="Smoothed")
        self._ax_light.scatter(timestamps, lights, color="#f39c12", s=8, alpha=0.3, label="Raw")
        self._ax_light.set_ylabel("Level")
        self._ax_light.set_title("Light Level")
        self._ax_light.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self._ax_light.tick_params(axis="x", rotation=30, labelsize=7)
        self._ax_light.grid(True, alpha=0.3)

        self._canvas.draw_idle()