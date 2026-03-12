"""Generate the final kanji practice PDF."""
import json
import subprocess
import shutil
from pathlib import Path

from .config import WORKING_DIR, OUT_DIR, TEMPLATE_PATH
from .latex_snippets import make_latex_lengths, make_user_variables, kanjientries
from .stroke_order import generate_stroke_order_svg
from .worksheet_data import generate_worksheet_data


WORKING_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
STROKE_ORDER_DIR = WORKING_DIR / "stroke-order-diagrams"


def generate_stroke_order_svgs(worksheet_data: dict):
    """Generate stroke order SVGs for all kanji in the worksheet."""
    # Use first page size to get kanji (they're the same across sizes)
    first_size = next(iter(worksheet_data["page_sizes"].values()))
    for page in first_size["pages"]:
        for group in page["kanji"]["groups"]:
            for kanji_entry in group["kanji"]:
                char = kanji_entry["character"]
                generate_stroke_order_svg(char, 8, STROKE_ORDER_DIR)


def make_header_variables(worksheet_data: dict, page_config: dict) -> str:
    """
    Generate LaTeX header variable definitions from worksheet data.

    Defines the date and user info as LaTeX commands so the template
    can use them in headers.

    Args:
        worksheet_data: Full worksheet data dict
        page_config: Page configuration dict with gridsize, paperW, etc.
    """
    user = worksheet_data["user"]
    date_formatted = worksheet_data["date"]["formatted"]

    lines = [
        make_latex_lengths(page_config),
        make_user_variables(user["level"], user["username"], date_formatted),
    ]
    return "\n".join(lines)


def generate_page_content(page: dict, numcolumns: int) -> str:
    """Generate LaTeX content for a single page."""
    kanji_data = page["kanji"]
    groups = kanji_data["groups"]
    required_columns = kanji_data["required_legend_columns"]

    # Calculate colskip (numcolumns - required_columns)
    colskip = numcolumns - required_columns

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


def generate_document(pages: list, numcolumns: int) -> str:
    """Generate the complete LaTeX document body."""
    lines = ["\\begin{document}"]

    for page in pages:
        lines.append(generate_page_content(page, numcolumns))

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
    Generate the final kanji practice PDFs for all page sizes.

    Orchestrates the full workflow:
    1. Generate worksheet data (fetches from WaniKani, computes layout for all page sizes)
    2. Generate stroke order SVGs for all kanji
    3. Generate and compile LaTeX documents for each page size
    4. Move PDFs to output directory with date-based naming
    """
    # Generate worksheet data
    worksheet_data = generate_worksheet_data()

    print(worksheet_data)

    # Generate stroke order SVGs
    generate_stroke_order_svgs(worksheet_data)

    # Read template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Extract date for filename (ISO format date portion)
    iso_date = worksheet_data["date"]["datetime"][:10]

    generated_pdfs = []

    # Generate PDF for each page size
    for page_size, size_data in worksheet_data["page_sizes"].items():
        page_config = size_data["page_config"]
        pages = size_data["pages"]

        # Generate LaTeX content
        variables = make_header_variables(worksheet_data, page_config)
        numcolumns = page_config["numcolumns"]
        document = generate_document(pages, numcolumns)

        dated_tex_name = f"kanji-practice-{page_size}-{iso_date}.tex"
        dated_pdf_name = f"kanji-practice-{page_size}-{iso_date}.pdf"
        today_pdf_name = f"kanji-practice-{page_size}-today.pdf"

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

        shutil.copy2(src_pdf, dst_pdf)

        # Create/update symlink
        try:
            today_pdf.unlink()
        except FileNotFoundError:
            pass

        today_pdf.symlink_to(dated_pdf_name)

        print(f"Generated: {dst_pdf}")
        generated_pdfs.append(dst_pdf)

    return generated_pdfs


if __name__ == "__main__":
    generate_final_pdf()
