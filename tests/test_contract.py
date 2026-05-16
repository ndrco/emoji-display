from __future__ import annotations

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

    assert response == {"ok": True, "current": "🙂"}
    assert driver.shown == [DisplayItem("🙂", "slightly_smiling_face", 900)]
    assert app.status()["current"] == "🙂"
    assert app.status()["last_source"] == "listener"


def test_sequence_accepts_items_and_clear_resets_state():
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

    assert response == {"ok": True, "current": "✨", "accepted": 2}
    assert clear_response == {"ok": True}
    assert [item.symbol for item in driver.shown] == ["🙂", "✨"]
    assert driver.cleared == 1
    assert app.status()["current"] is None
    assert app.status()["last_reason"] == "interrupt"
