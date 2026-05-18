from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


SUPPORTED_DISPLAY_NAMES: tuple[str, ...] = (
    "HAPPY",
    "LAUGH",
    "WINK",
    "SURPRISE",
    "SAD",
    "CRY",
    "ANGRY",
    "LOVE",
    "KISS",
    "COOL",
    "SLEEP",
    "NEUTRAL",
    "CONFUSED",
    "THINK",
    "TONGUE",
    "DEAD",
    "WOW",
    "HEART",
    "YES",
    "NO",
    "OK",
    "ALERT",
    "MUSIC",
    "ROBOT",
    "GHOST",
    "CAT",
    "DOG",
    "FOOD",
    "STAR",
    "CAR",
    "FLOWER",
    "RAIN",
    "DEFAULT",
)

DISPLAY_SYMBOLS: dict[str, str] = {
    "HAPPY": "🙂",
    "LAUGH": "😆",
    "WINK": "😉",
    "SURPRISE": "😮",
    "SAD": "🙁",
    "CRY": "😢",
    "ANGRY": "😠",
    "LOVE": "😍",
    "KISS": "😘",
    "COOL": "😎",
    "SLEEP": "😴",
    "NEUTRAL": "😐",
    "CONFUSED": "😕",
    "THINK": "🤔",
    "TONGUE": "😛",
    "DEAD": "💀",
    "STAR": "🌟",
    "WOW": "😲",
    "HEART": "❤️",
    "YES": "✅",
    "NO": "❌",
    "OK": "👌",
    "ALERT": "⚠️",
    "MUSIC": "🎵",
    "ROBOT": "🤖",
    "GHOST": "👻",
    "CAT": "🐱",
    "DOG": "🐶",
    "FOOD": "🍽️",
    "CAR": "🚗",
    "FLOWER": "🌸",
    "RAIN": "🌧️",
    "DEFAULT": "❔",
}


@dataclass(frozen=True, slots=True)
class EmojiMatch:
    requested: str
    display_name: str
    display_symbol: str
    matched_by: str


_SUPPORTED_SET = set(SUPPORTED_DISPLAY_NAMES)
_VARIATION_SELECTORS = dict.fromkeys(map(ord, "\ufe0e\ufe0f"), None)
_SKIN_TONES = dict.fromkeys(range(0x1F3FB, 0x1F400), None)
_TEXT_SPLIT_RE = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)

