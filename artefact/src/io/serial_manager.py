# Serial communication with micro:bit

from __future__ import annotations

import threading
from typing import Callable, Optional
import serial
import serial.tools.list_ports

from src.io.data_source import DataSource


class SerialManager(DataSource):
    """Manages serial communication with micro:bit, implementing DataSource protocol."""

    def __init__(self):
        self._serial = None
        self._thread = None
        self._running = False
        self._callback = None

    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def start(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Alias for connect() using saved port/baud. Use connect() for full control."""
        # This satisfies DataSource interface but connect() is preferred for serial
        if callback is not None:
            self._callback = callback

    def connect(self, port, baud=115200, callback=None):
        if self._serial and self._serial.is_open:
            self.disconnect()

        self._serial = serial.Serial(port, baud, timeout=1)
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Alias for disconnect() to satisfy DataSource interface."""
        self.disconnect()

    def disconnect(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self._thread = None

    @property
    def is_active(self) -> bool:
        """Whether the serial connection is active (DataSource interface)."""
        return self._serial is not None and self._serial.is_open

    @property
    def is_connected(self):
        """Alias for is_active for backwards compatibility."""
        return self.is_active

    def send(self, message):
        if not self.is_connected:
            return
        try:
            self._serial.write(message.encode("utf-8"))
        except (serial.SerialException, OSError):
            pass

    def _read_loop(self):
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    raw = self._serial.readline()
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line and self._callback:
                        self._callback(line)
            except (serial.SerialException, OSError):
                self._running = False
                break