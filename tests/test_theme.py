"""Unit tests for ui/theme.py; no Textual required."""
from __future__ import annotations
import pytest
from ui.theme import (
    color_for_event,
    color_for_calendar,
    contrasting_text,
    GOOGLE_COLOR_ID_TO_HEX,
    DEFAULT_EVENT_COLOR,
    DEFAULT_CALENDAR_COLOR,
)
from models import GCalendar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeEvent:
    def __init__(self, color_id: str | None, calendar_id: str = "x"):
        self.color_id = color_id
        self.calendar_id = calendar_id


def _cal(color_id: str) -> GCalendar:
    return GCalendar(id="c@g.com", summary="Test", color_id=color_id)


# ---------------------------------------------------------------------------
# color_for_event
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("color_id,expected", list(GOOGLE_COLOR_ID_TO_HEX.items()))
def test_color_for_event_known_ids(color_id, expected):
    ev = _FakeEvent(color_id)
    assert color_for_event(ev) == expected


@pytest.mark.parametrize("color_id", ["14", "16", "0", "99", "abc"])
def test_color_for_event_unknown_id_returns_default(color_id):
    ev = _FakeEvent(color_id)
    assert color_for_event(ev) == DEFAULT_EVENT_COLOR


def test_color_for_event_none_id_no_calendar():
    ev = _FakeEvent(None)
    assert color_for_event(ev) == DEFAULT_EVENT_COLOR


def test_color_for_event_none_id_falls_back_to_calendar():
    ev = _FakeEvent(None)
    cal = _cal("1")  # lavender
    assert color_for_event(ev, cal) == "#7986cb"


def test_color_for_event_unknown_id_falls_back_to_calendar():
    ev = _FakeEvent("16")          # unknown event color
    cal = _cal("2")                # sage, valid calendar color
    assert color_for_event(ev, cal) == "#33b679"


def test_color_for_event_both_unknown_returns_default():
    ev = _FakeEvent("16")
    cal = _cal("14")
    assert color_for_event(ev, cal) == DEFAULT_EVENT_COLOR


# ---------------------------------------------------------------------------
# color_for_calendar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("color_id,expected", list(GOOGLE_COLOR_ID_TO_HEX.items()))
def test_color_for_calendar_known(color_id, expected):
    assert color_for_calendar(_cal(color_id)) == expected


@pytest.mark.parametrize("color_id", ["14", "16", "0", "42"])
def test_color_for_calendar_unknown_returns_default(color_id):
    assert color_for_calendar(_cal(color_id)) == DEFAULT_CALENDAR_COLOR


def test_color_for_calendar_none():
    assert color_for_calendar(None) == DEFAULT_CALENDAR_COLOR


# ---------------------------------------------------------------------------
# contrasting_text
# ---------------------------------------------------------------------------

def test_contrasting_text_dark_bg():
    assert contrasting_text("#000000") == "#ffffff"


def test_contrasting_text_light_bg():
    assert contrasting_text("#ffffff") == "#000000"


def test_contrasting_text_mid_dark():
    assert contrasting_text("#3f51b5") == "#ffffff"  # blueberry


def test_contrasting_text_banana():
    # banana (#f6bf26) is bright yellow; should get dark text
    assert contrasting_text("#f6bf26") == "#000000"
