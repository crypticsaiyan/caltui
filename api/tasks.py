from __future__ import annotations
import time
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from models import Task, TaskList, task_from_api_dict, task_list_from_api_dict


class TasksAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TasksAPI:
    def __init__(self, creds: Credentials) -> None:
        self._creds = creds
        self._svc = None

    def _service(self):
        if self._svc is None:
            self._svc = build("tasks", "v1", credentials=self._creds)
        return self._svc

    def _retry(self, request, max_attempts: int = 5) -> dict:
        for attempt in range(max_attempts):
            try:
                return request.execute()
            except HttpError as exc:
                if exc.resp.status in (429, 500, 503) and attempt < max_attempts - 1:
                    time.sleep(min(2**attempt, 32))
                    continue
                raise TasksAPIError(str(exc), exc.resp.status) from exc
            except Exception as exc:
                raise TasksAPIError(str(exc)) from exc
        raise TasksAPIError("Max retry attempts exceeded")

    def list_task_lists(self) -> list[TaskList]:
        results: list[TaskList] = []
        page_token = None
        svc = self._service()
        while True:
            req = svc.tasklists().list(maxResults=100, pageToken=page_token)
            resp = self._retry(req)
            results.extend(task_list_from_api_dict(item) for item in resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def list_tasks(
        self,
        task_list_id: str,
        show_completed: bool = False,
        due_min: datetime | None = None,
        due_max: datetime | None = None,
    ) -> list[Task]:
        results: list[Task] = []
        page_token = None
        svc = self._service()
        while True:
            kwargs: dict = dict(
                tasklist=task_list_id,
                showCompleted=show_completed,
                showHidden=show_completed,
                maxResults=100,
                pageToken=page_token,
            )
            if due_min:
                kwargs["dueMin"] = _rfc3339(due_min)
            if due_max:
                kwargs["dueMax"] = _rfc3339(due_max)
            req = svc.tasks().list(**{k: v for k, v in kwargs.items() if v is not None})
            resp = self._retry(req)
            results.extend(task_from_api_dict(item, task_list_id) for item in resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def complete_task(self, task_list_id: str, task_id: str) -> Task:
        req = self._service().tasks().patch(
            tasklist=task_list_id,
            task=task_id,
            body={"status": "completed"},
        )
        return task_from_api_dict(self._retry(req), task_list_id)

    def delete_task(self, task_list_id: str, task_id: str) -> None:
        req = self._service().tasks().delete(tasklist=task_list_id, task=task_id)
        self._retry(req)


def _rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
