"""Acceptance check: the frontend is a thin client (fixed rule 16). It may draw what the server sends, but it holds
no nutrition arithmetic, ranking, or access-level decisions.

Drawing primitives in src/ui/components may scale server values to pixels (ring arcs, bar widths); nothing else may
do arithmetic on nutrient values."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
DRAWING = SRC / "ui" / "components"

NUTRIENT_MATH = re.compile(r"\.(low|mid|high|energy_kcal|protein_g|carbs_g|fat_g)\b\s*[-+*/]|[-+*/]\s*[\w.?!\]]*\.(low|mid|high)\b(?!\w)")
LEVEL_NAMES = re.compile(r"""["'](subscriber|grace|lapsed)["']""")   # "preview" is also an ordinary word (cache keys)
SORTING = re.compile(r"\.sort\(")


def _files():
    return [p for p in SRC.rglob("*.ts*") if p.suffix in (".ts", ".tsx")]


def _hits(pattern, files):
    out = []
    for f in files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if pattern.search(line) and not line.strip().startswith("//"):
                out.append(f"{f.relative_to(SRC)}:{n}: {line.strip()[:120]}")
    return out


def test_no_nutrition_arithmetic_outside_drawing_primitives():
    files = [f for f in _files() if DRAWING not in f.parents]
    assert _hits(NUTRIENT_MATH, files) == []


def test_no_access_level_logic():
    files = [f for f in _files() if f.name != "types.ts"]   # the type union names the levels; nothing may branch on them
    assert _hits(LEVEL_NAMES, files) == []


def test_no_client_side_ranking():
    assert _hits(SORTING, _files()) == []
