from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date, timezone


@dataclass
class CalEvent:
    id: str
    summary: str
    start: datetime | date
    end: datetime | date
    calendar_id: str
    color_id: str | None = None
    location: str | None = None
    description: str | None = None
    attendees: list[str] = field(default_factory=list)
    is_recurring: bool = False
    is_all_day: bool = False
    html_link: str | None = None

    def start_dt(self) -> datetime:
        """Return start as datetime (midnight UTC for all-day events)."""
        if isinstance(self.start, datetime):
            return self.start
        return datetime(self.start.year, self.start.month, self.start.day, tzinfo=timezone.utc)

    def end_dt(self) -> datetime:
        if isinstance(self.end, datetime):
            return self.end
        return datetime(self.end.year, self.end.month, self.end.day, tzinfo=timezone.utc)

    def start_date(self) -> date:
        if isinstance(self.start, datetime):
            return self.start.date()
        return self.start

    def end_date(self) -> date:
        if isinstance(self.end, datetime):
            return self.end.date()
        return self.end

    def format_time(self) -> str:
        if self.is_all_day:
            return "all day"
        if isinstance(self.start, datetime) and isinstance(self.end, datetime):
            return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"
        return ""

    def duration_minutes(self) -> int:
        if self.is_all_day:
            return 0
        s = self.start_dt()
        e = self.end_dt()
        return max(30, int((e - s).total_seconds() / 60))


@dataclass
class GCalendar:
    id: str
    summary: str
    color_id: str = "9"
    primary: bool = False
    selected: bool = True
    access_role: str = "reader"
    time_zone: str = ""

    @property
    def writable(self) -> bool:
        return self.access_role in ("owner", "writer")


@dataclass
class Task:
    id: str
    task_list_id: str
    title: str
    due: date | None = None
    notes: str | None = None
    completed: bool = False


@dataclass
class TaskList:
    id: str
    title: str


def event_from_api_dict(item: dict, cal_id: str) -> CalEvent:
    start_info = item.get("start", {})
    end_info = item.get("end", {})
    is_all_day = "date" in start_info and "dateTime" not in start_info

    if is_all_day:
        start: datetime | date = date.fromisoformat(start_info["date"])
        end: datetime | date = date.fromisoformat(end_info.get("date", start_info["date"]))
    else:
        raw_start = start_info.get("dateTime", "")
        raw_end = end_info.get("dateTime", "")
        try:
            start = datetime.fromisoformat(raw_start)
            end = datetime.fromisoformat(raw_end)
        except (ValueError, TypeError):
            now = datetime.now(timezone.utc)
            start = now
            end = now

    attendees = [
        a.get("displayName") or a.get("email", "")
        for a in item.get("attendees", [])
    ]
    attendees = [a for a in attendees if a]

    return CalEvent(
        id=item.get("id", ""),
        summary=item.get("summary", "(no title)"),
        start=start,
        end=end,
        calendar_id=cal_id,
        color_id=item.get("colorId"),
        location=item.get("location"),
        description=item.get("description"),
        attendees=attendees,
        is_recurring=bool(item.get("recurringEventId")),
        is_all_day=is_all_day,
        html_link=item.get("htmlLink"),
    )


def calendar_from_api_dict(item: dict) -> GCalendar:
    return GCalendar(
        id=item["id"],
        summary=item.get("summary", item.get("id", "Unknown")),
        color_id=item.get("colorId", "9"),
        primary=item.get("primary", False),
        selected=item.get("selected", True),
        access_role=item.get("accessRole", "reader"),
        time_zone=item.get("timeZone", ""),
    )


def task_from_api_dict(item: dict, task_list_id: str) -> Task:
    due_str = item.get("due", "")
    due = None
    if due_str:
        try:
            due = datetime.fromisoformat(due_str.rstrip("Z")).date()
        except (ValueError, AttributeError):
            pass
    return Task(
        id=item.get("id", ""),
        task_list_id=task_list_id,
        title=item.get("title", "(no title)"),
        due=due,
        notes=item.get("notes"),
        completed=item.get("status") == "completed",
    )


def task_list_from_api_dict(item: dict) -> TaskList:
    return TaskList(id=item["id"], title=item.get("title", "Tasks"))


def event_to_insert_body(
    summary: str,
    start: datetime | date,
    end: datetime | date,
    description: str = "",
    location: str = "",
    color_id: str | None = None,
    is_all_day: bool = False,
) -> dict:
    if is_all_day:
        s = start if isinstance(start, date) and not isinstance(start, datetime) else start.date()  # type: ignore[union-attr]
        e = end if isinstance(end, date) and not isinstance(end, datetime) else end.date()  # type: ignore[union-attr]
        body: dict = {
            "summary": summary,
            "start": {"date": s.isoformat()},
            "end": {"date": e.isoformat()},
        }
    else:
        s_dt = start if isinstance(start, datetime) else datetime(start.year, start.month, start.day, 9, 0)
        e_dt = end if isinstance(end, datetime) else datetime(end.year, end.month, end.day, 10, 0)
        body = {
            "summary": summary,
            "start": {"dateTime": s_dt.isoformat()},
            "end": {"dateTime": e_dt.isoformat()},
        }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if color_id:
        body["colorId"] = color_id
    return body


def event_to_patch_body(event: CalEvent) -> dict:
    return event_to_insert_body(
        summary=event.summary,
        start=event.start,
        end=event.end,
        description=event.description or "",
        location=event.location or "",
        color_id=event.color_id,
        is_all_day=event.is_all_day,
    )
