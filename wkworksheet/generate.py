"""Generate the final kanji practice PDF."""
import json
import os
import subprocess
from pathlib import Path

from .config import WORKING_DIR, OUT_DIR, TEMPLATE_PATH
from .latex_snippets import LATEX_LENGTHS, make_user_variables, kanjientries
from .stroke_order import generate_stroke_order_svg
from .worksheet_data import generate_worksheet_data


WORKING_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
STROKE_ORDER_DIR = WORKING_DIR / "stroke-order-diagrams"


def generate_stroke_order_svgs(worksheet_data: dict):
    """Generate stroke order SVGs for all kanji in the worksheet."""
    for page in worksheet_data["pages"]:
        for group in page["kanji"]["groups"]:
            for kanji_entry in group["kanji"]:
                char = kanji_entry["character"]
                generate_stroke_order_svg(char, 8, STROKE_ORDER_DIR)


def make_header_variables(worksheet_data: dict) -> str:
    """
    Generate LaTeX header variable definitions from worksheet data.

    Defines the date and user info as LaTeX commands so the template
    can use them in headers.
    """
    user = worksheet_data["user"]
    date_formatted = worksheet_data["date"]["formatted"]

    lines = [
        LATEX_LENGTHS,
        make_user_variables(user["level"], user["username"], date_formatted),
    ]
    return "\n".join(lines)


def generate_page_content(page: dict) -> str:
    """Generate LaTeX content for a single page."""
    kanji_data = page["kanji"]
    groups = kanji_data["groups"]
    required_columns = kanji_data["required_legend_columns"]

    # Calculate colskip (3 - required_columns)
    colskip = 3 - required_columns

    # Get all kanji characters for the grid
    grid_chars = []
    for group in groups:
        for k in group["kanji"]:
            grid_chars.append(k["character"])

    lines = [
        f"\\KanjiGrid{{{','.join(grid_chars)}}}",
        kanjientries(groups, colskip),
    ]
    return "\n".join(lines)


def generate_document(worksheet_data: dict) -> str:
    """Generate the complete LaTeX document body."""
    lines = ["\\begin{document}"]

    for page in worksheet_data["pages"]:
        lines.append(generate_page_content(page))

    lines.append("\\finishonevenpage")
    lines.append("\\end{document}")

    return "\n".join(lines)


def embed_json_metadata(pdf_path: Path, worksheet_data: dict):
    """
    Embed the worksheet data JSON as PDF metadata using exiftool.

    Stores the JSON in the 'Subject' field which is a standard PDF metadata field.
    """
    json_str = json.dumps(worksheet_data, ensure_ascii=False, separators=(',', ':'))

    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            f"-Subject={json_str}",
            str(pdf_path)
        ],
        check=True,
        capture_output=True
    )


def generate_final_pdf():
    """
    Generate the final kanji practice PDF.

    Orchestrates the full workflow:
    1. Generate worksheet data (fetches from WaniKani, computes layout)
    2. Generate stroke order SVGs for all kanji
    3. Generate and compile LaTeX document
    4. Embed worksheet data JSON as PDF metadata
    5. Move PDF to output directory with date-based naming
    """
    # Generate worksheet data
    worksheet_data = generate_worksheet_data()

    print(worksheet_data)

    # Generate stroke order SVGs
    generate_stroke_order_svgs(worksheet_data)

    # Read template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Generate LaTeX content
    variables = make_header_variables(worksheet_data)
    document = generate_document(worksheet_data)

    # Extract date for filename (ISO format date portion)
    iso_date = worksheet_data["date"]["datetime"][:10]
    dated_tex_name = f"kanji-practice-{iso_date}.tex"
    dated_pdf_name = f"kanji-practice-{iso_date}.pdf"
    today_pdf_name = "kanji-practice-today.pdf"

    # Write LaTeX file
    tex_path = WORKING_DIR / dated_tex_name
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(variables)
        f.write("\n")
        f.write(template)
        f.write("\n")
        f.write(document)

    # Compile with xelatex
    subprocess.run(
        ["xelatex", "-shell-escape", "-interaction=nonstopmode", dated_tex_name],
        cwd=WORKING_DIR,
        check=True
    )

    # Move PDF to output directory
    src_pdf = WORKING_DIR / dated_pdf_name
    dst_pdf = OUT_DIR / dated_pdf_name
    today_pdf = OUT_DIR / today_pdf_name

    os.rename(src_pdf, dst_pdf)

    # TODO: Embed JSON metadata (requires exiftool or alternative)
    # embed_json_metadata(dst_pdf, worksheet_data)

    # Create/update symlink
    try:
        today_pdf.unlink()
    except FileNotFoundError:
        pass

    today_pdf.symlink_to(dated_pdf_name)

    print(f"Generated: {dst_pdf}")
    return dst_pdf


if __name__ == "__main__":
    generate_final_pdf()
