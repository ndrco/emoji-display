# emoji-display

`emoji-display` is a local bridge between applications and a small Arduino LED
emoji panel. It owns the serial port, normalizes incoming emoji to the limited
set supported by the 8x8 matrix, and exposes both HTTP and CLI interfaces.

The bundled firmware lives in
[`Arduino/max7219_emoji_panel`](Arduino/max7219_emoji_panel). Flash the Arduino
first, then come back here to install the daemon.

## What You Get

- A local HTTP daemon for showing emoji on the panel.
- A `displayctl` CLI for testing and debugging.
- Automatic emoji normalization such as `😺 -> CAT`, `🚀 -> CAR`,
  `🌸 -> FLOWER`, `☔ -> RAIN`.
- Serial port auto-detection when the Arduino changes from `/dev/ttyACM0` to
  `/dev/ttyACM1`.
- `systemd` service templates for both system-wide and per-user installs.

## Quick Start

This is the shortest path from a freshly flashed Arduino to a working local
service on Linux.

1. Flash the firmware from
   [`Arduino/max7219_emoji_panel`](Arduino/max7219_emoji_panel).
2. Disconnect the Arduino IDE Serial Monitor after flashing.
3. Find the stable serial path:

```bash
ls -l /dev/serial/by-id/
```

You want the Arduino path, for example:

```text
/dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00
```

4. Clone the repository and install it:

```bash
git clone https://github.com/ndrco/emoji-display.git
cd emoji-display
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

5. Start the daemon manually:

```bash
emoji-displayd --driver serial --serial-port /dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00
```

6. In another terminal, check that it is alive:

```bash
curl http://127.0.0.1:18791/v1/status
displayctl --url http://127.0.0.1:18791 status
```

When the driver opens the port it logs the resolved device, for example:

```text
opening serial display port /dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00 (configured)
```

If that works, continue to one of the service setups below.

## Requirements

- Linux, macOS, or Windows.
- Python 3.10+.
- A flashed Arduino-compatible board connected over USB.
- `pyserial` is installed automatically with the package.

Linux users should prefer `/dev/serial/by-id/...` over `/dev/ttyACM0` or
`/dev/ttyUSB0`, because the `by-id` path stays stable across reconnects.

## Run Manually

Explicit port:

```bash
emoji-displayd --driver serial --serial-port /dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00
```

Auto-detect:

```bash
emoji-displayd --driver serial
```

Auto-detect works well when one Arduino-like serial device is clearly
identifiable. When several USB serial devices are connected, the daemon tries
to prefer real Arduino metadata and then probes candidates for the panel boot
banner.

Windows PowerShell example:

```powershell
.\.venv\Scripts\emoji-displayd --driver serial --serial-port COM3
```

## Service Setup

There are two supported service styles:

- `systemd --user`: easiest when you install into your home directory and do
  not want `sudo`.
- system-wide `systemd`: best when the service should survive logout and live in
  `/opt/emoji-display`.

## User Service

This is the easiest GitHub-friendly Linux install.

1. Install the repo in your preferred location, for example
   `/home/<user>/Applications/emoji-display`.
2. Create an environment file:

```bash
mkdir -p ~/.config/emoji-display
cp packaging/systemd/emoji-display.env.example ~/.config/emoji-display/emoji-display.env
```

3. Edit `~/.config/emoji-display/emoji-display.env`.

Recommended:

```bash
EMOJI_DISPLAY_PORT=/dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00
```

Or leave `EMOJI_DISPLAY_PORT` unset to use auto-detection.

4. Create `~/.config/systemd/user/emoji-display.service`:

```ini
[Unit]
Description=Emoji Display Arduino bridge
Documentation=https://github.com/ndrco/emoji-display
After=default.target

[Service]
Type=simple
WorkingDirectory=/home/USER/Applications/emoji-display
EnvironmentFile=-/home/USER/.config/emoji-display/emoji-display.env
ExecStart=/home/USER/Applications/emoji-display/.venv/bin/emoji-displayd --driver serial
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
```

Replace `USER` with your real username.

5. Enable and start it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now emoji-display.service
```

6. Verify:

```bash
systemctl --user status emoji-display.service
journalctl --user -u emoji-display.service -f
curl http://127.0.0.1:18791/v1/status
```

## System-Wide Service

Use this when you want a conventional machine-wide service.

```bash
sudo useradd --system --home-dir /opt/emoji-display \
  --shell /usr/sbin/nologin --groups dialout emoji-display
sudo mkdir -p /etc/emoji-display
sudo git clone https://github.com/ndrco/emoji-display.git /opt/emoji-display
sudo python3 -m venv /opt/emoji-display/.venv
sudo /opt/emoji-display/.venv/bin/pip install -e /opt/emoji-display
sudo cp packaging/systemd/emoji-display.env.example /etc/emoji-display/emoji-display.env
sudo nano /etc/emoji-display/emoji-display.env
sudo cp packaging/systemd/emoji-display.service /etc/systemd/system/emoji-display.service
sudo systemctl daemon-reload
sudo systemctl enable --now emoji-display
```

Then verify:

```bash
sudo systemctl status emoji-display
sudo journalctl -u emoji-display -f
curl http://127.0.0.1:18791/v1/status
```

Use a stable port in `/etc/emoji-display/emoji-display.env` when possible:

