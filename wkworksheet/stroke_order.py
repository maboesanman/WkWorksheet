"""Stroke order SVG generation for kanji worksheets."""
import re
from copy import deepcopy
from pathlib import Path

from lxml import etree
from lxml.etree import _Element as Element

from .config import ROOT_DIR


KANJIVG_DIR = ROOT_DIR / "data" / "kanjivg" / "kanji"
NS = {"svg": "http://www.w3.org/2000/svg"}
MOVE_CMD = re.compile(r"[Mm]\s*([0-9.\-]+)[ ,]([0-9.\-]+)")


def unicode_to_hex(kanji: str) -> str:
    """Convert single-character kanji to KanjiVG filename."""
    return format(ord(kanji), "05x")


def load_kanjivg_svg(kanji: str):
    """Load and parse the KanjiVG SVG file for the given kanji."""
    hexcode = unicode_to_hex(kanji)
    path = KANJIVG_DIR / f"{hexcode}.svg"
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path}")
    return etree.parse(str(path))


def _localname(tag: str) -> str:
    """Strip namespace from an XML tag name."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def get_kanji_root(tree, kanji: str):
    """Return the <g> node that represents the top-level kanji element."""
    hexcode = unicode_to_hex(kanji)
    target_id = f"kvg:{hexcode}"
    for g in tree.iterfind(".//{http://www.w3.org/2000/svg}g"):
        if g.get("id") == target_id:
            return g
    raise RuntimeError(f"Top-level group with id={target_id} not found.")


def count_strokes(node: Element) -> int:
    """
    Recursively count strokes under this node.
    In KanjiVG, each <path> corresponds to exactly one stroke.
    """
    name = _localname(node.tag)
    if name == "path":
        return 1
    total = 0
    for child in node:
        if isinstance(child.tag, str):
            total += count_strokes(child)
    return total


def compute_phase_starts(node: Element, k: int) -> list[int]:
    """
    Compute the starting stroke indices for k phases.

    Divides strokes into k roughly equal groups based on
    the hierarchical structure of the kanji.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    if k == 1:
        return [0]

    children = [child for child in node]
    total_strokes = count_strokes(node)
    if total_strokes == 0:
        return []

    child_weights = [count_strokes(c) for c in children]
    child_total = sum(child_weights)
    if child_total == 0:
        return []

    if child_total <= k:
        return list(range(child_total))

    if len(children) <= k:
        child_allocs = [1 for _ in children]

        for _ in range(k - len(children)):
            max_index = max(
                range(len(children)),
                key=lambda i: k * child_weights[i] - child_allocs[i] * child_total
            )
            child_allocs[max_index] += 1

        phase_starts = []
        stroke_cursor = 0
        for child, alloc, weight in zip(children, child_allocs, child_weights):
            local_starts = compute_phase_starts(child, alloc)
            phase_starts.extend(stroke_cursor + s for s in local_starts)
            stroke_cursor += weight

        return phase_starts
    else:
        # Oversubscribed: more children than available phases.
        n = len(children)
        total = sum(child_weights)
        target_step = total / k
        targets = [i * target_step for i in range(k)]

        cum = []
        s = 0
        for w in child_weights:
            s += w
            cum.append(s)

        cuts = []
        idx = 0
        for t in targets[1:]:
            while idx < n - 1 and cum[idx] < t:
                idx += 1
            cuts.append(idx)

        cuts = sorted(set(cuts))
        cuts = [c for c in cuts if 0 < c < n]

        stroke_starts = [0]
        s = 0
        for i, w in enumerate(child_weights):
            s += w
            if i in cuts:
                stroke_starts.append(s)

        stroke_starts = [x for x in stroke_starts if x < total_strokes]

        return stroke_starts


