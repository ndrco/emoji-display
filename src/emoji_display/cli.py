from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .emoji import normalize_emoji, supported_catalog

DEFAULT_URL = "http://127.0.0.1:18791"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="displayctl")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--token", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("supported")

    normalize = sub.add_parser("normalize")
    normalize.add_argument("symbol")
    normalize.add_argument("--name", default=None)

    show = sub.add_parser("show")
    show.add_argument("symbol")
    show.add_argument("--name", default=None)
    show.add_argument("--hold-ms", type=int, default=None)
    show.add_argument("--mode", choices=["replace", "queue"], default="replace")
    show.add_argument("--source", default="displayctl")
    show.add_argument("--id", default=None)

    sequence = sub.add_parser("sequence")
    sequence.add_argument("symbols", nargs="+")
    sequence.add_argument("--hold-ms", type=int, default=None)
    sequence.add_argument("--mode", choices=["replace", "queue"], default="queue")
    sequence.add_argument("--source", default="displayctl")
    sequence.add_argument("--id", default=None)

    clear = sub.add_parser("clear")
    clear.add_argument("--source", default="displayctl")
    clear.add_argument("--reason", default="manual")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            payload = _get_json(args.url, "/v1/status", token=args.token)
        elif args.command == "supported":
            try:
                payload = _get_json(args.url, "/v1/supported", token=args.token)
            except RuntimeError as exc:
                if str(exc).startswith("HTTP "):
                    raise
                payload = {"ok": True, "items": supported_catalog(), "source": "local"}
        elif args.command == "normalize":
            match = normalize_emoji(args.symbol, args.name)
            payload = {
                "ok": True,
                "requested": match.requested,
                "display_name": match.display_name,
                "display_symbol": match.display_symbol,
                "matched_by": match.matched_by,
            }
        elif args.command == "show":
            show_payload = {
                "symbol": args.symbol,
                "name": args.name,
                "mode": args.mode,
                "source": args.source,
                "id": args.id,
            }
            if args.hold_ms is not None:
                show_payload["hold_ms"] = args.hold_ms
            payload = _post_json(
                args.url,
                "/v1/show",
                show_payload,
                token=args.token,
            )
        elif args.command == "sequence":
            items = [{"symbol": symbol} for symbol in args.symbols]
            if args.hold_ms is not None:
                for item in items:
                    item["hold_ms"] = args.hold_ms
            payload = _post_json(
                args.url,
                "/v1/sequence",
                {
                    "items": items,
                    "mode": args.mode,
                    "source": args.source,
                    "id": args.id,
                },
                token=args.token,
            )
        elif args.command == "clear":
            payload = _post_json(
                args.url,
                "/v1/clear",
                {"source": args.source, "reason": args.reason},
                token=args.token,
            )
        else:
            raise AssertionError(args.command)
    except RuntimeError as exc:
        print(f"displayctl: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _get_json(base_url: str, path: str, *, token: str | None) -> dict[str, Any]:
    request = urllib.request.Request(_url(base_url, path), headers=_headers(token), method="GET")
    return _open_json(request)


def _post_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    token: str | None,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8", **_headers(token)}
    request = urllib.request.Request(_url(base_url, path), data=data, headers=headers, method="POST")
    return _open_json(request)


def _open_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HTTP {exc.code}: {details or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid JSON response") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("JSON response must be an object")
    return payload


def _url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


if __name__ == "__main__":
    raise SystemExit(main())
