from __future__ import annotations
from datetime import date, datetime

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        layout: horizontal;
        background: $primary-darken-2;
        dock: bottom;
    }
    StatusBar Label {
        padding: 0 1;
    }
    #sb-date-view {
        width: 32;
        color: $text;
    }
    #sb-sync {
        width: 1fr;
        color: $text-muted;
    }
    #sb-hints {
        width: auto;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="sb-date-view")
        yield Label("", id="sb-sync")
        yield Label("", id="sb-hints")

    def update(
        self,
        current_date: date,
        view_name: str,
        last_sync: datetime | None,
        is_loading: bool,
        error: str | None = None,
    ) -> None:
        date_str = current_date.strftime("%a %d %b %Y")
        self.query_one("#sb-date-view", Label).update(
            f" {date_str}  [{view_name.capitalize()}]"
        )

        if error:
            sync_text = f"Error: {error[:40]}"
        elif is_loading:
            sync_text = " ⟳ Syncing…"
        elif last_sync:
            sync_text = f" ✓ {last_sync.strftime('%H:%M')}"
        else:
            sync_text = " Not synced"

        self.query_one("#sb-sync", Label).update(sync_text)

        base = "q/m:month w:week d:day a:agenda │ ::go n:new e:edit x:del s:search r:sync ctrl+q:quit"
        if view_name in ("monthly", "weekly"):
            hints = f"enter:day │ {base}"
        else:
            hints = base
        self.query_one("#sb-hints", Label).update(hints)
