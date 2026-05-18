#!/usr/bin/env python3
"""
MAX7219 Emoji Editor
====================

Простой Tkinter-редактор 8x8 эмодзи/анимаций для проекта max7219_emoji_panel.
Умеет:
  - читать текущий emojis.h;
  - редактировать до 4 кадров на эмодзи;
  - задавать индивидуальный FPS;
  - показывать Unicode emoji reference и предлагать имя по Unicode/CLDR-названию;
  - сохранять обновлённый emojis.h в формате, который использует прошивка;
  - примерно оценивать Flash относительно последней компиляции.

Запуск:
  python3 emoji_editor.py
  python3 emoji_editor.py --file ./emojis.h

Зависимости: только стандартная библиотека Python 3 + tkinter.
На Ubuntu, если tkinter не установлен:
  sudo apt install python3-tk
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except Exception as exc:  # pragma: no cover - GUI dependency
    print("Не удалось импортировать tkinter.")
    print("На Ubuntu установи: sudo apt install python3-tk")
    print(f"Ошибка: {exc}")
    raise

# -----------------------------------------------------------------------------
# Параметры железа/прошивки. Их можно переопределить из CLI.
# -----------------------------------------------------------------------------
DEFAULT_TOTAL_FLASH = 28672
DEFAULT_COMPILED_FLASH_USED = 10466

MAX_ANIM_FRAMES = 4
MIN_FPS = 1
MAX_FPS = 30
DEFAULT_FPS = 8

CELL = 34
GRID_PAD = 10

# -----------------------------------------------------------------------------
# Unicode reference.
# Если установлен пакет emoji, редактор сможет взять большой список из него.
# Без него используется встроенный набор самых ходовых emoji.
# -----------------------------------------------------------------------------
FALLBACK_UNICODE_EMOJIS: List[Tuple[str, str]] = [
    ("😀", "GRINNING FACE"),
    ("😃", "GRINNING FACE WITH BIG EYES"),
    ("😄", "GRINNING FACE WITH SMILING EYES"),
    ("😁", "BEAMING FACE WITH SMILING EYES"),
    ("😆", "GRINNING SQUINTING FACE"),
    ("😅", "GRINNING FACE WITH SWEAT"),
    ("😂", "FACE WITH TEARS OF JOY"),
    ("🤣", "ROLLING ON THE FLOOR LAUGHING"),
    ("🙂", "SLIGHTLY SMILING FACE"),
    ("🙃", "UPSIDE-DOWN FACE"),
    ("😉", "WINKING FACE"),
    ("😊", "SMILING FACE WITH SMILING EYES"),
    ("😇", "SMILING FACE WITH HALO"),
    ("🥰", "SMILING FACE WITH HEARTS"),
    ("😍", "SMILING FACE WITH HEART-EYES"),
    ("😘", "FACE BLOWING A KISS"),
    ("😗", "KISSING FACE"),
    ("😋", "FACE SAVORING FOOD"),
    ("😛", "FACE WITH TONGUE"),
    ("😜", "WINKING FACE WITH TONGUE"),
    ("🤪", "ZANY FACE"),
    ("😎", "SMILING FACE WITH SUNGLASSES"),
    ("🤓", "NERD FACE"),
    ("🧐", "FACE WITH MONOCLE"),
    ("🤔", "THINKING FACE"),
    ("🤨", "FACE WITH RAISED EYEBROW"),
    ("😐", "NEUTRAL FACE"),
    ("😑", "EXPRESSIONLESS FACE"),
    ("😶", "FACE WITHOUT MOUTH"),
    ("😏", "SMIRKING FACE"),
    ("😒", "UNAMUSED FACE"),
    ("🙄", "FACE WITH ROLLING EYES"),
    ("😬", "GRIMACING FACE"),
    ("😮", "FACE WITH OPEN MOUTH"),
    ("😯", "HUSHED FACE"),
    ("😲", "ASTONISHED FACE"),
    ("😳", "FLUSHED FACE"),
    ("🥺", "PLEADING FACE"),
    ("😦", "FROWNING FACE WITH OPEN MOUTH"),
    ("😧", "ANGUISHED FACE"),
    ("😨", "FEARFUL FACE"),
    ("😰", "ANXIOUS FACE WITH SWEAT"),
    ("😥", "SAD BUT RELIEVED FACE"),
    ("😢", "CRYING FACE"),
    ("😭", "LOUDLY CRYING FACE"),
    ("😱", "FACE SCREAMING IN FEAR"),
    ("😖", "CONFOUNDED FACE"),
    ("😣", "PERSEVERING FACE"),
    ("😞", "DISAPPOINTED FACE"),
    ("😓", "DOWNCAST FACE WITH SWEAT"),
    ("😩", "WEARY FACE"),
    ("😫", "TIRED FACE"),
    ("🥱", "YAWNING FACE"),
    ("😤", "FACE WITH STEAM FROM NOSE"),
    ("😡", "POUTING FACE"),
    ("😠", "ANGRY FACE"),
    ("🤬", "FACE WITH SYMBOLS ON MOUTH"),
    ("😴", "SLEEPING FACE"),
    ("🤯", "EXPLODING HEAD"),
    ("🥳", "PARTYING FACE"),
    ("🥶", "COLD FACE"),
    ("🥵", "HOT FACE"),
    ("🤖", "ROBOT"),
    ("👻", "GHOST"),
    ("💀", "SKULL"),
    ("👽", "ALIEN"),
    ("😺", "GRINNING CAT"),
    ("😸", "GRINNING CAT WITH SMILING EYES"),
    ("😹", "CAT WITH TEARS OF JOY"),
    ("😻", "SMILING CAT WITH HEART-EYES"),
    ("😼", "CAT WITH WRY SMILE"),
    ("🙀", "WEARY CAT"),
    ("🐶", "DOG FACE"),
    ("🐱", "CAT FACE"),
    ("🐭", "MOUSE FACE"),
    ("🐹", "HAMSTER"),
    ("🐰", "RABBIT FACE"),
    ("🐻", "BEAR"),
    ("🐼", "PANDA"),
    ("🐸", "FROG"),
    ("🐵", "MONKEY FACE"),
    ("❤️", "RED HEART"),
    ("🧡", "ORANGE HEART"),
    ("💛", "YELLOW HEART"),
    ("💚", "GREEN HEART"),
    ("💙", "BLUE HEART"),
    ("💜", "PURPLE HEART"),
    ("🤍", "WHITE HEART"),
    ("🖤", "BLACK HEART"),
    ("💔", "BROKEN HEART"),
    ("💕", "TWO HEARTS"),
    ("💖", "SPARKLING HEART"),
    ("💘", "HEART WITH ARROW"),
    ("⭐", "STAR"),
    ("🌟", "GLOWING STAR"),
    ("✨", "SPARKLES"),
    ("💫", "DIZZY"),
    ("🎆", "FIREWORKS"),
    ("🎇", "SPARKLER"),
    ("🔥", "FIRE"),
    ("💥", "COLLISION"),
    ("⚡", "HIGH VOLTAGE"),
    ("💧", "DROPLET"),
    ("☀️", "SUN"),
    ("🌙", "CRESCENT MOON"),
    ("☁️", "CLOUD"),
    ("🌧️", "CLOUD WITH RAIN"),
    ("⛈️", "CLOUD WITH LIGHTNING AND RAIN"),
    ("☔", "UMBRELLA WITH RAIN DROPS"),
    ("❄️", "SNOWFLAKE"),
    ("✅", "CHECK MARK BUTTON"),
    ("❌", "CROSS MARK"),
    ("⭕", "HOLLOW RED CIRCLE"),
    ("⚠️", "WARNING"),
    ("❗", "RED EXCLAMATION MARK"),
    ("❓", "RED QUESTION MARK"),
    ("👍", "THUMBS UP"),
    ("👎", "THUMBS DOWN"),
    ("👌", "OK HAND"),
    ("👏", "CLAPPING HANDS"),
    ("🙏", "FOLDED HANDS"),
    ("👋", "WAVING HAND"),
    ("🎵", "MUSICAL NOTE"),
    ("🎶", "MUSICAL NOTES"),
    ("🎸", "GUITAR"),
    ("🎹", "MUSICAL KEYBOARD"),
    ("🥁", "DRUM"),
    ("☕", "HOT BEVERAGE"),
    ("🍕", "PIZZA"),
    ("🍔", "HAMBURGER"),
    ("🚗", "AUTOMOBILE"),
    ("🚀", "ROCKET"),
    ("✈️", "AIRPLANE"),
    ("🛸", "FLYING SAUCER"),
    ("🌸", "CHERRY BLOSSOM"),
    ("🌹", "ROSE"),
    ("🌱", "SEEDLING"),
    ("🌳", "DECIDUOUS TREE"),
    ("🔔", "BELL"),
    ("🔕", "BELL WITH SLASH"),
    ("⏰", "ALARM CLOCK"),
    ("💡", "LIGHT BULB"),
    ("🔋", "BATTERY"),
    ("🔌", "ELECTRIC PLUG"),
]

SHORT_ALIASES: Dict[str, str] = {
    "FACE WITH TEARS OF JOY": "LAUGH",
    "WINKING FACE": "WINK",
    "SMILING FACE WITH HEART-EYES": "LOVE",
    "FACE BLOWING A KISS": "KISS",
    "SMILING FACE WITH SUNGLASSES": "COOL",
    "THINKING FACE": "THINK",
    "NEUTRAL FACE": "NEUTRAL",
    "FACE WITH TONGUE": "TONGUE",
    "CRYING FACE": "CRY",
    "ANGRY FACE": "ANGRY",
    "SLEEPING FACE": "SLEEP",
    "ROBOT": "ROBOT",
    "GHOST": "GHOST",
    "DOG FACE": "DOG",
    "CAT FACE": "CAT",
    "RED HEART": "HEART",
    "STAR": "STAR",
    "GLOWING STAR": "STAR",
    "SPARKLES": "STAR",
    "DIZZY": "STAR",
    "FIREWORKS": "STAR",
    "SPARKLER": "STAR",
    "FIRE": "ALERT",
    "DROPLET": "RAIN",
    "SUN": "RAIN",
    "CLOUD": "RAIN",
    "CLOUD WITH RAIN": "RAIN",
    "CLOUD WITH LIGHTNING AND RAIN": "RAIN",
    "UMBRELLA WITH RAIN DROPS": "RAIN",
    "SNOWFLAKE": "RAIN",
    "CHECK MARK BUTTON": "YES",
    "CROSS MARK": "NO",
    "WARNING": "ALERT",
    "MUSICAL NOTE": "MUSIC",
    "MUSICAL NOTES": "MUSIC",
    "GUITAR": "MUSIC",
    "MUSICAL KEYBOARD": "MUSIC",
    "DRUM": "MUSIC",
    "HOT BEVERAGE": "FOOD",
    "PIZZA": "FOOD",
    "HAMBURGER": "FOOD",
    "AUTOMOBILE": "CAR",
    "ROCKET": "CAR",
    "AIRPLANE": "CAR",
    "FLYING SAUCER": "CAR",
    "CHERRY BLOSSOM": "FLOWER",
    "ROSE": "FLOWER",
    "SEEDLING": "FLOWER",
    "DECIDUOUS TREE": "FLOWER",
}

# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------
@dataclass
class EmojiAnim:
    name: str
    frames: List[List[int]] = field(default_factory=lambda: [[0] * 8])
    fps: int = DEFAULT_FPS
    ref_symbol: str = ""
    ref_name: str = ""

    # Поля редактора. Они не сохраняются в emojis.h.
    # virtual_pixels + viewport позволяют сдвигать картинку туда-сюда
    # без потери строк/столбцов, ушедших за видимую область 8x8.
    virtual_pixels: List[Set[Tuple[int, int]]] = field(default_factory=list, repr=False)
    viewports: List[Tuple[int, int]] = field(default_factory=list, repr=False)
    baseline_frames: List[List[int]] = field(default_factory=list, repr=False)
    active_n_frames: int = 0
    baseline_n_frames: int = 0
    saved_signature: Optional[Tuple[object, ...]] = field(default=None, repr=False)
    saved_in_session: bool = field(default=False, repr=False)

    def normalize(self) -> None:
        self.name = sanitize_name(self.name) or "EMOJI"
        self.fps = int(max(MIN_FPS, min(MAX_FPS, self.fps)))
        if not self.frames:
            self.frames = [[0] * 8]
        self.frames = self.frames[:MAX_ANIM_FRAMES]
        for frame in self.frames:
            while len(frame) < 8:
                frame.append(0)
            del frame[8:]
            for i, row in enumerate(frame):
                frame[i] = int(row) & 0xFF
        if self.active_n_frames <= 0:
            self.active_n_frames = len(self.frames)
        self.active_n_frames = max(1, min(MAX_ANIM_FRAMES, self.active_n_frames, len(self.frames)))
        if self.baseline_n_frames <= 0:
            self.baseline_n_frames = self.active_n_frames
        self.baseline_n_frames = max(1, min(MAX_ANIM_FRAMES, self.baseline_n_frames, len(self.frames)))

    @property
    def n_frames(self) -> int:
        """Visible frame count. Frames beyond this value are soft-deleted until save."""
        if self.active_n_frames <= 0:
            return len(self.frames)
        return max(1, min(len(self.frames), int(self.active_n_frames)))

    @property
    def stored_frames(self) -> int:
        """Physical frames kept in the editor, including soft-deleted ones."""
        return len(self.frames)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def sanitize_name(name: str) -> str:
    """Arduino/command-friendly ASCII uppercase name."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.upper()
    name = re.sub(r"[^A-Z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if name and name[0].isdigit():
        name = "E_" + name
    return name[:48]


def cpp_ident_from_name(name: str, used: Optional[set] = None) -> str:
    base = sanitize_name(name) or "EMOJI"
    ident = base
    if used is not None:
        n = 2
        while ident in used:
            ident = f"{base}_{n}"
            n += 1
        used.add(ident)
    return ident


def parse_int_token(tok: str) -> int:
    tok = tok.strip().rstrip(",")
    if tok.startswith(("0b", "0B")):
        return int(tok[2:], 2)
    return int(tok, 0)


def byte_to_bin(v: int) -> str:
    return "0b" + format(int(v) & 0xFF, "08b")


def estimate_payload_flash(anims: List[EmojiAnim]) -> int:
    """Оценка Flash-объёма именно emoji payload: имена + кадры + таблица ANIMS.

    На ATmega32U4 указатели 2 байта. AnimDef: PGM_P(2) + frame ptr(2) + nFrames(1) + fps(1) = ~6 байт.
    Выравнивание у AVR обычно байтовое, так что 6 — хорошая практическая оценка.
    """
    total = 0
    for anim in anims:
        name = sanitize_name(anim.name) or "EMOJI"
        total += len(name.encode("ascii")) + 1      # PROGMEM string + \0
        total += anim.n_frames * 8                 # frame bytes saved to emojis.h
        total += 6                                  # AnimDef table row
    return total


def load_unicode_reference() -> List[Tuple[str, str]]:
    """Пытается взять большой список из пакета emoji, иначе использует fallback."""
    try:
        import emoji  # type: ignore
        refs = []
        data = getattr(emoji, "EMOJI_DATA", {})
        for char, meta in data.items():
            name = ""
            if isinstance(meta, dict):
                name = meta.get("en") or meta.get("E") or ""
            if not name:
                try:
                    name = emoji.demojize(char).strip(":").replace("_", " ").upper()
                except Exception:
                    name = ""
            name = name.strip(": ").replace("_", " ").upper()
            if not name:
                continue
            # Не тащим совсем длинные ZWJ-семьи/флаги в простой список по умолчанию.
            if len(char) > 4:
                continue
            refs.append((char, name))
        refs.sort(key=lambda x: (len(x[1]), x[1]))
        # Добавим fallback в начало/поверх, чтобы популярные были быстро доступны.
        merged = []
        seen = set()
        for item in FALLBACK_UNICODE_EMOJIS + refs:
            if item[0] not in seen:
                merged.append(item)
                seen.add(item[0])
        return merged
    except Exception:
        return FALLBACK_UNICODE_EMOJIS[:]

# -----------------------------------------------------------------------------
# emojis.h parser / writer
# -----------------------------------------------------------------------------
NAME_RE = re.compile(r'const\s+char\s+NAME_(\w+)\[\]\s+PROGMEM\s*=\s*"([^"]*)"\s*;', re.M)
ARRAY_RE = re.compile(r'const\s+uint8_t\s+EMO_(\w+)\[\]\s+PROGMEM\s*=\s*\{(.*?)\}\s*;', re.S)
TABLE_RE = re.compile(r'\{\s*NAME_(\w+)\s*,\s*EMO_(\w+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}')
REF_COMMENT_RE = re.compile(r'//\s*Ref:\s*(.*?)\s+-\s*(.*?)\s*\n\s*const\s+uint8_t\s+EMO_(\w+)\[\]', re.S)
BYTE_RE = re.compile(r'0b[01]{1,8}|0x[0-9A-Fa-f]+|\b\d+\b')


def parse_emojis_h(path: Path) -> List[EmojiAnim]:
    text = path.read_text(encoding="utf-8")

    names = {m.group(1): m.group(2) for m in NAME_RE.finditer(text)}

    refs_by_key: Dict[str, Tuple[str, str]] = {}
    for m in REF_COMMENT_RE.finditer(text):
        sym, ref_name, key = m.group(1).strip(), m.group(2).strip(), m.group(3)
        refs_by_key[key] = (sym, ref_name)

    arrays: Dict[str, List[int]] = {}
    for m in ARRAY_RE.finditer(text):
        key = m.group(1)
        body = m.group(2)

        # Важно: внутри массивов generate_emojis_h() пишет комментарии вида
        #   // frame 0
        # Старый парсер видел цифру "0" в комментарии как байт кадра,
        # из-за чего после сохранения/перезапуска все картинки сдвигались
        # на одну строку вниз. Перед поиском byte-токенов вычищаем C/C++ comments.
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        body = re.sub(r"//.*", "", body)

        values = []
        for tok in BYTE_RE.findall(body):
            try:
                values.append(parse_int_token(tok) & 0xFF)
            except Exception:
                pass
        arrays[key] = values

    anims: List[EmojiAnim] = []
    for m in TABLE_RE.finditer(text):
        name_key, emo_key, n_s, fps_s = m.groups()
        n_frames = max(1, min(MAX_ANIM_FRAMES, int(n_s)))
        fps = max(MIN_FPS, min(MAX_FPS, int(fps_s) or DEFAULT_FPS))
        name = names.get(name_key, name_key)
        values = arrays.get(emo_key, [])[: n_frames * 8]
        while len(values) < n_frames * 8:
            values.append(0)
        frames = [values[i * 8:(i + 1) * 8] for i in range(n_frames)]
        ref_symbol, ref_name = refs_by_key.get(emo_key, ("", ""))
        anims.append(EmojiAnim(name=name, frames=frames, fps=fps, ref_symbol=ref_symbol, ref_name=ref_name,
                               active_n_frames=n_frames, baseline_n_frames=n_frames))

    if not anims:
        raise ValueError(f"Не удалось распарсить ANIMS из {path}")
    for anim in anims:
        anim.normalize()
    return anims


def generate_emojis_h(anims: List[EmojiAnim]) -> str:
    # Нормализация и дедупликация имён команд.
    cleaned: List[EmojiAnim] = []
    used_names = set()
    for anim in anims:
        a = copy.deepcopy(anim)
        a.normalize()
        a.frames = [frame[:] for frame in a.frames[:a.n_frames]]
        a.active_n_frames = len(a.frames)
        a.baseline_n_frames = a.active_n_frames
        base = a.name
        name = base
        n = 2
        while name in used_names:
            name = f"{base}_{n}"
            n += 1
        a.name = name
        used_names.add(name)
        cleaned.append(a)

    used_idents: set = set()
    idents: Dict[str, str] = {}
    for anim in cleaned:
        idents[anim.name] = cpp_ident_from_name(anim.name, used_idents)

    lines: List[str] = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("#include <Arduino.h>")
    lines.append("#include <avr/pgmspace.h>")
    lines.append('#include "config.h"')
    lines.append("")
    lines.append("// This file is generated by emoji_editor.py.")
    lines.append("// Manual edits are possible, but the editor may rewrite formatting on next save.")
    lines.append("")
    lines.append("struct AnimDef {")
    lines.append("  PGM_P name;              // PROGMEM string")
    lines.append("  const uint8_t *frames;   // PROGMEM, nFrames * 8 bytes")
    lines.append("  uint8_t nFrames;         // 1..MAX_ANIM_FRAMES")
    lines.append("  uint8_t fps;             // 0 -> use DEFAULT_ANIM_FPS")
    lines.append("};")
    lines.append("")

    lines.append("// -------------------- NAMES --------------------")
    max_ident = max((len(idents[a.name]) for a in cleaned), default=4)
    for anim in cleaned:
        ident = idents[anim.name]
        pad = " " * max(1, max_ident - len(ident) + 1)
        lines.append(f'const char NAME_{ident}[]{pad}PROGMEM = "{anim.name}";')
    lines.append("")

    lines.append("// -------------------- FRAMES --------------------")
    lines.append("// Every animation is a continuous byte stream:")
    lines.append("//   frame0 rows[0..7], frame1 rows[0..7], ...")
    lines.append("// One row byte = left-to-right pixels, MSB first.")
    lines.append("// Keep NUMBER_OF_FRAMES <= MAX_ANIM_FRAMES.")
    lines.append("")
    for anim in cleaned:
        ident = idents[anim.name]
        if anim.ref_symbol or anim.ref_name:
            ref = (anim.ref_symbol or "?").replace("\n", " ")
            ref_name = (anim.ref_name or "").replace("\n", " ")
            lines.append(f"// Ref: {ref} - {ref_name}")
        lines.append(f"const uint8_t EMO_{ident}[] PROGMEM = {{")
        for fi, frame in enumerate(anim.frames):
            row_bytes = ", ".join(byte_to_bin(v) for v in frame)
            comma = "," if fi < len(anim.frames) - 1 else ""
            lines.append(f"  // frame {fi}")
            lines.append(f"  {row_bytes}{comma}")
        lines.append("};")
        lines.append("")

    lines.append("// -------------------- TABLE --------------------")
    lines.append("// Entry format:")
    lines.append("//   { NAME, FRAME_ARRAY, NUMBER_OF_FRAMES, FPS }")
    lines.append("// FPS=0 means DEFAULT_ANIM_FPS from config.h.")
    lines.append("const AnimDef ANIMS[] PROGMEM = {")
    for anim in cleaned:
        ident = idents[anim.name]
        lines.append(f"  {{ NAME_{ident}, EMO_{ident}, {len(anim.frames)}, {anim.fps} }},")
    lines.append("};")
    lines.append("")
    lines.append("const uint8_t N_ANIMS = sizeof(ANIMS) / sizeof(ANIMS[0]);")
    lines.append("")
    return "\n".join(lines)

# -----------------------------------------------------------------------------
# GUI
# -----------------------------------------------------------------------------
class EmojiEditorApp:
    def __init__(self, root: tk.Tk, args: argparse.Namespace):
        self.root = root
        self.args = args
        self.root.title("MAX7219 Emoji Editor 8x8")
        self.root.geometry("1450x900")

        self.total_flash = int(args.total_flash)
        self.compile_flash_used = int(args.flash_used)

        self.file_path = Path(args.file).resolve() if args.file else self.find_default_file()
        self.animations: List[EmojiAnim] = []
        self.saved_file_signature: Optional[Tuple[object, ...]] = None
        self.loaded_payload_flash = 0
        self.base_flash_est = self.compile_flash_used
        self.current_index = -1
        self.current_frame = 0
        self.drag_value: Optional[bool] = None
        self.debug_var = tk.BooleanVar(value=False)
        self.playing = False
        self.play_after_id: Optional[str] = None

        self.refs = load_unicode_reference()
        self.filtered_refs: List[Tuple[str, str]] = []

        self._build_ui()
        self.load_file(self.file_path)
        self.filter_refs()

    def find_default_file(self) -> Path:
        here = Path(__file__).resolve().parent
        p = here / "emojis.h"
        if p.exists():
            return p
        return Path.cwd() / "emojis.h"

    # ---------------- Virtual edit buffer ----------------
    def frame_to_pixels(self, frame: List[int], viewport: Tuple[int, int] = (0, 0)) -> Set[Tuple[int, int]]:
        """Convert visible 8x8 frame bytes to world-coordinate pixels."""
        vr, vc = viewport
        pixels: Set[Tuple[int, int]] = set()
        for r in range(8):
            row = int(frame[r]) & 0xFF if r < len(frame) else 0
            for c in range(8):
                if row & (1 << (7 - c)):
                    pixels.add((vr + r, vc + c))
        return pixels

    def pixels_to_frame(self, pixels: Set[Tuple[int, int]], viewport: Tuple[int, int]) -> List[int]:
        """Extract visible 8x8 bytes from world-coordinate pixels and viewport."""
        vr, vc = viewport
        out = [0] * 8
        for r in range(8):
            for c in range(8):
                if (vr + r, vc + c) in pixels:
                    out[r] |= 1 << (7 - c)
        return out

    def ensure_editor_state(self, anim: Optional[EmojiAnim]) -> None:
        """Keep virtual buffers, viewports and undo baselines aligned with stored frames.

        Stored frames may be greater than visible frames: reducing "Кадров" only
        soft-deletes the tail. Those hidden frames stay here until explicit save.
        """
        if not anim:
            return
        anim.normalize()
        stored_n = anim.stored_frames
        while len(anim.virtual_pixels) < stored_n:
            i = len(anim.virtual_pixels)
            anim.virtual_pixels.append(self.frame_to_pixels(anim.frames[i], (0, 0)))
        del anim.virtual_pixels[stored_n:]

        while len(anim.viewports) < stored_n:
            anim.viewports.append((0, 0))
        del anim.viewports[stored_n:]

        while len(anim.baseline_frames) < stored_n:
            i = len(anim.baseline_frames)
            anim.baseline_frames.append(anim.frames[i][:])
        del anim.baseline_frames[stored_n:]
        if anim.baseline_n_frames <= 0:
            anim.baseline_n_frames = anim.n_frames

    def reset_virtual_from_visible(self, anim: Optional[EmojiAnim], frame_index: Optional[int] = None,
                                   update_baseline: bool = False) -> None:
        """Drop offscreen edit buffer and rebuild it from visible 8x8 frames."""
        if not anim:
            return
        anim.normalize()
        indexes = range(anim.stored_frames) if frame_index is None else [frame_index]
        self.ensure_editor_state(anim)
        for i in indexes:
            if 0 <= i < anim.n_frames:
                anim.viewports[i] = (0, 0)
                anim.virtual_pixels[i] = self.frame_to_pixels(anim.frames[i], (0, 0))
                if update_baseline:
                    anim.baseline_frames[i] = anim.frames[i][:]

    def sync_frame_from_virtual(self, anim: Optional[EmojiAnim], frame_index: Optional[int] = None) -> None:
        """Write the current viewport contents back into anim.frames."""
        if not anim:
            return
        self.ensure_editor_state(anim)
        i = self.current_frame if frame_index is None else frame_index
        if 0 <= i < anim.n_frames:
            anim.frames[i] = self.pixels_to_frame(anim.virtual_pixels[i], anim.viewports[i])

    def sync_all_frames_from_virtual(self, anim: Optional[EmojiAnim]) -> None:
        if not anim:
            return
        self.ensure_editor_state(anim)
        for i in range(anim.stored_frames):
            self.sync_frame_from_virtual(anim, i)

    def finalize_virtual_buffers(self, anim: Optional[EmojiAnim] = None, update_baseline: bool = True) -> None:
        """Commit visible frames, physically drop soft-deleted frames and clear hidden shift buffers.

        emojis.h stores only active 8x8 frames. While editing, frames beyond
        active_n_frames are recoverable; explicit save makes the deletion real.
        """
        def finalize_one(a: EmojiAnim) -> None:
            self.ensure_editor_state(a)
            self.sync_all_frames_from_virtual(a)
            # Explicit save is the commit point: tail frames hidden by "Кадров"
            # are finally removed from the in-memory model and from emojis.h.
            a.frames = [frame[:] for frame in a.frames[:a.n_frames]]
            a.active_n_frames = len(a.frames)
            a.baseline_n_frames = a.active_n_frames
            self.reset_virtual_from_visible(a, update_baseline=update_baseline)

        if anim is None:
            for a in self.animations:
                finalize_one(a)
        else:
            finalize_one(anim)

    # ---------------- UI construction ----------------
    def _build_ui(self) -> None:
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        # Left: emoji list
        left = ttk.Frame(root, padding=8)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="Эмодзи в emojis.h").grid(row=0, column=0, columnspan=2, sticky="w")
        # Короткая легенда с wraplength: длинный Label в Tkinter расширяет всю левую колонку.
        # Поэтому держим левую панель компактной, как в исходной версии редактора.
        ttk.Label(
            left,
            text="Цвет: красный — не сохранено; зелёный — сохранено в этой сессии",
            font=("TkDefaultFont", 9),
            wraplength=210,
            justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 4))
        self.emoji_list = tk.Listbox(
            left, width=28, height=30, exportselection=False,
            selectforeground="black", selectbackground="#d0d0ff"
        )
        self.emoji_list.grid(row=2, column=0, columnspan=2, sticky="ns")
        self.emoji_list.bind("<<ListboxSelect>>", self.on_list_select)

        ttk.Button(left, text="Новый", command=self.new_emoji).grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(left, text="Дубль", command=self.duplicate_emoji).grid(row=3, column=1, sticky="ew", pady=(6, 0))
        ttk.Button(left, text="Удалить", command=self.delete_emoji).grid(row=4, column=0, sticky="ew")
        ttk.Button(left, text="Переименовать", command=self.rename_emoji).grid(row=4, column=1, sticky="ew")
        ttk.Button(left, text="Копия кадра", command=self.copy_frame_to_next).grid(row=5, column=0, columnspan=2, sticky="ew")
        ttk.Separator(left).grid(row=6, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Button(left, text="Открыть emojis.h", command=self.open_file_dialog).grid(row=7, column=0, columnspan=2, sticky="ew")
        ttk.Button(left, text="Сохранить", command=self.save_file).grid(row=8, column=0, sticky="ew")
        ttk.Button(left, text="Сохранить как…", command=self.save_file_as).grid(row=8, column=1, sticky="ew")

        # Center: editor
        center = ttk.Frame(root, padding=8)
        center.grid(row=0, column=1, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(2, weight=1)

        form = ttk.LabelFrame(center, text="Параметры", padding=8)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Имя команды:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(form, textvariable=self.name_var, width=32)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.name_entry.bind("<FocusOut>", lambda e: (self.apply_form_to_current(), self.refresh_list()))
        self.name_entry.bind("<Return>", lambda e: (self.apply_form_to_current(), self.refresh_list()))
        self.name_entry.bind("<KeyRelease>", lambda e: (self.apply_form_to_current(), self.refresh_list()))

        ttk.Label(form, text="FPS:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.fps_var = tk.IntVar(value=DEFAULT_FPS)
        self.fps_spin = ttk.Spinbox(form, from_=MIN_FPS, to=MAX_FPS, textvariable=self.fps_var, width=5, command=self.apply_form_to_current)
        self.fps_spin.grid(row=0, column=3, sticky="w")
        self.fps_spin.bind("<FocusOut>", lambda e: (self.apply_form_to_current(), self.refresh_list()))

        ttk.Label(form, text="Кадров:").grid(row=0, column=4, sticky="w", padx=(12, 0))
        self.nframes_var = tk.IntVar(value=1)
        self.nframes_spin = ttk.Spinbox(form, from_=1, to=MAX_ANIM_FRAMES, textvariable=self.nframes_var, width=5, command=self.on_nframes_changed)
        self.nframes_spin.grid(row=0, column=5, sticky="w")
        self.nframes_spin.bind("<FocusOut>", lambda e: self.on_nframes_changed())

        ttk.Label(form, text="Текущий кадр:").grid(row=0, column=6, sticky="w", padx=(12, 0))
        self.frame_var = tk.IntVar(value=1)
        self.frame_spin = ttk.Spinbox(form, from_=1, to=MAX_ANIM_FRAMES, textvariable=self.frame_var, width=5, command=self.on_frame_changed)
        self.frame_spin.grid(row=0, column=7, sticky="w")
        self.frame_spin.bind("<FocusOut>", lambda e: self.on_frame_changed())

        tools = ttk.Frame(center)
        tools.grid(row=1, column=0, sticky="ew", pady=(8, 4))
        ttk.Button(tools, text="Отменить", command=self.undo_current_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="Сохранить", command=self.save_current_emoji).pack(side=tk.LEFT, padx=2)
        self.play_button = ttk.Button(tools, text="Play", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Button(tools, text="Очистить кадр", command=self.clear_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="Инвертировать", command=self.invert_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="←", width=3, command=lambda: self.shift_frame(-1, 0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="→", width=3, command=lambda: self.shift_frame(1, 0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="↑", width=3, command=lambda: self.shift_frame(0, -1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="↓", width=3, command=lambda: self.shift_frame(0, 1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="Зеркало X", command=self.mirror_x).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools, text="Зеркало Y", command=self.mirror_y).pack(side=tk.LEFT, padx=2)

        grid_frame = ttk.LabelFrame(center, text="8×8 кадр: клик/drag переключает пиксели", padding=8)
        grid_frame.grid(row=2, column=0, sticky="nsew")
        grid_frame.columnconfigure(0, weight=0)
        grid_frame.columnconfigure(1, weight=1)

        canvas_w = GRID_PAD * 2 + CELL * 8
        canvas_h = GRID_PAD * 2 + CELL * 8
        self.canvas = tk.Canvas(grid_frame, width=canvas_w, height=canvas_h, bg="#d8d8d8", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nw")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag_value", None))
        self.rects: Dict[Tuple[int, int], int] = {}
        for r in range(8):
            for c in range(8):
                x0 = GRID_PAD + c * CELL
                y0 = GRID_PAD + r * CELL
                rect = self.canvas.create_rectangle(x0, y0, x0 + CELL - 2, y0 + CELL - 2, fill="white", outline="#777")
                self.rects[(r, c)] = rect

        side = ttk.Frame(grid_frame, padding=(12, 0, 0, 0))
        side.grid(row=0, column=1, sticky="nsew")
        ttk.Label(side, text="C++ bytes текущего кадра:").pack(anchor="w")
        self.bytes_text = tk.Text(side, width=62, height=10, font=("monospace", 10))
        self.bytes_text.pack(fill=tk.X, pady=(2, 10))
        ttk.Label(side, text="Справка:").pack(anchor="w")
        help_txt = (
            "• 1 кадр = 8 байт Flash.\n"
            "• Имя и таблица ANIMS живут во Flash.\n"
            "• Для команд используйте ASCII: HAPPY, ROBOT, SMILING_FACE."
        )
        ttk.Label(side, text=help_txt, justify=tk.LEFT).pack(anchor="w")

        mem = ttk.LabelFrame(center, text="Память, приблизительная оценка", padding=8)
        mem.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.memory_label = ttk.Label(mem, text="")
        self.memory_label.pack(anchor="w")

        # Right: Unicode reference
        right = ttk.Frame(root, padding=8)
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(3, weight=1)
        ttk.Label(right, text="Unicode emoji reference").grid(row=0, column=0, sticky="w")
        self.ref_filter_var = tk.StringVar()
        ref_filter = ttk.Entry(right, textvariable=self.ref_filter_var, width=34)
        ref_filter.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        ref_filter.bind("<KeyRelease>", lambda e: self.filter_refs())

        self.ref_preview = ttk.Label(right, text="🙂", font=("sans", 44))
        self.ref_preview.grid(row=2, column=0, sticky="ew")

        self.ref_list = tk.Listbox(right, width=42, height=28, exportselection=False)
        self.ref_list.grid(row=3, column=0, sticky="nsew")
        self.ref_list.bind("<<ListboxSelect>>", self.on_ref_select)
        self.ref_list.bind("<Double-Button-1>", lambda e: self.apply_reference_name())

        ttk.Button(right, text="Взять имя из Unicode", command=self.apply_reference_name).grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(right, text="Новый эмодзи из reference", command=self.new_from_reference).grid(row=5, column=0, sticky="ew")
        ttk.Label(right, text="Подсказка: двойной клик по reference подставляет имя.\nПиксели всё равно рисуем руками — 8×8 не любит иллюзии грандиозности.", wraplength=300, justify=tk.LEFT).grid(row=6, column=0, sticky="w", pady=(8, 0))

        # Status bar
        self.status_var = tk.StringVar(value="Готово")
        status = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.grid(row=1, column=0, columnspan=3, sticky="ew")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- Dirty-state tracking ----------------
    def anim_signature(self, anim: EmojiAnim) -> Tuple[object, ...]:
        """Return the part of an animation that will be written to emojis.h."""
        anim.normalize()
        frames = tuple(tuple(int(v) & 0xFF for v in frame) for frame in anim.frames[:anim.n_frames])
        return (anim.name, int(anim.fps), anim.ref_symbol, anim.ref_name, int(anim.n_frames), frames)

    def mark_anim_saved(self, anim: EmojiAnim, saved_in_session: bool = True) -> None:
        self.ensure_editor_state(anim)
        self.sync_all_frames_from_virtual(anim)
        anim.saved_signature = self.anim_signature(anim)
        anim.saved_in_session = bool(saved_in_session)
        anim.baseline_n_frames = anim.n_frames
        anim.baseline_frames = [frame[:] for frame in anim.frames[:anim.n_frames]]

    def file_signature(self) -> Tuple[object, ...]:
        return tuple(self.anim_signature(anim) for anim in self.animations)

    def mark_all_saved(self, saved_in_session: bool = True) -> None:
        for anim in self.animations:
            self.mark_anim_saved(anim, saved_in_session=saved_in_session)
        self.saved_file_signature = self.file_signature()

    def is_anim_dirty(self, anim: EmojiAnim) -> bool:
        if anim.saved_signature is None:
            return True
        return self.anim_signature(anim) != anim.saved_signature

    def dirty_anims(self) -> List[EmojiAnim]:
        self.apply_form_to_current()
        for anim in self.animations:
            self.ensure_editor_state(anim)
        return [anim for anim in self.animations if self.is_anim_dirty(anim)]

    def has_unsaved_changes(self) -> bool:
        self.apply_form_to_current()
        current = self.file_signature()
        return self.saved_file_signature is None or current != self.saved_file_signature

    def on_close(self) -> None:
        dirty = self.dirty_anims()
        file_changed = self.has_unsaved_changes()
        if file_changed:
            if dirty:
                names = ", ".join(a.name for a in dirty[:6])
                if len(dirty) > 6:
                    names += f" и ещё {len(dirty) - 6}"
                details = f"Изменённые/новые эмодзи: {names}"
            else:
                details = "Изменён состав списка эмодзи: например, были удалены сохранённые элементы."
            msg = (
                "Есть несохранённые изменения в emojis.h.\n\n"
                f"{details}\n\n"
                "Выйти без сохранения?"
            )
            if not messagebox.askyesno("Несохранённые изменения", msg):
                return
        self.stop_play()
        self.root.destroy()

    # ---------------- File operations ----------------
    def load_file(self, path: Path) -> None:
        try:
            self.stop_play()
            self.animations = parse_emojis_h(path)
            for anim in self.animations:
                self.reset_virtual_from_visible(anim, update_baseline=True)
            self.mark_all_saved(saved_in_session=False)
            self.file_path = path
            self.loaded_payload_flash = estimate_payload_flash(self.animations)
            self.base_flash_est = max(0, self.compile_flash_used - self.loaded_payload_flash)
            self.current_index = 0 if self.animations else -1
            self.current_frame = 0
            self.refresh_list()
            self.load_current_to_form()
            self.refresh_all()
            self.set_status(f"Открыт {path}")
        except Exception as exc:
            messagebox.showerror("Ошибка открытия", str(exc))
            if not self.animations:
                self.animations = [EmojiAnim(name="NEW", frames=[[0] * 8], fps=DEFAULT_FPS)]
                self.current_index = 0
                self.refresh_list()
                self.load_current_to_form()

    def open_file_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Открыть emojis.h",
            initialdir=str(self.file_path.parent if self.file_path else Path.cwd()),
            filetypes=[("Arduino header", "*.h"), ("All files", "*")],
        )
        if path:
            self.load_file(Path(path))

    def save_file(self) -> None:
        if not self.file_path:
            self.save_file_as()
            return
        self._save_to_path(self.file_path)

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить emojis.h",
            initialdir=str(self.file_path.parent if self.file_path else Path.cwd()),
            initialfile="emojis.h",
            defaultextension=".h",
            filetypes=[("Arduino header", "*.h"), ("All files", "*")],
        )
        if path:
            self._save_to_path(Path(path))

    def _save_to_path(self, path: Path) -> None:
        try:
            self.apply_form_to_current()

            # Важно: зелёным после сохранения должны становиться только те
            # эмодзи, которые реально были новыми/изменёнными перед этим
            # сохранением. Раньше mark_all_saved() красил всю коллекцию, потому
            # что всем выставлялся saved_in_session=True.
            changed_before_save = {id(anim) for anim in self.animations if self.is_anim_dirty(anim)}
            was_saved_in_session = {id(anim) for anim in self.animations if getattr(anim, "saved_in_session", False)}

            self.finalize_virtual_buffers(update_baseline=True)
            text = generate_emojis_h(self.animations)
            if path.exists():
                backup = path.with_suffix(path.suffix + ".bak")
                backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.write_text(text, encoding="utf-8")
            self.file_path = path
            self.loaded_payload_flash = estimate_payload_flash(self.animations)

            for anim in self.animations:
                anim_id = id(anim)
                self.mark_anim_saved(
                    anim,
                    saved_in_session=(anim_id in changed_before_save or anim_id in was_saved_in_session),
                )
            self.saved_file_signature = self.file_signature()

            self.set_status(f"Сохранено: {path}")
            self.refresh_list()
            self.refresh_memory()
        except Exception as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))

    def save_current_emoji(self) -> None:
        """Save the whole emojis.h after committing current emoji and clearing its virtual buffer."""
        anim = self.current_anim()
        if not anim:
            return
        self.apply_form_to_current()
        self.finalize_virtual_buffers(anim, update_baseline=True)
        self.refresh_all()
        if not self.file_path:
            self.save_file_as()
        else:
            self._save_to_path(self.file_path)
        self.set_status(f"Сохранён текущий эмодзи {anim.name}; виртуальный буфер очищен")

    # ---------------- List/reference ----------------
    def refresh_list(self) -> None:
        self.emoji_list.delete(0, tk.END)
        for idx, anim in enumerate(self.animations):
            hidden = anim.stored_frames - anim.n_frames
            tail = f", +{hidden} скрыт." if hidden else ""
            dirty = self.is_anim_dirty(anim)
            self.emoji_list.insert(tk.END, f"{anim.name}  ({anim.n_frames}f{tail} @ {anim.fps}fps)")
            # Цвета без маркеров:
            #   обычный — загружен при старте и не менялся;
            #   красный — новый/изменённый, но ещё не сохранён;
            #   зелёный — был сохранён в этой сессии и сейчас не имеет несохранённых правок.
            if dirty:
                self.emoji_list.itemconfig(idx, foreground="#b00020", background="#fff1f1")
            elif getattr(anim, "saved_in_session", False):
                self.emoji_list.itemconfig(idx, foreground="#0a7f25", background="#eaffea")
            else:
                self.emoji_list.itemconfig(idx, foreground="black", background="white")
        if 0 <= self.current_index < len(self.animations):
            self.emoji_list.selection_clear(0, tk.END)
            self.emoji_list.selection_set(self.current_index)
            self.emoji_list.see(self.current_index)

    def on_list_select(self, event=None) -> None:
        sel = self.emoji_list.curselection()
        if not sel:
            return
        self.stop_play()
        self.apply_form_to_current()
        self.current_index = int(sel[0])
        self.current_frame = 0
        self.load_current_to_form()
        self.refresh_all()

    def filter_refs(self) -> None:
        q = self.ref_filter_var.get().strip().upper()
        self.filtered_refs = []
        self.ref_list.delete(0, tk.END)
        for sym, name in self.refs:
            slug = self.suggest_name_from_ref_name(name)
            hay = f"{sym} {name} {slug}".upper()
            if not q or q in hay:
                self.filtered_refs.append((sym, name))
                self.ref_list.insert(tk.END, f"{sym}  {name}  [{slug}]")
        if self.filtered_refs:
            self.ref_list.selection_set(0)
            self.on_ref_select()

    def get_selected_ref(self) -> Optional[Tuple[str, str]]:
        sel = self.ref_list.curselection()
        if not sel:
            return None
        idx = int(sel[0])
        if 0 <= idx < len(self.filtered_refs):
            return self.filtered_refs[idx]
        return None

    def on_ref_select(self, event=None) -> None:
        ref = self.get_selected_ref()
        if not ref:
            return
        sym, name = ref
        self.ref_preview.configure(text=sym)
        self.set_status(f"Reference: {sym} {name} -> {self.suggest_name_from_ref_name(name)}")

    def suggest_name_from_ref_name(self, ref_name: str) -> str:
        ref_name = ref_name.upper().strip()
        if ref_name in SHORT_ALIASES:
            return SHORT_ALIASES[ref_name]
        # Делаем имя ближе к общепринятому Unicode/CLDR short name, но не безумно длинным.
        slug = sanitize_name(ref_name)
        remove_prefixes = [
            "FACE_WITH_", "SMILING_FACE_WITH_", "GRINNING_FACE_WITH_",
        ]
        for p in remove_prefixes:
            if slug.startswith(p) and len(slug) > len(p) + 3:
                short = slug[len(p):]
                if len(short) <= 24:
                    return short
        return slug[:40]

    def apply_reference_name(self) -> None:
        ref = self.get_selected_ref()
        if not ref or self.current_index < 0:
            return
        sym, ref_name = ref
        suggested = self.suggest_name_from_ref_name(ref_name)
        self.name_var.set(suggested)
        anim = self.animations[self.current_index]
        anim.ref_symbol = sym
        anim.ref_name = ref_name
        self.apply_form_to_current()
        self.refresh_list()
        self.set_status(f"Имя подставлено: {suggested}")

    def new_from_reference(self) -> None:
        ref = self.get_selected_ref()
        if not ref:
            return
        sym, ref_name = ref
        suggested = self.suggest_name_from_ref_name(ref_name)
        self.apply_form_to_current()
        anim = EmojiAnim(name=suggested, frames=[[0] * 8], fps=DEFAULT_FPS, ref_symbol=sym, ref_name=ref_name)
        self.animations.append(anim)
        self.current_index = len(self.animations) - 1
        self.current_frame = 0
        self.refresh_list()
        self.load_current_to_form()
        self.refresh_all()
        self.set_status(f"Создан новый эмодзи {suggested} по reference {sym}")

    # ---------------- Animation editing ----------------
    def current_anim(self) -> Optional[EmojiAnim]:
        if 0 <= self.current_index < len(self.animations):
            return self.animations[self.current_index]
        return None

    def new_emoji(self) -> None:
        self.stop_play()
        self.apply_form_to_current()
        name = self.unique_name("NEW")
        anim = EmojiAnim(name=name, frames=[[0] * 8], fps=DEFAULT_FPS)
        self.reset_virtual_from_visible(anim, update_baseline=True)
        self.animations.append(anim)
        self.current_index = len(self.animations) - 1
        self.current_frame = 0
        self.refresh_list()
        self.load_current_to_form()
        self.refresh_all()

    def unique_name(self, base: str) -> str:
        base = sanitize_name(base) or "NEW"
        names = {a.name for a in self.animations}
        if base not in names:
            return base
        n = 2
        while f"{base}_{n}" in names:
            n += 1
        return f"{base}_{n}"

    def duplicate_emoji(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        self.stop_play()
        self.apply_form_to_current()
        self.sync_all_frames_from_virtual(anim)
        new_anim = copy.deepcopy(anim)
        new_anim.name = self.unique_name(anim.name + "_COPY")
        new_anim.saved_signature = None
        new_anim.saved_in_session = False
        self.reset_virtual_from_visible(new_anim, update_baseline=True)
        self.animations.insert(self.current_index + 1, new_anim)
        self.current_index += 1
        self.current_frame = 0
        self.refresh_list()
        self.load_current_to_form()
        self.refresh_all()

    def rename_emoji(self) -> None:
        """Rename the selected emoji from the left panel without editing pixels."""
        anim = self.current_anim()
        if not anim:
            return
        self.stop_play()
        # First commit any value currently typed into the main name field, so the
        # rename dialog starts from the actual current editor state.
        self.apply_form_to_current()
        current_name = anim.name
        raw = simpledialog.askstring(
            "Переименовать эмодзи",
            "Новое имя команды:",
            initialvalue=current_name,
            parent=self.root,
        )
        if raw is None:
            return
        clean = sanitize_name(raw)
        if not clean:
            messagebox.showwarning("Некорректное имя", "Имя должно содержать хотя бы одну ASCII-букву или цифру.")
            return

        # Keep names unique, but do not treat the current emoji's own name as a conflict.
        existing = {a.name for i, a in enumerate(self.animations) if i != self.current_index}
        base = clean
        new_name = base
        n = 2
        while new_name in existing:
            new_name = f"{base}_{n}"
            n += 1

        anim.name = new_name
        self.name_var.set(new_name)
        self.refresh_list()
        self.refresh_memory()
        if new_name != current_name:
            suffix = "" if new_name == clean else f"; имя {clean} уже было, использовано {new_name}"
            self.set_status(f"Эмодзи переименован: {current_name} → {new_name}{suffix}")
        else:
            self.set_status(f"Имя эмодзи не изменилось: {current_name}")

    def delete_emoji(self) -> None:
        if len(self.animations) <= 1:
            messagebox.showwarning("Нельзя удалить", "Должен остаться хотя бы один эмодзи.")
            return
        anim = self.current_anim()
        if not anim:
            return
        if not messagebox.askyesno("Удалить", f"Удалить {anim.name}?"):
            return
        self.stop_play()
        del self.animations[self.current_index]
        self.current_index = max(0, min(self.current_index, len(self.animations) - 1))
        self.current_frame = 0
        self.refresh_list()
        self.load_current_to_form()
        self.refresh_all()

    def load_current_to_form(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        anim.normalize()
        self.ensure_editor_state(anim)
        self.name_var.set(anim.name)
        self.fps_var.set(anim.fps)
        self.nframes_var.set(anim.n_frames)
        self.current_frame = max(0, min(self.current_frame, anim.n_frames - 1))
        self.frame_var.set(self.current_frame + 1)
        self.frame_spin.configure(to=anim.n_frames)

    def apply_form_to_current(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        raw_name = self.name_var.get()
        clean_name = sanitize_name(raw_name)
        if not clean_name:
            clean_name = anim.name or "EMOJI"
        anim.name = clean_name
        try:
            anim.fps = int(self.fps_var.get())
        except Exception:
            anim.fps = DEFAULT_FPS
        anim.normalize()
        self.ensure_editor_state(anim)
        self.name_var.set(anim.name)
        self.fps_var.set(anim.fps)
        self.refresh_memory()

    def on_nframes_changed(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        self.stop_play()
        self.apply_form_to_current()
        try:
            n = int(self.nframes_var.get())
        except Exception:
            n = anim.n_frames
        n = max(1, min(MAX_ANIM_FRAMES, n))

        # Soft delete / restore: decreasing count does not remove frames.
        # Increasing count reveals previously hidden frames; if there are not
        # enough stored frames, append new blank ones.
        while len(anim.frames) < n:
            anim.frames.append([0] * 8)
        anim.active_n_frames = n
        anim.normalize()
        self.ensure_editor_state(anim)

        self.current_frame = min(self.current_frame, anim.n_frames - 1)
        self.nframes_var.set(anim.n_frames)
        self.frame_spin.configure(to=anim.n_frames)
        self.frame_var.set(self.current_frame + 1)
        self.refresh_all()
        if anim.stored_frames > anim.n_frames:
            self.set_status(f"Кадров: {anim.n_frames}; скрыто до сохранения: {anim.stored_frames - anim.n_frames}")

    def on_frame_changed(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        self.stop_play()
        try:
            frame = int(self.frame_var.get()) - 1
        except Exception:
            frame = self.current_frame
        self.current_frame = max(0, min(anim.n_frames - 1, frame))
        self.frame_var.set(self.current_frame + 1)
        self.refresh_all()

    def copy_frame_to_next(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        self.stop_play()
        self.ensure_editor_state(anim)
        self.sync_frame_from_virtual(anim, self.current_frame)
        src = copy.deepcopy(anim.frames[self.current_frame])
        src_pixels = set(anim.virtual_pixels[self.current_frame])
        src_viewport = tuple(anim.viewports[self.current_frame])
        src_baseline = src[:]
        if anim.n_frames < MAX_ANIM_FRAMES and anim.stored_frames < MAX_ANIM_FRAMES:
            insert_at = self.current_frame + 1
            anim.frames.insert(insert_at, src)
            anim.virtual_pixels.insert(insert_at, src_pixels)
            anim.viewports.insert(insert_at, src_viewport)
            anim.baseline_frames.insert(insert_at, src_baseline)
            anim.active_n_frames = anim.n_frames + 1
            self.current_frame = insert_at
        else:
            # Если за активным хвостом уже лежат soft-deleted кадры, не сдвигаем
            # массив с потерей последнего кадра, а переиспользуем следующий слот.
            target = min(MAX_ANIM_FRAMES - 1, self.current_frame + 1)
            if target >= len(anim.frames):
                anim.frames.append(src)
                anim.virtual_pixels.append(src_pixels)
                anim.viewports.append(src_viewport)
                anim.baseline_frames.append(src_baseline)
            else:
                anim.frames[target] = src
                if target < len(anim.virtual_pixels):
                    anim.virtual_pixels[target] = src_pixels
                if target < len(anim.viewports):
                    anim.viewports[target] = src_viewport
                if target < len(anim.baseline_frames):
                    anim.baseline_frames[target] = src_baseline
            anim.active_n_frames = max(anim.n_frames, target + 1)
            self.current_frame = target
        anim.normalize()
        self.ensure_editor_state(anim)
        self.nframes_var.set(anim.n_frames)
        self.frame_spin.configure(to=anim.n_frames)
        self.frame_var.set(self.current_frame + 1)
        self.refresh_all()
        self.refresh_list()

    # ---------------- Pixel operations ----------------
    def frame(self) -> Optional[List[int]]:
        anim = self.current_anim()
        if not anim:
            return None
        self.ensure_editor_state(anim)
        return anim.frames[self.current_frame]

    def pixel_at_event(self, event) -> Optional[Tuple[int, int]]:
        c = (event.x - GRID_PAD) // CELL
        r = (event.y - GRID_PAD) // CELL
        if 0 <= r < 8 and 0 <= c < 8:
            return int(r), int(c)
        return None

    def get_pixel(self, frame: List[int], r: int, c: int) -> bool:
        return bool(frame[r] & (1 << (7 - c)))

    def set_pixel(self, frame: List[int], r: int, c: int, value: bool) -> None:
        mask = 1 << (7 - c)
        if value:
            frame[r] |= mask
        else:
            frame[r] &= ~mask
        frame[r] &= 0xFF

    def on_canvas_click(self, event) -> None:
        f = self.frame()
        pos = self.pixel_at_event(event)
        if f is None or pos is None:
            return
        self.stop_play()
        anim = self.current_anim()
        if not anim:
            return
        r, c = pos
        vr, vc = anim.viewports[self.current_frame]
        world = (vr + r, vc + c)
        new_value = world not in anim.virtual_pixels[self.current_frame]
        self.drag_value = new_value
        if new_value:
            anim.virtual_pixels[self.current_frame].add(world)
        else:
            anim.virtual_pixels[self.current_frame].discard(world)
        self.sync_frame_from_virtual(anim)
        self.refresh_grid()
        self.refresh_bytes()
        self.refresh_memory()
        self.refresh_list()

    def on_canvas_drag(self, event) -> None:
        f = self.frame()
        pos = self.pixel_at_event(event)
        if f is None or pos is None or self.drag_value is None:
            return
        anim = self.current_anim()
        if not anim:
            return
        r, c = pos
        vr, vc = anim.viewports[self.current_frame]
        world = (vr + r, vc + c)
        if self.drag_value:
            anim.virtual_pixels[self.current_frame].add(world)
        else:
            anim.virtual_pixels[self.current_frame].discard(world)
        self.sync_frame_from_virtual(anim)
        self.refresh_grid()
        self.refresh_bytes()
        self.refresh_list()

    def clear_frame(self) -> None:
        f = self.frame()
        if f is None:
            return
        self.stop_play()
        anim = self.current_anim()
        if not anim:
            return
        for i in range(8):
            f[i] = 0
        anim.virtual_pixels[self.current_frame].clear()
        anim.viewports[self.current_frame] = (0, 0)
        self.refresh_all()

    def invert_frame(self) -> None:
        f = self.frame()
        if f is None:
            return
        self.stop_play()
        anim = self.current_anim()
        if not anim:
            return
        vr, vc = anim.viewports[self.current_frame]
        pixels = anim.virtual_pixels[self.current_frame]
        for r in range(8):
            for c in range(8):
                world = (vr + r, vc + c)
                if world in pixels:
                    pixels.discard(world)
                else:
                    pixels.add(world)
        self.sync_frame_from_virtual(anim)
        self.refresh_all()

    def shift_frame(self, dx: int, dy: int) -> None:
        f = self.frame()
        if f is None:
            return
        self.stop_play()
        anim = self.current_anim()
        if not anim:
            return
        vr, vc = anim.viewports[self.current_frame]
        # Чтобы видимое изображение сдвинулось вправо/вниз, viewport движется в обратную сторону.
        anim.viewports[self.current_frame] = (vr - dy, vc - dx)
        self.sync_frame_from_virtual(anim)
        self.refresh_all()

    def mirror_x(self) -> None:
        f = self.frame()
        if f is None:
            return
        self.stop_play()
        anim = self.current_anim()
        if not anim:
            return
        vr, vc = anim.viewports[self.current_frame]
        pixels = anim.virtual_pixels[self.current_frame]
        anim.virtual_pixels[self.current_frame] = {(r, 2 * vc + 7 - c) for (r, c) in pixels}
        self.sync_frame_from_virtual(anim)
        self.refresh_all()

    def mirror_y(self) -> None:
        f = self.frame()
        if f is None:
            return
        self.stop_play()
        anim = self.current_anim()
        if not anim:
            return
        vr, vc = anim.viewports[self.current_frame]
        pixels = anim.virtual_pixels[self.current_frame]
        anim.virtual_pixels[self.current_frame] = {(2 * vr + 7 - r, c) for (r, c) in pixels}
        self.sync_frame_from_virtual(anim)
        self.refresh_all()

    def undo_current_frame(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        self.stop_play()
        self.ensure_editor_state(anim)
        baseline_count = max(1, min(MAX_ANIM_FRAMES, anim.baseline_n_frames or anim.n_frames))

        # Restore the whole saved animation shape, not only the visible current
        # frame. This makes "Кадров" reductions reversible through "Отменить".
        while len(anim.frames) < baseline_count:
            anim.frames.append([0] * 8)
        self.ensure_editor_state(anim)
        for i in range(min(len(anim.baseline_frames), len(anim.frames))):
            anim.frames[i] = anim.baseline_frames[i][:]
        anim.active_n_frames = baseline_count
        anim.normalize()
        self.ensure_editor_state(anim)
        for i in range(anim.stored_frames):
            self.reset_virtual_from_visible(anim, frame_index=i, update_baseline=False)

        self.current_frame = min(self.current_frame, anim.n_frames - 1)
        self.nframes_var.set(anim.n_frames)
        self.frame_spin.configure(to=anim.n_frames)
        self.frame_var.set(self.current_frame + 1)
        self.refresh_all()
        self.set_status(f"Анимация {anim.name} сброшена к последнему сохранённому состоянию")

    # ---------------- Animation preview ----------------
    def toggle_play(self) -> None:
        if self.playing:
            self.stop_play()
        else:
            self.start_play()

    def start_play(self) -> None:
        anim = self.current_anim()
        if not anim:
            return
        self.apply_form_to_current()
        self.ensure_editor_state(anim)
        self.playing = True
        if hasattr(self, "play_button"):
            self.play_button.configure(text="Stop")
        self.set_status(f"Preview: {anim.name} @ {anim.fps} FPS")
        self._play_tick(first=True)

    def stop_play(self) -> None:
        if self.play_after_id is not None:
            try:
                self.root.after_cancel(self.play_after_id)
            except Exception:
                pass
            self.play_after_id = None
        self.playing = False
        if hasattr(self, "play_button"):
            self.play_button.configure(text="Play")

    def _play_tick(self, first: bool = False) -> None:
        if not self.playing:
            return
        anim = self.current_anim()
        if not anim:
            self.stop_play()
            return
        self.ensure_editor_state(anim)
        if not first:
            self.current_frame = (self.current_frame + 1) % anim.n_frames
        self.frame_var.set(self.current_frame + 1)
        self.refresh_grid()
        self.refresh_bytes()
        delay_ms = max(20, int(round(1000.0 / max(MIN_FPS, min(MAX_FPS, anim.fps)))))
        self.play_after_id = self.root.after(delay_ms, self._play_tick)

    # ---------------- Refresh/render ----------------
    def refresh_all(self) -> None:
        self.refresh_grid()
        self.refresh_bytes()
        self.refresh_memory()
        self.refresh_list()

    def refresh_grid(self) -> None:
        f = self.frame()
        if f is None:
            return
        for r in range(8):
            for c in range(8):
                on = self.get_pixel(f, r, c)
                self.canvas.itemconfigure(self.rects[(r, c)], fill="#111111" if on else "#fafafa")

    def refresh_bytes(self) -> None:
        f = self.frame()
        if f is None:
            return
        lines = []
        for row in f:
            lines.append("  " + byte_to_bin(row) + ",")
        self.bytes_text.delete("1.0", tk.END)
        self.bytes_text.insert(tk.END, "\n".join(lines))

    def refresh_memory(self) -> None:
        payload = estimate_payload_flash(self.animations)
        flash_used = self.base_flash_est + payload
        flash_free = self.total_flash - flash_used
        frames_total = sum(a.n_frames for a in self.animations)
        hidden_total = sum(max(0, a.stored_frames - a.n_frames) for a in self.animations)
        # Грубая оценка: двухкадровый эмодзи со средним именем 14 символов и строкой таблицы ~37 байт payload.
        avg_two_frame_payload = 16 + 14 + 1 + 6
        safe_free = max(0, flash_free - 2048)  # небольшой запас под код, если прошивка ещё будет расти
        approx_more = safe_free // avg_two_frame_payload
        text = (
            f"Эмодзи: {len(self.animations)} шт., кадров к сохранению: {frames_total}, скрыто до сохранения: {hidden_total}, payload≈{payload} байт Flash.\n"
            f"Flash: используется≈{flash_used} / {self.total_flash}, свободно≈{flash_free} байт.\n"
            f"С запасом 2 КБ можно добавить примерно {approx_more} двухкадровых эмодзи."
        )
        self.memory_label.configure(text=text)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GUI editor for MAX7219 8x8 emojis.h")
    p.add_argument("--file", default="", help="Путь к emojis.h. По умолчанию ищется рядом со скриптом.")
    p.add_argument("--total-flash", type=int, default=DEFAULT_TOTAL_FLASH)
    p.add_argument("--flash-used", type=int, default=DEFAULT_COMPILED_FLASH_USED,
                   help="Сколько Flash показывала последняя компиляция, по умолчанию 10466")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    root = tk.Tk()
    app = EmojiEditorApp(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
