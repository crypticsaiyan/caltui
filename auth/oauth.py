from __future__ import annotations
import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

CONFIG_DIR = Path.home() / ".config" / "caltui"
TOKEN_PATH = CONFIG_DIR / "token.json"


def get_credentials(credentials_file: Path) -> Credentials:
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {credentials_file}\n"
            "Download it from: Google Cloud Console > APIs & Services > Credentials"
        )

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    creds = _load_cached_token()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception:
            pass  # fall through to re-auth

    creds = _run_flow(credentials_file)
    _save_token(creds)
    return creds


def _load_cached_token() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    try:
        with open(TOKEN_PATH) as f:
            data = json.load(f)
        return Credentials.from_authorized_user_info(data, SCOPES)
    except Exception:
        return None


def _save_token(creds: Credentials) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        f.write(creds.to_json())
    tmp.rename(TOKEN_PATH)
    os.chmod(TOKEN_PATH, 0o600)


def _run_flow(credentials_file: Path) -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    for port in (8080, 8081, 8082, 8083):
        try:
            return flow.run_local_server(port=port, open_browser=True)
        except OSError:
            continue
    raise RuntimeError(
        "Could not bind OAuth callback port (tried 8080–8083). "
        "Free one of those ports and try again."
    )


def refresh_if_expired(creds: Credentials) -> Credentials:
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
    return creds
