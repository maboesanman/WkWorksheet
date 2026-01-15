"""WaniKani API caching layer."""
import json
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import requests

from .config import API_TOKEN, API_URL, CACHE_FILE, RATE_LIMIT_DELAY


class WaniKaniCache:
    """Manages cached WaniKani API data with incremental updates."""

    def __init__(self, cache_path: Path = CACHE_FILE):
        self.cache_path = cache_path
        self.headers = {"Authorization": f"Bearer {API_TOKEN}"}
        self._cache_data: Optional[Dict[str, Any]] = None
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk if it exists."""
        if self.cache_path.exists():
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self._cache_data = json.load(f)
        else:
            self._cache_data = {
                "subjects": {
                    "data": [],
                    "last_updated": None
                },
                "assignments": {
                    "data": [],
                    "last_updated": None
                },
                "user": {
                    "data": None,
                    "last_updated": None
                }
            }

    def _save_cache(self) -> None:
        """Save cache to disk."""
        # Create a sorted version for stable output (idempotent except for timestamps)
        cache_copy = self._cache_data.copy()

        # Sort subjects by ID for deterministic ordering
        if "subjects" in cache_copy and "data" in cache_copy["subjects"]:
            cache_copy["subjects"]["data"] = sorted(
                cache_copy["subjects"]["data"],
                key=lambda x: x.get("id", 0)
            )

        # Sort assignments by ID for deterministic ordering
        if "assignments" in cache_copy and "data" in cache_copy["assignments"]:
            cache_copy["assignments"]["data"] = sorted(
                cache_copy["assignments"]["data"],
                key=lambda x: x.get("id", 0)
            )

        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_copy, f, indent=2, ensure_ascii=False, sort_keys=True)

    def _fetch_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all pages from a paginated endpoint."""
        results = []
        url = f"{API_URL}/{endpoint}"

        if params is None:
            params = {}

        while url:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            results.extend(data.get("data", []))
            url = data.get("pages", {}).get("next_url")

            # Only use params on first request (next_url already includes them)
            params = None
            time.sleep(RATE_LIMIT_DELAY)

        return results

    def fetch_subjects(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all subjects from WaniKani, using cache when possible.

        This function is idempotent: calling it multiple times will only
        fetch new/updated subjects from the API. The cache file will be
        updated with new timestamps but the subject data itself will remain
        stable unless there are actual changes.

        Args:
            force: If True, fetch all subjects regardless of cache state

        Returns:
            List of all subject data
        """
        last_updated = self._cache_data["subjects"]["last_updated"]

        params = {}
        if not force and last_updated:
            # Use updated_after to only fetch changes since last update
            params["updated_after"] = last_updated
            print(f"Fetching subjects updated after {last_updated}...")
        else:
            print("Fetching all subjects...")

        # Fetch subjects (all or incremental based on updated_after)
        new_subjects = self._fetch_paginated("subjects", params)

        if new_subjects:
            print(f"Fetched {len(new_subjects)} new/updated subjects")

            # Merge new subjects with existing cache
            if force or not last_updated:
                # Full refresh: replace all subjects
                self._cache_data["subjects"]["data"] = new_subjects
            else:
                # Incremental update: merge by ID
                existing_subjects = {
                    s["id"]: s for s in self._cache_data["subjects"]["data"]
                }

                for subject in new_subjects:
                    existing_subjects[subject["id"]] = subject

                self._cache_data["subjects"]["data"] = list(existing_subjects.values())
        else:
            print("No new subjects to fetch")

        # Update timestamp to current time
        self._cache_data["subjects"]["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Save cache to disk
        self._save_cache()

        return self._cache_data["subjects"]["data"]

    def get_subjects(self, subject_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get subjects from cache, optionally filtered by type.

        Args:
            subject_type: Optional filter (e.g., "kanji", "radical", "vocabulary")

        Returns:
            List of subject data
        """
        subjects = self._cache_data["subjects"]["data"]

        if subject_type:
            subjects = [
                s for s in subjects
                if s.get("object") == subject_type
            ]

        return subjects

    def get_subject_by_id(self, subject_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single subject by ID from cache.

        Args:
            subject_id: The subject ID to look up

        Returns:
            Subject data or None if not found
        """
        for subject in self._cache_data["subjects"]["data"]:
            if subject.get("id") == subject_id:
                return subject
        return None


def ensure_subjects_cached() -> WaniKaniCache:
    """
    Convenience function to ensure subjects are cached and return the cache.

    This is idempotent: calling it multiple times will only fetch updates.

    Returns:
        WaniKaniCache instance with subjects loaded
    """
    cache = WaniKaniCache()
    cache.fetch_subjects()
    return cache


if __name__ == "__main__":
    # Test the caching functionality
    print("Testing WaniKani cache...")
    cache = ensure_subjects_cached()

    # Print statistics
    all_subjects = cache.get_subjects()
    kanji = cache.get_subjects("kanji")
    radicals = cache.get_subjects("radical")
    vocabulary = cache.get_subjects("vocabulary")

    print(f"\nCache statistics:")
    print(f"  Total subjects: {len(all_subjects)}")
    print(f"  Kanji: {len(kanji)}")
    print(f"  Radicals: {len(radicals)}")
    print(f"  Vocabulary: {len(vocabulary)}")
    print(f"\nCache saved to: {CACHE_FILE}")
