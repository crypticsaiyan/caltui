from __future__ import annotations
from datetime import datetime, date, timedelta

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Input, Checkbox, Select, TextArea
from textual.containers import Container, Horizontal, Vertical

from models import CalEvent, GCalendar, event_to_insert_body, event_to_patch_body
from ui.theme import GOOGLE_COLOR_NAMES, GOOGLE_COLOR_NAME_TO_ID


class EventFormModal(ModalScreen[dict | None]):
    DEFAULT_CSS = """
    EventFormModal {
        align: center middle;
    }
    EventFormModal > Container {
        width: 64;
        height: auto;
        max-height: 90%;
        overflow-y: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    .form-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .form-label {
        color: $text-muted;
        margin-top: 1;
        height: 1;
    }
    .form-row {
        layout: horizontal;
        height: auto;
        margin-bottom: 0;
    }
    .form-actions {
        layout: horizontal;
        margin-top: 2;
        height: 3;
    }
    .form-actions Button {
        margin-right: 1;
    }
    #f-description {
        height: 3;
        margin-top: 0;
    }
    """

    def __init__(self, event: CalEvent | None, calendars: list[GCalendar]) -> None:
        super().__init__()
        self._event = event
        self._calendars = [c for c in calendars if c.writable] or calendars

    def compose(self) -> ComposeResult:
        ev = self._event
        is_edit = ev is not None
        title = "Edit Event" if is_edit else "New Event"

        with Container():
            yield Label(title, classes="form-title")

            yield Label("Title *", classes="form-label")
            yield Input(
                value=ev.summary if ev else "",
                placeholder="Event title",
                id="f-summary",
            )

            yield Label("Calendar", classes="form-label")
            cal_options = [(c.summary, c.id) for c in self._calendars]
            current_cal = ev.calendar_id if ev else (self._calendars[0].id if self._calendars else "")
            yield Select(
                cal_options,
                value=current_cal,
                id="f-calendar",
            )

            yield Label("All day", classes="form-label")
            yield Checkbox("All-day event", value=ev.is_all_day if ev else False, id="f-allday")

            yield Label("Start (YYYY-MM-DD HH:MM)", classes="form-label", id="f-start-label")
            start_val = _format_dt(ev.start) if ev else _default_start()
            yield Input(value=start_val, placeholder="2025-01-01 09:00", id="f-start")

            yield Label("End (YYYY-MM-DD HH:MM)", classes="form-label", id="f-end-label")
            end_val = _format_dt(ev.end) if ev else _default_end()
            yield Input(value=end_val, placeholder="2025-01-01 10:00", id="f-end")

            yield Label("Location", classes="form-label")
            yield Input(
                value=ev.location or "" if ev else "",
                placeholder="Location (optional)",
                id="f-location",
            )

            yield Label("Description", classes="form-label")
            yield TextArea(
                text=ev.description or "" if ev else "",
                id="f-description",
            )

            yield Label("Color", classes="form-label")
            color_options: list[tuple[str, str]] = [("(calendar default)", "")]
            color_options += [(name, name) for name in GOOGLE_COLOR_NAMES]
            current_color = ""
            if ev and ev.color_id:
                for name, cid in GOOGLE_COLOR_NAME_TO_ID.items():
                    if cid == ev.color_id:
                        current_color = name
                        break
            yield Select(color_options, value=current_color, id="f-color")

            yield Label("", id="f-error", classes="form-label")

            with Horizontal(classes="form-actions"):
                yield Button("Save", variant="primary", id="f-save")
                yield Button("Cancel", id="f-cancel")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "f-allday":
            return
        is_all_day = event.value
        start_label = self.query_one("#f-start-label", Label)
        end_label = self.query_one("#f-end-label", Label)
        if is_all_day:
            start_label.update("Start date (YYYY-MM-DD)")
            end_label.update("End date (YYYY-MM-DD)")
        else:
            start_label.update("Start (YYYY-MM-DD HH:MM)")
            end_label.update("End (YYYY-MM-DD HH:MM)")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "f-cancel":
            self.dismiss(None)
        elif event.button.id == "f-save":
            self._try_save()

    def _try_save(self) -> None:
        error_label = self.query_one("#f-error", Label)

        summary = self.query_one("#f-summary", Input).value.strip()
        if not summary:
            error_label.update("Title is required.")
            return

        is_all_day = self.query_one("#f-allday", Checkbox).value
        start_str = self.query_one("#f-start", Input).value.strip()
        end_str = self.query_one("#f-end", Input).value.strip()

        try:
            start, end = _parse_start_end(start_str, end_str, is_all_day)
        except ValueError as exc:
            error_label.update(str(exc))
            return

        location = self.query_one("#f-location", Input).value.strip()
        description = self.query_one("#f-description", TextArea).text.strip()

        color_val = self.query_one("#f-color", Select).value
        color_id = GOOGLE_COLOR_NAME_TO_ID.get(color_val) if color_val else None

        cal_id = self.query_one("#f-calendar", Select).value

        body = event_to_insert_body(
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=location,
            color_id=color_id,
            is_all_day=is_all_day,
        )
        body["_calendar_id"] = cal_id  # signal to App which calendar to use
        if self._event:
            body["_event_id"] = self._event.id

        error_label.update("")
        self.dismiss(body)


def _format_dt(dt) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    if isinstance(dt, date):
        return dt.strftime("%Y-%m-%d")
    return str(dt)


def _default_start() -> str:
    now = datetime.now()
    rounded = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return rounded.strftime("%Y-%m-%d %H:%M")


def _default_end() -> str:
    now = datetime.now()
    rounded = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    return rounded.strftime("%Y-%m-%d %H:%M")


def _parse_start_end(start_str: str, end_str: str, is_all_day: bool):
    if is_all_day:
        try:
            start = date.fromisoformat(start_str[:10])
            end = date.fromisoformat(end_str[:10]) if end_str else start + timedelta(days=1)
        except ValueError:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD.")
    else:
        fmts = ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"]
        start = None
        for fmt in fmts:
            try:
                start = datetime.strptime(start_str, fmt)
                break
            except ValueError:
                pass
        if start is None:
            raise ValueError("Invalid start time. Use YYYY-MM-DD HH:MM.")

        end = None
        if end_str:
            for fmt in fmts:
                try:
                    end = datetime.strptime(end_str, fmt)
                    break
                except ValueError:
                    pass
        if end is None:
            end = start + timedelta(hours=1)

        if end <= start:
            raise ValueError("End time must be after start time.")

    return start, end
