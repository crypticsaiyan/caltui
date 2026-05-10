from __future__ import annotations
from datetime import date, datetime, timezone

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.containers import ScrollableContainer, Vertical
from textual import work

from models import CalEvent, GCalendar, Task
from ui.theme import color_for_event, DEFAULT_TASK_COLOR
from ui.messages import EventSelected


class AgendaView(ScrollableContainer):
    DEFAULT_CSS = """
    AgendaView {
        overflow-y: auto;
        padding: 0;
    }
    .agenda-empty {
        text-align: center;
        color: $text-muted;
        padding: 4;
    }
    .agenda-date-header {
        text-style: bold;
        background: $surface-darken-1;
        padding: 0 1;
        color: $accent;
        height: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected_idx = -1
        self._rows: list[Widget] = []

    def compose(self) -> ComposeResult:
        yield Label("No events to display.", classes="agenda-empty", id="agenda-empty")

    def update(
        self,
        events: list[CalEvent],
        tasks: list[Task],
        calendars: list[GCalendar],
        start_date: date,
    ) -> None:
        cal_map = {c.id: c for c in calendars}
        self._selected_idx = -1
        self._rows = []

        grouped = _group_by_date(events, tasks, start_date)

        widgets: list[Widget] = []
        if not grouped:
            widgets.append(Label("No upcoming events.", classes="agenda-empty"))
        else:
            for day, (day_events, day_tasks) in sorted(grouped.items()):
                widgets.append(Label(_fmt_date_header(day), classes="agenda-date-header"))
                for ev in day_events:
                    cal = cal_map.get(ev.calendar_id)
                    color = color_for_event(ev, cal)
                    row = AgendaEventRow(ev, cal, color)
                    widgets.append(row)
                    self._rows.append(row)
                for task in day_tasks:
                    row = AgendaTaskRow(task)
                    widgets.append(row)
                    self._rows.append(row)

        self._pending_widgets = widgets
        self._do_rebuild()

    @work(exclusive=True)
    async def _do_rebuild(self) -> None:
        await self.remove_children()
        self.mount(*self._pending_widgets)

    def move_selection(self, delta: int) -> None:
        if not self._rows:
            return
        if self._selected_idx >= 0 and self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].remove_class("selected")
        self._selected_idx = max(0, min(len(self._rows) - 1, self._selected_idx + delta))
        row = self._rows[self._selected_idx]
        row.add_class("selected")
        row.scroll_visible()

    def get_selected_event(self) -> CalEvent | None:
        if self._selected_idx < 0 or self._selected_idx >= len(self._rows):
            return None
        row = self._rows[self._selected_idx]
        if isinstance(row, AgendaEventRow):
            return row.event
        return None

    def on_agenda_event_row_clicked(self, message: "AgendaEventRow.Clicked") -> None:
        self.post_message(EventSelected(message.event))

    def on_agenda_task_row_space_pressed(self, message: "AgendaTaskRow.SpacePressed") -> None:
        pass  # handled by App


class AgendaEventRow(Static):
    class Clicked(Message):
        def __init__(self, event: CalEvent) -> None:
            super().__init__()
            self.event = event

    DEFAULT_CSS = """
    AgendaEventRow {
        layout: horizontal;
        height: 1;
        padding: 0 1;
    }
    AgendaEventRow:hover {
        background: $primary-darken-3;
    }
    AgendaEventRow.selected {
        background: $primary-darken-2;
    }
    .ae-time {
        width: 13;
        color: $text-muted;
    }
    .ae-dot {
        width: 2;
    }
    .ae-title {
        width: 1fr;
        overflow: hidden;
    }
    .ae-cal {
        width: 12;
        color: $text-muted;
        text-align: right;
        overflow: hidden;
    }
    """

    def __init__(self, event: CalEvent, cal: GCalendar | None, color: str) -> None:
        super().__init__()
        self.event = event
        self._cal = cal
        self._color = color

    def compose(self) -> ComposeResult:
        recur = "↻ " if self.event.is_recurring else ""
        if self.event.is_all_day:
            time_str = "all day      "
        elif isinstance(self.event.start, datetime):
            time_str = self.event.start.strftime("%H:%M") + (
                f"–{self.event.end.strftime('%H:%M')}" if isinstance(self.event.end, datetime) else ""
            )
        else:
            time_str = ""

        yield Label(time_str, classes="ae-time")
        yield Label(f"[{self._color}]●[/{self._color}]", classes="ae-dot", markup=True)
        yield Label(recur + self.event.summary, classes="ae-title")
        cal_name = self._cal.summary if self._cal else ""
        yield Label(cal_name[:12], classes="ae-cal")

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.event))


class AgendaTaskRow(Static):
    class SpacePressed(Message):
        def __init__(self, task: Task) -> None:
            super().__init__()
            self.task = task

    DEFAULT_CSS = """
    AgendaTaskRow {
        layout: horizontal;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    AgendaTaskRow.selected {
        background: $primary-darken-2;
    }
    .at-check {
        width: 3;
    }
    .at-title {
        width: 1fr;
    }
    """

    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task

    def compose(self) -> ComposeResult:
        check = "[✓]" if self.task.completed else "[ ]"
        yield Label(check, classes="at-check")
        title = self.task.title
        if self.task.completed:
            title = f"[strike]{title}[/strike]"
        yield Label(title, classes="at-title", markup=True)


def _group_by_date(
    events: list[CalEvent],
    tasks: list[Task],
    start_date: date,
) -> dict[date, tuple[list[CalEvent], list[Task]]]:
    groups: dict[date, tuple[list[CalEvent], list[Task]]] = {}

    for ev in events:
        if ev.is_all_day:
            # Multi-day all-day events that started before today are still
            # ongoing if end_date > start_date (Google end is exclusive).
            if ev.end_date() <= start_date:
                continue
            d = max(start_date, ev.start_date())
        else:
            d = ev.start_date()
            if d < start_date:
                continue
        if d not in groups:
            groups[d] = ([], [])
        groups[d][0].append(ev)

    for task in tasks:
        if not task.due:
            continue
        d = task.due
        if d < start_date:
            continue
        if d not in groups:
            groups[d] = ([], [])
        groups[d][1].append(task)

    return groups


def _fmt_date_header(d: date) -> str:
    today = date.today()
    if d == today:
        return d.strftime("  Today · %A, %d %B %Y")
    elif d == today.replace(day=today.day + 1) if today.day < 28 else today:
        return d.strftime("  Tomorrow · %A, %d %B %Y")
    return d.strftime("  %A, %d %B %Y")
