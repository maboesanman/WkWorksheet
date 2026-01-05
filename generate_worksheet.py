#!/usr/bin/env python3
import requests
import itertools
from datetime import date
from pathlib import Path
import subprocess
import os
import bisect

API_TOKEN = "bd2b206a-665c-4b50-b365-2416e5e5da1f"
API_URL = "https://api.wanikani.com/v2"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
TEMPLATE_PATH = Path("template.tex")
WORKING_DIR = Path("working")
WORKING_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def get_apprentice_kanji_ids():
    """Fetch all kanji subject IDs with SRS 1–4."""
    ids = []
    url = f"{API_URL}/assignments?srs_stages=1,2,3,4&subject_types=kanji"
    while url:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        ids.extend(a["data"]["subject_id"] for a in data["data"])
        url = data["pages"]["next_url"]
    return ids

def get_user():
    url = f"{API_URL}/user"
    """Return the user's current WaniKani level as an integer."""
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    return data["data"]


def get_kanji_info(subject_ids):
    """Fetch kanji details for given subject IDs."""
    results = []
    for i in range(0, len(subject_ids), 1000):
        chunk = subject_ids[i:i+1000]
        url = f"{API_URL}/subjects?ids={','.join(map(str, chunk))}"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()

        for item in data["data"]:
            d = item["data"]
            readings = d["readings"]
            meanings = d["meanings"]
            results.append({
                "character": d["characters"],
                "level": d["level"],
                "readings": readings,
                "meanings": meanings,
            })
    return results

def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def hira_to_kata(s: str) -> str:
    result = []
    for ch in s:
        code = ord(ch)
        # Hiragana range: 0x3041–0x3096
        if 0x3041 <= code <= 0x3096:
            result.append(chr(code + 0x60))  # Katakana is 0x30A1–0x30F6
        else:
            result.append(ch)
    return ''.join(result)

def format_readings(k):
    return "·".join([
        f"\\wkread{{{hira_to_kata(r['reading']) if r['type']=='onyomi' else r['reading']}}}"
        if r['primary']
        else (hira_to_kata(r['reading']) if r['type']=='onyomi' else r['reading'])
        for r in sorted(k["readings"], key=lambda x: x["type"], reverse=True)
    ])

def format_meanings(k):
    return ", ".join(m["meaning"] for m in k["meanings"] if m["primary"])

def get_kanji_count(variables, template):
    filename = f"measure-kanji-per-page.tex"
    output_path = WORKING_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(variables)
        f.write(template)
        f.write("\\begin{document}")
        f.write("\\end{document}")
    
    result = subprocess.run(
            ["xelatex", "-shell-escape", "-synctex=1", filename],
            cwd=WORKING_DIR,
            check=True,
            capture_output=True,
            text=True
        )

    for line in result.stdout.splitlines():
        if line.startswith("KANJI_COUNT_PER_PAGE="):
            return int(line.split("=")[1])

def kanjientries(kanjiarray, colskip):
    # multicol section grouped by level
    document = []
    document.append(f"  \\begin{{kanjientries}}{{{colskip}}}")
    for level, group in itertools.groupby(kanjiarray, key=lambda x: x["level"]):
        level_str = f"{level}"
        document.append(f"  \\begin{{level}}{{{level_str}}}")
        for k in group:
            readings = format_readings(k)
            meaning = format_meanings(k)
            document.append(f"  \\kanjientry{{{k['character']}}}{{{readings}}}{{{meaning}}}")
        document.append("  \\end{level}\n")
    document.append("  \\end{kanjientries}\n")
    return "\n".join(document)

def kanjientries_for_fit(kanjiarray, fit, base_count):
    leftover = kanjiarray[base_count:]
    kanjiarray = kanjiarray[:base_count]

    if fit < 0:
        kanjiarray = kanjiarray[:fit]

    return [kanjientries(kanjiarray, max(0, fit)), len(kanjiarray)]

