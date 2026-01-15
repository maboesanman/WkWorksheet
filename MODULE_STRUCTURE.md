# WkWorksheet Module Structure

## Overview

This document describes the new modular architecture for the WkWorksheet project.

## Directory Structure

```
WkWorksheet/
├── wkworksheet/              # Main Python package
│   ├── __init__.py
│   ├── config.py             # Configuration and paths
│   └── wanikani_cache.py     # WaniKani API caching layer
├── cache/                    # Cached API data (gitignored)
│   └── wanikani_cache.json   # All WaniKani subjects/assignments
├── working/                  # Temporary build files
├── out/                      # Generated PDFs
├── generate_daily_kanji.py   # [LEGACY] Original script
├── generate_final_pdf.py     # [LEGACY] Original script
└── example_cache_usage.py    # Example of using the cache
```

## Modules

### `wkworksheet/config.py`

Central configuration for the entire project:

- **API settings**: WaniKani API token (from env or hardcoded), API URL
- **Paths**: Root, cache, working, output directories
- **Cache settings**: Cache file location, rate limiting

Environment variable support:
- `WANIKANI_API_TOKEN`: Override the default API token

### `wkworksheet/wanikani_cache.py`

Aggressive caching layer for WaniKani API data.

**Key Features:**
- **Idempotent**: Calling `fetch_subjects()` multiple times only fetches updates
- **Incremental updates**: Uses `updated_after` parameter to minimize API calls
- **Sorted output**: Subjects are sorted by ID for deterministic cache files
- **Rate limiting**: Built-in delays to respect API limits

**Classes:**

#### `WaniKaniCache`

Main cache management class.

**Methods:**

- `fetch_subjects(force=False)`: Fetch all subjects, using incremental updates
  - Returns: List of all subject data
  - `force=True`: Forces a full refresh instead of incremental

- `get_subjects(subject_type=None)`: Get subjects from cache
  - `subject_type`: Optional filter ("kanji", "radical", "vocabulary")
  - Returns: Filtered list of subjects

- `get_subject_by_id(subject_id)`: Look up a single subject by ID
  - Returns: Subject data or None

**Functions:**

- `ensure_subjects_cached()`: Convenience function that creates cache and fetches subjects

## Cache Format

The cache file (`cache/wanikani_cache.json`) has this structure:

```json
{
  "subjects": {
    "data": [ /* array of subject objects */ ],
    "last_updated": "2026-01-15T00:13:51.240927+00:00"
  },
  "assignments": {
    "data": [],
    "last_updated": null
  },
  "user": {
    "data": null,
    "last_updated": null
  }
}
```

Each section tracks:
- **data**: The actual API response objects
- **last_updated**: ISO timestamp for incremental updates

## Usage Examples

### Basic Usage

```python
from wkworksheet.wanikani_cache import WaniKaniCache

# Initialize and fetch
cache = WaniKaniCache()
cache.fetch_subjects()  # Only fetches new/updated subjects

# Get all kanji
kanji = cache.get_subjects("kanji")
print(f"Total kanji: {len(kanji)}")

# Get a specific subject
subject = cache.get_subject_by_id(440)
if subject:
    print(subject["data"]["characters"])
```

### Filtering by Level

```python
from wkworksheet.wanikani_cache import WaniKaniCache

cache = WaniKaniCache()
cache.fetch_subjects()

# Get all level 5 kanji
level_5_kanji = [
    s for s in cache.get_subjects("kanji")
    if s["data"]["level"] == 5
]
```

### Command Line Testing

```bash
# Fetch and cache all subjects
python3 -m wkworksheet.wanikani_cache

# Run the example script
python3 example_cache_usage.py
```

## Current Stats (as of testing)

- **Total subjects**: 9,331
  - Kanji: 2,087
  - Radicals: 499
  - Vocabulary: 6,685
- **Cache file size**: ~35MB

## Idempotency Guarantee

The caching system is designed to be **idempotent except for the `last_updated` timestamp**:

1. First run: Fetches all subjects from API
2. Subsequent runs: Only fetches subjects modified since last update
3. If no updates: Cache file is rewritten with new timestamp but same data
4. Subjects are always sorted by ID for deterministic output

## Future Enhancements

Planned additions to `wanikani_cache.py`:

- [ ] `fetch_assignments()`: Cache user assignment data
- [ ] `fetch_user()`: Cache user profile data
- [ ] `fetch_reviews()`: Cache review data
- [ ] `fetch_review_statistics()`: Cache review statistics
- [ ] Better error handling and retry logic
- [ ] Progress indicators for large fetches
- [ ] Cache validation and repair
