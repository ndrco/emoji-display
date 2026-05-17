from __future__ import annotations

from http import HTTPStatus
from io import BytesIO

from emoji_display.server import EmojiDisplayHandler


class BrokenPipeStream(BytesIO):
    def write(self, data: bytes) -> int:
        raise BrokenPipeError(32, "Broken pipe")


def test_send_json_ignores_broken_pipe():
    handler = EmojiDisplayHandler.__new__(EmojiDisplayHandler)
    handler.wfile = BrokenPipeStream()
    sent: list[tuple[str, str]] = []

    handler.send_response = lambda status: sent.append(("status", str(status)))
    handler.send_header = lambda name, value: sent.append((name, value))
    handler.end_headers = lambda: sent.append(("end_headers", ""))

    handler._send_json(HTTPStatus.OK, {"ok": True})

    assert ("status", "200") in sent
    assert ("Content-Type", "application/json; charset=utf-8") in sent
