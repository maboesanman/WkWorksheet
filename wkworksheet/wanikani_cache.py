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
                "review_statistics": {
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

        # Sort review_statistics by ID for deterministic ordering
        if "review_statistics" in cache_copy and "data" in cache_copy["review_statistics"]:
            cache_copy["review_statistics"]["data"] = sorted(
                cache_copy["review_statistics"]["data"],
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

    def fetch_assignments(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all assignments from WaniKani, using cache when possible.

        This function is idempotent: calling it multiple times will only
        fetch new/updated assignments from the API. The cache file will be
        updated with new timestamps but the assignment data itself will remain
        stable unless there are actual changes.

        Args:
            force: If True, fetch all assignments regardless of cache state

        Returns:
            List of all assignment data
        """
        last_updated = self._cache_data["assignments"]["last_updated"]

        params = {}
        if not force and last_updated:
            # Use updated_after to only fetch changes since last update
            params["updated_after"] = last_updated
            print(f"Fetching assignments updated after {last_updated}...")
        else:
            print("Fetching all assignments...")

        # Fetch assignments (all or incremental based on updated_after)
        new_assignments = self._fetch_paginated("assignments", params)

        if new_assignments:
            print(f"Fetched {len(new_assignments)} new/updated assignments")

            # Merge new assignments with existing cache
            if force or not last_updated:
                # Full refresh: replace all assignments
                self._cache_data["assignments"]["data"] = new_assignments
            else:
                # Incremental update: merge by ID
                existing_assignments = {
                    a["id"]: a for a in self._cache_data["assignments"]["data"]
                }

                for assignment in new_assignments:
                    existing_assignments[assignment["id"]] = assignment

                self._cache_data["assignments"]["data"] = list(existing_assignments.values())
        else:
            print("No new assignments to fetch")

        # Update timestamp to current time
        self._cache_data["assignments"]["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Save cache to disk
        self._save_cache()

        return self._cache_data["assignments"]["data"]

    def get_assignments(
        self,
        subject_type: Optional[str] = None,
        srs_stages: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get assignments from cache, optionally filtered by subject type and SRS stage.

        Args:
            subject_type: Optional filter (e.g., "kanji", "radical", "vocabulary")
            srs_stages: Optional list of SRS stages to filter by (e.g., [1, 2, 3, 4] for apprentice)

        Returns:
            List of assignment data
        """
        assignments = self._cache_data["assignments"]["data"]

        # Filter by SRS stage if specified
        if srs_stages is not None:
            assignments = [
                a for a in assignments
                if a["data"]["srs_stage"] in srs_stages
            ]

        # Filter by subject type if specified
        if subject_type:
            # Need to look up subject IDs and filter
            subject_ids = {
                s["id"] for s in self._cache_data["subjects"]["data"]
                if s.get("object") == subject_type
            }
            assignments = [
                a for a in assignments
                if a["data"]["subject_id"] in subject_ids
            ]

        return assignments

    def get_assignment_by_id(self, assignment_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single assignment by ID from cache.

        Args:
            assignment_id: The assignment ID to look up

        Returns:
            Assignment data or None if not found
        """
        for assignment in self._cache_data["assignments"]["data"]:
            if assignment.get("id") == assignment_id:
                return assignment
        return None

    def get_assignment_by_subject_id(self, subject_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single assignment by subject ID from cache.

        Args:
            subject_id: The subject ID to look up

        Returns:
            Assignment data or None if not found
        """
        for assignment in self._cache_data["assignments"]["data"]:
            if assignment["data"]["subject_id"] == subject_id:
                return assignment
        return None

    def fetch_review_statistics(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all review statistics from WaniKani, using cache when possible.

        This function is idempotent: calling it multiple times will only
        fetch new/updated review statistics from the API. The cache file will be
        updated with new timestamps but the review statistics data itself will remain
        stable unless there are actual changes.

        Args:
            force: If True, fetch all review statistics regardless of cache state

        Returns:
            List of all review statistics data
        """
        last_updated = self._cache_data["review_statistics"]["last_updated"]

        params = {}
        if not force and last_updated:
            # Use updated_after to only fetch changes since last update
            params["updated_after"] = last_updated
            print(f"Fetching review statistics updated after {last_updated}...")
        else:
            print("Fetching all review statistics...")

        # Fetch review statistics (all or incremental based on updated_after)
        new_review_stats = self._fetch_paginated("review_statistics", params)

        if new_review_stats:
            print(f"Fetched {len(new_review_stats)} new/updated review statistics")

            # Merge new review statistics with existing cache
            if force or not last_updated:
                # Full refresh: replace all review statistics
                self._cache_data["review_statistics"]["data"] = new_review_stats
            else:
                # Incremental update: merge by ID
                existing_review_stats = {
                    r["id"]: r for r in self._cache_data["review_statistics"]["data"]
                }

                for review_stat in new_review_stats:
                    existing_review_stats[review_stat["id"]] = review_stat

                self._cache_data["review_statistics"]["data"] = list(existing_review_stats.values())
        else:
            print("No new review statistics to fetch")

        # Update timestamp to current time
        self._cache_data["review_statistics"]["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Save cache to disk
        self._save_cache()

        return self._cache_data["review_statistics"]["data"]

    def get_review_statistics(
        self,
        subject_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get review statistics from cache, optionally filtered by subject type.

        Args:
            subject_type: Optional filter (e.g., "kanji", "radical", "vocabulary")

        Returns:
            List of review statistics data
        """
        review_stats = self._cache_data["review_statistics"]["data"]

        # Filter by subject type if specified
        if subject_type:
            # Need to look up subject IDs and filter
            subject_ids = {
                s["id"] for s in self._cache_data["subjects"]["data"]
                if s.get("object") == subject_type
            }
            review_stats = [
                r for r in review_stats
                if r["data"]["subject_id"] in subject_ids
            ]

        return review_stats

    def get_review_statistics_by_subject_id(self, subject_id: int) -> Optional[Dict[str, Any]]:
        """
        Get review statistics for a single subject by subject ID from cache.

        Args:
            subject_id: The subject ID to look up

        Returns:
            Review statistics data or None if not found
        """
        for review_stat in self._cache_data["review_statistics"]["data"]:
            if review_stat["data"]["subject_id"] == subject_id:
                return review_stat
        return None

    def fetch_user(self) -> Dict[str, Any]:
        """
        Fetch user information from WaniKani, using If-Modified-Since for efficiency.

        Returns:
            User data
        """
        last_updated = self._cache_data["user"]["last_updated"]

        request_headers = {**self.headers}
        if last_updated:
            # Convert ISO timestamp to HTTP date format for If-Modified-Since
            dt = datetime.fromisoformat(last_updated)
            http_date = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
            request_headers["If-Modified-Since"] = http_date
            print(f"Fetching user information (if modified since {last_updated})...")
        else:
            print("Fetching user information...")

        response = requests.get(f"{API_URL}/user", headers=request_headers)

        if response.status_code == 304:
            print("User information not modified")
        else:
            response.raise_for_status()
            self._cache_data["user"]["data"] = response.json()
            self._cache_data["user"]["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._save_cache()
            print("User information fetched")

        return self._cache_data["user"]["data"]

    def get_user(self) -> Optional[Dict[str, Any]]:
        """
        Get user data from cache.

        Returns:
            User data or None if not cached
        """
        return self._cache_data["user"]["data"]

    def get_last_updated(self) -> Optional[datetime]:
        """
        Get the last update time of the assignments cache.

        Returns:
            datetime object of last update, or None if never updated
        """
        last_updated = self._cache_data["assignments"]["last_updated"]
        if last_updated:
            return datetime.fromisoformat(last_updated)
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


def ensure_cache_loaded() -> WaniKaniCache:
    """
    Convenience function to ensure subjects, assignments, review statistics, and user data are cached.

    This is idempotent: calling it multiple times will only fetch updates.

    Returns:
        WaniKaniCache instance with all data loaded
    """
    cache = WaniKaniCache()
    cache.fetch_subjects()
    cache.fetch_assignments()
    cache.fetch_review_statistics()
    cache.fetch_user()
    return cache


if __name__ == "__main__":
    # Test the caching functionality
    print("Testing WaniKani cache...")
    cache = WaniKaniCache()

    # Fetch subjects, assignments, review statistics, and user data
    cache.fetch_subjects()
    cache.fetch_assignments()
    cache.fetch_review_statistics()
    cache.fetch_user()

    # Print statistics
    all_subjects = cache.get_subjects()
    kanji = cache.get_subjects("kanji")
    radicals = cache.get_subjects("radical")
    vocabulary = cache.get_subjects("vocabulary")

    print(f"\nSubject statistics:")
    print(f"  Total subjects: {len(all_subjects)}")
    print(f"  Kanji: {len(kanji)}")
    print(f"  Radicals: {len(radicals)}")
    print(f"  Vocabulary: {len(vocabulary)}")

    # Print assignment statistics
    all_assignments = cache.get_assignments()
    apprentice_assignments = cache.get_assignments(srs_stages=[1, 2, 3, 4])
    apprentice_kanji = cache.get_assignments(subject_type="kanji", srs_stages=[1, 2, 3, 4])

    print(f"\nAssignment statistics:")
    print(f"  Total assignments: {len(all_assignments)}")
    print(f"  Apprentice items: {len(apprentice_assignments)}")
    print(f"  Apprentice kanji: {len(apprentice_kanji)}")

    # Print review statistics
    all_review_stats = cache.get_review_statistics()
    kanji_review_stats = cache.get_review_statistics("kanji")

    print(f"\nReview statistics:")
    print(f"  Total review statistics: {len(all_review_stats)}")
    print(f"  Kanji review statistics: {len(kanji_review_stats)}")

    # Print user information
    user = cache.get_user()
    if user:
        user_data = user.get("data", {})
        print(f"\nUser information:")
        print(f"  Username: {user_data.get('username')}")
        print(f"  Level: {user_data.get('level')}")

    print(f"\nCache saved to: {CACHE_FILE}")
