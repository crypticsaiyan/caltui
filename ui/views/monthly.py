from __future__ import annotations
import calendar as cal_mod
from datetime import date, time, timedelta

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Button, Static
from textual.containers import Horizontal, Vertical
from textual import work

from models import CalEvent, GCalendar, Task
from ui.theme import color_for_event
from ui.messages import DateSelected, EventSelected


class MonthlyView(Widget):
    DEFAULT_CSS = """
    MonthlyView {
        layout: vertical;
    }
    .month-nav {
        layout: horizontal;
        height: 1;
        background: $surface-darken-1;
    }
    .month-nav-btn {
        width: 3;
        min-width: 3;
        border: none;
        background: $surface-darken-1;
        color: $text;
    }
    .month-title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        padding: 0 1;
    }
    .month-dow-row {
        layout: grid;
        grid-size: 7;
        height: 1;
        background: $surface-darken-1;
    }
    .month-dow-label {
        text-align: center;
        color: $text-muted;
    }
    .month-grid {
        layout: grid;
        grid-size: 7;
        height: 1fr;
    }
    """

    _year: int
    _month: int

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._events: list[CalEvent] = []
        self._tasks: list[Task] = []
        self._calendars: list[GCalendar] = []
        self._selected_date: date = today
        self._max_chips = 3

    def compose(self) -> ComposeResult:
        with Horizontal(classes="month-nav"):
            prev_button = Button("◀", id="mv-prev", classes="month-nav-btn")
            prev_button.can_focus = False
            yield prev_button
            yield Label("", id="mv-title", classes="month-title")
            next_button = Button("▶", id="mv-next", classes="month-nav-btn")
            next_button.can_focus = False
            yield next_button
        with Horizontal(classes="month-dow-row"):
            for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
                yield Label(day, classes="month-dow-label")
        yield Vertical(id="mv-grid", classes="month-grid")

    def on_mount(self) -> None:
        self._rebuild()

    def update(
        self,
        events: list[CalEvent],
        tasks: list[Task],
        calendars: list[GCalendar],
        current_date: date,
        max_chips: int = 3,
    ) -> None:
        self._events = events
        self._tasks = tasks
        self._calendars = calendars
        self._selected_date = current_date
        self._year = current_date.year
        self._month = current_date.month
        self._max_chips = max_chips
        self._rebuild()

    def go_prev_month(self) -> None:
        m = self._month - 1
        y = self._year
        if m < 1:
            m = 12
            y -= 1
        self._year, self._month = y, m
        self._rebuild()
        self.post_message(DateSelected(date(y, m, 1)))

    def go_next_month(self) -> None:
        m = self._month + 1
        y = self._year
        if m > 12:
            m = 1
            y += 1
        self._year, self._month = y, m
        self._rebuild()
        self.post_message(DateSelected(date(y, m, 1)))

    def set_selected_date(self, new_date: date) -> None:
        """Fast-path: same month → toggle CSS only. Different month → full rebuild."""
        old_date = self._selected_date
        self._selected_date = new_date

        if new_date.year == self._year and new_date.month == self._month:
            # Same month — just move the selected class, no widget churn
            if old_date != new_date:
                try:
                    self.query_one(f"#mday-{old_date.isoformat()}", DayCell).remove_class("selected")
                except Exception:
                    pass
                try:
                    self.query_one(f"#mday-{new_date.isoformat()}", DayCell).add_class("selected")
                except Exception:
                    pass
        else:
            self._year = new_date.year
            self._month = new_date.month
            self._rebuild()

    def _rebuild(self) -> None:
        title = self.query_one("#mv-title", Label)
        title.update(f"{cal_mod.month_name[self._month]} {self._year}")
        self._pending_cells = self._build_cells()
        self._do_rebuild()

    def _build_cells(self) -> list["DayCell"]:
        cal_map = {c.id: c for c in self._calendars}
        events_by_date: dict[date, list[CalEvent]] = {}
        tasks_by_date: dict[date, list[Task]] = {}

        for ev in self._events:
            start = ev.start_date()
            if ev.is_all_day:
                # Google all-day end date is exclusive; expand across all spanned days
                current = start
                end = ev.end_date()
                while current < end:
                    events_by_date.setdefault(current, []).append(ev)
                    current += timedelta(days=1)
            else:
                current = start
                end = _inclusive_timed_end_date(ev)
                while current <= end:
                    events_by_date.setdefault(current, []).append(ev)
                    current += timedelta(days=1)

        for task in self._tasks:
            if task.due:
                tasks_by_date.setdefault(task.due, []).append(task)

        weeks = cal_mod.monthcalendar(self._year, self._month)
        while len(weeks) < 6:
            last = weeks[-1]
            last_day = max(d for d in last if d != 0)
            next_week_start = date(self._year, self._month, last_day) + timedelta(days=1)
            new_week = []
            for i in range(7):
                nd = next_week_start + timedelta(days=i)
                new_week.append(nd.day if nd.month == self._month else 0)
            weeks.append(new_week)

        cells: list[DayCell] = []
        for week in weeks:
            for day_num in week:
                if day_num == 0:
                    cells.append(DayCell(None, False, False, True, [], [], cal_map, self._max_chips))
                else:
                    d = date(self._year, self._month, day_num)
                    cells.append(DayCell(
                        d, d == date.today(), d == self._selected_date, False,
                        events_by_date.get(d, []), tasks_by_date.get(d, []),
                        cal_map, self._max_chips,
                        id=f"mday-{d.isoformat()}",
                    ))
        return cells

    @work(exclusive=True)
    async def _do_rebuild(self) -> None:
        grid = self.query_one("#mv-grid", Vertical)
        await grid.remove_children()
        grid.mount(*self._pending_cells)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mv-prev":
            self.go_prev_month()
        elif event.button.id == "mv-next":
            self.go_next_month()

    def on_day_cell_selected(self, message: "DayCellSelected") -> None:
        self._selected_date = message.date_
        self.post_message(DateSelected(message.date_))

    def on_day_cell_event_clicked(self, message: "DayCellEventClicked") -> None:
        self.post_message(EventSelected(message.event))


