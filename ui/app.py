from __future__ import annotations
import calendar as cal_mod
from datetime import date, datetime, timedelta, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import ContentSwitcher
from textual import work
from textual.worker import Worker, WorkerState

from models import CalEvent, GCalendar, Task, TaskList
from api.calendar import CalendarAPI, CalendarAPIError
from api.tasks import TasksAPI, TasksAPIError
import api.cache as cache
from ui.messages import DateSelected, EventSelected
from ui.views.agenda import AgendaView
from ui.views.monthly import MonthlyView
from ui.views.daily import DailyModal
from ui.views.weekly import WeeklyView
from ui.components.status_bar import StatusBar
from ui.components.event_panel import EventPanel, EditRequested, DeleteRequested
from ui.components.delete_confirm import DeleteConfirmModal
from ui.components.event_form import EventFormModal
from ui.components.search_modal import SearchModal
from ui.components.help_modal import HelpModal
from ui.components.date_jump_modal import DateJumpModal


class CalTuiApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "caltui"
    SUB_TITLE = "Google Calendar in your terminal"

    BINDINGS = [
        # Views
        Binding("m", "view_monthly", "Month", show=False),
        Binding("w", "view_weekly", "Week", show=False),
        Binding("d", "view_daily", "Day", show=False),
        Binding("a", "view_agenda", "Agenda", show=False),
        # Day-level navigation (hjkl / arrows)
        Binding("left",  "nav_prev", "Prev day", show=False),
        Binding("h",     "nav_prev", "Prev day", show=False),
        Binding("right", "nav_next", "Next day", show=False),
        Binding("l",     "nav_next", "Next day", show=False),
        Binding("up",    "nav_up",   "Prev week", show=False),
        Binding("k",     "nav_up",   "Prev week", show=False),
        Binding("down",  "nav_down", "Next week", show=False),
        Binding("j",     "nav_down", "Next week", show=False),
        # Period-level navigation (month / week jump)
        Binding("[", "nav_prev_period", "Prev month/week", show=False),
        Binding("]", "nav_next_period", "Next month/week", show=False),
        Binding("t", "go_today", "Today", show=False),
        # Events
        Binding("n",      "new_event",    "New event", show=False),
        Binding("e",      "edit_event",   "Edit",      show=False),
        Binding("x",      "delete_event", "Delete",    show=False),
        Binding("delete", "delete_event", "Delete",    show=False),
        Binding("enter",  "open_event",   "Open",      show=False),
        Binding("escape", "close_panel",  "Close",     show=False),
        # Other
        Binding("s",             "search",  "Search",  show=False),
        Binding("/",             "search",  "Search",  show=False),
        Binding("r",             "refresh", "Refresh", show=False),
        Binding("question_mark", "help",    "Help",    show=False),
        Binding("colon",         "jump_date", "Go to date", show=False),
        Binding("q",             "view_monthly", "Month", show=False),
        Binding("ctrl+q",        "quit",    "Quit",    show=False),
    ]

    def __init__(
        self,
        cal_api: CalendarAPI,
        tasks_api: TasksAPI,
        config: dict,
    ) -> None:
        super().__init__()
        self._cal_api = cal_api
        self._tasks_api = tasks_api
        self._config = config

        self._current_date: date = date.today()
        configured_view = config.get("calendar", {}).get("default_view", "monthly")
        self._view_name: str = configured_view if configured_view in {"monthly", "weekly", "agenda"} else "monthly"
        self._events: list[CalEvent] = []
        self._calendars: list[GCalendar] = []
        self._tasks: list[Task] = []
        self._task_lists: list[TaskList] = []
        self._selected_event: CalEvent | None = None
        self._is_loading: bool = False
        self._last_sync: datetime | None = None
        self._last_error: str | None = None
        self._max_chips: int = config.get("display", {}).get("max_event_chips_per_day", 3)
        self._show_tasks: bool = config.get("display", {}).get("show_tasks", True)
        self._pending_panel_action: str | None = None

    # ── Layout ─────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-body"):
            with Vertical(id="main-content"):
                with ContentSwitcher(initial=self._view_name, id="switcher"):
                    yield MonthlyView(id="monthly")
                    yield WeeklyView(id="weekly")
                    yield AgendaView(id="agenda")
            yield EventPanel(id="event-panel")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self._set_view(self._view_name)
        self._update_status_bar()
        self.load_data()

    # ── Data loading ────────────────────────────────────────────────────

    @work(thread=True, exclusive=True)
    def load_data(self, force: bool = False) -> None:
        ttl = self._config.get("api", {}).get("cache_ttl_seconds", 300)
        time_min, time_max = self._event_window()

        # Try disk cache first (skip on force refresh)
        if not force:
            entry = cache.load()
            if (
                entry is not None
                and entry.age_seconds() < ttl
                and entry.covers_window(time_min, time_max)
            ):
                self.call_from_thread(
                    self._apply_data,
                    entry.calendars, entry.events, entry.tasks, entry.task_lists,
                    from_cache=True,
                )
                return

        self.call_from_thread(self._set_loading, True)
        try:
            calendars = self._cal_api.list_calendars()
        except CalendarAPIError as exc:
            self.call_from_thread(self._set_error, f"Calendar API: {exc}")
            return
        except Exception as exc:
            self.call_from_thread(self._set_error, f"Network error: {exc}")
            return

        all_events: list[CalEvent] = []
        for cal in calendars:
            if not cal.selected:
                continue
            try:
                evs = self._cal_api.list_events(cal.id, time_min, time_max)
                all_events.extend(evs)
            except CalendarAPIError:
                pass

        all_events.sort(key=lambda e: e.start_dt())

        all_tasks: list[Task] = []
        all_task_lists: list[TaskList] = []
        if self._show_tasks:
            try:
                task_lists = self._tasks_api.list_task_lists()
                all_task_lists = task_lists
                for tl in task_lists:
                    try:
                        tasks = self._tasks_api.list_tasks(
                            tl.id,
                            show_completed=False,
                            due_min=time_min,
                            due_max=time_max,
                        )
                        all_tasks.extend(tasks)
                    except TasksAPIError:
                        pass
            except TasksAPIError:
                pass

        cache.save(time_min, time_max, calendars, all_events, all_tasks, all_task_lists)
        self.call_from_thread(
            self._apply_data, calendars, all_events, all_tasks, all_task_lists
        )

    def _apply_data(
        self,
        calendars: list[GCalendar],
        events: list[CalEvent],
        tasks: list[Task],
        task_lists: list[TaskList],
        from_cache: bool = False,
    ) -> None:
        self._calendars = calendars
        self._events = events
        self._tasks = tasks
        self._task_lists = task_lists
        self._is_loading = False
        self._last_sync = datetime.now()
        self._last_error = None

        self._update_active_view()
        self._update_status_bar()

    def _set_loading(self, loading: bool) -> None:
        self._is_loading = loading
        self._update_status_bar()

    def _set_error(self, msg: str) -> None:
        self._is_loading = False
        self._last_error = msg
        self._update_status_bar()
        self.notify(msg, severity="error", timeout=10)

    # ── View management ─────────────────────────────────────────────────

    def _set_view(self, view_name: str) -> None:
        if view_name == self._view_name:
            return
        self._view_name = view_name
        try:
            self.query_one("#switcher", ContentSwitcher).current = view_name
        except Exception:
            pass
        self._update_active_view()
        self._update_status_bar()

    def _update_active_view(self) -> None:
        if self._view_name == "monthly":
            view = self.query_one("#monthly", MonthlyView)
            view.update(
                self._events, self._tasks, self._calendars,
                self._current_date, self._max_chips,
            )
        elif self._view_name == "weekly":
            view = self.query_one("#weekly", WeeklyView)
            view.update(self._events, self._tasks, self._calendars, self._current_date)
        elif self._view_name == "agenda":
            view = self.query_one("#agenda", AgendaView)
            view.update(self._events, self._tasks, self._calendars, self._current_date)

    def _update_status_bar(self) -> None:
        try:
            sb = self.query_one("#status-bar", StatusBar)
            sb.update(
                current_date=self._current_date,
                view_name=self._view_name,
                last_sync=self._last_sync,
                is_loading=self._is_loading,
                error=self._last_error,
            )
        except Exception:
            pass

    def _event_window(self) -> tuple[datetime, datetime]:
        cfg = self._config.get("api", {})
        behind = cfg.get("events_lookbehind_days", 30)
        ahead = cfg.get("events_lookahead_days", 60)
        now = datetime.now(timezone.utc)
        return (
            now - timedelta(days=behind),
            now + timedelta(days=ahead),
        )

    # ── Actions ─────────────────────────────────────────────────────────

    def action_view_monthly(self) -> None:
        self._set_view("monthly")

    def action_view_weekly(self) -> None:
        self._set_view("weekly")

    def action_view_daily(self) -> None:
        self._open_daily_modal()

    def action_view_agenda(self) -> None:
        self._set_view("agenda")

    def _sync_date(self) -> None:
        """Called on keyboard navigation. Uses per-view fast path where possible."""
        self._update_selection()
        self._update_status_bar()

    def _update_selection(self) -> None:
        """Update selected date without a full data-driven rebuild.

        Monthly: toggle CSS class on existing DayCells (no remount unless month changes).
        Weekly:  update day-header highlights (no remount unless week changes).
        Agenda: full update needed since displayed content changes per day.
        """
        if self._view_name == "monthly":
            self.query_one("#monthly", MonthlyView).set_selected_date(self._current_date)
        elif self._view_name == "weekly":
            self.query_one("#weekly", WeeklyView).set_selected_date(self._current_date)
        elif self._view_name == "agenda":
            self.query_one("#agenda", AgendaView).update(
                self._events, self._tasks, self._calendars, self._current_date
            )

    def action_nav_prev(self) -> None:
        self._current_date -= timedelta(days=1)
        self._sync_date()

    def action_nav_next(self) -> None:
        self._current_date += timedelta(days=1)
        self._sync_date()

    def action_nav_up(self) -> None:
        if self._view_name == "agenda":
            self.query_one("#agenda", AgendaView).move_selection(-1)
        else:
            self._current_date -= timedelta(weeks=1)
            self._sync_date()

    def action_nav_down(self) -> None:
        if self._view_name == "agenda":
            self.query_one("#agenda", AgendaView).move_selection(1)
        else:
            self._current_date += timedelta(weeks=1)
            self._sync_date()

    def action_nav_prev_period(self) -> None:
        """[ — jump back one month (monthly view) or one week (others)."""
        if self._view_name == "monthly":
            m = self._current_date.month - 1
            y = self._current_date.year
            if m < 1:
                m, y = 12, y - 1
            max_day = cal_mod.monthrange(y, m)[1]
            self._current_date = date(y, m, min(self._current_date.day, max_day))
        else:
            self._current_date -= timedelta(weeks=1)
        self._sync_date()

    def action_nav_next_period(self) -> None:
        """] — jump forward one month (monthly view) or one week (others)."""
        if self._view_name == "monthly":
            m = self._current_date.month + 1
            y = self._current_date.year
            if m > 12:
                m, y = 1, y + 1
            max_day = cal_mod.monthrange(y, m)[1]
            self._current_date = date(y, m, min(self._current_date.day, max_day))
        else:
            self._current_date += timedelta(weeks=1)
        self._sync_date()

    def action_go_today(self) -> None:
        self._current_date = date.today()
        self._update_active_view()
        self._update_status_bar()

    def action_new_event(self) -> None:
        if not self._calendars:
            self.notify("No calendars loaded yet. Wait for sync.", severity="warning")
            return
        self.push_screen(
            EventFormModal(None, self._calendars),
            callback=self._on_event_form_result,
        )

    def action_edit_event(self) -> None:
        ev = self._selected_event
        if ev is None:
            if self._view_name == "agenda":
                ev = self.query_one("#agenda", AgendaView).get_selected_event()
        if ev is None and self._view_name in ("monthly", "weekly"):
            self._pending_panel_action = "edit"
            self._open_daily_modal()
            return
        if ev is None:
            self.notify("No event selected.", severity="warning")
            return
        self.push_screen(
            EventFormModal(ev, self._calendars),
            callback=self._on_event_form_result,
        )

    def action_delete_event(self) -> None:
        ev = self._selected_event
        if ev is None:
            if self._view_name == "agenda":
                ev = self.query_one("#agenda", AgendaView).get_selected_event()
        if ev is None and self._view_name in ("monthly", "weekly"):
            self._pending_panel_action = "delete"
            self._open_daily_modal()
            return
        if ev is None:
            self.notify("No event selected.", severity="warning")
            return
        self.push_screen(
            DeleteConfirmModal(ev.summary),
            callback=lambda confirmed: self._on_delete_confirmed(confirmed, ev),  # type: ignore[arg-type]
        )

    def action_open_event(self) -> None:
        # Monthly / weekly: Enter opens a floating day view for the selected date.
        if self._view_name in ("monthly", "weekly"):
            self._open_daily_modal()
            return
        if self._selected_event:
            # Toggle panel closed
            panel = self.query_one("#event-panel", EventPanel)
            if "visible" in panel.classes:
                self._close_panel()
            return
        # Try agenda selection
        if self._view_name == "agenda":
            ev = self.query_one("#agenda", AgendaView).get_selected_event()
            if ev:
                self._select_event(ev)

    def action_close_panel(self) -> None:
        self._close_panel()

    def action_search(self) -> None:
        cal_ids = [c.id for c in self._calendars if c.selected]
        self.push_screen(
            SearchModal(self._cal_api, cal_ids),
            callback=self._on_search_result,
        )

    def action_refresh(self) -> None:
        self.notify("Refreshing…", timeout=2)
        self.load_data(force=True)

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_jump_date(self) -> None:
        self.push_screen(DateJumpModal(self._current_date), callback=self._on_date_jump_result)

    def _open_daily_modal(self) -> None:
        self.push_screen(
            DailyModal(self._events, self._tasks, self._calendars, self._current_date),
            callback=self._on_daily_modal_result,
        )

    # ── Message handlers ────────────────────────────────────────────────

    def on_date_selected(self, msg: DateSelected) -> None:
        self._current_date = msg.date_
        self._update_active_view()
        self._update_status_bar()

    def on_event_selected(self, msg: EventSelected) -> None:
        if msg.event:
            self._select_event(msg.event)

    def on_edit_requested(self, msg: EditRequested) -> None:
        self.push_screen(
            EventFormModal(msg.event, self._calendars),
            callback=self._on_event_form_result,
        )

    def on_delete_requested(self, msg: DeleteRequested) -> None:
        ev = msg.event
        self.push_screen(
            DeleteConfirmModal(ev.summary),
            callback=lambda confirmed: self._on_delete_confirmed(confirmed, ev),  # type: ignore[arg-type]
        )

    # ── Screen callbacks ────────────────────────────────────────────────

    def _on_event_form_result(self, body: dict | None) -> None:
        if body is None:
            return
        cal_id = body.pop("_calendar_id", None)
        event_id = body.pop("_event_id", None)

        if event_id:
            self._do_patch_event(cal_id or "", event_id, body)
        else:
            self._do_insert_event(cal_id or "", body)

    def _on_delete_confirmed(self, confirmed: bool, event: CalEvent) -> None:
        if confirmed:
            self._do_delete_event(event)

    def _on_search_result(self, event: CalEvent | None) -> None:
        if event:
            self._current_date = event.start_date()
            self._select_event(event)

    def _on_daily_modal_result(self, event: CalEvent | None) -> None:
        if event:
            self._select_event(event)
            action = self._pending_panel_action
            self._pending_panel_action = None
            if action == "edit":
                self.push_screen(
                    EventFormModal(event, self._calendars),
                    callback=self._on_event_form_result,
                )
            elif action == "delete":
                self.push_screen(
                    DeleteConfirmModal(event.summary),
                    callback=lambda confirmed: self._on_delete_confirmed(confirmed, event),
                )
        else:
            self._pending_panel_action = None

    def _on_date_jump_result(self, target: date | None) -> None:
        if target is None:
            return
        self._current_date = target
        self._update_active_view()
        self._update_status_bar()

    # ── API mutations (background) ──────────────────────────────────────

    @work(thread=True)
    def _do_insert_event(self, calendar_id: str, body: dict) -> None:
        try:
            ev = self._cal_api.insert_event(calendar_id, body)
            self.call_from_thread(self._on_event_created, ev)
        except CalendarAPIError as exc:
            self.call_from_thread(
                self.notify, f"Failed to create event: {exc}", severity="error"
            )

    @work(thread=True)
    def _do_patch_event(self, calendar_id: str, event_id: str, body: dict) -> None:
        try:
            ev = self._cal_api.patch_event(calendar_id, event_id, body)
            self.call_from_thread(self._on_event_updated, ev)
        except CalendarAPIError as exc:
            self.call_from_thread(
                self.notify, f"Failed to update event: {exc}", severity="error"
            )

    @work(thread=True)
    def _do_delete_event(self, event: CalEvent) -> None:
        try:
            self._cal_api.delete_event(event.calendar_id, event.id)
            self.call_from_thread(self._on_event_deleted, event.id)
        except CalendarAPIError as exc:
            self.call_from_thread(
                self.notify, f"Failed to delete event: {exc}", severity="error"
            )

    def _on_event_created(self, event: CalEvent) -> None:
        self._events.append(event)
        self._events.sort(key=lambda e: e.start_dt())
        self._update_active_view()
        self.notify(f"Created: {event.summary}", timeout=3)

    def _on_event_updated(self, event: CalEvent) -> None:
        self._events = [e for e in self._events if e.id != event.id]
        self._events.append(event)
        self._events.sort(key=lambda e: e.start_dt())
        if self._selected_event and self._selected_event.id == event.id:
            self._selected_event = event
            self.query_one("#event-panel", EventPanel).current_event = event
        self._update_active_view()
        self.notify(f"Updated: {event.summary}", timeout=3)

    def _on_event_deleted(self, event_id: str) -> None:
        self._events = [e for e in self._events if e.id != event_id]
        if self._selected_event and self._selected_event.id == event_id:
            self._close_panel()
        self._update_active_view()
        self.notify("Event deleted.", timeout=3)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _select_event(self, event: CalEvent) -> None:
        self._selected_event = event
        panel = self.query_one("#event-panel", EventPanel)
        panel.current_event = event
        panel.add_class("visible")

    def _close_panel(self) -> None:
        self._selected_event = None
        panel = self.query_one("#event-panel", EventPanel)
        panel.current_event = None
        panel.remove_class("visible")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self._is_loading = False
            self._update_status_bar()
            err = str(event.worker.error) if event.worker.error else "Unknown error"
            self.notify(f"Error: {err}", severity="error", timeout=8)
