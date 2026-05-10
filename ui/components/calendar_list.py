from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Checkbox
from rich.text import Text

from models import GCalendar
from ui.theme import color_for_calendar


class CalendarsChanged(Message):
    def __init__(self, calendars: list[GCalendar]) -> None:
        super().__init__()
        self.calendars = calendars


class CalendarList(Widget):
    DEFAULT_CSS = """
    CalendarList {
        padding: 0 1;
        height: auto;
        border-top: solid $surface-lighten-2;
    }
    .cal-list-title {
        text-style: bold;
        color: $text-muted;
        height: 1;
        padding: 1 0 0 0;
    }
    CalendarList Checkbox {
        height: 1;
        background: transparent;
        border: none;
        padding: 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._calendars: list[GCalendar] = []

    def compose(self) -> ComposeResult:
        yield Label("Calendars", classes="cal-list-title")

    @staticmethod
    def _cb_id(cal: GCalendar) -> str:
        return f"cal-cb-{cal.id.replace('@', '_').replace('.', '_')}"

    def update(self, calendars: list[GCalendar]) -> None:
        self._calendars = calendars
        wanted: dict[str, GCalendar] = {self._cb_id(c): c for c in calendars}

        # Remove checkboxes no longer needed (schedule async removal is fine
        # because we only add IDs absent from the current child set below)
        for cb in list(self.query(Checkbox)):
            if cb.id not in wanted:
                cb.remove()

        # Add missing, update existing — query AFTER scheduling removals so
        # existing_ids still contains them (prevents duplicate-ID mount race)
        existing_ids: set[str] = {cb.id for cb in self.query(Checkbox)}
        for cb_id, cal in wanted.items():
            if cb_id in existing_ids:
                self.query_one(f"#{cb_id}", Checkbox).value = cal.selected
            else:
                color = color_for_calendar(cal)
                label = Text()
                label.append("● ", style=f"bold {color}")
                label.append(cal.summary[:15])
                self.mount(Checkbox(label, value=cal.selected, id=cb_id))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        # Find the calendar by matching checkbox id
        cb_id = event.checkbox.id or ""
        for cal in self._calendars:
            sanitized = f"cal-cb-{cal.id.replace('@', '_').replace('.', '_')}"
            if sanitized == cb_id:
                cal.selected = event.value
                break
        self.post_message(CalendarsChanged(list(self._calendars)))
