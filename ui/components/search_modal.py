from __future__ import annotations
from datetime import datetime, timedelta, timezone

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Input, ListView, ListItem
from textual.containers import Container, Horizontal
from textual import work

from models import CalEvent
from api.calendar import CalendarAPI, CalendarAPIError


class SearchModal(ModalScreen[CalEvent | None]):
    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }
    SearchModal > Container {
        width: 72;
        height: 36;
        background: $surface;
        border: round $primary;
        padding: 1 2;
        layout: vertical;
    }
    .search-title {
        text-style: bold;
        margin-bottom: 1;
        height: 1;
    }
    .search-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    .search-row Input {
        width: 1fr;
    }
    .search-row Button {
        width: 10;
        margin-left: 1;
    }
    #search-results {
        height: 1fr;
        border: solid $surface-lighten-1;
        overflow-y: auto;
    }
    .search-status {
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }
    .search-actions {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    SearchResultItem {
        height: 2;
        padding: 0 1;
    }
    SearchResultItem:hover {
        background: $primary-darken-3;
    }
    .sri-title {
        text-style: bold;
        height: 1;
    }
    .sri-meta {
        color: $text-muted;
        height: 1;
    }
    """

    def __init__(self, cal_api: CalendarAPI, calendar_ids: list[str]) -> None:
        super().__init__()
        self._cal_api = cal_api
        self._calendar_ids = calendar_ids
        self._results: list[CalEvent] = []

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Search Events", classes="search-title")
            with Horizontal(classes="search-row"):
                yield Input(placeholder="Keyword…", id="search-input")
                yield Button("Search", variant="primary", id="search-go")
            yield ListView(id="search-results")
            yield Label("", id="search-status", classes="search-status")
            with Horizontal(classes="search-actions"):
                yield Button("Open", variant="primary", id="search-open", disabled=True)
                yield Button("Cancel", id="search-cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._do_search()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-go":
            self._do_search()
        elif event.button.id == "search-cancel":
            self.dismiss(None)
        elif event.button.id == "search-open":
            self._open_selected()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.query_one("#search-open", Button).disabled = False

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self.query_one("#search-open", Button).disabled = event.item is None

    def _do_search(self) -> None:
        query = self.query_one("#search-input", Input).value.strip()
        if not query:
            return
        status = self.query_one("#search-status", Label)
        status.update("Searching…")
        lv = self.query_one("#search-results", ListView)
        lv.clear()
        self._results = []
        self.query_one("#search-open", Button).disabled = True
        self._run_search(query)

    @work(thread=True, exclusive=True)
    def _run_search(self, query: str) -> None:
        now = datetime.now(timezone.utc)
        time_min = now - timedelta(days=365)
        time_max = now + timedelta(days=365)
        try:
            results = self._cal_api.search_events(
                query=query,
                time_min=time_min,
                time_max=time_max,
                calendar_ids=self._calendar_ids,
                max_per_calendar=30,
            )
        except CalendarAPIError as exc:
            self.call_from_thread(self._show_error, str(exc))
            return
        self.call_from_thread(self._show_results, results)

    def _show_results(self, results: list[CalEvent]) -> None:
        self._results = results
        lv = self.query_one("#search-results", ListView)
        lv.clear()
        if not results:
            self.query_one("#search-status", Label).update("No results found.")
            return
        for ev in results:
            item = SearchResultItem(ev)
            lv.append(item)
        self.query_one("#search-status", Label).update(f"{len(results)} result(s)")

    def _show_error(self, msg: str) -> None:
        self.query_one("#search-status", Label).update(f"Error: {msg[:60]}")

    def _open_selected(self) -> None:
        lv = self.query_one("#search-results", ListView)
        if lv.highlighted_child is None:
            return
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._results):
            self.dismiss(self._results[idx])


class SearchResultItem(ListItem):
    def __init__(self, event: CalEvent) -> None:
        super().__init__()
        self.event = event

    def compose(self) -> ComposeResult:
        yield Label(self.event.summary, classes="sri-title")
        when = self.event.format_time()
        date_str = self.event.start_date().strftime("%a %d %b %Y")
        yield Label(f"{date_str}  {when}", classes="sri-meta")