_EXACT_SYMBOLS: dict[str, str] = {
    "😀": "HAPPY",
    "😃": "HAPPY",
    "😄": "HAPPY",
    "😁": "HAPPY",
    "🙂": "HAPPY",
    "😊": "HAPPY",
    "☺": "HAPPY",
    "😆": "LAUGH",
    "😂": "LAUGH",
    "🤣": "LAUGH",
    "😉": "WINK",
    "😮": "SURPRISE",
    "😯": "SURPRISE",
    "😲": "WOW",
    "😱": "WOW",
    "🤯": "WOW",
    "🙁": "SAD",
    "☹": "SAD",
    "😞": "SAD",
    "😔": "SAD",
    "😢": "CRY",
    "😭": "CRY",
    "😠": "ANGRY",
    "😡": "ANGRY",
    "🤬": "ANGRY",
    "😍": "LOVE",
    "🥰": "LOVE",
    "😘": "KISS",
    "😗": "KISS",
    "😙": "KISS",
    "😚": "KISS",
    "😎": "COOL",
    "🤩": "COOL",
    "😴": "SLEEP",
    "💤": "SLEEP",
    "😐": "NEUTRAL",
    "😑": "NEUTRAL",
    "😶": "NEUTRAL",
    "😕": "CONFUSED",
    "😟": "CONFUSED",
    "🤔": "THINK",
    "🧐": "THINK",
    "😛": "TONGUE",
    "😜": "TONGUE",
    "🤪": "TONGUE",
    "⭐": "STAR",
    "🌟": "STAR",
    "✨": "STAR",
    "💫": "STAR",
    "☄": "STAR",
    "🎆": "STAR",
    "🎇": "STAR",
    "😋": "FOOD",
    "💀": "DEAD",
    "☠": "DEAD",
    "😵": "DEAD",
    "😵‍💫": "DEAD",
    "❤️": "HEART",
    "❤": "HEART",
    "♥": "HEART",
    "💖": "HEART",
    "💘": "HEART",
    "💙": "HEART",
    "💚": "HEART",
    "💛": "HEART",
    "💜": "HEART",
    "🤍": "HEART",
    "✅": "YES",
    "✔": "YES",
    "☑": "YES",
    "👍": "YES",
    "❌": "NO",
    "✖": "NO",
    "✕": "NO",
    "👎": "NO",
    "🆗": "OK",
    "👌": "OK",
    "⭕": "OK",
    "⚠": "ALERT",
    "❗": "ALERT",
    "❕": "ALERT",
    "🚨": "ALERT",
    "🎵": "MUSIC",
    "🎶": "MUSIC",
    "🎼": "MUSIC",
    "🎤": "MUSIC",
    "🎧": "MUSIC",
    "🎷": "MUSIC",
    "🎸": "MUSIC",
    "🎹": "MUSIC",
    "🎺": "MUSIC",
    "🎻": "MUSIC",
    "🥁": "MUSIC",
    "🪕": "MUSIC",
    "🤖": "ROBOT",
    "👻": "GHOST",
    "🐱": "CAT",
    "🐈": "CAT",
    "😺": "CAT",
    "😸": "CAT",
    "😹": "CAT",
    "😻": "CAT",
    "😼": "CAT",
    "😽": "CAT",
    "🙀": "CAT",
    "😿": "CAT",
    "😾": "CAT",
    "🐶": "DOG",
    "🐕": "DOG",
    "🦮": "DOG",
    "🐩": "DOG",
    "🍕": "FOOD",
    "🍔": "FOOD",
    "🍟": "FOOD",
    "🍩": "FOOD",
    "🍪": "FOOD",
    "🍎": "FOOD",
    "🍏": "FOOD",
    "🍊": "FOOD",
    "🍋": "FOOD",
    "🍌": "FOOD",
    "🍉": "FOOD",
    "🍇": "FOOD",
    "🍓": "FOOD",
    "🍒": "FOOD",
    "🍑": "FOOD",
    "🍍": "FOOD",
    "🥝": "FOOD",
    "🥑": "FOOD",
    "🥦": "FOOD",
    "🥕": "FOOD",
    "🌽": "FOOD",
    "🥐": "FOOD",
    "🍞": "FOOD",
    "🥨": "FOOD",
    "🧀": "FOOD",
    "🥚": "FOOD",
    "🍳": "FOOD",
    "🥞": "FOOD",
    "🥓": "FOOD",
    "🥩": "FOOD",
    "🍗": "FOOD",
    "🍖": "FOOD",
    "🌭": "FOOD",
    "🌮": "FOOD",
    "🌯": "FOOD",
    "🥗": "FOOD",
    "🍝": "FOOD",
    "🍣": "FOOD",
    "🍤": "FOOD",
    "🍦": "FOOD",
    "🍰": "FOOD",
    "🎂": "FOOD",
    "🍫": "FOOD",
    "🍿": "FOOD",
    "☕": "FOOD",
    "🍵": "FOOD",
    "🍼": "FOOD",
    "🥤": "FOOD",
    "🍽": "FOOD",
    "🚗": "CAR",
    "🚕": "CAR",
    "🚙": "CAR",
    "🚌": "CAR",
    "🚎": "CAR",
    "🏎": "CAR",
    "🚓": "CAR",
    "🚑": "CAR",
    "🚒": "CAR",
    "🚐": "CAR",
    "🛻": "CAR",
    "🚚": "CAR",
    "🚛": "CAR",
    "🚜": "CAR",
    "🏍": "CAR",
    "🛵": "CAR",
    "🚲": "CAR",
    "🛴": "CAR",
    "🚂": "CAR",
    "🚆": "CAR",
    "🚇": "CAR",
    "🚋": "CAR",
    "✈": "CAR",
    "🚀": "CAR",
    "🛸": "CAR",
    "🚁": "CAR",
    "⛵": "CAR",
    "🚤": "CAR",
    "🚢": "CAR",
    "🌸": "FLOWER",
    "🌹": "FLOWER",
    "🌺": "FLOWER",
    "🌻": "FLOWER",
    "🌼": "FLOWER",
    "🌷": "FLOWER",
    "💐": "FLOWER",
    "🪷": "FLOWER",
    "🌱": "FLOWER",
    "🌿": "FLOWER",
    "☘": "FLOWER",
    "🍀": "FLOWER",
    "🍃": "FLOWER",
    "🍂": "FLOWER",
    "🍁": "FLOWER",
    "🌵": "FLOWER",
    "🌴": "FLOWER",
    "🌲": "FLOWER",
    "🌳": "FLOWER",
    "🌧": "RAIN",
    "🌦": "RAIN",
    "⛈": "RAIN",
    "🌩": "RAIN",
    "🌨": "RAIN",
    "☔": "RAIN",
    "☂": "RAIN",
    "🌂": "RAIN",
    "🌈": "RAIN",
    "☁": "RAIN",
    "🌤": "RAIN",
    "⛅": "RAIN",
    "☀": "RAIN",
    "❄": "RAIN",
    "☃": "RAIN",
    "⛄": "RAIN",
    "🌬": "RAIN",
    "🌪": "RAIN",
    "🌫": "RAIN",
    "💧": "RAIN",
}

