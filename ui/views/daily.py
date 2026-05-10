from __future__ import annotations
from dataclasses import replace
from datetime import date, datetime, time, timedelta

from textual.app import ComposeResult
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Label, Button, Static
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from rich.text import Text
from rich.console import RenderableType

from models import CalEvent, GCalendar, Task
from ui.theme import color_for_event, DEFAULT_TASK_COLOR, contrasting_text
from ui.messages import DateSelected, EventSelected


class DailyView(Widget):
    DEFAULT_CSS = """
    DailyView {
        layout: vertical;
    }
    .dv-header {
        layout: horizontal;
        height: 1;
        background: $surface-darken-1;
    }
    .dv-nav-btn {
        width: 3;
        min-width: 3;
        border: none;
        background: $surface-darken-1;
    }
    .dv-title {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    .dv-allday {
        layout: horizontal;
        min-height: 1;
        background: $surface-darken-2;
        border-bottom: solid $surface-lighten-1;
    }
    .dv-allday-gutter {
        width: 6;
        color: $text-muted;
        padding: 0 1;
    }
    .dv-allday-chips {
        width: 1fr;
        overflow: hidden;
    }
    .dv-body {
        layout: vertical;
        height: 1fr;
        overflow-y: auto;
    }
    DailyEventList {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }
    DailyEventRow {
        height: 1;
        overflow: hidden;
    }
    DailyEventRow:hover {
        text-style: bold;
    }
    .dv-task-row {
        height: 1;
        overflow: hidden;
    }
    .dv-empty {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._date: date = date.today()
        self._events: list[CalEvent] = []
        self._tasks: list[Task] = []
        self._cal_map: dict[str, GCalendar] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(classes="dv-header"):
            prev_button = Button("◀", id="dv-prev", classes="dv-nav-btn")
            prev_button.can_focus = False
            yield prev_button
            yield Label("", id="dv-title", classes="dv-title")
            next_button = Button("▶", id="dv-next", classes="dv-nav-btn")
            next_button.can_focus = False
            yield next_button
        with Horizontal(classes="dv-allday"):
            yield Label("allday", classes="dv-allday-gutter")
            yield Label("", id="dv-allday-chips", markup=True, classes="dv-allday-chips")
        with Vertical(classes="dv-body"):
            yield DailyEventList(id="dv-events")

    def on_mount(self) -> None:
        self._update_title()

    def update(
        self,
        events: list[CalEvent],
        tasks: list[Task],
        calendars: list[GCalendar],
        day: date,
    ) -> None:
        self._date = day
        self._events = [
            e for e in events
            if (e.is_all_day and e.start_date() <= day < e.end_date())
            or (not e.is_all_day and _timed_event_segment_for_day(e, day) is not None)
        ]
        self._tasks = [task for task in tasks if task.due == day]
        self._cal_map = {c.id: c for c in calendars}
        self._update_title()
        self._update_allday()
        self._update_event_list()

    def go_prev_day(self) -> None:
        self._date -= timedelta(days=1)
        self.post_message(DateSelected(self._date))

    def go_next_day(self) -> None:
        self._date += timedelta(days=1)
        self.post_message(DateSelected(self._date))

    def _update_title(self) -> None:
        today = date.today()
        suffix = " (Today)" if self._date == today else ""
        label = self.query_one("#dv-title", Label)
        label.update(self._date.strftime("%A, %d %B %Y") + suffix)

    def _update_allday(self) -> None:
        parts: list[str] = []
        for ev in self._events:
            if ev.is_all_day:
                cal = self._cal_map.get(ev.calendar_id)
                color = color_for_event(ev, cal)
                fg = contrasting_text(color)
                parts.append(f"[{fg} on {color}] {ev.summary[:20]} [/{fg} on {color}]")
        self.query_one("#dv-allday-chips", Label).update(" ".join(parts))

    def _update_event_list(self) -> None:
        event_list = self.query_one("#dv-events", DailyEventList)
        event_list.update_day(self._date, self._events, self._tasks, self._cal_map)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dv-prev":
            self.go_prev_day()
        elif event.button.id == "dv-next":
            self.go_next_day()

    def on_daily_event_row_clicked(self, message: "DailyEventRow.Clicked") -> None:
        self.post_message(EventSelected(message.event))


class DailyEventList(VerticalScroll):
    def update_day(
        self,
        day: date,
        events: list[CalEvent],
        tasks: list[Task],
        cal_map: dict[str, GCalendar],
    ) -> None:
        for child in list(self.children):
            child.remove()

        rows: list[Widget] = []
        all_day_events = [event for event in events if event.is_all_day]
        timed_events = [
            (segment, event)
            for event in events
            if not event.is_all_day
            for segment in [_timed_event_segment_for_day(event, day)]
            if segment is not None
        ]

        for event in sorted(all_day_events, key=lambda ev: ev.summary.lower()):
            rows.append(DailyEventRow("all day", event.summary, event, cal_map))
        for segment, event in sorted(timed_events, key=lambda pair: pair[0].start_dt()):
            rows.append(DailyEventRow(_format_timed_segment(segment), event.summary, event, cal_map))
        for task in sorted(tasks, key=lambda t: t.title.lower()):
            rows.append(DailyTaskRow(task))

        if not rows:
            rows.append(Label("No events", classes="dv-empty"))
        self.mount(*rows)


class DailyEventRow(Static):
    class Clicked(Message):
        def __init__(self, event: CalEvent) -> None:
            super().__init__()
            self.event = event

    def __init__(
        self,
        when: str,
        summary: str,
        event: CalEvent,
        cal_map: dict[str, GCalendar],
    ) -> None:
        super().__init__()
        self._when = when
        self._summary = summary
        self._event = event
        self._color = color_for_event(event, cal_map.get(event.calendar_id))

    def render(self) -> RenderableType:
        fg = contrasting_text(self._color)
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append(f"{self._when:<11} ", style="dim")
        text.append(self._summary, style=f"{fg} on {self._color}")
        return text

    def on_click(self, event) -> None:
        event.stop()
        self.post_message(self.Clicked(self._event))


class DailyTaskRow(Static):
    def __init__(self, task: Task) -> None:
        super().__init__(classes="dv-task-row")
        self._task = task

    def render(self) -> RenderableType:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("task        ", style="dim")
        text.append("☐ " + self._task.title, style=f"on {DEFAULT_TASK_COLOR}")
        return text


class DailyModal(ModalScreen[CalEvent | None]):
    DEFAULT_CSS = """
    DailyModal {
        align: center middle;
    }
    DailyModal > Container {
        width: 82;
        max-width: 92%;
        height: 28;
        max-height: 86%;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    DailyModal DailyView {
        height: 1fr;
    }
    """

    def __init__(
        self,
        events: list[CalEvent],
        tasks: list[Task],
        calendars: list[GCalendar],
        day: date,
    ) -> None:
        super().__init__()
        self._events = events
        self._tasks = tasks
        self._calendars = calendars
        self._day = day

    def compose(self) -> ComposeResult:
        with Container():
            yield DailyView(id="daily-modal-view")

    def on_mount(self) -> None:
        self._update_view()

    def _update_view(self) -> None:
        self.query_one("#daily-modal-view", DailyView).update(
            self._events, self._tasks, self._calendars, self._day
        )

    def on_date_selected(self, message: DateSelected) -> None:
        message.stop()
        self._day = message.date_
        self._update_view()

    def on_event_selected(self, message: EventSelected) -> None:
        message.stop()
        self.dismiss(message.event)

    def on_key(self, event) -> None:
        if event.key in ("escape", "q"):
            self.dismiss(None)


def _timed_event_segment_for_day(event: CalEvent, day: date) -> CalEvent | None:
    start = event.start_dt()
    end = event.end_dt()
    day_start = datetime.combine(day, time.min, tzinfo=start.tzinfo)
    day_end = day_start + timedelta(days=1)

    if end <= day_start or start >= day_end:
        return None

    clipped_start = max(start, day_start)
    clipped_end = min(end, day_end)
    if clipped_end <= clipped_start:
        return None

    return replace(event, start=clipped_start, end=clipped_end)


def _format_timed_segment(event: CalEvent) -> str:
    start = event.start_dt()
    end = event.end_dt()
    return f"{start:%H:%M}-{end:%H:%M}"
