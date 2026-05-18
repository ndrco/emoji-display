from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .driver import DisplayDriver, DisplayItem, LoggingDisplayDriver, SerialDisplayDriver
from .emoji import normalize_emoji, supported_catalog

log = logging.getLogger(__name__)


@dataclass(slots=True)
class DisplayState:
    current: str | None = None
    display_name: str | None = None
    display_symbol: str | None = None
    pending: str | None = None
    pending_display_name: str | None = None
    pending_display_symbol: str | None = None
    queue_size: int = 0
    last_error: str | None = None
    last_source: str | None = None
    last_id: str | None = None
    last_reason: str | None = None


@dataclass(slots=True)
class EmojiDisplayApp:
    driver: DisplayDriver = field(default_factory=LoggingDisplayDriver)
    state: DisplayState = field(default_factory=DisplayState)
    interrupt_ms: int = 1600
    clock: Callable[[], float] = time.monotonic
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _current_started_at: float | None = field(default=None, init=False, repr=False)
    _current_until: float | None = field(default=None, init=False, repr=False)
    _pending_item: DisplayItem | None = field(default=None, init=False, repr=False)
    _pending_source: str | None = field(default=None, init=False, repr=False)
    _pending_id: str | None = field(default=None, init=False, repr=False)
    _pending_at: float | None = field(default=None, init=False, repr=False)
    _pending_timer: threading.Timer | None = field(default=None, init=False, repr=False)

    def status(self) -> dict:
        with self.lock:
            driver_status = self.driver.status()
            return {
                "ok": True,
                "connected": bool(driver_status.get("connected")),
                "driver": driver_status.get("driver", self.driver.name),
                "current": self.state.current,
                "display_name": self.state.display_name,
                "display_symbol": self.state.display_symbol,
                "pending": self.state.pending,
                "pending_display_name": self.state.pending_display_name,
                "pending_display_symbol": self.state.pending_display_symbol,
                "queue_size": self.state.queue_size,
                "last_error": self.state.last_error or driver_status.get("last_error"),
                "last_source": self.state.last_source,
                "last_id": self.state.last_id,
                "last_reason": self.state.last_reason,
                "port": driver_status.get("port"),
                "baudrate": driver_status.get("baudrate"),
            }

    def show(self, payload: dict[str, Any]) -> dict:
        with self.lock:
            item = _item_from_payload(payload)
            mode = _mode_from_payload(payload)
            source = _optional_text(payload.get("source"))
            event_id = _optional_text(payload.get("id"))
            response = self._replace_or_defer(item, source=source, event_id=event_id)
            log.debug(
                "show accepted symbol=%s display=%s mode=%s source=%s",
                item.symbol,
                item.display_name,
                mode,
                self.state.last_source,
            )
            return response

    def sequence(self, payload: dict[str, Any]) -> dict:
        with self.lock:
            raw_items = payload.get("items")
            if not isinstance(raw_items, list) or not raw_items:
                raise ValueError("items must be a non-empty array")
            mode = _mode_from_payload(payload)

            raw_item = raw_items[-1]
            if not isinstance(raw_item, dict):
                raise ValueError("last sequence item must be an object")

            item = _item_from_payload(raw_item)
            source = _optional_text(payload.get("source"))
            event_id = _optional_text(payload.get("id"))
            response = self._replace_or_defer(item, source=source, event_id=event_id)
            log.debug(
                "sequence replaced current with last item count=%d mode=%s source=%s",
                len(raw_items),
                mode,
                self.state.last_source,
            )
            response["accepted"] = 1
            response["ignored"] = len(raw_items) - 1
            response["selected"] = "last"
            return response

    def clear(self, payload: dict[str, Any]) -> dict:
        with self.lock:
            self._cancel_pending()
            self.driver.clear()
            self.state.current = None
            self.state.display_name = None
            self.state.display_symbol = None
            self.state.pending = None
            self.state.pending_display_name = None
            self.state.pending_display_symbol = None
            self.state.queue_size = 0
            self.state.last_source = _optional_text(payload.get("source"))
            self.state.last_reason = _optional_text(payload.get("reason"))
            self.state.last_id = None
            self.state.last_error = None
            self._current_started_at = None
            self._current_until = None
            log.debug("clear accepted source=%s reason=%s", self.state.last_source, self.state.last_reason)
            return {"ok": True}

    def _replace_or_defer(self, item: DisplayItem, *, source: str | None, event_id: str | None) -> dict:
        now = self.clock()
        wait_until = self._interrupt_wait_until(now)
        if wait_until is not None:
            self._set_pending(item, source=source, event_id=event_id, when=wait_until)
            return {
                "ok": True,
                "current": self.state.current,
                "display_name": self.state.display_name,
                "display_symbol": self.state.display_symbol,
                "pending": item.symbol,
                "pending_display_name": item.display_name,
                "pending_display_symbol": item.display_symbol,
                "deferred_ms": max(0, int((wait_until - now) * 1000)),
                "queue_size": 0,
            }

        self._cancel_pending()
        self._apply_show(item, source=source, event_id=event_id, now=now)
        return {
            "ok": True,
            "current": self.state.current,
            "display_name": self.state.display_name,
            "display_symbol": self.state.display_symbol,
            "queue_size": 0,
        }

    def _interrupt_wait_until(self, now: float) -> float | None:
        if self.interrupt_ms <= 0 or self._current_started_at is None or self._current_until is None:
            return None
        if now >= self._current_until:
            return None
        wait_until = min(self._current_started_at + self.interrupt_ms / 1000.0, self._current_until)
        return wait_until if now < wait_until else None

    def _set_pending(
        self,
        item: DisplayItem,
        *,
        source: str | None,
        event_id: str | None,
        when: float,
    ) -> None:
        self._pending_item = item
        self._pending_source = source
        self._pending_id = event_id
        self._pending_at = when
        self.state.pending = item.symbol
        self.state.pending_display_name = item.display_name
        self.state.pending_display_symbol = item.display_symbol
        self.state.queue_size = 0
        self.state.last_source = source
        self.state.last_id = event_id
        self.state.last_reason = None
        self.state.last_error = None
        self._schedule_pending(when)

    def _schedule_pending(self, when: float) -> None:
        self._cancel_pending_timer()
        delay = max(0.0, when - self.clock())
        self._pending_timer = threading.Timer(delay, self._flush_pending)
        self._pending_timer.daemon = True
        self._pending_timer.start()

    def _flush_pending(self) -> None:
        with self.lock:
            if self._pending_item is None or self._pending_at is None:
                return
            now = self.clock()
            if now < self._pending_at:
                self._schedule_pending(self._pending_at)
                return
            item = self._pending_item
            source = self._pending_source
            event_id = self._pending_id
            self._clear_pending_state()
            try:
                self._apply_show(item, source=source, event_id=event_id, now=now)
            except Exception as exc:  # noqa: BLE001 - timer thread must not die noisily
                self.state.last_error = str(exc)
                log.exception("pending show failed")

    def _apply_show(self, item: DisplayItem, *, source: str | None, event_id: str | None, now: float) -> None:
        self.driver.show(item)
        self.state.current = item.symbol
        self.state.display_name = item.display_name
        self.state.display_symbol = item.display_symbol
        self.state.pending = None
        self.state.pending_display_name = None
        self.state.pending_display_symbol = None
        self.state.queue_size = 0
        self.state.last_source = source
        self.state.last_id = event_id
        self.state.last_reason = None
        self.state.last_error = None
        self._current_started_at = now
        self._current_until = now + max(0, item.hold_ms) / 1000.0

    def _cancel_pending(self) -> None:
        self._cancel_pending_timer()
        self._clear_pending_state()

    def _cancel_pending_timer(self) -> None:
        if self._pending_timer is not None:
            self._pending_timer.cancel()
            self._pending_timer = None

    def _clear_pending_state(self) -> None:
        self._pending_item = None
        self._pending_source = None
        self._pending_id = None
        self._pending_at = None
        self.state.pending = None
        self.state.pending_display_name = None
        self.state.pending_display_symbol = None


