# Settings panel for COM port and thresholds

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox


class SettingsFrame(ttk.Frame):

    def __init__(self, parent, settings_manager, serial_manager, **kwargs):
        super().__init__(parent, **kwargs)
        self._settings = settings_manager
        self._serial = serial_manager
        self._build_widgets()
        self._load_from_settings()

    def _build_widgets(self):
        ttk.Label(self, text="Settings", font=("Helvetica", 18, "bold")).pack(
            pady=(15, 5)
        )
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # --- Scrollable wrapper ---
        scroll_outer = ttk.Frame(self)
        scroll_outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(scroll_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            scroll_outer, orient="vertical", command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        container = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=container, anchor="nw"
        )

        # Keep scroll region up-to-date when contents change size
        container.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        # Stretch the inner frame to match the canvas width
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(
                self._canvas_window, width=e.width
            ),
        )

        # Mouse-wheel scrolling (Windows & Linux)
        self._bind_mousewheel(self._canvas)
        container.bind(
            "<Enter>",
            lambda e: self._bind_mousewheel_recursive(container),
        )

        container.configure(padding=(30, 10))

        # --- Connection section ---
        conn_frame = ttk.LabelFrame(container, text="Micro:bit Connection", padding=10)
        conn_frame.pack(fill="x", pady=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, sticky="w", pady=3)
        self.port_combo = ttk.Combobox(conn_frame, state="readonly", width=20)
        self.port_combo.grid(row=0, column=1, padx=5, pady=3)

        self.refresh_btn = ttk.Button(
            conn_frame, text="↻ Scan Ports", width=10, command=self._refresh_ports
        )
        self.refresh_btn.grid(row=0, column=2, padx=5)

        ttk.Label(conn_frame, text="Speed (baud):").grid(row=1, column=0, sticky="w", pady=3)
        self.baud_var = tk.StringVar(value="115200")
        ttk.Entry(conn_frame, textvariable=self.baud_var, width=22).grid(
            row=1, column=1, padx=5, pady=3
        )

        btn_frame = ttk.Frame(conn_frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=8)

        self.connect_btn = ttk.Button(btn_frame, text="Connect", width=14)
        self.connect_btn.pack(side="left", padx=5)
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect", width=14)
        self.disconnect_btn.pack(side="left", padx=5)

        self.status_label = ttk.Label(conn_frame, text="● Disconnected", foreground="red")
        self.status_label.grid(row=3, column=0, columnspan=3, pady=3)

        # --- Temperature thresholds ---
        temp_frame = ttk.LabelFrame(container, text="When does temperature become risky? (°C)", padding=10)
        temp_frame.pack(fill="x", pady=5)

        self.temp_mod_var = tk.IntVar()
        self.temp_high_var = tk.IntVar()
        self.temp_crit_var = tk.IntVar()

        self._threshold_row(temp_frame, "Watch (moderate):", self.temp_mod_var, 0, 0, 60)
        self._threshold_row(temp_frame, "Warning (high):", self.temp_high_var, 1, 0, 60)
        self._threshold_row(temp_frame, "Danger (critical):", self.temp_crit_var, 2, 0, 60)

        # --- Light thresholds ---
        light_frame = ttk.LabelFrame(container, text="When does light level become risky? (0–255)", padding=10)
        light_frame.pack(fill="x", pady=5)

        self.light_mod_var = tk.IntVar()
        self.light_high_var = tk.IntVar()
        self.light_crit_var = tk.IntVar()

        self._threshold_row(light_frame, "Watch (moderate):", self.light_mod_var, 0, 0, 255)
        self._threshold_row(light_frame, "Warning (high):", self.light_high_var, 1, 0, 255)
        self._threshold_row(light_frame, "Danger (critical):", self.light_crit_var, 2, 0, 255)

        # --- Adaptive risk settings ---
        adaptive_frame = ttk.LabelFrame(
            container, text="How the system reacts", padding=10
        )
        adaptive_frame.pack(fill="x", pady=5)

        # Sensitivity factor (0.0 = static behaviour, 2.0 = very aggressive)
        self.sensitivity_var = tk.DoubleVar()
        ttk.Label(adaptive_frame, text="Risk sensitivity:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            adaptive_frame, from_=0.0, to=2.0,
            variable=self.sensitivity_var, length=250,
        ).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.sensitivity_var, width=5).grid(
            row=0, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(0 = fixed rules only, higher = reacts more to changes)",
            font=("Helvetica", 8),
        ).grid(row=0, column=3, sticky="w", padx=5)

        # Context temperature threshold (°C)
        self.context_temp_var = tk.DoubleVar()
        ttk.Label(adaptive_frame, text="Hot weather starts at (°C):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            adaptive_frame, from_=15.0, to=45.0,
            variable=self.context_temp_var, length=250,
        ).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.context_temp_var, width=5).grid(
            row=1, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(above this, temperature matters 3× more than light)",
            font=("Helvetica", 8),
        ).grid(row=1, column=3, sticky="w", padx=5)

        # Dynamic sampling rate – normal (low-risk) interval
        ttk.Label(adaptive_frame, text="Normal read speed (ms):").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.poll_normal_var = tk.IntVar()
        ttk.Spinbox(
            adaptive_frame, textvariable=self.poll_normal_var,
            from_=500, to=600000, increment=500, width=8,
        ).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.poll_normal_var, width=6).grid(
            row=2, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(how often readings are taken when risk is low)",
            font=("Helvetica", 8),
        ).grid(row=2, column=3, sticky="w", padx=5)

        # Dynamic sampling rate – fast (high-risk) interval
        ttk.Label(adaptive_frame, text="Fast read speed (ms):").grid(
            row=3, column=0, sticky="w", pady=2
        )
        self.poll_fast_var = tk.IntVar()
        ttk.Spinbox(
            adaptive_frame, textvariable=self.poll_fast_var,
            from_=100, to=10000, increment=100, width=8,
        ).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.poll_fast_var, width=6).grid(
            row=3, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(how often readings are taken when risk is high)",
            font=("Helvetica", 8),
        ).grid(row=3, column=3, sticky="w", padx=5)

        # Threshold escalation – number of readings before escalation
        ttk.Label(adaptive_frame, text="Readings before escalation:").grid(
            row=4, column=0, sticky="w", pady=2
        )
        self.escalation_readings_var = tk.IntVar()
        ttk.Spinbox(
            adaptive_frame, textvariable=self.escalation_readings_var,
            from_=2, to=20, increment=1, width=8,
        ).grid(row=4, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.escalation_readings_var, width=5).grid(
            row=4, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(consecutive high readings needed to tighten thresholds)",
            font=("Helvetica", 8),
        ).grid(row=4, column=3, sticky="w", padx=5)

        # Threshold escalation factor
        self.escalation_factor_var = tk.DoubleVar()
        ttk.Label(adaptive_frame, text="Escalation factor:").grid(
            row=5, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            adaptive_frame, from_=0.0, to=0.30,
            variable=self.escalation_factor_var, length=250,
        ).grid(row=5, column=1, padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.escalation_factor_var, width=5).grid(
            row=5, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(fraction to lower thresholds when risk stays high)",
            font=("Helvetica", 8),
        ).grid(row=5, column=3, sticky="w", padx=5)

        # Auto-adjust model weights toggle
        self.weight_adapt_var = tk.BooleanVar()
        ttk.Checkbutton(
            adaptive_frame,
            text="Auto-adjust model weights based on recent data",
            variable=self.weight_adapt_var,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(
            adaptive_frame,
            text="(shifts weights toward the dominant risk driver)",
            font=("Helvetica", 8),
        ).grid(row=6, column=3, sticky="w", padx=5)

        # Max weight shift
        self.weight_max_shift_var = tk.DoubleVar()
        ttk.Label(adaptive_frame, text="Max weight shift:").grid(
            row=7, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            adaptive_frame, from_=0.0, to=0.30,
            variable=self.weight_max_shift_var, length=250,
        ).grid(row=7, column=1, padx=5, pady=2)
        ttk.Label(adaptive_frame, textvariable=self.weight_max_shift_var, width=5).grid(
            row=7, column=2, padx=5
        )
        ttk.Label(
            adaptive_frame,
            text="(how far each weight can move from its default)",
            font=("Helvetica", 8),
        ).grid(row=7, column=3, sticky="w", padx=5)

        # --- Wildfire model weights ---
        weights_frame = ttk.LabelFrame(
            container, text="Wildfire model weights (must sum to 1.0)", padding=10
        )
        weights_frame.pack(fill="x", pady=5)

        self.w_temp_var = tk.DoubleVar()
        self.w_light_var = tk.DoubleVar()
        self.w_wind_var = tk.DoubleVar()

        ttk.Label(weights_frame, text="Temperature weight:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            weights_frame, from_=0.0, to=1.0,
            variable=self.w_temp_var, length=250,
        ).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(weights_frame, textvariable=self.w_temp_var, width=5).grid(
            row=0, column=2, padx=5
        )

        ttk.Label(weights_frame, text="Light weight:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            weights_frame, from_=0.0, to=1.0,
            variable=self.w_light_var, length=250,
        ).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(weights_frame, textvariable=self.w_light_var, width=5).grid(
            row=1, column=2, padx=5
        )

        ttk.Label(weights_frame, text="Wind weight:").grid(
            row=2, column=0, sticky="w", pady=2
        )
        ttk.Scale(
            weights_frame, from_=0.0, to=1.0,
            variable=self.w_wind_var, length=250,
        ).grid(row=2, column=1, padx=5, pady=2)
        ttk.Label(weights_frame, textvariable=self.w_wind_var, width=5).grid(
            row=2, column=2, padx=5
        )

        self.weights_note = ttk.Label(
            weights_frame,
            text="Weights are auto-normalised to sum to 1.0 on save.",
            font=("Helvetica", 8), foreground="grey",
        )
        self.weights_note.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # --- Action buttons ---
        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x", pady=10)

        self.save_btn = ttk.Button(
            action_frame, text="💾 Save Settings", command=self._save_settings
        )
        self.save_btn.pack(side="left", padx=5)

        self.reset_btn = ttk.Button(
            action_frame, text="↩ Reset Defaults", command=self._reset_defaults
        )
        self.reset_btn.pack(side="left", padx=5)

        # --- Simulation section ---
        sim_frame = ttk.LabelFrame(container, text="Test Mode (no micro:bit needed)", padding=10)
        sim_frame.pack(fill="x", pady=5)

        self.simulate_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            sim_frame,
            text="Use simulated data instead of a real sensor",
            variable=self.simulate_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        # Scenario
        ttk.Label(sim_frame, text="Test scenario:").grid(row=1, column=0, sticky="w", pady=2)
        self.sim_scenario_var = tk.StringVar(value="random")
        self.sim_scenario_combo = ttk.Combobox(
            sim_frame,
            textvariable=self.sim_scenario_var,
            values=["random", "drought_ramp", "heatwave", "day_night_cycle", "calm"],
            state="readonly",
            width=18,
        )
        self.sim_scenario_combo.grid(row=1, column=1, padx=5, pady=2)

        # Speed
        ttk.Label(sim_frame, text="Seconds between readings:").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=2)
        self.sim_speed_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(
            sim_frame,
            textvariable=self.sim_speed_var,
            from_=0.5,
            to=10.0,
            increment=0.5,
            width=6,
        ).grid(row=1, column=3, padx=5, pady=2)

        # Temperature range
        ttk.Label(sim_frame, text="Lowest temp (°C):").grid(row=2, column=0, sticky="w", pady=2)
        self.sim_temp_min_var = tk.DoubleVar(value=15.0)
        ttk.Spinbox(
            sim_frame, textvariable=self.sim_temp_min_var,
            from_=-10, to=60, increment=1, width=6,
        ).grid(row=2, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(sim_frame, text="Highest temp (°C):").grid(row=2, column=2, sticky="w", padx=(10, 0), pady=2)
        self.sim_temp_max_var = tk.DoubleVar(value=45.0)
        ttk.Spinbox(
            sim_frame, textvariable=self.sim_temp_max_var,
            from_=-10, to=80, increment=1, width=6,
        ).grid(row=2, column=3, padx=5, pady=2)

        # Light range
        ttk.Label(sim_frame, text="Lowest light:").grid(row=3, column=0, sticky="w", pady=2)
        self.sim_light_min_var = tk.IntVar(value=30)
        ttk.Spinbox(
            sim_frame, textvariable=self.sim_light_min_var,
            from_=0, to=255, increment=5, width=6,
        ).grid(row=3, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(sim_frame, text="Highest light:").grid(row=3, column=2, sticky="w", padx=(10, 0), pady=2)
        self.sim_light_max_var = tk.IntVar(value=255)
        ttk.Spinbox(
            sim_frame, textvariable=self.sim_light_max_var,
            from_=0, to=255, increment=5, width=6,
        ).grid(row=3, column=3, padx=5, pady=2)

        # Noise factor
        ttk.Label(sim_frame, text="Randomness:").grid(row=4, column=0, sticky="w", pady=2)
        self.sim_noise_var = tk.DoubleVar(value=1.0)
        ttk.Scale(
            sim_frame, from_=0.0, to=5.0, variable=self.sim_noise_var, length=180,
        ).grid(row=4, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(sim_frame, textvariable=self.sim_noise_var, width=5).grid(
            row=4, column=2, padx=5, sticky="w"
        )

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def _on_mousewheel(self, event):
        """Scroll the settings canvas on mouse-wheel events."""
        # Windows sends delta in multiples of 120
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)          # Windows
        widget.bind("<Button-4>", lambda e: self._canvas.yview_scroll(-3, "units"))  # Linux up
        widget.bind("<Button-5>", lambda e: self._canvas.yview_scroll(3, "units"))   # Linux down

    def _bind_mousewheel_recursive(self, widget):
        """Bind scroll events to *all* descendants so scrolling works
        even when the cursor is over a child widget (scale, label, etc.)."""
        self._bind_mousewheel(widget)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _threshold_row(parent, label, var, row, from_, to):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        scale = ttk.Scale(parent, from_=from_, to=to, variable=var, length=250)
        scale.grid(row=row, column=1, padx=5, pady=2)
        value_lbl = ttk.Label(parent, textvariable=var, width=5)
        value_lbl.grid(row=row, column=2, padx=5)

    def _refresh_ports(self):
        """Re-scan available COM ports and update the dropdown."""
        from src.io.serial_manager import SerialManager
        ports = SerialManager.list_ports()
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)

    def _load_from_settings(self):
        """Populate widgets from the current SettingsManager values."""
        s = self._settings
        self.baud_var.set(str(s.get("baud_rate")))
        self.temp_mod_var.set(s.get("temp_moderate"))
        self.temp_high_var.set(s.get("temp_high"))
        self.temp_crit_var.set(s.get("temp_critical"))
        self.light_mod_var.set(s.get("light_moderate"))
        self.light_high_var.set(s.get("light_high"))
        self.light_crit_var.set(s.get("light_critical"))

        # Adaptive risk settings
        self.sensitivity_var.set(s.get("adaptive_sensitivity"))
        self.context_temp_var.set(s.get("context_temp_threshold"))
        self.poll_normal_var.set(s.get("polling_interval_normal_ms"))
        self.poll_fast_var.set(s.get("polling_interval_fast_ms"))
        self.escalation_readings_var.set(s.get("escalation_readings"))
        self.escalation_factor_var.set(s.get("escalation_factor"))
        self.weight_adapt_var.set(s.get("weight_adapt_enabled"))
        self.weight_max_shift_var.set(s.get("weight_adapt_max_shift"))

        # Wildfire model weights
        self.w_temp_var.set(s.get("w_temp"))
        self.w_light_var.set(s.get("w_light"))
        self.w_wind_var.set(s.get("w_wind"))

        # Simulation fields
        self.sim_scenario_var.set(s.get("sim_scenario"))
        self.sim_speed_var.set(s.get("sim_speed_sec"))
        self.sim_temp_min_var.set(s.get("sim_temp_min"))
        self.sim_temp_max_var.set(s.get("sim_temp_max"))
        self.sim_light_min_var.set(s.get("sim_light_min"))
        self.sim_light_max_var.set(s.get("sim_light_max"))
        self.sim_noise_var.set(s.get("sim_noise"))

        # Populate COM port list
        self._refresh_ports()
        saved_port = s.get("com_port")
        if saved_port and saved_port in (self.port_combo["values"] or []):
            self.port_combo.set(saved_port)

    def _save_settings(self):
        """Write current widget values into SettingsManager and persist."""
        s = self._settings
        s.set("com_port", self.port_combo.get())
        s.set("baud_rate", int(self.baud_var.get()))
        s.set("temp_moderate", self.temp_mod_var.get())
        s.set("temp_high", self.temp_high_var.get())
        s.set("temp_critical", self.temp_crit_var.get())
        s.set("light_moderate", self.light_mod_var.get())
        s.set("light_high", self.light_high_var.get())
        s.set("light_critical", self.light_crit_var.get())

        # Adaptive risk settings
        s.set("adaptive_sensitivity", self.sensitivity_var.get())
        s.set("context_temp_threshold", self.context_temp_var.get())
        s.set("polling_interval_normal_ms", self.poll_normal_var.get())
        s.set("polling_interval_fast_ms", self.poll_fast_var.get())
        s.set("escalation_readings", self.escalation_readings_var.get())
        s.set("escalation_factor", self.escalation_factor_var.get())
        s.set("weight_adapt_enabled", self.weight_adapt_var.get())
        s.set("weight_adapt_max_shift", self.weight_max_shift_var.get())

        # Wildfire model weights – auto-normalise to sum to 1.0
        raw_wt = self.w_temp_var.get()
        raw_wl = self.w_light_var.get()
        raw_ww = self.w_wind_var.get()
        total_w = raw_wt + raw_wl + raw_ww
        if total_w > 0:
            s.set("w_temp", round(raw_wt / total_w, 4))
            s.set("w_light", round(raw_wl / total_w, 4))
            s.set("w_wind", round(raw_ww / total_w, 4))
        else:
            # Fallback to equal weights if all sliders are at zero
            s.set("w_temp", 0.34)
            s.set("w_light", 0.33)
            s.set("w_wind", 0.33)

        # Simulation settings
        s.set("sim_scenario", self.sim_scenario_var.get())
        s.set("sim_speed_sec", self.sim_speed_var.get())
        s.set("sim_temp_min", self.sim_temp_min_var.get())
        s.set("sim_temp_max", self.sim_temp_max_var.get())
        s.set("sim_light_min", self.sim_light_min_var.get())
        s.set("sim_light_max", self.sim_light_max_var.get())
        s.set("sim_noise", self.sim_noise_var.get())

        s.save()
        messagebox.showinfo("Settings", "Settings saved successfully.")

    def _reset_defaults(self):
        """Reset to factory defaults and refresh widgets."""
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            self._settings.reset_defaults()
            self._load_from_settings()

    # ------------------------------------------------------------------
    # Public accessors used by app.py
    # ------------------------------------------------------------------

    def update_connection_status(self, connected: bool):
        """Update the connection status indicator."""
        if connected:
            self.status_label.config(text="● Connected", foreground="green")
        else:
            self.status_label.config(text="● Disconnected", foreground="red")