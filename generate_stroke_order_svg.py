#!/usr/bin/env python3
from pathlib import Path
from lxml import etree
from lxml.etree import _Element as Element
from lxml.etree import _ElementTree as ElementTree
import sys
from copy import deepcopy
from pathlib import Path

KANJIVG_DIR = Path("data/kanjivg/kanji")
NS = {"svg": "http://www.w3.org/2000/svg"}

def unicode_to_hex(kanji: str) -> str:
    """Convert single-character kanji to KanjiVG filename."""
    return format(ord(kanji), "05x")

def load_kanjivg_svg(kanji: str) -> ElementTree:
    """Load and parse the KanjiVG SVG file for the given kanji."""
    hexcode = unicode_to_hex(kanji)
    path = KANJIVG_DIR / f"{hexcode}.svg"
    print(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path}")
    return etree.parse(str(path))

def compute_phase_starts(node: Element, k: int) -> list[int]:
    if k <= 0:
        raise ValueError("k must be positive")
    if k == 1:
        # Only one phase: everything is in one bucket
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
        return [x for x in range(child_total)]
    
    if len(children) <= k:
        child_allocs = [1 for _ in children]

        for _ in range(k - len(children)):
            max_index = max(range(len(children)),
                key=lambda i: k * child_weights[i] - child_allocs[i] * child_total)
            child_allocs[max_index] += 1

        # recurse and reassemble
        phase_starts = []
        stroke_cursor = 0
        for child, alloc, weight in zip(children, child_allocs, child_weights):
            local_starts = compute_phase_starts(child, alloc)
            phase_starts.extend(stroke_cursor + s for s in local_starts)
            stroke_cursor += weight

        return phase_starts
            
        # distribute the k phases such that:
        # - each child receives at least 1 phase
        # - the ratio of phases each child receives is as close to the childrens' weight ratio as possible.
        # - the sum of the phases each child receives is exactly k
        #
        # then recurse to resolve within the children
    else:
        # Oversubscribed: more children than available phases.
        # Goal:
        # - Divide children into k contiguous groups.
        # - Groups should have roughly equal total stroke weights.
        # - Each group has at least one child.
        # - Return the stroke index at the start of each group (within this node).

        n = len(children)
        group_targets = [0]  # cumulative target weights at group boundaries
        total = sum(child_weights)
        target_step = total / k
        targets = [i * target_step for i in range(k)]

        # cumulative weights of children
        cum = []
        s = 0
        for w in child_weights:
            s += w
            cum.append(s)

        # find the child index where each group boundary should fall
        cuts = []
        idx = 0
        for t in targets[1:]:  # skip the first (0)
            # find the first child whose cumulative weight >= t
            while idx < n - 1 and cum[idx] < t:
                idx += 1
            cuts.append(idx)

        # deduplicate & ensure strictly increasing
        cuts = sorted(set(cuts))
        cuts = [c for c in cuts if 0 < c < n]  # valid cuts only

        # compute starting stroke index of each group
        stroke_starts = [0]
        s = 0
        for i, w in enumerate(child_weights):
            s += w
            if i in cuts:
                stroke_starts.append(s)

        # clamp to total_strokes
        stroke_starts = [x for x in stroke_starts if x < total_strokes]

        return stroke_starts

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
    # For <g> or <svg> (or anything else), sum children
    total = 0
    for child in node:
        # Only count element children (skip comments/text)
        if isinstance(child.tag, str):
            total += count_strokes(child)
    return total

def make_phase_svgs(tree, phase_starts, outdir: Path, kanji: str):
    """
    For each phase in `phase_starts`:
      - keep only the paths belonging to that phase,
      - keep only the corresponding <text> numbers,
      - renumber them 1..N for that phase.
    """
    root = tree.getroot()
    all_paths = root.xpath(".//svg:g[starts-with(@id,'kvg:StrokePaths_')]//svg:path", namespaces=NS)
    all_texts = root.xpath(".//svg:g[starts-with(@id,'kvg:StrokeNumbers_')]//svg:text", namespaces=NS)
    total = len(all_paths)

    # Add an artificial end marker for the last phase
    bounds = phase_starts + [total]
    outdir.mkdir(parents=True, exist_ok=True)

    for i, start in enumerate(phase_starts):
        end = bounds[i + 1]
        tcopy = deepcopy(tree)
        r2 = tcopy.getroot()
        paths = r2.xpath(".//svg:g[starts-with(@id,'kvg:StrokePaths_')]//svg:path", namespaces=NS)
        texts = r2.xpath(".//svg:g[starts-with(@id,'kvg:StrokeNumbers_')]//svg:text", namespaces=NS)

        # Remove paths outside [0,end)
        for idx, p in enumerate(paths):
            if not (idx < end):
                p.getparent().remove(p)

            if (start < idx < end):
                grey_level = (idx - start) / (end - start)
                hex_color = '#{0:02x}{0:02x}{0:02x}'.format(int(255 * grey_level))
                p.set("stroke", hex_color)

        # Remove numbers outside [start,end)
        for idx, t in enumerate(texts):
            if True:
                t.getparent().remove(t)
        
        

        # Re-enumerate surviving <text> labels 1..N for this phase
        surviving_texts = r2.xpath(".//svg:g[starts-with(@id,'kvg:StrokeNumbers_')]//svg:text", namespaces=NS)
        for newnum, text_el in enumerate(surviving_texts, 1):
            text_el.text = str(newnum)

        # Remove empty groups but keep text-only groups
        _clean_empty_groups_keep_text(r2)

        out_path = outdir / f"{kanji}-{i+1:02d}.svg"
        tcopy.write(str(out_path), encoding="utf-8", xml_declaration=True)
        print("→ wrote", out_path)


def _clean_empty_groups_keep_text(node):
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

def main():
    if len(sys.argv) != 4:
        print("Usage: play_kanji.py <KANJI> <COUNT> <DIR>")
        sys.exit(1)

    kanji = sys.argv[1]
    tree = load_kanjivg_svg(kanji)

    root = get_kanji_root(tree, kanji)

    make_phase_svgs(tree, compute_phase_starts(root, int(sys.argv[2])), Path(sys.argv[3]), kanji)

    print(tree)


if __name__ == "__main__":
    main()