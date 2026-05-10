from __future__ import annotations
from dataclasses import replace
from datetime import date, datetime, time, timedelta

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Button, Static
from textual.containers import Horizontal, VerticalScroll
from rich.text import Text
from rich.console import RenderableType

from models import CalEvent, GCalendar, Task
from ui.theme import color_for_event, contrasting_text, DEFAULT_TASK_COLOR
from ui.messages import DateSelected, EventSelected


class WeeklyView(Widget):
    DEFAULT_CSS = """
    WeeklyView {
        layout: vertical;
    }
    .wv-header {
        layout: horizontal;
        height: 1;
        background: $surface-darken-1;
    }
    .wv-nav-btn {
        width: 3;
        min-width: 3;
        border: none;
        background: $surface-darken-1;
    }
    .wv-title {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    .wv-day-headers {
        layout: horizontal;
        height: 2;
        background: $surface-darken-1;
    }
    .wv-day-header {
        width: 1fr;
        text-align: center;
        border-left: solid $surface-lighten-1;
        padding: 0 1;
    }
    .wv-day-header.today {
        color: $accent;
        text-style: bold;
    }
    .wv-day-header.selected {
        background: $primary-darken-2;
        text-style: bold;
    }
    .wv-week-columns {
        layout: horizontal;
        height: 1fr;
    }
    WeekDayColumn {
        width: 1fr;
        border-left: solid $surface-lighten-1;
        padding: 0 1;
    }
    WeekDayColumn.today {
        border-left: solid $accent;
    }
    .wv-empty {
        height: 1;
        color: $text-muted;
    }
    WeekEventRow {
        height: 1;
        overflow: hidden;
    }
    WeekEventRow:hover {
        text-style: bold;
    }
    .wv-task-row {
        height: 1;
        overflow: hidden;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        today = date.today()
        self._week_start: date = _monday_of(today)
        self._events: list[CalEvent] = []
        self._tasks: list[Task] = []
        self._cal_map: dict[str, GCalendar] = {}
        self._selected_date: date = today

    def compose(self) -> ComposeResult:
        with Horizontal(classes="wv-header"):
            prev_button = Button("◀", id="wv-prev", classes="wv-nav-btn")
            prev_button.can_focus = False
            yield prev_button
            yield Label("", id="wv-title", classes="wv-title")
            next_button = Button("▶", id="wv-next", classes="wv-nav-btn")
            next_button.can_focus = False
            yield next_button
        with Horizontal(classes="wv-day-headers"):
            for i in range(7):
                yield Label("", id=f"wv-day-hdr-{i}", classes="wv-day-header")
        with Horizontal(classes="wv-week-columns"):
            for i in range(7):
                yield WeekDayColumn(id=f"wv-day-{i}")

    def on_mount(self) -> None:
        self._update_title()
        self._update_day_headers()

    def update(
        self,
        events: list[CalEvent],
        tasks: list[Task],
        calendars: list[GCalendar],
        selected_date: date,
    ) -> None:
        self._events = events
        self._tasks = tasks
        self._cal_map = {c.id: c for c in calendars}
        self._selected_date = selected_date
        self._week_start = _monday_of(selected_date)
        self._update_title()
        self._update_day_headers()
        self._update_days()

    def set_selected_date(self, new_date: date) -> None:
        """Fast-path: same week → header highlight only. Different week → full update."""
        week_start = _monday_of(new_date)
        if week_start == self._week_start:
            self._selected_date = new_date
            self._update_day_headers()
        else:
            # Week changed — need new events; fire DateSelected so app re-fetches view
            self._selected_date = new_date
            self._week_start = week_start
            self._update_title()
            self._update_day_headers()
            self._update_days()

    def go_prev_week(self) -> None:
        self._week_start -= timedelta(weeks=1)
        self._selected_date = self._week_start
        self.post_message(DateSelected(self._selected_date))

    def go_next_week(self) -> None:
        self._week_start += timedelta(weeks=1)
        self._selected_date = self._week_start
        self.post_message(DateSelected(self._selected_date))

    def _update_title(self) -> None:
        week_end = self._week_start + timedelta(days=6)
        title = f"{self._week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
        self.query_one("#wv-title", Label).update(title)

    def _update_day_headers(self) -> None:
        today = date.today()
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            label = self.query_one(f"#wv-day-hdr-{i}", Label)
            label.update(d.strftime("%a\n%d"))
            if d == today:
                label.add_class("today")
            else:
                label.remove_class("today")
            if d == self._selected_date:
                label.add_class("selected")
            else:
                label.remove_class("selected")

    def _update_days(self) -> None:
        for i in range(7):
            d = self._week_start + timedelta(days=i)
            column = self.query_one(f"#wv-day-{i}", WeekDayColumn)
            column.update_day(d, self._events, self._tasks, self._cal_map)
            if d == date.today():
                column.add_class("today")
            else:
                column.remove_class("today")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wv-prev":
            self.go_prev_week()
        elif event.button.id == "wv-next":
            self.go_next_week()

    def on_week_event_row_clicked(self, message: "WeekEventRow.Clicked") -> None:
        self.post_message(EventSelected(message.event))

    def on_week_day_column_selected(self, message: "WeekDayColumn.Selected") -> None:
        self._selected_date = message.day
        self._update_day_headers()
        self._update_days()
        self.post_message(DateSelected(message.day))


class WeekDayColumn(VerticalScroll):
    class Selected(Message):
        def __init__(self, day: date) -> None:
            super().__init__()
            self.day = day

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._day = date.today()

    def update_day(
        self,
        day: date,
        events: list[CalEvent],
        tasks: list[Task],
        cal_map: dict[str, GCalendar],
    ) -> None:
        self._day = day
        for child in list(self.children):
            child.remove()

        rows: list[Widget] = []
        all_day_events = [
            event for event in events
            if event.is_all_day and event.start_date() <= day < event.end_date()
        ]
        timed_events = [
            (segment, event)
            for event in events
            if not event.is_all_day
            for segment in [_timed_event_segment_for_day(event, day)]
            if segment is not None
        ]

        for event in sorted(all_day_events, key=lambda ev: ev.summary.lower()):
            rows.append(WeekEventRow("all day", event.summary, event, cal_map))
        for segment, event in sorted(timed_events, key=lambda pair: pair[0].start_dt()):
            rows.append(WeekEventRow(_format_timed_segment(segment), event.summary, event, cal_map))
        for task in sorted((task for task in tasks if task.due == day), key=lambda t: t.title.lower()):
            rows.append(WeekTaskRow(task))

        if not rows:
            rows.append(Label("No events", classes="wv-empty"))
        self.mount(*rows)

    def on_click(self, event) -> None:
        self.post_message(self.Selected(self._day))


class WeekEventRow(Static):
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


class WeekTaskRow(Static):
    def __init__(self, task: Task) -> None:
        super().__init__(classes="wv-task-row")
        self._task = task

    def render(self) -> RenderableType:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("task        ", style="dim")
        text.append("☐ " + self._task.title, style=f"on {DEFAULT_TASK_COLOR}")
        return text


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


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
