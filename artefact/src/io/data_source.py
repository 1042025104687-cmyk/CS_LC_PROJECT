# Abstract base class for data sources (sensor, simulator, etc.)

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional


class DataSource(ABC):
    """
    Protocol for data sources that produce sensor readings.
    
    Both SerialManager (real hardware) and Simulator (fake data)
    implement this interface, allowing the Controller to work
    with either without knowing the concrete type.
    """

    @abstractmethod
    def start(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Start producing data. Calls callback(line) for each reading."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop producing data."""
        ...

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Return True if currently producing data."""
        ...