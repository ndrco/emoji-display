# emoji-display

`emoji-display` is a small local bridge for an external LED emoji device.
It owns the hardware connection and exposes a stable HTTP API plus a CLI, so
Listener and other programs do not need to import `serial` or know the Arduino
protocol.

The current skeleton ships with a logging driver only. A later hardware driver
can implement `emoji_display.driver.DisplayDriver` and become the single owner
of the USB COM port.

## Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
emoji-displayd --host 127.0.0.1 --port 18791
```

## CLI

```bash
displayctl status
displayctl show "🙂" --hold-ms 1200
displayctl sequence "🙂" "✨" "❤️"
displayctl clear --reason interrupt
```

Use `--url` when the daemon is not running on `http://127.0.0.1:18791`.

## HTTP API

`GET /v1/status`

```json
{
  "ok": true,
  "connected": true,
  "driver": "logging",
  "current": "🙂",
  "queue_size": 0,
  "last_error": null
}
```

`POST /v1/show`

```json
{
  "symbol": "🙂",
  "name": "slightly_smiling_face",
  "hold_ms": 1200,
  "mode": "replace",
  "source": "listener",
  "id": "run-123:segment-4:0"
}
```

`POST /v1/sequence`

```json
{
  "items": [
    {"symbol": "🙂", "name": "slightly_smiling_face", "hold_ms": 1200},
    {"symbol": "✨", "name": "sparkles", "hold_ms": 1200}
  ],
  "mode": "queue",
  "source": "listener",
  "id": "run-123:segment-4"
}
```

`POST /v1/clear`

```json
{
  "source": "listener",
  "reason": "interrupt"
}
```

If `--token` is set on the daemon, clients must send
`Authorization: Bearer <token>`.

## Listener Config

```json
{
  "speaker": {
    "emoji_display": {
      "enabled": true,
      "url": "http://127.0.0.1:18791",
      "timeout_s": 0.25,
      "hold_ms": 1200,
      "mode": "replace",
      "source": "listener",
      "send": "all",
      "clear_on_interrupt": true
    }
  }
}
```

