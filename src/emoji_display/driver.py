from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .emoji import normalize_emoji

log = logging.getLogger(__name__)

_AUTO_DETECT_BANNER_MARKERS = (
    "MAX7219 8x8 Emoji Panel ready.",
    "Available EMO names:",
    "Commands:",
)
_ARDUINO_USB_IDS = {
    (0x2341, 0x8037),  # Arduino Micro
    (0x2341, 0x8036),  # Leonardo
    (0x2341, 0x0037),  # older Arduino Micro VID/PID pair
    (0x2341, 0x0036),  # older Leonardo VID/PID pair
    (0x2A03, 0x8037),  # Arduino.org Micro
    (0x2A03, 0x8036),  # Arduino.org Leonardo
    (0x1B4F, 0x9205),  # SparkFun Pro Micro 5V
    (0x1B4F, 0x9203),  # SparkFun Pro Micro 3.3V
}


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
            resolved_port = (
                auto_detect_serial_port(
                    serial_factory=factory,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.write_timeout,
                    reset_wait=self.reset_wait,
                    ack_timeout=self.ack_timeout,
                )
                if self.port == "auto"
                else self.port
            )
            if not resolved_port:
                raise SerialDisplayError("serial port is not configured")

            log.info(
                "opening serial display port %s (%s)",
                resolved_port,
                "auto-detected" if self.port == "auto" else "configured",
            )
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


def auto_detect_serial_port(
    *,
    serial_factory: Callable[..., Any] | None = None,
    baudrate: int = 115200,
    timeout: float = 0.25,
    write_timeout: float = 1.0,
    reset_wait: float = 2.0,
    ack_timeout: float = 1.0,
) -> str:
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise SerialDisplayError("pyserial is not installed; cannot auto-detect serial ports") from exc

    ports = list(list_ports.comports())
    if not ports:
        raise SerialDisplayError("no serial ports found; set EMOJI_DISPLAY_PORT or --serial-port")

    scored_candidates: list[tuple[int, str]] = []
    for port in ports:
        device = str(getattr(port, "device", "") or "")
        score = _serial_port_score(port)
        if score > 0:
            scored_candidates.append((score, device))

    candidates = [device for _, device in scored_candidates] or [str(getattr(port, "device", "") or "") for port in ports]
    candidates = [candidate for candidate in dict.fromkeys(candidates) if candidate]
    if len(candidates) == 1:
        return candidates[0]

    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    if scored_candidates:
        best_score, best_device = scored_candidates[0]
        best_devices = [device for score, device in scored_candidates if score == best_score]
        if len(best_devices) == 1:
            return best_device

    factory = serial_factory or _pyserial_factory()
    probed = _probe_serial_candidates(
        candidates,
        serial_factory=factory,
        baudrate=baudrate,
        timeout=timeout,
        write_timeout=write_timeout,
        reset_wait=reset_wait,
        ack_timeout=ack_timeout,
    )
    if len(probed) == 1:
        return probed[0]
    if len(probed) > 1:
        raise SerialDisplayError(
            "multiple Arduino-like serial ports responded; choose one with --serial-port: " + ", ".join(probed)
        )

    raise SerialDisplayError(
        "multiple serial ports found; choose one with --serial-port: " + ", ".join(candidates)
    )


def _serial_port_score(port: Any) -> int:
    device = str(getattr(port, "device", "") or "")
    text = " ".join(
        str(getattr(port, attr, "") or "")
        for attr in ("device", "description", "manufacturer", "product", "interface", "hwid")
    ).casefold()
    vid = getattr(port, "vid", None)
    pid = getattr(port, "pid", None)

    score = 0
    if (vid, pid) in _ARDUINO_USB_IDS:
        score += 100
    if any(marker in text for marker in ("arduino", "promicro", "pro micro", "leonardo", "arduino micro")):
        score += 80
    if any(marker in device for marker in ("/dev/ttyACM", "/dev/cu.usbmodem")):
        score += 30
    if any(marker in text for marker in ("ch340", "wch usb serial", "usb serial", "usbmodem", "usbserial")):
        score += 15
    if any(marker in device for marker in ("/dev/ttyUSB", "/dev/cu.usbserial", "COM")):
        score += 10
    if device and os.path.exists(device):
        score += 1
    return score


def _probe_serial_candidates(
    candidates: list[str],
    *,
    serial_factory: Callable[..., Any],
    baudrate: int,
    timeout: float,
    write_timeout: float,
    reset_wait: float,
    ack_timeout: float,
) -> list[str]:
    matched: list[str] = []
    for candidate in candidates:
        if _serial_port_looks_like_panel(
            candidate,
            serial_factory=serial_factory,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=write_timeout,
            reset_wait=reset_wait,
            ack_timeout=ack_timeout,
        ):
            matched.append(candidate)
    return matched


def _serial_port_looks_like_panel(
    device: str,
    *,
    serial_factory: Callable[..., Any],
    baudrate: int,
    timeout: float,
    write_timeout: float,
    reset_wait: float,
    ack_timeout: float,
) -> bool:
    ser: Any | None = None
    try:
        ser = serial_factory(
            port=device,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=write_timeout,
        )
        reset_input_buffer = getattr(ser, "reset_input_buffer", None)
        if callable(reset_input_buffer):
            reset_input_buffer()
        if reset_wait:
            time.sleep(reset_wait)

        deadline = time.monotonic() + max(ack_timeout, timeout, 0.5)
        seen: list[str] = []
        while time.monotonic() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            seen.append(line)
            if any(marker in line for marker in _AUTO_DETECT_BANNER_MARKERS):
                log.debug("auto-detect matched %s via banner: %s", device, line)
                return True
        if seen:
            log.debug("auto-detect probe for %s saw unrelated serial lines: %s", device, seen[-3:])
        return False
    except Exception as exc:  # noqa: BLE001 - probing should be best-effort only
        log.debug("auto-detect probe failed for %s: %s", device, exc)
        return False
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:  # noqa: BLE001 - best-effort close after probe
                pass
