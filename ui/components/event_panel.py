from __future__ import annotations
import textwrap

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Button
from textual.containers import Horizontal

from models import CalEvent


class EditRequested(Message):
    def __init__(self, event: CalEvent) -> None:
        super().__init__()
        self.event = event


class DeleteRequested(Message):
    def __init__(self, event: CalEvent) -> None:
        super().__init__()
        self.event = event


class EventPanel(Widget):
    DEFAULT_CSS = """
    EventPanel {
        padding: 1;
        overflow-y: auto;
    }
    #ep-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    .ep-row {
        color: $text-muted;
        margin-bottom: 0;
    }
    .ep-value {
        color: $text;
        margin-left: 2;
        margin-bottom: 1;
    }
    #ep-actions {
        layout: horizontal;
        margin-top: 2;
        height: 3;
    }
    #ep-actions Button {
        margin-right: 1;
    }
    """

    current_event: reactive[CalEvent | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("", id="ep-title")
        yield Label("", id="ep-when", classes="ep-row")
        yield Label("", id="ep-where", classes="ep-value")
        yield Label("", id="ep-calendar", classes="ep-row")
        yield Label("", id="ep-cal-name", classes="ep-value")
        yield Label("", id="ep-description", classes="ep-value")
        yield Label("", id="ep-attendees", classes="ep-value")
        yield Label("", id="ep-recurring", classes="ep-value")
        with Horizontal(id="ep-actions"):
            yield Button("Edit [e]", id="ep-edit", variant="primary")
            yield Button("Delete [d]", id="ep-delete", variant="error")

    def watch_current_event(self, event: CalEvent | None) -> None:
        if event is None:
            self._clear()
            return
        self._populate(event)

    def _clear(self) -> None:
        for id_ in ("#ep-title", "#ep-when", "#ep-where", "#ep-calendar",
                    "#ep-cal-name", "#ep-description", "#ep-attendees", "#ep-recurring"):
            self.query_one(id_, Label).update("")

    def _populate(self, event: CalEvent) -> None:
        title = ("↻ " if event.is_recurring else "") + event.summary
        self.query_one("#ep-title", Label).update(title)

        when = _format_when(event)
        self.query_one("#ep-when", Label).update(f"🕐 {when}")
        self.query_one("#ep-where", Label).update(event.location or "")
        self.query_one("#ep-calendar", Label).update("📅 Calendar:")
        self.query_one("#ep-cal-name", Label).update(event.calendar_id)

        desc = event.description or ""
        if desc:
            desc = "\n".join(textwrap.wrap(desc, width=30))
        self.query_one("#ep-description", Label).update(desc)

        att = ""
        if event.attendees:
            att = "👥 " + ", ".join(event.attendees[:5])
            if len(event.attendees) > 5:
                att += f" +{len(event.attendees) - 5}"
        self.query_one("#ep-attendees", Label).update(att)

        rec = "↻ Recurring event" if event.is_recurring else ""
        self.query_one("#ep-recurring", Label).update(rec)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.current_event is None:
            return
        if event.button.id == "ep-edit":
            self.post_message(EditRequested(self.current_event))
        elif event.button.id == "ep-delete":
            self.post_message(DeleteRequested(self.current_event))


def _format_when(event: CalEvent) -> str:
    if event.is_all_day:
        from datetime import date
        s = event.start if isinstance(event.start, date) else event.start.date()
        return s.strftime("%a %d %b") + " (all day)"
    if hasattr(event.start, "strftime"):
        s = event.start.strftime("%a %d %b, %H:%M")  # type: ignore[union-attr]
        e = event.end.strftime("%H:%M") if hasattr(event.end, "strftime") else ""  # type: ignore[union-attr]
        return f"{s}–{e}"
    return str(event.start)