_KEYWORD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CAT", ("cat", "kitten", "кошка", "кот", "котик")),
    ("DOG", ("dog", "puppy", "собака", "пес", "пёс")),
    ("ROBOT", ("robot", "bot", "робот")),
    ("GHOST", ("ghost", "boo", "привидение", "призрак")),
    ("MUSIC", ("music", "musical", "note", "song", "instrument", "guitar", "piano", "drum", "saxophone", "trumpet", "violin", "microphone", "headphone", "музыка", "нота", "инструмент", "гитара", "пианино", "барабан")),
    ("CAR", ("car", "automobile", "auto", "vehicle", "transport", "taxi", "bus", "truck", "tractor", "motorcycle", "scooter", "bicycle", "train", "tram", "metro", "railway", "airplane", "plane", "rocket", "helicopter", "ship", "boat", "ferry", "saucer", "транспорт", "машина", "авто", "автомобиль", "ракета", "поезд", "самолет", "самолёт", "корабль", "лодка")),
    ("FLOWER", ("flower", "blossom", "bouquet", "rose", "tulip", "plant", "seedling", "leaf", "leaves", "herb", "tree", "palm", "cactus", "shamrock", "clover", "флора", "цвет", "роза", "раст", "лист", "дерево", "кактус")),
    ("RAIN", ("rain", "cloud", "weather", "umbrella", "thunder", "lightning", "storm", "snow", "snowflake", "sun", "sunny", "fog", "wind", "tornado", "droplet", "погод", "дожд", "туч", "облак", "зонт", "гроза", "молния", "снег", "солн", "ветер", "туман")),
    ("ALERT", ("alert", "warning", "exclamation", "bang", "alarm", "danger", "внимание", "тревога")),
    ("YES", ("yes", "check", "approve", "approved", "thumbs up", "like", "да", "окей")),
    ("NO", ("no", "cross", "wrong", "deny", "denied", "thumbs down", "нет")),
    ("OK", ("ok", "okay", "ok hand", "circle", "норм")),
    ("HEART", ("heart", "серд", "love letter")),
    ("KISS", ("kiss", "kissing", "поцел")),
    ("LOVE", ("love", "loving", "heart eyes", "smiling face with hearts", "любов")),
    ("FOOD", ("food", "savoring", "savouring", "pizza", "burger", "fries", "hot dog", "taco", "burrito", "sandwich", "bread", "croissant", "cheese", "egg", "bacon", "meat", "chicken", "rice", "noodle", "sushi", "cake", "cookie", "chocolate", "coffee", "tea", "drink", "beverage", "fruit", "vegetable", "еда", "вкус", "пицца", "кофе", "чай", "напиток", "фрукт", "овощ")),
    ("LAUGH", ("laugh", "joy", "tears of joy", "rofl", "grin", "сме", "хохот")),
    ("WINK", ("wink", "подмиг")),
    ("STAR", ("star", "glowing star", "sparkles", "sparkle", "fireworks", "sparkler", "comet", "dizzy", "shooting star", "звезда", "звезд", "салют", "фейерверк", "блест")),
    ("WOW", ("astonished", "scream", "mind blown", "shocked", "wow", "вау", "шок")),
    ("SURPRISE", ("surprise", "open mouth", "hushed", "удив")),
    ("CRY", ("cry", "sob", "tear", "sad but relieved", "плач", "слез")),
    ("ANGRY", ("angry", "rage", "swear", "mad", "зл", "ярост")),
    ("COOL", ("cool", "sunglasses", "star struck", "крут")),
    ("SLEEP", ("sleep", "sleeping", "zzz", "сон")),
    ("CONFUSED", ("confused", "frown", "worried", "concerned", "confus", "сомнен", "растер")),
    ("THINK", ("think", "thinking", "monocle", "дума")),
    ("TONGUE", ("tongue", "zany", "silly", "язык")),
    ("DEAD", ("dead", "skull", "dizzy", "x eyes", "мертв", "череп")),
    ("SAD", ("sad", "slightly frowning", "frowning", "unhappy", "груст", "печал")),
    ("NEUTRAL", ("neutral", "expressionless", "blank", "без эмоций", "нейтр")),
    ("HAPPY", ("happy", "smile", "smiling", "grinning", "slightly smiling", "рад", "улыб")),
)


