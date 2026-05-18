from __future__ import annotations

import time

from emoji_display.driver import DisplayItem
from emoji_display.server import EmojiDisplayApp


class RecordingDriver:
    name = "recording"

    def __init__(self) -> None:
        self.shown: list[DisplayItem] = []
        self.cleared = 0

    def show(self, item: DisplayItem) -> None:
        self.shown.append(item)

    def clear(self) -> None:
        self.cleared += 1

    def status(self) -> dict:
        return {"connected": True, "driver": self.name, "last_error": None}


def test_show_updates_state_and_driver():
    driver = RecordingDriver()
    app = EmojiDisplayApp(driver=driver)

    response = app.show(
        {
            "symbol": "🙂",
            "name": "slightly_smiling_face",
            "hold_ms": 900,
            "source": "listener",
            "id": "run:seg:0",
        }
    )

    assert response == {
        "ok": True,
        "current": "🙂",
        "display_name": "HAPPY",
        "display_symbol": "🙂",
        "queue_size": 0,
    }
    assert driver.shown == [DisplayItem("🙂", "slightly_smiling_face", 900, "HAPPY", "🙂")]
    assert app.status()["current"] == "🙂"
    assert app.status()["display_name"] == "HAPPY"
    assert app.status()["last_source"] == "listener"


def test_sequence_replaces_with_last_item_and_clear_resets_state():
    driver = RecordingDriver()
    app = EmojiDisplayApp(driver=driver)

    response = app.sequence(
        {
            "items": [{"symbol": "🙂"}, {"symbol": "✨", "hold_ms": 500}],
            "mode": "queue",
            "source": "test",
        }
    )
    clear_response = app.clear({"source": "test", "reason": "interrupt"})

    assert response == {
        "ok": True,
        "current": "✨",
        "display_name": "STAR",
        "display_symbol": "🌟",
        "queue_size": 0,
        "accepted": 1,
        "ignored": 1,
        "selected": "last",
    }
    assert clear_response == {"ok": True}
    assert [item.symbol for item in driver.shown] == ["✨"]
    assert [item.display_name for item in driver.shown] == ["STAR"]
    assert driver.cleared == 1
    assert app.status()["current"] is None
    assert app.status()["last_reason"] == "interrupt"


def test_sequence_ignores_earlier_invalid_items():
    driver = RecordingDriver()
    app = EmojiDisplayApp(driver=driver)

    response = app.sequence(
        {
            "items": ["not-used", {"symbol": "🙂"}],
            "mode": "queue",
            "source": "test",
        }
    )

    assert response["ok"] is True
    assert response["current"] == "🙂"
    assert response["ignored"] == 1
    assert [item.symbol for item in driver.shown] == ["🙂"]
    assert app.status()["queue_size"] == 0


def test_show_uses_server_default_hold_ms():
    driver = RecordingDriver()
    app = EmojiDisplayApp(driver=driver)

    app.show({"symbol": "✨"})

    assert driver.shown[0].hold_ms == 7000


def test_new_item_replaces_after_interrupt_window():
    driver = RecordingDriver()
    app = EmojiDisplayApp(driver=driver, interrupt_ms=20)

    first_response = app.show({"symbol": "🙂", "hold_ms": 7000})
    second_response = app.show({"symbol": "🐶", "hold_ms": 7000})

    assert first_response["current"] == "🙂"
    assert second_response["current"] == "🙂"
    assert second_response["pending"] == "🐶"
    assert [item.symbol for item in driver.shown] == ["🙂"]

    time.sleep(0.05)

    assert [item.symbol for item in driver.shown] == ["🙂", "🐶"]
    assert app.status()["current"] == "🐶"
    assert app.status()["pending"] is None


def test_pending_sequence_keeps_only_latest_last_item():
    driver = RecordingDriver()
    app = EmojiDisplayApp(driver=driver, interrupt_ms=20)

    app.show({"symbol": "🙂", "hold_ms": 7000})
    first_pending = app.show({"symbol": "🐱", "hold_ms": 7000})
    second_pending = app.sequence(
        {
            "items": [{"symbol": "❤️"}, {"symbol": "✨"}],
            "source": "test",
        }
    )

    assert first_pending["pending"] == "🐱"
    assert second_pending["pending"] == "✨"
    assert second_pending["selected"] == "last"
    assert [item.symbol for item in driver.shown] == ["🙂"]

    time.sleep(0.05)

    assert [item.symbol for item in driver.shown] == ["🙂", "✨"]
    assert app.status()["current"] == "✨"
    assert app.status()["queue_size"] == 0
