"""Layout computation for kanji worksheet typesetting."""

import re
import subprocess
from pathlib import Path

from .latex_snippets import kanjientries_inner


WORKING_DIR = Path("working")
WORKING_DIR.mkdir(parents=True, exist_ok=True)


def measure_grid_width(variables, template):
    """
    Run a minimal xelatex pass to measure the grid width (kanji per page).

    Args:
        variables: LaTeX variable definitions
        template: LaTeX template content

    Returns:
        int: The number of kanji that fit per page (grid width)
    """
    filename = "measure-grid.tex"
    output_path = WORKING_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(variables)
        f.write(template)
        f.write("\\begin{document}\n")
        f.write("\\end{document}\n")

    result = subprocess.run(
        ["xelatex", "-shell-escape", "-interaction=nonstopmode", filename],
        cwd=WORKING_DIR,
        check=True,
        capture_output=True,
        text=True
    )

    # Parse KANJI_COUNT_PER_PAGE from output
    for line in result.stdout.splitlines():
        if "KANJI_COUNT_PER_PAGE=" in line:
            match = re.search(r"KANJI_COUNT_PER_PAGE=(\d+)", line)
            if match:
                return int(match.group(1))

    # Fallback if not found
    raise ValueError("Could not determine KANJI_COUNT_PER_PAGE from LaTeX output")


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

    # Parse the output to find start/end page numbers for each slice
    # START and END are on separate lines:
    #   SLICE:0_8:COLSKIP:0:START:2
    #   END:3
    results = {}
    pending = None  # (start, end, colskip, start_page)

    for line in result.stdout.splitlines():
        if line.startswith("SLICE:"):
            match = re.search(
                r"SLICE:(\d+)_(\d+):COLSKIP:(\d+):START:(\d+)",
                line
            )
            if match:
                start = int(match.group(1))
                end = int(match.group(2))
                colskip = int(match.group(3))
                start_page = int(match.group(4))
                pending = (start, end, colskip, start_page)
        elif line.startswith("END:") and pending is not None:
            match = re.search(r"END:(\d+)", line)
            if match:
                end_page = int(match.group(1))
                start, end, colskip, start_page = pending
                # Content overflows if END is on the next page after START
                overflows = (start_page + 1 != end_page)
                results[(start, end, colskip)] = overflows
                pending = None

    return results


def generate_all_test_cases(n, numcolumns, max_slice_size):
    """Generate all (start, end, colskip) combinations to test."""
    cases = []
    # colskip ranges from 0 to numcolumns-1 (0 = use all columns, numcolumns-1 = use 1 column)
    for colskip in range(numcolumns):
        for start in range(n):
            for end in range(start + 1, min(n + 1, start + max_slice_size + 1)):
                cases.append((start, end, colskip))
    return cases


def compute_all_rolling_windows(variables, template, groups, numcolumns):
    """
    Compute rolling windows for all column configurations using batch page testing.

    Args:
        variables: LaTeX variable definitions
        template: LaTeX template content
        groups: List of {groupName: str, kanji: [...]}
        numcolumns: Number of columns in the word bank area

    Returns:
        Tuple of (rolling_windows, max_slice_size) where:
        - rolling_windows: {(start, end, colskip) => (True/False)} for all slices
        - max_slice_size: The grid width (max kanji per page)

        the boolean value is "subset overflows the requested colskip"
    """
    n = count_kanji(groups)
    if n == 0:
        return {}, 0

    # Measure grid width from LaTeX
    max_slice_size = measure_grid_width(variables, template)

    # Generate all test cases
    test_cases = generate_all_test_cases(n, numcolumns, max_slice_size)

    # Batch test all slices in one xelatex run
    rolling_windows = batch_test_slices(variables, template, groups, test_cases)
    return rolling_windows, max_slice_size


def assign_pages(groups, rolling_windows, numcolumns, max_slice_size):
    """
    Greedily assign kanji to pages, pulling as many items as possible per page.

    Args:
        groups: List of {groupName: str, kanji: [...]}
        rolling_windows: Dict {(start, end, colskip): fits} from compute_all_rolling_windows
        numcolumns: Number of columns in the word bank area
        max_slice_size: Maximum kanji per page (grid width)

    Returns:
        List of page dicts with kanji groups and required legend columns
    """
    n = count_kanji(groups)
    if n == 0:
        return []

    pages = []
    i = 0

    while i < n:
        # Greedy: find the largest slice starting at i that fits with colskip=0 (all columns)
        # Note: rolling_windows value is True when it overflows, False when it fits
        best_end = i + 1  # At minimum, take one item

        for end in range(i + 1, min(n + 1, i + max_slice_size + 1)):
            if not rolling_windows.get((i, end, 0), True):
                best_end = end

        # Determine minimum columns needed for this slice
        # colskip = numcolumns - required_columns
        # Try from fewest columns (highest colskip) to most columns (colskip=0)
        required_columns = numcolumns  # Default to all columns
        for colskip in range(numcolumns - 1, -1, -1):
            if not rolling_windows.get((i, best_end, colskip), True):
                required_columns = numcolumns - colskip
                break

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
