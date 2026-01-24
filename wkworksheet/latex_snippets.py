"""LaTeX snippet generation for kanji worksheets."""


# LaTeX length configurations (constant)
LATEX_LENGTHS = "\n".join([
    "\\newlength{\\gridsize}",
    "\\newlength{\\wordbankminheight}",
    "\\setlength{\\gridsize}{11.5mm}",
    "\\setlength{\\wordbankminheight}{40mm}",
])


def make_user_variables(user_level, username):
    """
    Generate LaTeX user variable definitions.

    Args:
        user_level: WaniKani user level (int)
        username: WaniKani username (str)

    Returns:
        LaTeX string with user variable definitions
    """
    return "\n".join([
        f"\\newcommand{{\\WKLevel}}{{{user_level}}}",
        f"\\newcommand{{\\WKUsername}}{{{username}}}",
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
