"""Textual widget tests for CalendarList.

Run with:  pytest tests/test_calendar_list.py -v
Requires:  pip install pytest pytest-asyncio
"""
from __future__ import annotations
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Checkbox

from models import GCalendar
from ui.components.calendar_list import CalendarList, CalendarsChanged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cal(id_: str, summary: str = "Test", color_id: str = "1", selected: bool = True) -> GCalendar:
    return GCalendar(
        id=id_,
        summary=summary,
        color_id=color_id,
        primary=False,
        selected=selected,
        access_role="reader",
        time_zone="UTC",
    )


CLASSROOM_CALS = [
    _cal("c_classroom34f64120@group.calendar.google.com", "Behaviour E/F/G/H", "16"),
    _cal("c_classroom261778d4@group.calendar.google.com", "NHSA102 LAB SEC F", "16"),
    _cal("24je0678@iitism.ac.in",                         "Primary",            "14", True),
    _cal("c_classroom41b68d49@group.calendar.google.com", "Algorithm Design",   "8"),
    _cal("c_classroomf8ee4895@group.calendar.google.com", "TOC",                "16"),
]


class CalListApp(App):
    """Minimal host app for CalendarList integration tests."""

    def compose(self) -> ComposeResult:
        yield CalendarList(id="cal-list")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_update_mounts_checkboxes():
    calendars = [_cal("a@g.com", "Cal A"), _cal("b@g.com", "Cal B")]
    app = CalListApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        cal_list.update(calendars)
        await pilot.pause()
        cbs = list(app.query(Checkbox))
        assert len(cbs) == 2


@pytest.mark.asyncio
async def test_update_twice_no_duplicate_ids():
    """Calling update() twice with same list must not raise DuplicateIds."""
    calendars = [_cal("a@g.com", "Cal A"), _cal("b@g.com", "Cal B")]
    app = CalListApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        cal_list.update(calendars)
        await pilot.pause()
        cal_list.update(calendars)  # would raise DuplicateIds before fix
        await pilot.pause()
        cbs = list(app.query(Checkbox))
        assert len(cbs) == 2


@pytest.mark.asyncio
async def test_unknown_color_ids_do_not_crash():
    """Google Classroom calendars use color IDs 14 and 16 — outside our map."""
    app = CalListApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        cal_list.update(CLASSROOM_CALS)
        await pilot.pause()
        assert len(list(app.query(Checkbox))) == len(CLASSROOM_CALS)


@pytest.mark.asyncio
async def test_repeated_updates_classroom_cals():
    """Simulate the exact scenario from the reported crash: five classroom
    calendars, update called multiple times (e.g., on every data refresh)."""
    app = CalListApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        for _ in range(3):
            cal_list.update(CLASSROOM_CALS)
            await pilot.pause()
        assert len(list(app.query(Checkbox))) == len(CLASSROOM_CALS)


@pytest.mark.asyncio
async def test_update_adds_new_calendar():
    initial = [_cal("a@g.com", "Cal A")]
    updated = [_cal("a@g.com", "Cal A"), _cal("b@g.com", "Cal B")]
    app = CalListApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        cal_list.update(initial)
        await pilot.pause()
        assert len(list(app.query(Checkbox))) == 1
        cal_list.update(updated)
        await pilot.pause()
        assert len(list(app.query(Checkbox))) == 2


@pytest.mark.asyncio
async def test_update_removes_stale_calendar():
    initial = [_cal("a@g.com", "Cal A"), _cal("b@g.com", "Cal B")]
    updated = [_cal("a@g.com", "Cal A")]
    app = CalListApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        cal_list.update(initial)
        await pilot.pause()
        assert len(list(app.query(Checkbox))) == 2
        cal_list.update(updated)
        await pilot.pause(delay=0.1)  # removal is async — give event loop a tick
        assert len(list(app.query(Checkbox))) == 1


@pytest.mark.asyncio
async def test_checkbox_toggle_posts_calendars_changed():
    calendars = [_cal("a@g.com", "Cal A", selected=True)]
    messages: list[CalendarsChanged] = []

    class TrackingApp(App):
        def compose(self) -> ComposeResult:
            yield CalendarList(id="cal-list")

        def on_calendars_changed(self, msg: CalendarsChanged) -> None:
            messages.append(msg)

    app = TrackingApp()
    async with app.run_test() as pilot:
        cal_list = app.query_one(CalendarList)
        cal_list.update(calendars)
        await pilot.pause()
        cb = app.query_one(Checkbox)
        await pilot.click(cb)
        await pilot.pause()
        assert messages, "CalendarsChanged not posted"
        assert messages[-1].calendars[0].selected is False
