from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .driver import DisplayDriver, DisplayItem, LoggingDisplayDriver

log = logging.getLogger(__name__)


@dataclass(slots=True)
class DisplayState:
    current: str | None = None
    queue_size: int = 0
    last_error: str | None = None
    last_source: str | None = None
    last_id: str | None = None
    last_reason: str | None = None


@dataclass(slots=True)
class EmojiDisplayApp:
    driver: DisplayDriver = field(default_factory=LoggingDisplayDriver)
    state: DisplayState = field(default_factory=DisplayState)

    def status(self) -> dict:
        driver_status = self.driver.status()
        return {
            "ok": True,
            "connected": bool(driver_status.get("connected")),
            "driver": driver_status.get("driver", self.driver.name),
            "current": self.state.current,
            "queue_size": self.state.queue_size,
            "last_error": self.state.last_error or driver_status.get("last_error"),
            "last_source": self.state.last_source,
            "last_id": self.state.last_id,
            "last_reason": self.state.last_reason,
        }

    def show(self, payload: dict[str, Any]) -> dict:
        item = _item_from_payload(payload)
        mode = _mode_from_payload(payload)
        if mode == "replace":
            self.state.queue_size = 0
        self.driver.show(item)
        self.state.current = item.symbol
        self.state.last_source = _optional_text(payload.get("source"))
        self.state.last_id = _optional_text(payload.get("id"))
        self.state.last_reason = None
        self.state.last_error = None
        log.debug("show accepted symbol=%s mode=%s source=%s", item.symbol, mode, self.state.last_source)
        return {"ok": True, "current": self.state.current}

    def sequence(self, payload: dict[str, Any]) -> dict:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("items must be a non-empty array")
        mode = _mode_from_payload(payload)
        if mode == "replace":
            self.state.queue_size = 0
        else:
            self.state.queue_size += max(0, len(raw_items) - 1)
        last_item: DisplayItem | None = None
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise ValueError("each sequence item must be an object")
            last_item = _item_from_payload(raw_item)
            self.driver.show(last_item)
        self.state.current = last_item.symbol if last_item else None
        self.state.last_source = _optional_text(payload.get("source"))
        self.state.last_id = _optional_text(payload.get("id"))
        self.state.last_reason = None
        self.state.last_error = None
        log.debug(
            "sequence accepted count=%d mode=%s source=%s",
            len(raw_items),
            mode,
            self.state.last_source,
        )
        return {"ok": True, "current": self.state.current, "accepted": len(raw_items)}

    def clear(self, payload: dict[str, Any]) -> dict:
        self.driver.clear()
        self.state.current = None
        self.state.queue_size = 0
        self.state.last_source = _optional_text(payload.get("source"))
        self.state.last_reason = _optional_text(payload.get("reason"))
        self.state.last_id = None
        self.state.last_error = None
        log.debug("clear accepted source=%s reason=%s", self.state.last_source, self.state.last_reason)
        return {"ok": True}


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
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="emoji-displayd")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18791)
    parser.add_argument("--token", default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = EmojiDisplayApp()
    server = EmojiDisplayServer((args.host, args.port), app, token=args.token)
    log.info("emoji-display listening on http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


def _item_from_payload(payload: dict[str, Any]) -> DisplayItem:
    symbol = _required_text(payload.get("symbol"), "symbol")
    return DisplayItem(
        symbol=symbol,
        name=_optional_text(payload.get("name")),
        hold_ms=max(0, int(payload.get("hold_ms", 1200) or 0)),
    )


def _mode_from_payload(payload: dict[str, Any]) -> str:
    mode = str(payload.get("mode") or "replace").strip().casefold()
    if mode not in {"replace", "queue"}:
        raise ValueError("mode must be 'replace' or 'queue'")
    return mode


def _required_text(value: Any, field_name: str) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