```bash
EMOJI_DISPLAY_PORT=/dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00
```

If you leave the port unset, watch the journal for the resolved port name.

## Verify The Install

Useful checks after any install:

```bash
curl http://127.0.0.1:18791/v1/status
displayctl --url http://127.0.0.1:18791 status
displayctl --url http://127.0.0.1:18791 supported
displayctl --url http://127.0.0.1:18791 show "😺"
displayctl --url http://127.0.0.1:18791 clear --reason test
```

Expected signs of success:

- `/v1/status` returns `"connected": true`.
- The reported `"port"` is the Arduino serial device.
- Logs contain `opening serial display port ...`.
- The matrix reacts to `displayctl show`.

## Troubleshooting

`The daemon says "multiple serial ports found"`:
Use `/dev/serial/by-id/...` explicitly, or disconnect the other USB serial
devices while testing.

`Nothing happens on the display`:
Make sure the Arduino IDE Serial Monitor is closed. Only one process can own the
serial port at a time.

`Permission denied on /dev/ttyACM0 or /dev/ttyUSB0`:
Your user probably needs the serial group, usually `dialout`. Some
distributions use `uucp` or `lock` instead.

`The Arduino changes from /dev/ttyACM0 to /dev/ttyACM1`:
Use `/dev/serial/by-id/...` in your env file instead of the moving `/dev/tty*`
name.

`The service started but the first HTTP request feels slow`:
The serial driver opens the Arduino lazily on first use and may wait for the
board reset timeout before the first response.

`Auto-detect still picks the wrong device`:
Pin `EMOJI_DISPLAY_PORT` to the exact `/dev/serial/by-id/...` path.

## Supported Display Names

The Arduino panel currently contains these display names:

```text
HAPPY LAUGH WINK SURPRISE SAD CRY ANGRY LOVE KISS COOL SLEEP NEUTRAL
CONFUSED THINK TONGUE DEAD WOW HEART YES NO OK ALERT MUSIC ROBOT GHOST
CAT DOG FOOD STAR CAR FLOWER RAIN DEFAULT
```

Emoji without an exact hardware drawing are classified by domain when possible:

- transport -> `CAR`
- plants -> `FLOWER`
- weather -> `RAIN`
- food and drinks -> `FOOD`
- music and instruments -> `MUSIC`
- sparkles, fireworks, stars -> `STAR`
- truly unknown -> `DEFAULT`

To add a new hardware icon, add frames to
[`Arduino/max7219_emoji_panel/emojis.h`](Arduino/max7219_emoji_panel/emojis.h)
and then add normalization rules in
[`src/emoji_display/emoji.py`](src/emoji_display/emoji.py).

## CLI

```bash
displayctl status
displayctl supported
displayctl normalize "😺"
displayctl show "😺"
displayctl clear --reason interrupt
```

Use top-level options before the command when the daemon is not running on
`http://127.0.0.1:18791`:

```bash
displayctl --url http://127.0.0.1:18791 status
```

If the daemon uses a bearer token, pass `--token`.

## HTTP API

`GET /v1/status`

```json
{
  "ok": true,
  "connected": true,
  "driver": "serial",
  "current": "😺",
  "display_name": "CAT",
  "display_symbol": "🐱",
  "queue_size": 0,
  "last_error": null
}
```

`GET /v1/supported`

`POST /v1/show`

```json
{
  "symbol": "😺",
  "name": "smiling_cat_face",
  "hold_ms": 7000,
  "mode": "replace",
  "source": "listener",
  "id": "run-123:segment-4:0"
}
```

If `hold_ms` is omitted, the server uses its default `7000` ms.

When a new symbol arrives while another one is still fresh, the daemon keeps
the current symbol for at most `1600` ms total, then replaces it with the latest
incoming symbol. The Arduino firmware has its own standalone default `1600` ms,
used only when the board receives `EMO <name>` without an explicit duration.

`POST /v1/sequence` is accepted for compatibility, but it never queues display
items. The daemon selects the last item in the request and ignores the rest.

`POST /v1/clear`

```json
{
  "source": "listener",
  "reason": "interrupt"
}
```

If `--token` is set, clients must send `Authorization: Bearer <token>`.

## Firmware And Hardware Notes

The wiring guide, component list, and firmware details live in
[`Arduino/max7219_emoji_panel/README.md`](Arduino/max7219_emoji_panel/README.md).
That document covers:

- required Arduino and MAX7219 hardware
- LDR and potentiometer wiring
- Arduino IDE setup
- the serial protocol
- manual hardware testing
- tuning brightness and animation timing

## Development

```bash
.venv/bin/python -m pytest -q
```

The Arduino helper
[`Arduino/max7219_emoji_panel/test_all_emojis.py`](Arduino/max7219_emoji_panel/test_all_emojis.py)
is a manual hardware test, not a pytest test:

```bash
python Arduino/max7219_emoji_panel/test_all_emojis.py /dev/ttyACM0
```

## Listener Config Example

```json
{
  "speaker": {
    "emoji_display": {
      "enabled": true,
      "url": "http://127.0.0.1:18791",
      "timeout_s": 0.25,
      "mode": "replace",
      "source": "listener",
      "send": "last",
      "clear_on_interrupt": true
    }
  }
}
```
