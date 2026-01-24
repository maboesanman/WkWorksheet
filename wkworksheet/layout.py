"""Layout computation for kanji worksheet typesetting."""

import re
import subprocess
from pathlib import Path

from .latex_snippets import kanjientries_inner


WORKING_DIR = Path("working")
WORKING_DIR.mkdir(parents=True, exist_ok=True)


def slice_groups(groups, start, end):
    """
    Slice a groups structure by flat kanji index.

    Args:
        groups: List of {groupName: str, kanji: [...]}
        start: Start index (inclusive) in flattened kanji list
        end: End index (exclusive) in flattened kanji list

    Returns:
        New groups structure containing only kanji[start:end]
    """
    result = []
    current_idx = 0

    for group in groups:
        group_kanji = group["kanji"]
        group_start = current_idx
        group_end = current_idx + len(group_kanji)

        # Check if this group overlaps with [start, end)
        slice_start = max(start, group_start) - group_start
        slice_end = min(end, group_end) - group_start

        if slice_start < slice_end:
            result.append({
                "groupName": group["groupName"],
                "kanji": group_kanji[slice_start:slice_end]
            })

        current_idx = group_end

    return result


def count_kanji(groups):
    """Count total kanji across all groups."""
    return sum(len(g["kanji"]) for g in groups)


# Maximum slice size to consider (larger slices definitely overflow)
MAX_SLICE_SIZE = 14


def batch_test_slices(variables, template, groups, slices_with_colskip):
    """
    Test multiple slice/colskip combinations in a single xelatex run.

    Each test renders a full page with empty KanjiGrid + the slice content,
    then checks if it overflowed to a second page.

    Args:
        variables: LaTeX variable definitions
        template: LaTeX template content
        groups: List of {groupName: str, kanji: [...]}
        slices_with_colskip: List of (start, end, colskip) tuples to test

    Returns:
        Dict {(start, end, colskip): fits} where fits is True if content fits on one page
    """
    if not slices_with_colskip:
        return {}

    # Generate test document
    filename = "batch-test.tex"
    output_path = WORKING_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(variables)
        f.write(template)
        f.write("\\begin{document}\n")

        for start, end, colskip in slices_with_colskip:
            sliced = slice_groups(groups, start, end)
            content = kanjientries_inner(sliced)
            slice_id = f"{start}_{end}"
            f.write(f"\\testslice{{{slice_id}}}{{{colskip}}}{{{content}}}\n")

        f.write("\\end{document}\n")

    result = subprocess.run(
        ["xelatex", "-shell-escape", "-interaction=nonstopmode", filename],
        cwd=WORKING_DIR,
        check=True,
        capture_output=True,
        text=True
    )

    # Parse the output to find page numbers for each slice
    # Each slice reports its page number after rendering
    # If slice N is on page P, and slice N+1 is on page P+1, then slice N fit on one page
    # If slice N+1 is on page P+2 or more, then slice N overflowed

    slice_pages = []  # List of ((start, end, colskip), page_number)

    for line in result.stdout.splitlines():
        if line.startswith("SLICE:"):
            # Parse: "SLICE:0_5:COLSKIP:0:PAGE:3"
            match = re.search(r"SLICE:(\d+)_(\d+):COLSKIP:(\d+):PAGE:(\d+)", line)
            if match:
                start = int(match.group(1))
                end = int(match.group(2))
                colskip = int(match.group(3))
                page = int(match.group(4))
                slice_pages.append(((start, end, colskip), page))

    # Determine if each slice fit by comparing consecutive page numbers
    # Each \testslice advances to an even page, then renders KanjiGrid + content.
    # The reported page is where the content ENDED.
    #
    # Structure per test:
    # - \null\newpage advances from page P to P+1
    # - \ifodd check: if P+1 is odd, another \null\newpage to P+2 (even)
    # - So content always starts on an even page
    # - If content fits, it stays on that even page
    # - If content overflows, it goes to an odd page (or further)
    #
    # First test: starts on page 1, \null\newpage -> page 2, which is even, content on page 2
    # If fits: reports page 2. If overflows: reports page 3+.
    #
    # Subsequent tests: prev ended on page P
    # - \null\newpage -> page P+1
    # - If P+1 is odd, another \null\newpage -> page P+2 (even)
    # - If P was even (content fit), P+1 is odd, so we go to P+2
    # - If P was odd (content overflowed), P+1 is even, so we stay at P+1
    #
    # To check if slice i fit: its reported page should be even
    results = {}

    for (start, end, colskip), page in slice_pages:
        # Content starts on an even page. If it fits, it ends on that same even page.
        # If it overflows, it ends on an odd page (or further).
        fits = (page % 2 == 0)
        results[(start, end, colskip)] = fits

    return results


def generate_all_test_cases(n):
    """Generate all (start, end, colskip) combinations to test."""
    cases = []
    for colskip in [0, 1, 2]:
        for start in range(n):
            for end in range(start + 1, min(n + 1, start + MAX_SLICE_SIZE + 1)):
                cases.append((start, end, colskip))
    return cases


def compute_all_rolling_windows(variables, template, groups):
    """
    Compute rolling windows for 1, 2, and 3 columns using batch page testing.

    Args:
        variables: LaTeX variable definitions
        template: LaTeX template content
        groups: List of {groupName: str, kanji: [...]}

    Returns:
        {(start, end, colskip) => (True/False)} for all slices into groups with length less than or equal to 14, and all colskips

        the boolean value is "subset overflows the requested colskip"
    """
    n = count_kanji(groups)
    if n == 0:
        return {0: [], 1: [], 2: []}

    # Generate all test cases
    test_cases = generate_all_test_cases(n)

    # Batch test all slices in one xelatex run
    return batch_test_slices(variables, template, groups, test_cases)


def assign_pages(groups, rolling_windows):
    """
    Greedily assign kanji to pages, pulling as many items as possible per page.

    Args:
        groups: List of {groupName: str, kanji: [...]}
        rolling_windows: Dict {(start, end, colskip): fits} from compute_all_rolling_windows

    Returns:
        List of page dicts with kanji groups and required legend columns
    """
    n = count_kanji(groups)
    if n == 0:
        return []

    pages = []
    i = 0

    while i < n:
        # Greedy: find the largest slice starting at i that fits with colskip=0 (3 columns)
        # Note: rolling_windows value is True when it overflows, False when it fits
        best_end = i + 1  # At minimum, take one item

        for end in range(i + 1, min(n + 1, i + MAX_SLICE_SIZE + 1)):
            if not rolling_windows.get((i, end, 0), True):
                best_end = end

        # Determine minimum columns needed for this slice
        # colskip=2 -> 1 column, colskip=1 -> 2 columns, colskip=0 -> 3 columns
        if not rolling_windows.get((i, best_end, 2), True):
            required_columns = 1
        elif not rolling_windows.get((i, best_end, 1), True):
            required_columns = 2
        else:
            required_columns = 3

        # Slice the groups for this page
        page_groups = slice_groups(groups, i, best_end)

        pages.append({
            "kanji": {
                "groups": page_groups,
                "required_legend_columns": required_columns
            }
        })

        i = best_end

    return pages