def normalize_emoji(symbol: str, name: str | None = None) -> EmojiMatch:
    requested = symbol.strip() if isinstance(symbol, str) else ""
    requested_name = name.strip() if isinstance(name, str) else ""

    direct = _direct_display_name(requested)
    if direct:
        return _match(requested, direct, "display-name")

    cleaned_symbol = _clean_symbol(requested)
    exact = _EXACT_SYMBOLS.get(cleaned_symbol)
    if exact:
        return _match(requested, exact, "symbol")

    direct_name = _direct_display_name(requested_name)
    if direct_name:
        return _match(requested, direct_name, "name")

    text = " ".join(part for part in (requested_name, _unicode_name(cleaned_symbol), requested) if part)
    text_key = _normalize_text(text)
    for display_name, keywords in _KEYWORD_GROUPS:
        if any(_keyword_in_text(keyword, text_key) for keyword in keywords):
            return _match(requested, display_name, "keyword")

    return _match(requested, "DEFAULT", "fallback")


def supported_catalog() -> list[dict[str, str]]:
    return [
        {"name": display_name, "symbol": DISPLAY_SYMBOLS[display_name]}
        for display_name in SUPPORTED_DISPLAY_NAMES
    ]


def _match(requested: str, display_name: str, matched_by: str) -> EmojiMatch:
    return EmojiMatch(
        requested=requested,
        display_name=display_name,
        display_symbol=DISPLAY_SYMBOLS[display_name],
        matched_by=matched_by,
    )


def _direct_display_name(value: str) -> str | None:
    normalized = value.strip().replace("-", "_").replace(" ", "_").upper()
    return normalized if normalized in _SUPPORTED_SET else None


def _clean_symbol(symbol: str) -> str:
    return symbol.translate(_VARIATION_SELECTORS).translate(_SKIN_TONES)


def _unicode_name(symbol: str) -> str:
    names: list[str] = []
    for char in symbol:
        try:
            names.append(unicodedata.name(char))
        except ValueError:
            continue
    return " ".join(names)


def _normalize_text(value: str) -> str:
    text = value.casefold().replace("_", " ")
    return " ".join(part for part in _TEXT_SPLIT_RE.split(text) if part)


def _keyword_in_text(keyword: str, text: str) -> bool:
    normalized = _normalize_text(keyword)
    if " " in normalized:
        return normalized in text
    return normalized in text.split()
