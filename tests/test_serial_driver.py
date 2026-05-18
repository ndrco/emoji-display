from __future__ import annotations

import pytest
from serial.tools import list_ports

from emoji_display.driver import DisplayItem, SerialDisplayDriver, SerialDisplayError, auto_detect_serial_port


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


class FakePort:
    def __init__(
        self,
        device: str,
        *,
        description: str = "",
        manufacturer: str | None = None,
        product: str | None = None,
        interface: str | None = None,
        hwid: str = "",
        vid: int | None = None,
        pid: int | None = None,
    ) -> None:
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.product = product
        self.interface = interface
        self.hwid = hwid
        self.vid = vid
        self.pid = pid


class ProbeSerial(FakeSerial):
    def __init__(self, responses: list[bytes] | None = None) -> None:
        super().__init__(responses=responses)

    def reset_input_buffer(self) -> None:
        pass


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


def test_serial_driver_logs_resolved_port(caplog):
    fake = FakeSerial()
    driver = SerialDisplayDriver(port="COM9", reset_wait=0, serial_factory=lambda **_: fake)

    with caplog.at_level("INFO"):
        driver.show(DisplayItem("😺", hold_ms=900))

    assert "opening serial display port COM9 (configured)" in caplog.text


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


def test_auto_detect_prefers_actual_arduino_metadata(monkeypatch):
    ports = [
        FakePort("/dev/ttyUSB0", description="FT231X USB UART", manufacturer="FTDI", product="FT231X USB UART"),
        FakePort("/dev/ttyUSB1", description="CP2102 USB to UART Bridge Controller", manufacturer="Silicon Labs"),
        FakePort(
            "/dev/ttyACM0",
            description="Arduino Micro",
            manufacturer="Arduino LLC",
            product="Arduino Micro",
            vid=0x2341,
            pid=0x8037,
        ),
    ]
    monkeypatch.setattr(list_ports, "comports", lambda: ports)

    detected = auto_detect_serial_port(reset_wait=0)

    assert detected == "/dev/ttyACM0"


def test_auto_detect_can_probe_banner_when_metadata_is_ambiguous(monkeypatch):
    ports = [
        FakePort("/dev/ttyUSB0", description="USB Serial"),
        FakePort("/dev/ttyUSB1", description="USB Serial"),
    ]
    monkeypatch.setattr(list_ports, "comports", lambda: ports)

    def serial_factory(**kwargs):
        if kwargs["port"] == "/dev/ttyUSB1":
            return ProbeSerial([b"MAX7219 8x8 Emoji Panel ready.\n"])
        return ProbeSerial()

    detected = auto_detect_serial_port(serial_factory=serial_factory, reset_wait=0, ack_timeout=0.05, timeout=0.01)

    assert detected == "/dev/ttyUSB1"
