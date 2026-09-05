# Advice log panel

import tkinter as tk
from tkinter import ttk


URGENCY_BG = {
    "INFO": "#d5f5e3",
    "WARNING": "#fef9e7",
    "URGENT": "#fdebd0",
    "CRITICAL": "#fadbd8",
}

URGENCY_FG = {
    "INFO": "#1e8449",
    "WARNING": "#7d6608",
    "URGENT": "#af601a",
    "CRITICAL": "#922b21",
}


class FeedbackFrame(ttk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_widgets()

    def _build_widgets(self):
        ttk.Label(
            self, text="Mitigation Advice Log", font=("Helvetica", 18, "bold")
        ).pack(pady=(15, 5))
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=5)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=20, pady=5)
        self.clear_btn = ttk.Button(toolbar, text="Clear Advice Log")
        self.clear_btn.pack(side="right")
        self.count_label = ttk.Label(toolbar, text="0 advice items")
        self.count_label.pack(side="left")

        # Treeview table
        columns = ("time", "urgency", "advice")
        self.tree = ttk.Treeview(
            self, columns=columns, show="headings", height=20
        )
        self.tree.heading("time", text="Time")
        self.tree.heading("urgency", text="Urgency")
        self.tree.heading("advice", text="Advice")
        self.tree.column("time", width=90, anchor="center")
        self.tree.column("urgency", width=80, anchor="center")
        self.tree.column("advice", width=560)

        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(
            side="left", fill="both", expand=True, padx=(20, 0), pady=10
        )
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=10)

    def refresh(self, advice_history):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for advice in reversed(advice_history):
            ts = advice.timestamp.strftime("%H:%M:%S")
            tag = advice.urgency.lower()
            self.tree.insert("", "end", values=(ts, advice.urgency, advice.message), tags=(tag,))

        for urgency, bg in URGENCY_BG.items():
            fg = URGENCY_FG.get(urgency, "black")
            self.tree.tag_configure(urgency.lower(), background=bg, foreground=fg)

        self.count_label.config(text=f"{len(advice_history)} advice item(s)")


