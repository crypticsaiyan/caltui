from __future__ import annotations
import calendar as cal_mod
from datetime import date

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Button
from textual.containers import Horizontal

from ui.messages import DateSelected


class MiniCalendar(Widget):
    DEFAULT_CSS = """
    MiniCalendar {
        height: auto;
        padding: 0 1;
    }
    .mc-nav {
        layout: horizontal;
        height: 1;
    }
    .mc-nav Button {
        width: 3;
        min-width: 3;
        border: none;
        background: transparent;
        color: $text;
    }
    .mc-month-label {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    .mc-dow {
        layout: horizontal;
        height: 1;
    }
    .mc-dow Label {
        width: 3;
        text-align: center;
        color: $text-muted;
    }
    .mc-week {
        layout: horizontal;
        height: 1;
    }
    .mc-day {
        width: 3;
        text-align: center;
        background: transparent;
        border: none;
        min-width: 3;
        color: $text;
    }
    .mc-day.today {
        color: $accent;
        text-style: bold;
    }
    .mc-day.selected {
        background: $primary;
        color: $background;
    }
    .mc-day.other {
        color: $text-disabled;
    }
    .mc-day.has-dot {
        text-style: underline;
    }
    .mc-pad {
        width: 3;
    }
    """

    selected_date: reactive[date] = reactive(date.today)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._event_dates: set[date] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(classes="mc-nav"):
            yield Button("◀", id="mc-prev", classes="mc-nav")
            yield Label("", id="mc-month-label", classes="mc-month-label")
            yield Button("▶", id="mc-next", classes="mc-nav")
        with Horizontal(classes="mc-dow"):
            for day in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"):
                yield Label(day)
        yield Label("", id="mc-weeks-placeholder")

    def on_mount(self) -> None:
        self._redraw()

    def watch_selected_date(self, new_date: date) -> None:
        self._year = new_date.year
        self._month = new_date.month
        self._redraw()

    def reset_month(self) -> None:
        """Force display back to the selected_date's month (e.g. after a nav button stole Enter)."""
        self._year = self.selected_date.year
        self._month = self.selected_date.month
        self._redraw()

    def mark_event_dots(self, event_dates: set[date]) -> None:
        self._event_dates = event_dates
        self._redraw()

    def _redraw(self) -> None:
        label = self.query_one("#mc-month-label", Label)
        label.update(f"{cal_mod.month_name[self._month][:3]} {self._year}")

        placeholder = self.query_one("#mc-weeks-placeholder", Label)
        # Build a text grid representation
        weeks = cal_mod.monthcalendar(self._year, self._month)
        today = date.today()
        lines: list[str] = []
        for week in weeks:
            parts: list[str] = []
            for day in week:
                if day == 0:
                    parts.append("   ")
                    continue
                d = date(self._year, self._month, day)
                s = f"{day:2d}"
                if d in self._event_dates:
                    s = f"{day:2d}·"
                else:
                    s = f"{day:2d} "
                if d == self.selected_date:
                    parts.append(f"[reverse]{s}[/reverse]")
                elif d == today:
                    parts.append(f"[bold cyan]{s}[/bold cyan]")
                else:
                    parts.append(s)
            lines.append("".join(parts))
        placeholder.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mc-prev":
            self._shift_month(-1)
        elif event.button.id == "mc-next":
            self._shift_month(1)

    def _shift_month(self, delta: int) -> None:
        m = self._month + delta
        y = self._year
        if m < 1:
            m = 12
            y -= 1
        elif m > 12:
            m = 1
            y += 1
        self._year, self._month = y, m
        self._redraw()

    def on_click(self, event) -> None:
        # Grid text starts at row 2 (nav row + dow row), each row = 1 line
        # Each cell is 3 chars wide
        if not hasattr(event, "offset"):
            return
        row = event.offset.y - 2  # account for nav + dow header
        if row < 0:
            return
        weeks = cal_mod.monthcalendar(self._year, self._month)
        if row >= len(weeks):
            return
        col = event.offset.x // 3
        if col < 0 or col > 6:
            return
        day = weeks[row][col]
        if day == 0:
            return
        selected = date(self._year, self._month, day)
        self.selected_date = selected
        self.post_message(DateSelected(selected))
