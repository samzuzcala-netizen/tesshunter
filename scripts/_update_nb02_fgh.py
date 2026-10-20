"""Patch notebooks/02_single_target_search.ipynb for the f/g/h targeted search.

Patches:
  cell 3  — config: period range 8-21 d, relaxed thresholds, FOUND_PLANETS list
  cell 11 — detection loop: pre-masks b/c/d/e, then searches for f/g/h only

Run from the repo root:
    python scripts/_update_nb02_fgh.py
"""

import json
import pathlib

NB_PATH = pathlib.Path(__file__).parent.parent / "notebooks" / "02_single_target_search.ipynb"


def to_source_lines(src: str) -> list[str]:
    lines = src.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines else [])


def load_src(name: str) -> str:
    p = pathlib.Path(__file__).parent / name
    return p.read_text(encoding="utf-8")


CONFIG_SRC = load_src("_cell_config_fgh_src.py")
LOOP_SRC   = load_src("_cell_loop_fgh_src.py")

with open(NB_PATH, encoding="utf-8") as f:
    nb = json.load(f)

cells = nb["cells"]
n = len(cells)
print(f"Notebook has {n} cells.")

PATCHES = {3: CONFIG_SRC, 11: LOOP_SRC}

for idx, src in PATCHES.items():
    if idx >= n:
        print(f"  WARNING: cell {idx} does not exist — skipping")
        continue
    cell = cells[idx]
    if cell["cell_type"] != "code":
        print(f"  WARNING: cell {idx} is '{cell['cell_type']}', not 'code' — skipping")
        continue
    cell["source"]          = to_source_lines(src)
    cell["outputs"]         = []
    cell["execution_count"] = None
    print(f"  Patched cell {idx}")

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"\nWrote {NB_PATH}")
print("\nNext steps:")
print("  1. In Jupyter: Kernel > Restart & Clear Output")
print("  2. Run all cells top to bottom (Shift+Enter or Run All)")
print("  3. Cell 11 will pre-mask b/c/d/e then search 8-21 d for f/g/h")
