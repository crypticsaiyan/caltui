from __future__ import annotations
import time
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from models import CalEvent, GCalendar, event_from_api_dict, calendar_from_api_dict


class CalendarAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CalendarAPI:
    def __init__(self, creds: Credentials) -> None:
        self._creds = creds
        self._svc = None

    def _service(self):
        if self._svc is None:
            self._svc = build("calendar", "v3", credentials=self._creds)
        return self._svc

    def _retry(self, request, max_attempts: int = 5) -> dict:
        for attempt in range(max_attempts):
            try:
                return request.execute()
            except HttpError as exc:
                if exc.resp.status in (429, 500, 503) and attempt < max_attempts - 1:
                    time.sleep(_backoff(attempt))
                    continue
                raise CalendarAPIError(str(exc), exc.resp.status) from exc
            except Exception as exc:
                raise CalendarAPIError(str(exc)) from exc
        raise CalendarAPIError("Max retry attempts exceeded")

    # ── Calendars ──────────────────────────────────────────────────────

    def list_calendars(self) -> list[GCalendar]:
        results: list[GCalendar] = []
        page_token = None
        svc = self._service()
        while True:
            req = svc.calendarList().list(showHidden=False, pageToken=page_token)
            resp = self._retry(req)
            results.extend(calendar_from_api_dict(item) for item in resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    # ── Events ─────────────────────────────────────────────────────────

    def list_events(
        self,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        query: str | None = None,
        max_results: int | None = None,
    ) -> list[CalEvent]:
        results: list[CalEvent] = []
        page_token = None
        svc = self._service()
        while True:
            req = svc.events().list(
                calendarId=calendar_id,
                timeMin=_rfc3339(time_min),
                timeMax=_rfc3339(time_max),
                singleEvents=True,
                orderBy="startTime",
                q=query,
                maxResults=2500,
                pageToken=page_token,
            )
            resp = self._retry(req)
            results.extend(event_from_api_dict(item, calendar_id) for item in resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
            if max_results is not None and len(results) >= max_results:
                break
        return results if max_results is None else results[:max_results]

    def get_event(self, calendar_id: str, event_id: str) -> CalEvent:
        req = self._service().events().get(calendarId=calendar_id, eventId=event_id)
        return event_from_api_dict(self._retry(req), calendar_id)

    def insert_event(self, calendar_id: str, body: dict) -> CalEvent:
        req = self._service().events().insert(calendarId=calendar_id, body=body)
        return event_from_api_dict(self._retry(req), calendar_id)

    def patch_event(self, calendar_id: str, event_id: str, body: dict) -> CalEvent:
        req = self._service().events().patch(
            calendarId=calendar_id, eventId=event_id, body=body
        )
        return event_from_api_dict(self._retry(req), calendar_id)

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        req = self._service().events().delete(calendarId=calendar_id, eventId=event_id)
        self._retry(req)

    def search_events(
        self,
        query: str,
        time_min: datetime,
        time_max: datetime,
        calendar_ids: list[str] | None = None,
        max_per_calendar: int = 50,
    ) -> list[CalEvent]:
        if not calendar_ids:
            cals = self.list_calendars()
            calendar_ids = [c.id for c in cals if c.selected]

        all_events: list[CalEvent] = []
        for cal_id in calendar_ids:
            try:
                events = self.list_events(
                    cal_id, time_min, time_max, query=query, max_results=max_per_calendar
                )
                all_events.extend(events)
            except CalendarAPIError:
                pass

        all_events.sort(key=lambda e: e.start_dt())
        return all_events


def _rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _backoff(attempt: int) -> float:
    return min(2**attempt, 32)
