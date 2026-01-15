#!/usr/bin/env python3
"""Example of using the WaniKani cache."""

from wkworksheet.wanikani_cache import WaniKaniCache

# Initialize cache and fetch/update subjects
cache = WaniKaniCache()
cache.fetch_subjects()  # Idempotent: only fetches updates

# Get all kanji
kanji_subjects = cache.get_subjects("kanji")
print(f"Total kanji in WaniKani: {len(kanji_subjects)}")

# Get a specific subject by ID
subject = cache.get_subject_by_id(440)
if subject:
    data = subject["data"]
    print(f"\nExample kanji: {data['characters']}")
    print(f"  Level: {data['level']}")
    print(f"  Meanings: {[m['meaning'] for m in data['meanings'] if m['primary']]}")
    print(f"  Readings: {[r['reading'] for r in data['readings'] if r['primary']]}")

# Show all level 1 kanji
level_1_kanji = [
    s for s in kanji_subjects
    if s["data"]["level"] == 1
]
print(f"\nLevel 1 kanji ({len(level_1_kanji)} total):")
for s in level_1_kanji[:5]:  # Show first 5
    data = s["data"]
    print(f"  {data['characters']} - {', '.join(m['meaning'] for m in data['meanings'] if m['primary'])}")
