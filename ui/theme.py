from __future__ import annotations

GOOGLE_COLOR_ID_TO_HEX: dict[str, str] = {
    "1":  "#7986cb",  # lavender
    "2":  "#33b679",  # sage
    "3":  "#8e24aa",  # grape
    "4":  "#e67c73",  # flamingo
    "5":  "#f6bf26",  # banana
    "6":  "#f4511e",  # tangerine
    "7":  "#039be5",  # peacock
    "8":  "#616161",  # graphite
    "9":  "#3f51b5",  # blueberry
    "10": "#0b8043",  # basil
    "11": "#d50000",  # tomato
}

GOOGLE_COLOR_NAME_TO_ID: dict[str, str] = {
    "lavender":  "1",
    "sage":      "2",
    "grape":     "3",
    "flamingo":  "4",
    "banana":    "5",
    "tangerine": "6",
    "peacock":   "7",
    "graphite":  "8",
    "blueberry": "9",
    "basil":     "10",
    "tomato":    "11",
}

GOOGLE_COLOR_NAMES: list[str] = list(GOOGLE_COLOR_NAME_TO_ID.keys())

DEFAULT_EVENT_COLOR    = "#4a90d9"
DEFAULT_TASK_COLOR     = "#26a69a"
DEFAULT_CALENDAR_COLOR = "#3f51b5"


def color_for_event(event, calendar=None) -> str:
    if event.color_id:
        if event.color_id in GOOGLE_COLOR_ID_TO_HEX:
            return GOOGLE_COLOR_ID_TO_HEX[event.color_id]
        # Google sometimes returns background colors not in our map; try calendar
    if calendar and calendar.color_id in GOOGLE_COLOR_ID_TO_HEX:
        return GOOGLE_COLOR_ID_TO_HEX[calendar.color_id]
    return DEFAULT_EVENT_COLOR


def color_for_calendar(calendar) -> str:
    if calendar and calendar.color_id in GOOGLE_COLOR_ID_TO_HEX:
        return GOOGLE_COLOR_ID_TO_HEX[calendar.color_id]
    return DEFAULT_CALENDAR_COLOR


def contrasting_text(bg_hex: str) -> str:
    """Return #000000 or #ffffff for readable text on bg_hex."""
    h = bg_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"
