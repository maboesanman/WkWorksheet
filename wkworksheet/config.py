"""Configuration for WkWorksheet."""
import os
from pathlib import Path

# API Configuration
API_TOKEN = os.environ.get("WANIKANI_API_TOKEN", "bd2b206a-665c-4b50-b365-2416e5e5da1f")
API_URL = "https://api.wanikani.com/v2"

# Directory paths
ROOT_DIR = Path(__file__).parent.parent
CACHE_DIR = ROOT_DIR / "cache"
WORKING_DIR = ROOT_DIR / "working"
OUT_DIR = ROOT_DIR / "out"
BOOKKEEPING_DIR = OUT_DIR / "bookkeeping"
TEMPLATE_PATH = ROOT_DIR / "template.tex"

# Kanji ledger path
KANJI_LEDGER_PATH = BOOKKEEPING_DIR / "kanji_ledger.json"

# Cache settings
CACHE_FILE = CACHE_DIR / "wanikani_cache.json"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BOOKKEEPING_DIR.mkdir(parents=True, exist_ok=True)

# API rate limiting
RATE_LIMIT_DELAY = 0.1  # seconds between requests (conservative to avoid hitting limits)