def _clean_empty_groups_keep_text(node):
    """Remove empty groups but keep text-only groups."""
    for child in list(node):
        if isinstance(child.tag, str):
            _clean_empty_groups_keep_text(child)
    if isinstance(node.tag, str) and node.tag.endswith("g"):
        has_content = any(
            isinstance(c.tag, str)
            and (c.tag.endswith("path") or c.tag.endswith("g") or c.tag.endswith("text"))
            for c in node
        )
        if not has_content and node.getparent() is not None:
            node.getparent().remove(node)


def make_phase_svgs(tree, phase_starts: list[int], outdir: Path, kanji: str, num: int):
    """
    Generate phase SVGs for stroke order practice.

    For each phase:
      - keep only the paths belonging to that phase,
      - add dots at stroke start points,
      - gray out previous strokes.
    """
    root = tree.getroot()
    all_paths = root.xpath(
        ".//svg:g[starts-with(@id,'kvg:StrokePaths_')]//svg:path",
        namespaces=NS
    )
    total = len(all_paths)

    bounds = phase_starts + [total]
    outdir.mkdir(parents=True, exist_ok=True)

    for i, start in enumerate(phase_starts):
        end = bounds[i + 1]
        tcopy = deepcopy(tree)
        r2 = tcopy.getroot()
        paths = r2.xpath(
            ".//svg:g[starts-with(@id,'kvg:StrokePaths_')]//svg:path",
            namespaces=NS
        )
        texts = r2.xpath(
            ".//svg:g[starts-with(@id,'kvg:StrokeNumbers_')]//svg:text",
            namespaces=NS
        )

        # Remove paths outside [0,end)
        for idx, p in enumerate(paths):
            if not (idx < end):
                p.getparent().remove(p)

            if start < idx < end:
                grey_level = (idx - start) / (end - start)
                hex_color = '#{0:02x}{0:02x}{0:02x}'.format(int(255 * grey_level))
                p.set("stroke", hex_color)

        # Remove all stroke numbers
        for t in texts:
            t.getparent().remove(t)

        # Add dots to paths inside [start,end)
        for idx, path in enumerate(paths):
            if start <= idx < end:
                d = path.get("d")
                m = MOVE_CMD.match(d)
                if not m:
                    continue
                x, y = map(float, m.groups())

                dot = etree.Element("{http://www.w3.org/2000/svg}circle")
                dot.set("cx", str(x))
                dot.set("cy", str(y))
                dot.set("r", "5")
                dot.set("fill", "black")
                dot.set("stroke", "none")

                path.addnext(dot)

        _clean_empty_groups_keep_text(r2)

        out_path = outdir / f"{kanji}-{i+1:02d}.svg"
        tcopy.write(str(out_path), encoding="utf-8", xml_declaration=True)

    # Generate empty SVGs for remaining slots
    for i in range(len(phase_starts), num):
        tcopy = deepcopy(tree)
        r2 = tcopy.getroot()
        paths = r2.xpath(
            ".//svg:g[starts-with(@id,'kvg:StrokePaths_')]//svg:path",
            namespaces=NS
        )
        texts = r2.xpath(
            ".//svg:g[starts-with(@id,'kvg:StrokeNumbers_')]//svg:text",
            namespaces=NS
        )

        for p in paths:
            p.getparent().remove(p)

        for t in texts:
            t.getparent().remove(t)

        _clean_empty_groups_keep_text(r2)

        out_path = outdir / f"{kanji}-{i+1:02d}.svg"
        tcopy.write(str(out_path), encoding="utf-8", xml_declaration=True)


def generate_stroke_order_svg(kanji: str, num_phases: int, outdir: Path):
    """
    Generate stroke order SVGs for a kanji character.

    Args:
        kanji: Single kanji character
        num_phases: Number of practice phases to generate
        outdir: Output directory for SVG files
    """
    tree = load_kanjivg_svg(kanji)
    root = get_kanji_root(tree, kanji)
    phase_starts = compute_phase_starts(root, num_phases)
    make_phase_svgs(tree, phase_starts, outdir, kanji, num_phases)
