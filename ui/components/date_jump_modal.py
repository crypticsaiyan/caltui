from __future__ import annotations

from datetime import date, datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class DateJumpModal(ModalScreen[date | None]):
    DEFAULT_CSS = """
    DateJumpModal {
        align: center middle;
    }
    DateJumpModal > Container {
        width: 46;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    .date-jump-title {
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }
    .date-jump-row {
        layout: horizontal;
        height: 3;
    }
    .date-jump-prefix {
        width: 2;
        content-align: center middle;
        color: $accent;
        text-style: bold;
    }
    #date-jump-input {
        width: 1fr;
    }
    .date-jump-status {
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }
    .date-jump-actions {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    .date-jump-actions Button {
        margin-right: 1;
    }
    """

    def __init__(self, current_date: date) -> None:
        super().__init__()
        self._current_date = current_date

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Go to date", classes="date-jump-title")
            with Horizontal(classes="date-jump-row"):
                yield Label(":", classes="date-jump-prefix")
                yield Input(placeholder="2026-05-10, 10 May, today, +7", id="date-jump-input")
            yield Label("", id="date-jump-status", classes="date-jump-status")
            with Horizontal(classes="date-jump-actions"):
                yield Button("Go", variant="primary", id="date-jump-go")
                yield Button("Cancel", id="date-jump-cancel")

    def on_mount(self) -> None:
        self.query_one("#date-jump-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "date-jump-input":
            self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "date-jump-go":
            self._submit()
        elif event.button.id == "date-jump-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def _submit(self) -> None:
        raw = self.query_one("#date-jump-input", Input).value
        parsed = parse_date_jump(raw, self._current_date)
        if parsed is None:
            self.query_one("#date-jump-status", Label).update(
                "Use YYYY-MM-DD, DD/MM/YYYY, 10 May, today, tomorrow, or +7."
            )
            return
        self.dismiss(parsed)


def parse_date_jump(raw: str, current_date: date) -> date | None:
    text = raw.strip()
    if text.startswith(":"):
        text = text[1:].strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"today", "tod"}:
        return date.today()
    if lowered in {"tomorrow", "tmr", "tom"}:
        return date.today() + timedelta(days=1)
    if lowered in {"yesterday", "yes"}:
        return date.today() - timedelta(days=1)

    if lowered[0] in {"+", "-"} and lowered[1:].isdigit():
        return current_date + timedelta(days=int(lowered))

    if lowered.isdigit() and 1 <= int(lowered) <= 31:
        try:
            return current_date.replace(day=int(lowered))
        except ValueError:
            return None

    for fmt in (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return date(parsed.year, parsed.month, parsed.day)

    for fmt in (
        "%d %b",
        "%d %B",
        "%b %d",
        "%B %d",
    ):
        try:
            parsed = datetime.strptime(f"{text} {current_date.year}", f"{fmt} %Y")
        except ValueError:
            continue
        return date(parsed.year, parsed.month, parsed.day)

    return None
