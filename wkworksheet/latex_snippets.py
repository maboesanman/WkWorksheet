"""LaTeX snippet generation for kanji worksheets."""


# Page configuration presets
PAGE_CONFIGS = {
    "b5": {
        "gridsize": "11.5mm",
        "wordbankminheight": "40mm",
        "paperW": "182mm",
        "paperH": "257mm",
        "numcolumns": 3,
        "wordbankfontsize": "small",  # LaTeX font size command
    },
    "a5": {
        "gridsize": "10.5mm",
        "wordbankminheight": "40mm",
        "paperW": "148mm",
        "paperH": "210mm",
        "numcolumns": 2,
        "wordbankfontsize": "footnotesize",  # smaller than \small
    },
}


def make_latex_lengths(page_config: dict) -> str:
    """
    Generate LaTeX length definitions from a page config.

    Args:
        page_config: Dict with gridsize, wordbankminheight, paperW, paperH, numcolumns

    Returns:
        LaTeX string with length and variable definitions
    """
    return "\n".join([
        "\\newlength{\\gridsize}",
        "\\newlength{\\wordbankminheight}",
        "\\newlength{\\paperW}",
        "\\newlength{\\paperH}",
        f"\\setlength{{\\gridsize}}{{{page_config['gridsize']}}}",
        f"\\setlength{{\\wordbankminheight}}{{{page_config['wordbankminheight']}}}",
        f"\\setlength{{\\paperW}}{{{page_config['paperW']}}}",
        f"\\setlength{{\\paperH}}{{{page_config['paperH']}}}",
        f"\\newcommand{{\\numcolumns}}{{{page_config['numcolumns']}}}",
        f"\\newcommand{{\\wordbankfontsize}}{{\\{page_config['wordbankfontsize']}}}",
    ])


# Legacy constant for backwards compatibility (uses B5 config)
LATEX_LENGTHS = make_latex_lengths(PAGE_CONFIGS["b5"])


def make_user_variables(user_level, username, worksheet_date=None):
    """
    Generate LaTeX user variable definitions.

    Args:
        user_level: WaniKani user level (int)
        username: WaniKani username (str)
        worksheet_date: Optional formatted date string for the worksheet header

    Returns:
        LaTeX string with user variable definitions
    """
    # Use placeholder if no date provided (for layout computation)
    date_str = worksheet_date if worksheet_date else "XXXX年XX月XX日（X）"
    return "\n".join([
        f"\\newcommand{{\\WKLevel}}{{{user_level}}}",
        f"\\newcommand{{\\WKUsername}}{{{username}}}",
        f"\\newcommand{{\\WorksheetDate}}{{{date_str}}}",
    ])


def format_readings(k):
    """
    Format kanji readings for LaTeX output.

    Expects kanji_debt format: readings is a list of {characters, primary}.
    """
    return "·".join([
        f"\\wkread{{{r['characters']}}}" if r['primary'] else r['characters']
        for r in k["readings"]
    ])


def kanjientries(groups, colskip):
    """
    Generate LaTeX for kanji entries from pre-grouped structure.

    Args:
        groups: List of {groupName: str, kanji: [{character, readings, meaning}]}
        colskip: Number of columns to skip in word bank

    Returns:
        LaTeX string for kanjientries environment
    """
    document = []
    document.append(f"  \\begin{{kanjientries}}{{{colskip}}}")
    for group in groups:
        document.append(f"  \\begin{{level}}{{{group['groupName']}}}")
        for k in group["kanji"]:
            readings = format_readings(k)
            document.append(f"  \\kanjientry{{{k['character']}}}{{{readings}}}{{{k['meaning']}}}")
        document.append("  \\end{level}\n")
    document.append("  \\end{kanjientries}\n")
    return "\n".join(document)


def kanjientries_inner(groups):
    """
    Generate LaTeX for kanji entries content only (no kanjientries wrapper).
    Used for batch testing with \testslice.

    Args:
        groups: List of {groupName: str, kanji: [{character, readings, meaning}]}

    Returns:
        LaTeX string for level/kanjientry content
    """
    document = []
    for group in groups:
        document.append(f"\\begin{{level}}{{{group['groupName']}}}")
        for k in group["kanji"]:
            readings = format_readings(k)
            document.append(f"\\kanjientry{{{k['character']}}}{{{readings}}}{{{k['meaning']}}}")
        document.append("\\end{level}")
    return "\n".join(document)
