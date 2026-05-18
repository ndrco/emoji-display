# emoji-display

`emoji-display` is a local bridge between applications and a small Arduino LED
emoji panel. The daemon owns the serial COM port, normalizes incoming emoji to
the limited set supported by the 8x8 matrix, and exposes both HTTP and CLI
interfaces.

The bundled Arduino firmware lives in
[`Arduino/max7219_emoji_panel`](Arduino/max7219_emoji_panel) and speaks a small
serial protocol:

```text
EMO CAT 7000
CLEAR
LIST
```

## Features

- Hardware output through Arduino over a serial COM port.
- Emoji normalization: for example `😺`, `😸`, `😹`, and `smiling cat face`
  are displayed as the built-in `CAT` icon.
- HTTP daemon for integrations and a `displayctl` CLI for manual testing.
- Linux `systemd` unit template for service startup.
- Tests and GitHub Actions workflow for publication.

## Supported Display Names

The Arduino panel currently contains these display names:

```text
HAPPY LAUGH WINK SURPRISE SAD CRY ANGRY LOVE KISS COOL SLEEP NEUTRAL
CONFUSED THINK TONGUE DEAD WOW HEART YES NO OK ALERT MUSIC ROBOT GHOST
CAT DOG FOOD STAR CAR FLOWER RAIN DEFAULT
```

Emoji that do not have an exact hardware drawing are classified by domain when
possible: transport maps to `CAR`, plants to `FLOWER`, weather to `RAIN`, food
to `FOOD`, music to `MUSIC`, and fireworks or sparkles to `STAR`. Truly
unknown emoji still fall back to `DEFAULT`. To add a new hardware icon, add the
8x8 frames to `Arduino/max7219_emoji_panel/emojis.h`, then add normalization
rules in [`src/emoji_display/emoji.py`](src/emoji_display/emoji.py).

## Install

Linux/macOS:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
```

`pyserial` is installed as a normal dependency because the production driver
uses it to own the Arduino COM port.

## Run With Arduino

1. Flash the firmware from `Arduino/max7219_emoji_panel`.
2. Close Arduino IDE Serial Monitor so the daemon can open the port.
3. Start the daemon with the serial driver:

```bash
emoji-displayd --driver serial --serial-port /dev/ttyACM0
```

On Windows, use a port like `COM3`:

```powershell
.\.venv\Scripts\emoji-displayd --driver serial --serial-port COM3
```

If only one Arduino-like serial device is connected, the daemon can auto-detect:

```bash
emoji-displayd --driver serial
```

Useful environment variables are listed in [`.env.example`](.env.example).

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

Use `--token` the same way if the daemon was started with `--token` or
`EMOJI_DISPLAY_TOKEN`.

If `hold_ms` is omitted, the server uses its default `7000` ms.
When a new symbol arrives while another one is still fresh, the daemon keeps
the current symbol for at most `1600` ms total, then replaces it with the latest
incoming symbol. The Arduino firmware has its own standalone default `1600` ms,
used only when
the board receives `EMO <name>` without an explicit duration.

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

The daemon sends `EMO CAT 7000` to Arduino after normalization.

`POST /v1/sequence`

```json
{
  "items": [
    {"symbol": "🙂", "name": "slightly_smiling_face", "hold_ms": 7000},
    {"symbol": "❤️", "name": "red_heart", "hold_ms": 7000}
  ],
  "mode": "replace",
  "source": "listener",
  "id": "run-123:segment-4"
}
```

`sequence` is accepted for compatibility, but it never queues display items.
The daemon selects the last item in the request, ignores the rest, and reports
`queue_size: 0`.

`POST /v1/clear`

```json
{
  "source": "listener",
  "reason": "interrupt"
}
```

If `--token` is set, clients must send `Authorization: Bearer <token>`.

## systemd Service

The unit template assumes the repository is installed in `/opt/emoji-display`.

```bash
sudo useradd --system --home-dir /opt/emoji-display \
  --shell /usr/sbin/nologin --groups dialout emoji-display
sudo mkdir -p /etc/emoji-display
sudo git clone https://github.com/NDRCo/emoji-display.git /opt/emoji-display
sudo python3 -m venv /opt/emoji-display/.venv
sudo /opt/emoji-display/.venv/bin/pip install -e /opt/emoji-display
sudo cp packaging/systemd/emoji-display.env.example /etc/emoji-display/emoji-display.env
sudo nano /etc/emoji-display/emoji-display.env
sudo cp packaging/systemd/emoji-display.service /etc/systemd/system/emoji-display.service
sudo systemctl daemon-reload
sudo systemctl enable --now emoji-display
sudo journalctl -u emoji-display -f
```

Set `EMOJI_DISPLAY_PORT=/dev/ttyACM0` or the correct device in
`/etc/emoji-display/emoji-display.env`. On some distributions the serial group
is `uucp` or `lock` instead of `dialout`; update the service/user group if
needed.

## Development

```bash
python -m pytest -q
```

The Arduino helper
`Arduino/max7219_emoji_panel/test_all_emojis.py` is a manual hardware test, not
a pytest test. Run it only when the board is connected:

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
