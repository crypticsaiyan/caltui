from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Label
from textual.containers import Container

HELP_TEXT = """\
 Views               Navigation
 ──────────────      ─────────────────────────────────
 m   Monthly         h / ←   Previous day
 w   Weekly          l / →   Next day
 d   Day popup       k / ↑   Previous week
 a   Agenda          j / ↓   Next week  (prev/next item in Agenda)
                     [       Previous month (Monthly) / week
                     ]       Next month (Monthly) / week
                     t       Jump to today
                     :       Go to date

 Events              Other
 ──────────────      ─────────────────────────────────
 n   New event       s / /   Search events
 e   Edit selected   r       Refresh / sync
 x   Delete          ?       This help
 Enter  Day popup    q       Month view
 Esc    Close panel  Ctrl+Q  Quit
"""


class HelpModal(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > Container {
        width: 56;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 2;
    }
    .help-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .help-body {
        color: $text;
    }
    #help-close {
        margin-top: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Keyboard Shortcuts — caltui", classes="help-title")
            yield Label(HELP_TEXT, classes="help-body")
            yield Button("Close [Esc]", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key in ("escape", "q", "?"):
            self.dismiss(None)
