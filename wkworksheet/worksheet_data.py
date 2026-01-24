"""Generate worksheet data by orchestrating cache updates and kanji selection."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import KANJI_LEDGER_PATH, TEMPLATE_PATH
from .wanikani_cache import WaniKaniCache
from .kanji_debt import generate_kanji_selection_report
from .layout import compute_all_rolling_windows, assign_pages
from .latex_snippets import LATEX_LENGTHS, make_user_variables


# Japanese day of week names
JAPANESE_WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日']


def format_japanese_date(dt: datetime) -> str:
    """
    Format a datetime as a Japanese date string with full-width digits.

    Args:
        dt: datetime object to format

    Returns:
        String like "２０２５年１０月２０日（火）"
    """
    # Convert to full-width digits
    year = str(dt.year).translate(str.maketrans('0123456789', '０１２３４５６７８９'))
    month = str(dt.month).translate(str.maketrans('0123456789', '０１２３４５６７８９'))
    day = str(dt.day).translate(str.maketrans('0123456789', '０１２３４５６７８９'))
    weekday = JAPANESE_WEEKDAYS[dt.weekday()]

    return f"{year}年{month}月{day}日（{weekday}）"


def generate_worksheet_data() -> dict:
    """
    Generate complete worksheet data by orchestrating all data sources.

    Updates the WaniKani cache, runs kanji debt selection, and produces
    a unified JSON structure for worksheet generation.

    Returns:
        dict with structure:
        {
            "user": {
                "username": str,
                "level": int
            },
            "date": {
                "datetime": ISO timestamp,
                "formatted": Japanese date string
            },
            "pages": [
                {
                    "kanji": {
                        "groups": [...],
                        "required_legend_columns": int
                    }
                }
            ]
        }
    """
    # Initialize and update cache
    cache = WaniKaniCache()
    cache.fetch_subjects()
    cache.fetch_assignments()
    cache.fetch_user()

    # Get user info
    user_data = cache.get_user()
    user_info = {
        "username": user_data["data"]["username"],
        "level": user_data["data"]["level"]
    }

    # Get the canonical update time from cache
    update_time = cache.get_last_updated()

    # Convert to Chicago timezone for display
    chicago_tz = ZoneInfo("America/Chicago")
    chicago_time = update_time.astimezone(chicago_tz)

    date_info = {
        "datetime": update_time.isoformat(),
        "formatted": format_japanese_date(chicago_time)
    }

    # Generate kanji selection
    kanji_report = generate_kanji_selection_report(cache, KANJI_LEDGER_PATH)

    print(kanji_report)

    # Build LaTeX variables and template for layout computation
    variables = LATEX_LENGTHS + "\n" + make_user_variables(user_info['level'], user_info['username'])

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    rolling_windows = compute_all_rolling_windows(variables, template, kanji_report["groups"])

    print(rolling_windows)

    # Assign kanji to pages using greedy algorithm
    pages = assign_pages(kanji_report["groups"], rolling_windows)

    return {
        "user": user_info,
        "date": date_info,
        "pages": pages
    }


if __name__ == "__main__":
    data = generate_worksheet_data()
    print(json.dumps(data, indent=2, ensure_ascii=False))
