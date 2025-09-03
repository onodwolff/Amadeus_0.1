from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):
    """Abstract trading strategy interface."""

    def __init__(self, cfg: dict[str, Any], client_wrapper: Any, events_cb: Any) -> None:
        self.cfg = cfg
        self.client_wrap = client_wrapper
        self.events_cb = events_cb

    @abstractmethod
    async def start(self) -> None:
        """Initialize resources for the strategy."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """Cleanup resources before shutdown."""
        raise NotImplementedError

    @abstractmethod
    async def step(self) -> None:
        """Execute one iteration of the strategy."""
        raise NotImplementedError
