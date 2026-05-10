from __future__ import annotations
import sys
import tomllib
from pathlib import Path


def main() -> None:
    config = _load_config()

    credentials_file = Path(config.get("auth", {}).get("credentials_file", "credentials.json"))
    if not credentials_file.is_absolute():
        credentials_file = Path(__file__).parent / credentials_file

    # Auth must complete before the TUI starts (blocking is intentional here)
    try:
        from auth.oauth import get_credentials
        creds = get_credentials(credentials_file)
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("\nTo set up authentication:", file=sys.stderr)
        print("  1. Go to https://console.cloud.google.com/", file=sys.stderr)
        print("  2. Create OAuth 2.0 credentials (Desktop application)", file=sys.stderr)
        print("  3. Download as credentials.json to this directory", file=sys.stderr)
        print("  4. Enable Calendar API and Tasks API in your project", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\nAuthentication failed: {exc}", file=sys.stderr)
        sys.exit(1)

    from api.calendar import CalendarAPI
    from api.tasks import TasksAPI
    from ui.app import CalTuiApp

    cal_api = CalendarAPI(creds)
    tasks_api = TasksAPI(creds)

    app = CalTuiApp(cal_api=cal_api, tasks_api=tasks_api, config=config)
    app.run()


def _load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "settings.toml"
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass
    return {}


if __name__ == "__main__":
    main()
