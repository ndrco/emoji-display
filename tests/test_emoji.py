from __future__ import annotations

from emoji_display.emoji import normalize_emoji


def test_cat_variants_collapse_to_cat():
    assert normalize_emoji("😺").display_name == "CAT"
    assert normalize_emoji("😹", "cat with tears of joy").display_name == "CAT"
    assert normalize_emoji("", "smiling cat face").display_name == "CAT"


def test_name_can_select_supported_display_without_symbol():
    match = normalize_emoji("", "face savoring food")

    assert match.display_name == "FOOD"
    assert match.display_symbol == "🍽️"


def test_common_status_symbols_are_supported():
    assert normalize_emoji("✅").display_name == "YES"
    assert normalize_emoji("❌").display_name == "NO"
    assert normalize_emoji("⚠️").display_name == "ALERT"


def test_star_variants_map_to_star():
    assert normalize_emoji("🌟").display_name == "STAR"
    assert normalize_emoji("✨").display_name == "STAR"


def test_unknown_emoji_falls_back_to_neutral():
    match = normalize_emoji("🛸")

    assert match.display_name == "NEUTRAL"
    assert match.matched_by == "fallback"
