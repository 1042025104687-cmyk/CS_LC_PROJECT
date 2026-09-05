# Alert history panel

from __future__ import annotations

from tkinter import ttk


class AlertsFrame(ttk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_widgets()

    def _build_widgets(self):
        ttk.Label(self, text="Alert History", font=("Helvetica", 18, "bold")).pack(
            pady=(15, 5)
        )
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=20, pady=5)
        self.clear_btn = ttk.Button(toolbar, text="Clear All Alerts")
        self.clear_btn.pack(side="right")
        self.count_label = ttk.Label(toolbar, text="0 alerts")
        self.count_label.pack(side="left")

        # Treeview table
        columns = ("time", "level", "message")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=18)
        self.tree.heading("time", text="Time")
        self.tree.heading("level", text="Level")
        self.tree.heading("message", text="Message")
        self.tree.column("time", width=120, anchor="center")
        self.tree.column("level", width=80, anchor="center")
        self.tree.column("message", width=500)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=10)

    def refresh(self, alerts):
        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Insert newest first
        for alert in reversed(alerts):
            ts = alert.timestamp.strftime("%H:%M:%S")
            tag = alert.level.lower()
            self.tree.insert("", "end", values=(ts, alert.level, alert.message), tags=(tag,))

        # Colour-code rows
        self.tree.tag_configure("high", background="#fdebd0")
        self.tree.tag_configure("critical", background="#fadbd8")

        self.count_label.config(text=f"{len(alerts)} alert(s)")