class DayCellSelected(Message):
    def __init__(self, date_: date) -> None:
        super().__init__()
        self.date_ = date_


class DayCellEventClicked(Message):
    def __init__(self, event: CalEvent) -> None:
        super().__init__()
        self.event = event


class DayCell(Widget):
    DEFAULT_CSS = """
    DayCell {
        border: solid $surface-lighten-1;
        overflow-y: auto;
        padding: 0;
        layout: vertical;
    }
    DayCell:focus {
        border: solid $accent;
    }
    DayCell.today .day-number {
        color: $accent;
        text-style: bold;
    }
    DayCell.today {
        border: solid $accent;
    }
    DayCell.selected {
        border: solid $primary;
    }
    DayCell.today.selected {
        border: solid $accent;
        background: $primary-darken-3;
    }
    DayCell.other-month {
        background: $surface-darken-1;
    }
    DayCell.other-month .day-number {
        color: $text-disabled;
    }
    .day-number {
        text-align: right;
        padding: 0 1;
        color: $text;
        height: 1;
    }
    .event-chip {
        height: 1;
        overflow: hidden;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        date_: date | None,
        is_today: bool,
        is_selected: bool,
        is_other_month: bool,
        events: list[CalEvent],
        tasks: list[Task],
        cal_map: dict[str, GCalendar],
        max_chips: int,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._date = date_
        self._is_today = is_today
        self._is_selected = is_selected
        self._is_other_month = is_other_month
        self._events = events
        self._tasks = tasks
        self._cal_map = cal_map
        self._max_chips = max_chips

        if is_today:
            self.add_class("today")
        if is_selected:
            self.add_class("selected")
        if is_other_month:
            self.add_class("other-month")

    def compose(self) -> ComposeResult:
        if self._date is None:
            yield Label("", classes="day-number")
            return

        yield Label(str(self._date.day), classes="day-number")

        all_items: list[tuple[str, str, CalEvent | None]] = []
        for ev in self._events:
            cal = self._cal_map.get(ev.calendar_id)
            color = color_for_event(ev, cal)
            prefix = "↻ " if ev.is_recurring else ""
            all_items.append((prefix + ev.summary, color, ev))
        for task in self._tasks:
            all_items.append(("☐ " + task.title, "#26a69a", None))

        for label, color, ev in all_items:
            yield EventChip(label, color, ev)

    def on_click(self) -> None:
        if self._date is not None:
            self.post_message(DayCellSelected(self._date))


class EventChip(Static):
    DEFAULT_CSS = """
    EventChip {
        height: 1;
        overflow: hidden;
        padding: 0 1;
    }
    EventChip:hover {
        text-style: bold;
    }
    """

    def __init__(self, label: str, color: str, event: CalEvent | None) -> None:
        super().__init__()
        self._label = label
        self._color = color
        self._event = event

    def render(self):
        from rich.text import Text
        t = Text(self._label, style=f"on {self._color}", overflow="ellipsis", no_wrap=True)
        return t

    def on_click(self, event) -> None:
        event.stop()
        if self._event is not None:
            self.post_message(DayCellEventClicked(self._event))


def _inclusive_timed_end_date(event: CalEvent) -> date:
    end = event.end_dt()
    if end.time() == time.min and end.date() > event.start_date():
        return end.date() - timedelta(days=1)
    return end.date()
