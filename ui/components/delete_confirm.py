from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Label
from textual.containers import Container, Horizontal


class DeleteConfirmModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    DeleteConfirmModal {
        align: center middle;
    }
    DeleteConfirmModal > Container {
        width: 52;
        height: auto;
        background: $surface;
        border: round $error;
        padding: 2;
    }
    #dc-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #dc-note {
        color: $text-muted;
        margin-bottom: 1;
    }
    #dc-actions {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    #dc-actions Button {
        margin-right: 1;
    }
    """

    def __init__(self, event_summary: str) -> None:
        super().__init__()
        self._summary = event_summary

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Delete \"{self._summary}\"?", id="dc-title")
            yield Label("This cannot be undone.", id="dc-note")
            with Horizontal(id="dc-actions"):
                yield Button("Delete", variant="error", id="dc-yes")
                yield Button("Cancel", id="dc-no")

    def on_key(self, event) -> None:
        if event.key in ("escape", "n"):
            self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "dc-yes")
