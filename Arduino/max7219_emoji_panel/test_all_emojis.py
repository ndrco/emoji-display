#!/usr/bin/env python3
import argparse
import re
import sys
import time

try:
    import serial
except ImportError:
    print("Не найден модуль pyserial.")
    print("Установи так:")
    print("  sudo apt install python3-serial")
    print("или:")
    print("  python3 -m pip install pyserial")
    sys.exit(1)


LIST_RE = re.compile(
    r"^([A-Z0-9_]{2,24})(?:\s+frames=(\d+)\s+fps=(\d+))?\s*$"
)


def read_lines_for(ser, seconds: float):
    end_time = time.time() + seconds
    lines = []

    while time.time() < end_time:
        raw = ser.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            lines.append(line)

    return lines


def send_command(ser, cmd: str):
    print(f">>> {cmd}")
    ser.write((cmd + "\n").encode("utf-8"))
    ser.flush()


def get_emoji_list(ser):
    ser.reset_input_buffer()

    send_command(ser, "LIST")
    lines = read_lines_for(ser, 2.0)

    print("\nОтвет на LIST:")
    for line in lines:
        print("  " + line)

    emojis = []

    for line in lines:
        m = LIST_RE.match(line.strip())
        if not m:
            continue

        name = m.group(1)
        frames = int(m.group(2)) if m.group(2) else None
        fps = int(m.group(3)) if m.group(3) else None

        # Отсекаем служебные слова, если вдруг они прошли regex
        if name in {"IMG", "EMO", "LIST", "CLEAR", "DEBUG", "HELP"}:
            continue

        emojis.append({
            "name": name,
            "frames": frames,
            "fps": fps,
        })

    # Убираем дубли по имени, сохраняя порядок
    unique = []
    seen = set()

    for e in emojis:
        if e["name"] not in seen:
            unique.append(e)
            seen.add(e["name"])

    return unique


def main():
    parser = argparse.ArgumentParser(
        description="Проверка всех EMO-анимаций MAX7219 через Arduino Serial"
    )

    parser.add_argument(
        "port",
        help="Serial-порт Arduino, например /dev/ttyACM0 или /dev/ttyUSB0"
    )

    parser.add_argument(
        "-b", "--baud",
        type=int,
        default=115200,
        help="Скорость Serial, по умолчанию 115200"
    )

    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=1600,
        help="Сколько миллисекунд показывать каждый эмодзи"
    )

    parser.add_argument(
        "-p", "--pause",
        type=float,
        default=0.8,
        help="Пауза после каждого эмодзи в секундах"
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Принудительный FPS для проверки, например --fps 12"
    )

    parser.add_argument(
        "--names",
        nargs="+",
        help="Явный список эмодзи вместо LIST, например: --names HAPPY WINK HEART"
    )

    parser.add_argument(
        "--reset-wait",
        type=float,
        default=2.5,
        help="Пауза после открытия порта; Pro Micro часто перезапускается"
    )

    args = parser.parse_args()

    print(f"Открываю порт {args.port} @ {args.baud}...")

    with serial.Serial(args.port, args.baud, timeout=0.15) as ser:
        time.sleep(args.reset_wait)

        startup_lines = read_lines_for(ser, 0.8)
        if startup_lines:
            print("\nСтартовые сообщения Arduino:")
            for line in startup_lines:
                print("  " + line)

        if args.names:
            emojis = [{"name": n.upper(), "frames": None, "fps": None} for n in args.names]
        else:
            emojis = get_emoji_list(ser)

        if not emojis:
            print("\nНе удалось получить список эмодзи через LIST.")
            print("Проверь:")
            print("  1. Serial Monitor в Arduino IDE закрыт")
            print("  2. порт правильный, например /dev/ttyACM0")
            print("  3. скорость 115200")
            print("  4. прошивка поддерживает команду LIST")
            sys.exit(2)

        print("\nНайденные эмодзи:")
        for e in emojis:
            if e["frames"] is not None and e["fps"] is not None:
                print(f"  {e['name']:12s} frames={e['frames']} fps={e['fps']}")
            else:
                print(f"  {e['name']}")

        print("\nНачинаю проверку...")

        for i, e in enumerate(emojis, 1):
            name = e["name"]

            if args.fps is None:
                cmd = f"EMO {name} {args.duration}"
            else:
                cmd = f"EMO {name} {args.duration} {args.fps}"

            print(f"\n[{i}/{len(emojis)}] {name}")
            send_command(ser, cmd)

            # Прошивка во время показа блокирующая, поэтому просто ждём:
            # время показа + fadeOut + небольшая пауза.
            time.sleep(args.duration / 1000.0 + args.pause)

            # Считываем возможные диагностические строки
            lines = read_lines_for(ser, 0.1)
            for line in lines:
                print("  " + line)

        print("\nГотово. Все эмодзи отправлены.")


if __name__ == "__main__":
    main()