class EmojiDisplayServer(ThreadingHTTPServer):
    def __init__(self, server_address, app: EmojiDisplayApp, token: str | None = None):
        super().__init__(server_address, EmojiDisplayHandler)
        self.app = app
        self.token = token


class EmojiDisplayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: EmojiDisplayServer

    def do_GET(self) -> None:
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if self.path == "/v1/status":
            self._send_json(HTTPStatus.OK, self.server.app.status())
            return
        if self.path == "/v1/supported":
            self._send_json(HTTPStatus.OK, {"ok": True, "items": supported_catalog()})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        try:
            payload = self._read_json()
            if self.path == "/v1/show":
                response = self.server.app.show(payload)
            elif self.path == "/v1/sequence":
                response = self.server.app.sequence(payload)
            elif self.path == "/v1/clear":
                response = self.server.app.clear(payload)
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                return
        except ValueError as exc:
            self.server.app.state.last_error = str(exc)
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - keep daemon alive and report failure
            self.server.app.state.last_error = str(exc)
            log.exception("request failed")
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, response)

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def _authorized(self) -> bool:
        token = self.server.token
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, socket.timeout) as exc:
            log.debug("client disconnected before response was fully sent: %s", exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="emoji-displayd")
    parser.add_argument("--host", default=os.getenv("EMOJI_DISPLAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EMOJI_DISPLAY_HTTP_PORT", "18791")))
    parser.add_argument("--token", default=os.getenv("EMOJI_DISPLAY_TOKEN") or None)
    parser.add_argument("--log-level", default=os.getenv("EMOJI_DISPLAY_LOG_LEVEL", "INFO"))
    parser.add_argument(
        "--driver",
        choices=["logging", "serial"],
        default=os.getenv("EMOJI_DISPLAY_DRIVER", "logging"),
        help="logging for development, serial for the Arduino MAX7219 panel",
    )
    parser.add_argument("--serial-port", default=os.getenv("EMOJI_DISPLAY_PORT") or None)
    parser.add_argument("--baud", type=int, default=int(os.getenv("EMOJI_DISPLAY_BAUD", "115200")))
    parser.add_argument(
        "--serial-timeout",
        type=float,
        default=float(os.getenv("EMOJI_DISPLAY_SERIAL_TIMEOUT", "0.25")),
    )
    parser.add_argument(
        "--serial-write-timeout",
        type=float,
        default=float(os.getenv("EMOJI_DISPLAY_SERIAL_WRITE_TIMEOUT", "1.0")),
    )
    parser.add_argument(
        "--reset-wait",
        type=float,
        default=float(os.getenv("EMOJI_DISPLAY_RESET_WAIT", "2.0")),
    )
    parser.add_argument(
        "--ack-timeout",
        type=float,
        default=float(os.getenv("EMOJI_DISPLAY_ACK_TIMEOUT", "1.0")),
    )
    parser.add_argument(
        "--interrupt-ms",
        type=int,
        default=int(os.getenv("EMOJI_DISPLAY_INTERRUPT_MS", "1600")),
        help="minimum time to keep the current symbol before replacing it",
    )
    parser.add_argument(
        "--no-serial-ack",
        action="store_true",
        default=os.getenv("EMOJI_DISPLAY_NO_SERIAL_ACK", "").lower() in {"1", "true", "yes"},
        help="send commands without waiting for OK/ERR; useful with older firmware",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = EmojiDisplayApp(driver=_driver_from_args(args), interrupt_ms=args.interrupt_ms)
    server = EmojiDisplayServer((args.host, args.port), app, token=args.token)
    log.info(
        "emoji-display listening on http://%s:%d using %s driver",
        args.host,
        args.port,
        app.driver.name,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


def _item_from_payload(payload: dict[str, Any]) -> DisplayItem:
    symbol = _optional_text(payload.get("symbol"))
    name = _optional_text(payload.get("name"))
    if not symbol and not name:
        raise ValueError("symbol or name is required")
    symbol = symbol or name or ""
    match = normalize_emoji(symbol, name)
    return DisplayItem(
        symbol=symbol,
        name=name,
        hold_ms=max(0, int(payload.get("hold_ms", 7000) or 0)),
        display_name=match.display_name,
        display_symbol=match.display_symbol,
    )


def _mode_from_payload(payload: dict[str, Any]) -> str:
    mode = str(payload.get("mode") or "replace").strip().casefold()
    if mode not in {"replace", "queue"}:
        raise ValueError("mode must be 'replace' or 'queue'")
    return mode


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _driver_from_args(args: argparse.Namespace) -> DisplayDriver:
    if args.driver == "logging":
        return LoggingDisplayDriver()
    if args.driver == "serial":
        return SerialDisplayDriver(
            port=args.serial_port,
            baudrate=args.baud,
            timeout=args.serial_timeout,
            write_timeout=args.serial_write_timeout,
            reset_wait=args.reset_wait,
            ack_timeout=args.ack_timeout,
            expect_ack=not args.no_serial_ack,
        )
    raise ValueError(f"unknown driver: {args.driver}")


if __name__ == "__main__":
    raise SystemExit(main())
