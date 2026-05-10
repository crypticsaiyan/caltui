"""Canonical app-level messages shared across all views and components."""
from __future__ import annotations
from datetime import date

from textual.message import Message

from models import CalEvent


class DateSelected(Message):
    """Posted by any view/component when the user selects a date."""
    def __init__(self, date_: date) -> None:
        super().__init__()
        self.date_ = date_


class EventSelected(Message):
    """Posted by any view when the user selects (or deselects) an event."""
    def __init__(self, event: CalEvent | None) -> None:
        super().__init__()
        self.event = event


class RefreshRequested(Message):
    """Posted when a view wants a full data reload."""
