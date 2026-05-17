from __future__ import annotations

import pytest

from emoji_display.driver import DisplayItem, SerialDisplayDriver, SerialDisplayError


class FakeSerial:
    is_open = True

    def __init__(self, responses: list[bytes] | None = None) -> None:
        self.responses = responses or []
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        command = data.decode("ascii").strip()
        if command.startswith("EMO "):
            self.responses.append(b"OK EMO\n")
        elif command == "CLEAR":
            self.responses.append(b"OK CLEAR\n")
        return len(data)

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        if self.responses:
            return self.responses.pop(0)
        return b""

    def reset_input_buffer(self) -> None:
        self.responses.clear()

    def close(self) -> None:
        self.closed = True
        self.is_open = False


def test_serial_driver_sends_normalized_emoji_command():
    fake = FakeSerial()
    driver = SerialDisplayDriver(port="COM9", reset_wait=0, serial_factory=lambda **_: fake)

    driver.show(DisplayItem("😺", hold_ms=900))

    assert fake.writes == [b"EMO CAT 900\n"]
    assert driver.status()["display_name"] == "CAT"
    assert driver.status()["connected"] is True


def test_serial_driver_clear_sends_clear_command():
    fake = FakeSerial()
    driver = SerialDisplayDriver(port="COM9", reset_wait=0, serial_factory=lambda **_: fake)

    driver.clear()

    assert fake.writes == [b"CLEAR\n"]
    assert driver.status()["current"] is None


def test_serial_driver_raises_on_arduino_error():
    class ErrorSerial(FakeSerial):
        def write(self, data: bytes) -> int:
            self.writes.append(data)
            self.responses.append(b"ERR: unknown EMO name. Try LIST.\n")
            return len(data)

    fake = ErrorSerial()
    driver = SerialDisplayDriver(port="COM9", reset_wait=0, serial_factory=lambda **_: fake)

    with pytest.raises(SerialDisplayError, match="unknown EMO"):
        driver.show(DisplayItem("HAPPY", hold_ms=100))
