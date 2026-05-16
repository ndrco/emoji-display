from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DisplayItem:
    symbol: str
    name: str | None = None
    hold_ms: int = 1200


class DisplayDriver(Protocol):
    name: str

    def show(self, item: DisplayItem) -> None:
        ...

    def clear(self) -> None:
        ...

    def status(self) -> dict:
        ...


class LoggingDisplayDriver:
    """Placeholder driver used until the Arduino protocol is implemented."""

    name = "logging"

    def __init__(self) -> None:
        self.current: DisplayItem | None = None
        self.connected = True
        self.last_error: str | None = None

    def show(self, item: DisplayItem) -> None:
        self.current = item
        log.info(
            "display show symbol=%s name=%s hold_ms=%d",
            item.symbol,
            item.name or "-",
            item.hold_ms,
        )

    def clear(self) -> None:
        self.current = None
        log.info("display clear")

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "driver": self.name,
            "current": self.current.symbol if self.current else None,
            "last_error": self.last_error,
        }
