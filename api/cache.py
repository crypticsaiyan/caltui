"""Disk cache for calendar/task data with TTL."""
from __future__ import annotations
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from models import CalEvent, GCalendar, Task, TaskList

CACHE_DIR = Path.home() / ".cache" / "caltui"
CACHE_FILE = CACHE_DIR / "cache.json"


# ── Serialization ────────────────────────────────────────────────────────────

def _ser_event(ev: CalEvent) -> dict:
    return {
        "id": ev.id,
        "summary": ev.summary,
        "start": ev.start.isoformat(),
        "end": ev.end.isoformat(),
        "calendar_id": ev.calendar_id,
        "color_id": ev.color_id,
        "location": ev.location,
        "description": ev.description,
        "attendees": ev.attendees,
        "is_recurring": ev.is_recurring,
        "is_all_day": ev.is_all_day,
        "html_link": ev.html_link,
    }


def _de_event(d: dict) -> CalEvent:
    is_all_day: bool = d.get("is_all_day", False)
    if is_all_day:
        start: datetime | date = date.fromisoformat(d["start"][:10])
        end: datetime | date = date.fromisoformat(d["end"][:10])
    else:
        start = datetime.fromisoformat(d["start"])
        end = datetime.fromisoformat(d["end"])
    return CalEvent(
        id=d["id"],
        summary=d["summary"],
        start=start,
        end=end,
        calendar_id=d["calendar_id"],
        color_id=d.get("color_id"),
        location=d.get("location"),
        description=d.get("description"),
        attendees=d.get("attendees", []),
        is_recurring=d.get("is_recurring", False),
        is_all_day=is_all_day,
        html_link=d.get("html_link"),
    )


def _ser_calendar(c: GCalendar) -> dict:
    return {
        "id": c.id,
        "summary": c.summary,
        "color_id": c.color_id,
        "primary": c.primary,
        "selected": c.selected,
        "access_role": c.access_role,
        "time_zone": c.time_zone,
    }


def _de_calendar(d: dict) -> GCalendar:
    return GCalendar(
        id=d["id"],
        summary=d["summary"],
        color_id=d.get("color_id", "9"),
        primary=d.get("primary", False),
        selected=d.get("selected", True),
        access_role=d.get("access_role", "reader"),
        time_zone=d.get("time_zone", ""),
    )


def _ser_task(t: Task) -> dict:
    return {
        "id": t.id,
        "task_list_id": t.task_list_id,
        "title": t.title,
        "due": t.due.isoformat() if t.due else None,
        "notes": t.notes,
        "completed": t.completed,
    }


def _de_task(d: dict) -> Task:
    return Task(
        id=d["id"],
        task_list_id=d["task_list_id"],
        title=d["title"],
        due=date.fromisoformat(d["due"]) if d.get("due") else None,
        notes=d.get("notes"),
        completed=d.get("completed", False),
    )


def _ser_task_list(tl: TaskList) -> dict:
    return {"id": tl.id, "title": tl.title}


def _de_task_list(d: dict) -> TaskList:
    return TaskList(id=d["id"], title=d["title"])


# ── Public API ────────────────────────────────────────────────────────────────

class CacheEntry:
    def __init__(
        self,
        fetched_at: datetime,
        time_min: datetime,
        time_max: datetime,
        calendars: list[GCalendar],
        events: list[CalEvent],
        tasks: list[Task],
        task_lists: list[TaskList],
    ) -> None:
        self.fetched_at = fetched_at
        self.time_min = time_min
        self.time_max = time_max
        self.calendars = calendars
        self.events = events
        self.tasks = tasks
        self.task_lists = task_lists

    def age_seconds(self) -> float:
        now = datetime.now(timezone.utc)
        fa = self.fetched_at
        if fa.tzinfo is None:
            fa = fa.replace(tzinfo=timezone.utc)
        return (now - fa).total_seconds()

    def covers_window(self, time_min: datetime, time_max: datetime) -> bool:
        """Return True if this cache covers at least the requested window."""
        c_min = self.time_min
        c_max = self.time_max
        if c_min.tzinfo is None:
            c_min = c_min.replace(tzinfo=timezone.utc)
        if c_max.tzinfo is None:
            c_max = c_max.replace(tzinfo=timezone.utc)
        if time_min.tzinfo is None:
            time_min = time_min.replace(tzinfo=timezone.utc)
        if time_max.tzinfo is None:
            time_max = time_max.replace(tzinfo=timezone.utc)
        return c_min <= time_min and c_max >= time_max


def load() -> CacheEntry | None:
    """Load cache from disk. Returns None if missing or corrupt."""
    try:
        raw = json.loads(CACHE_FILE.read_text())
        return CacheEntry(
            fetched_at=datetime.fromisoformat(raw["fetched_at"]),
            time_min=datetime.fromisoformat(raw["time_min"]),
            time_max=datetime.fromisoformat(raw["time_max"]),
            calendars=[_de_calendar(c) for c in raw.get("calendars", [])],
            events=[_de_event(e) for e in raw.get("events", [])],
            tasks=[_de_task(t) for t in raw.get("tasks", [])],
            task_lists=[_de_task_list(tl) for tl in raw.get("task_lists", [])],
        )
    except Exception:
        return None


def save(
    time_min: datetime,
    time_max: datetime,
    calendars: list[GCalendar],
    events: list[CalEvent],
    tasks: list[Task],
    task_lists: list[TaskList],
) -> None:
    """Write cache to disk. Silently ignores write errors."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "time_min": time_min.isoformat(),
            "time_max": time_max.isoformat(),
            "calendars": [_ser_calendar(c) for c in calendars],
            "events": [_ser_event(e) for e in events],
            "tasks": [_ser_task(t) for t in tasks],
            "task_lists": [_ser_task_list(tl) for tl in task_lists],
        }
        CACHE_FILE.write_text(json.dumps(payload))
    except Exception:
        pass


def clear() -> None:
    try:
        CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass
