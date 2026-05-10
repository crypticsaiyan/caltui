from __future__ import annotations

from datetime import date

from ui.components.date_jump_modal import parse_date_jump


def test_parse_iso_date():
    assert parse_date_jump("2026-05-10", date(2026, 1, 1)) == date(2026, 5, 10)


def test_parse_colon_prefixed_date():
    assert parse_date_jump(":10 May 2026", date(2026, 1, 1)) == date(2026, 5, 10)


def test_parse_monthless_day_uses_current_month():
    assert parse_date_jump("15", date(2026, 5, 10)) == date(2026, 5, 15)


def test_parse_relative_offset_uses_current_date():
    assert parse_date_jump("+7", date(2026, 5, 10)) == date(2026, 5, 17)
    assert parse_date_jump("-3", date(2026, 5, 10)) == date(2026, 5, 7)


def test_parse_rejects_invalid_date():
    assert parse_date_jump("31 Feb 2026", date(2026, 1, 1)) is None