def evaluate_fit(variables, template, kanjiarray, fit, base_count):
    if fit >= 3:
        return False

    if fit + len(kanjiarray[:base_count]) <= 0:
        return True

    entries = kanjientries_for_fit(kanjiarray, fit, base_count)[0]

    filename = f"evaluate-fit.tex"
    output_path = WORKING_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(variables)
        f.write(template)
        f.write("\\begin{document}\\null\\newpage\\KanjiGrid{}")
        f.write(entries)
        f.write("\\end{document}")

    result = subprocess.run(
        ["xelatex", "-shell-escape", "-synctex=1", filename],
        cwd=WORKING_DIR,
        check=True,
        capture_output=True,
        text=True
    )

    # Output written on example.pdf (2 pages).
    # Output written on example.pdf (3 pages).
    for line in result.stdout.splitlines():
        if line.startswith("Output written on evaluate-fit.pdf ("):
            pagecount = int(line.split("(")[1].split(" ")[0])
            if pagecount > 2:
                return False
            else:
                return True

def main():
    apprentice_ids = get_apprentice_kanji_ids()
    kanji_data = get_kanji_info(apprentice_ids)
    kanji_data = sorted(kanji_data, key=lambda x: x["level"], reverse=True)

    for k in kanji_data:
        char = k["character"]
        subprocess.run(
            ["python3", "generate_stroke_order_svg.py", char, "8", f"{WORKING_DIR}/stroke-order-diagrams"],
            check=True
        )

    chunks = list(chunked(kanji_data, 14))

    variables = ["\\newlength{\\gridsize}", "\\newlength{\\wordbankminheight}"]

    user = get_user()

    variables.append(f"\\newcommand{{\\WKLevel}}{{{user["level"]}}}")
    variables.append(f"\\newcommand{{\\WKUsername}}{{{user["username"]}}}")

    variables.append(f"\\setlength{{\\gridsize}}{{11.5mm}}")
    variables.append(f"\\setlength{{\\wordbankminheight}}{{40mm}}")

    variables = "\n".join(variables)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    base_count = get_kanji_count(variables, template)

    document = []
    document.append("\\begin{document}")

    while kanji_data:
        bestfit = (
            bisect.bisect_left(
                range(base_count + 3),                         # 0..base_count+2
                True,                                          # search first True in inverted predicate
                key=lambda i: not evaluate_fit(
                    variables, template, kanji_data, i - base_count, base_count
                ),
            )
            - 1 - base_count
        )

        x = kanjientries_for_fit(kanji_data, bestfit, base_count)
        grid_chars = ",".join(k["character"] for k in kanji_data[:x[1]])
        document.append(f"\\KanjiGrid{{{grid_chars}}}")
        document.append(x[0])
        kanji_data = kanji_data[x[1]:]

    document.append("\\finishonevenpage")
    document.append("\\end{document}")

    today = date.today().isoformat()
    dated_tex_name = f"kanji-practice-{today}.tex"
    dated_pdf_name = f"kanji-practice-{today}.pdf"
    today_pdf_name = "kanji-practice-today.pdf"
    dated_pdf_path = OUT_DIR / dated_pdf_name
    today_pdf_path = OUT_DIR / today_pdf_name

    with open(WORKING_DIR / dated_tex_name, "w", encoding="utf-8") as f:
        f.write(variables)
        f.write(template)
        f.write("\n".join(document))

    subprocess.run(
            ["xelatex", "-shell-escape", "-synctex=1", dated_tex_name],
            cwd=WORKING_DIR,
            check=True
        )
        
    
    os.rename(WORKING_DIR / dated_pdf_name, dated_pdf_path)

    # Remove existing symlink/file if present
    try:
        today_pdf_path.unlink()
    except FileNotFoundError:
        pass

    # Create relative symlink (preferred for Samba shares)
    today_pdf_path.symlink_to(dated_pdf_name)

if __name__ == "__main__":
    main()
