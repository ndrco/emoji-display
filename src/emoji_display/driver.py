from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .emoji import normalize_emoji

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DisplayItem:
    symbol: str
    name: str | None = None
    hold_ms: int = 1200
    display_name: str | None = None
    display_symbol: str | None = None


class DisplayDriver(Protocol):
    name: str

    def show(self, item: DisplayItem) -> None:
        ...

    def clear(self) -> None:
        ...

    def status(self) -> dict:
        ...


class LoggingDisplayDriver:
    """Development driver that logs the normalized item instead of using hardware."""

    name = "logging"

    def __init__(self) -> None:
        self.current: DisplayItem | None = None
        self.connected = True
        self.last_error: str | None = None

    def show(self, item: DisplayItem) -> None:
        self.current = item
        log.info(
            "display show symbol=%s display=%s name=%s hold_ms=%d",
            item.symbol,
            item.display_name or "-",
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
            "display_name": self.current.display_name if self.current else None,
            "last_error": self.last_error,
        }


class SerialDisplayError(RuntimeError):
    """Base error for Arduino serial communication failures."""


class SerialDisplayDriver:
    """Driver for the Arduino MAX7219 panel serial protocol."""

    name = "serial"
    host_timed_sequences = True

    def __init__(
        self,
        *,
        port: str | None = None,
        baudrate: int = 115200,
        timeout: float = 0.25,
        write_timeout: float = 1.0,
        reset_wait: float = 2.0,
        ack_timeout: float = 1.0,
        expect_ack: bool = True,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.port = port or "auto"
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.write_timeout = float(write_timeout)
        self.reset_wait = max(0.0, float(reset_wait))
        self.ack_timeout = max(0.05, float(ack_timeout))
        self.expect_ack = expect_ack
        self._serial_factory = serial_factory
        self._serial: Any | None = None
        self.current: DisplayItem | None = None
        self.connected = False
        self.last_error: str | None = None
        self.resolved_port: str | None = None

    def show(self, item: DisplayItem) -> None:
        normalized = normalize_emoji(item.symbol, item.name)
        display_name = item.display_name or normalized.display_name
        hold_ms = max(0, int(item.hold_ms))
        self._send_command(f"EMO {display_name} {hold_ms}")
        self.current = DisplayItem(
            symbol=item.symbol,
            name=item.name,
            hold_ms=hold_ms,
            display_name=display_name,
            display_symbol=item.display_symbol or normalized.display_symbol,
        )

    def clear(self) -> None:
        self._send_command("CLEAR")
        self.current = None

    def status(self) -> dict:
        if not self.connected:
            self._ensure_open(raise_on_error=False)
        return {
            "connected": self.connected,
            "driver": self.name,
            "current": self.current.symbol if self.current else None,
            "display_name": self.current.display_name if self.current else None,
            "display_symbol": self.current.display_symbol if self.current else None,
            "last_error": self.last_error,
            "port": self.resolved_port or self.port,
            "baudrate": self.baudrate,
        }

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.close()
        finally:
            self._serial = None
            self.connected = False

    def _send_command(self, command: str) -> None:
        ser = self._ensure_open(raise_on_error=True)
        assert ser is not None

        try:
            ser.write((command + "\n").encode("ascii"))
            ser.flush()
            if self.expect_ack:
                self._read_ack(command)
        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            try:
                ser.close()
            except Exception:  # noqa: BLE001 - best-effort close on broken ports
                pass
            self._serial = None
            if isinstance(exc, SerialDisplayError):
                raise
            raise SerialDisplayError(str(exc)) from exc

        self.last_error = None

    def _ensure_open(self, *, raise_on_error: bool) -> Any | None:
        if self._serial is not None and getattr(self._serial, "is_open", True):
            self.connected = True
            return self._serial

        try:
            factory = self._serial_factory or _pyserial_factory()
            resolved_port = auto_detect_serial_port() if self.port == "auto" else self.port
            if not resolved_port:
                raise SerialDisplayError("serial port is not configured")

            self._serial = factory(
                port=resolved_port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.write_timeout,
            )
            self.resolved_port = resolved_port
            self.connected = True
            if self.reset_wait:
                time.sleep(self.reset_wait)
            self._drain_input()
            self.last_error = None
            return self._serial
        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            self._serial = None
            if raise_on_error:
                if isinstance(exc, SerialDisplayError):
                    raise
                raise SerialDisplayError(str(exc)) from exc
            return None

    def _drain_input(self) -> None:
        if self._serial is None:
            return
        reset_input_buffer = getattr(self._serial, "reset_input_buffer", None)
        if callable(reset_input_buffer):
            reset_input_buffer()

    def _read_ack(self, command: str) -> str:
        assert self._serial is not None
        command_name = command.split(" ", 1)[0]
        deadline = time.monotonic() + self.ack_timeout
        seen: list[str] = []

        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            seen.append(line)
            if line.startswith("OK"):
                return line
            if line.startswith("ERR"):
                raise SerialDisplayError(line)

        details = "; ".join(seen[-3:])
        suffix = f" Last serial lines: {details}" if details else ""
        raise SerialDisplayError(f"no OK response for {command_name}.{suffix}")


def _pyserial_factory() -> Callable[..., Any]:
    try:
        import serial
    except ImportError as exc:
        raise SerialDisplayError(
            "pyserial is not installed; run `pip install -e .` or `pip install pyserial`"
        ) from exc
    return serial.Serial


def auto_detect_serial_port() -> str:
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise SerialDisplayError("pyserial is not installed; cannot auto-detect serial ports") from exc

    ports = list(list_ports.comports())
    if not ports:
        raise SerialDisplayError("no serial ports found; set EMOJI_DISPLAY_PORT or --serial-port")

    preferred: list[str] = []
    for port in ports:
        device = str(getattr(port, "device", "") or "")
        text = " ".join(
            str(getattr(port, attr, "") or "")
            for attr in ("device", "description", "manufacturer", "product", "hwid")
        ).casefold()
        if any(
            marker in text
            for marker in ("arduino", "promicro", "pro micro", "usb serial", "usbmodem", "usbserial", "ch340")
        ):
            preferred.append(device)
        elif any(marker in device for marker in ("/dev/ttyACM", "/dev/ttyUSB", "/dev/cu.usb", "COM")):
            preferred.append(device)

    candidates = preferred or [str(getattr(port, "device", "") or "") for port in ports]
    candidates = [candidate for candidate in dict.fromkeys(candidates) if candidate]
    if len(candidates) == 1:
        return candidates[0]

    raise SerialDisplayError(
        "multiple serial ports found; choose one with --serial-port: " + ", ".join(candidates)
    )
