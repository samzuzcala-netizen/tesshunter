"""Rebuild notebooks/02_single_target_search.ipynb with a clean, correct structure.

Keeps the four cells that ran successfully (imports, config, download, preprocess)
with their outputs intact.  Every other cell is replaced with fresh, correct source.
"""

import json
import copy

NB_PATH = "notebooks/02_single_target_search.ipynb"

with open(NB_PATH, encoding="utf-8") as f:
    nb = json.load(f)

old_cells = nb["cells"]


# ── helpers ───────────────────────────────────────────────────────────────────

def code(src, ec=None, outputs=None):
    return {
        "cell_type": "code",
        "execution_count": ec,
        "metadata": {},
        "outputs": outputs if outputs is not None else [],
        "source": [src] if isinstance(src, str) else src,
    }


def md(src):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [src] if isinstance(src, str) else src,
    }


def keep(idx):
    """Deep-copy an old cell so its outputs survive."""
    return copy.deepcopy(old_cells[idx])


# ── cell source strings ───────────────────────────────────────────────────────

IMPORTS_SRC = """\
import sys, logging
sys.path.insert(0, '../src')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

import matplotlib
matplotlib.use('inline')
%matplotlib inline

from tesshunter import download, preprocessing, bls_search, plotting, vetting, catalog_crossmatch, reporting
from tesshunter.config import PLOTS_DIR, CANDIDATES_DIR
"""

CONFIG_SRC = """\
# ── Set your target here ────────────────────────────────────────────────────
TIC_ID = 440887364        # Replace with your TIC ID
TARGET_LABEL = f"TIC {TIC_ID}"

# BLS search parameters
PERIOD_MIN = 1.0          # days
PERIOD_MAX = 12.0         # days
DURATION_MIN = 0.03       # days
DURATION_MAX = 0.15       # days
TOP_N = 20

# Preprocessing
DO_FLATTEN = True
FLATTEN_WINDOW = 0.5
SIGMA = 4.0
BIN_MINUTES = 10.0
# ────────────────────────────────────────────────────────────────────────────
"""

DOWNLOAD_SRC = """\
lcc = download.search_and_download(TIC_ID, sector=[11, 38])
if lcc is None:
    raise RuntimeError(f"No data found for TIC {TIC_ID}")

import warnings; warnings.filterwarnings('ignore', message='.*zero-centered.*')
lcc_normed = [lc.normalize() for lc in lcc]
lc_raw = download.stitch_collection(lcc_normed)
sectors = download.sectors_available(lcc)
print(f"Sectors: {sectors}  |  Cadences: {len(lc_raw)}")
"""

PREPROCESS_SRC = """\
lc_clean, prep_record = preprocessing.preprocess(
    lc_raw, sigma=SIGMA, do_flatten=DO_FLATTEN, flatten_window=FLATTEN_WINDOW
)
print("Preprocessing notes:")
for n in prep_record.notes:
    print(f"  {n}")
"""

BLS_SRC = """\
lc_binned = preprocessing.bin_lightcurve(lc_clean, bin_minutes=BIN_MINUTES)
print(f"Binned: {len(lc_clean)} \\u2192 {len(lc_binned)} cadences")

# Broad BLS search
bls_model, bls_result, candidates = bls_search.run_bls(
    lc_binned,
    period_min=PERIOD_MIN,
    period_max=PERIOD_MAX,
    duration_min=DURATION_MIN,
    duration_max=DURATION_MAX,
    top_n=TOP_N,
)

# 'score' = SNR x completeness (penalises periods whose transits fall in sector gaps)
print(candidates[['peak_rank','period_days','depth_ppt','duration_days','snr','score']].to_string(index=False))

# ── Targeted recovery sanity check (known planets only) ──────────────────────
known = {"TOI-836 b": 3.82, "TOI-836 c": 8.60}
for name, p in known.items():
    _, _, local = bls_search.run_bls(
        lc_binned,
        period_min=p * 0.95, period_max=p * 1.05,
        duration_min=0.03,   duration_max=0.20, top_n=3,
    )
    if local.empty:
        print(f"\\n{name} ({p:.2f} d): no valid candidates found")
    else:
        b = local.iloc[0]
        print(f"\\n{name} (expected {p:.2f} d):")
        print(f"  Best period : {b['period_days']:.4f} d")
        print(f"  Depth       : {b['depth_ppt']:.3f} ppt")
        print(f"  SNR         : {b['snr']:.1f}")
        print(f"  Delta from known: {abs(b['period_days']-p)/p*100:.2f}%")
"""

REFINE_SRC = """\
import pandas as pd

best_broad = candidates.iloc[0]
p0 = best_broad["period_days"]
refine_span = max(p0 * 0.10, 0.15)   # +-10% of period, min +-0.15 d

print(f"Broad-search candidate : {p0:.4f} d  SNR {best_broad['snr']:.1f}")
print(f"Refining in [{p0 - refine_span:.3f}, {p0 + refine_span:.3f}] d ...")

_, refined_result, refined_candidates = bls_search.run_bls(
    lc_binned,
    period_min=max(PERIOD_MIN, p0 - refine_span),
    period_max=min(PERIOD_MAX, p0 + refine_span),
    duration_min=DURATION_MIN,
    duration_max=DURATION_MAX,
    top_n=5,
)

if not refined_candidates.empty:
    best = refined_candidates.iloc[0]
    delta_min = abs(best["period_days"] - p0) * 24 * 60
    print(f"\\nRefined period : {best['period_days']:.6f} d  (delta = {delta_min:.1f} min from broad)")
    print(f"Epoch          : {best['epoch_btjd']:.4f} BTJD")
    print(f"Duration       : {best['duration_days']*24:.2f} h")
    print(f"Depth          : {best['depth_ppt']:.3f} ppt")
    print(f"SNR            : {best['snr']:.1f}")
    print()
    print(refined_candidates[["peak_rank","period_days","depth_ppt","duration_days","snr","score"]].to_string(index=False))
else:
    print("Refinement returned no candidates -- using broad-search result.")
    best = best_broad
"""

XMATCH_SRC = """\
xmatch = catalog_crossmatch.crossmatch(TIC_ID)

print("Cross-match summary:")
print(xmatch["summary_str"])
print(f"Is known TOI       : {xmatch['is_known_toi']}")
print(f"Is confirmed planet: {xmatch['is_confirmed_planet']}")

# Extract stellar radius for planet radius estimation
tic_meta = xmatch.get("tic_metadata") or {}
stellar_radius = tic_meta.get("stellar_radius_rsun")  # None if unavailable
if stellar_radius:
    print(f"Stellar radius from TIC: {stellar_radius:.3f} R_Sun")
else:
    print("Stellar radius not available -- planet radius estimate will be skipped.")
"""

VETTING_SRC = """\
# 'best' is the refined period from Step 3b.
# Safety net: fall back to broad-search result if Step 3b was skipped.
try:
    _ = best["period_days"]
except (NameError, KeyError):
    best = candidates.iloc[0]

vet = vetting.run_vetting(
    lc_clean,
    period_days=best["period_days"],
    epoch_btjd=best["epoch_btjd"],
    duration_days=best["duration_days"],
    depth_ppt=best["depth_ppt"],
    n_sectors=len(sectors),
    stellar_radius_rsun=stellar_radius,
    is_known_toi=xmatch["is_known_toi"],
)

print(f"Period vetted : {best['period_days']:.6f} d  (refined)")
print(f"VERDICT       : {vet.verdict}")
print("\\nVetting notes:")
for n in vet.notes:
    print(f"  {n}")
"""

PLOTS_SRC = """\
# Periodogram highlights all broad-search top periods.
# Fold and zoom use the sharpened period from Step 3b.
plot_paths = plotting.all_diagnostic_plots(
    lc_raw, lc_clean, bls_result, candidates, TARGET_LABEL
)

# Overwrite fold + zoom with refined period/epoch
plot_paths["folded"] = plotting.plot_folded_lightcurve(
    lc_clean,
    best["period_days"], best["epoch_btjd"], best["duration_days"],
    TARGET_LABEL,
)
plot_paths["zoom"] = plotting.plot_transit_zoom(
    lc_clean,
    best["epoch_btjd"], best["duration_days"], best["period_days"],
    TARGET_LABEL,
)

print("Plots saved:")
for k, p in plot_paths.items():
    print(f"  {k}: {p}")
"""

DISPLAY_SRC = """\
from IPython.display import Image
if "folded" in plot_paths:
    display(Image(str(plot_paths["folded"])))
"""

REPORT_SRC = """\
%pip install tabulate -q

# Use refined candidates for the report table if they exist.
try:
    report_candidates = refined_candidates if not refined_candidates.empty else candidates
except NameError:
    report_candidates = candidates

report_path = reporting.generate_report(
    target_id=TARGET_LABEL,
    tic_id=TIC_ID,
    sectors=sectors,
    prep_record=prep_record,
    candidates_df=report_candidates,
    vetting=vet,
    crossmatch_summary=xmatch["summary_str"],
    plot_paths=plot_paths,
)
print(f"Report written: {report_path}")

reporting.append_to_candidate_summary(
    tic_id=TIC_ID,
    target_id=TARGET_LABEL,
    sectors=sectors,
    period_days=best["period_days"],
    depth_ppt=best["depth_ppt"],
    duration_hours=best["duration_days"] * 24,
    bls_power=best["power"],
    snr=best["snr"],
    verdict=vet.verdict,
    crossmatch_summary=xmatch["summary_str"],
    summary_csv=CANDIDATES_DIR / "candidate_summary.csv",
)
"""


# ── assemble ──────────────────────────────────────────────────────────────────

def fresh_code(src):
    return code(src, ec=None, outputs=[])

def fresh_imports():
    # Preserve outputs from the cell that ran successfully (cell index 1)
    c = keep(1)
    c["source"] = [IMPORTS_SRC]
    return c

def fresh_config():
    c = keep(3)
    c["source"] = [CONFIG_SRC]
    return c

def fresh_download():
    c = keep(5)
    c["source"] = [DOWNLOAD_SRC]
    return c

def fresh_preprocess():
    c = keep(7)
    c["source"] = [PREPROCESS_SRC]
    return c


new_cells = [
    md("# Notebook 02: Single-Target Candidate Search\n\n"
       "**Purpose:** Run the full pipeline on one user-specified target and generate a candidate-vetting report.\n\n"
       "> Run notebook 01 first to confirm the pipeline recovers known signals."),

    fresh_imports(),

    md("## Configuration — edit these cells"),

    fresh_config(),

    md("## Step 1: Download"),

    fresh_download(),

    md("## Step 2: Preprocess"),

    fresh_preprocess(),

    md("## Step 3: BLS Search"),

    fresh_code(BLS_SRC),

    md("## Step 3b: Period Refinement (post-detection)\n\n"
       "The broad BLS resolves the period to roughly ±half a frequency-grid step. "
       "A high-resolution search centred on the best candidate sharpens the period, "
       "epoch, and duration before vetting — reducing spurious odd/even asymmetry "
       "caused by phase drift across a large sector gap."),

    fresh_code(REFINE_SRC),

    md("## Step 4: Catalog Cross-match"),

    fresh_code(XMATCH_SRC),

    md("## Step 5: Vetting"),

    fresh_code(VETTING_SRC),

    md("## Step 6: Diagnostic Plots"),

    fresh_code(PLOTS_SRC),

    fresh_code(DISPLAY_SRC),

    md("## Step 7: Generate Report"),

    fresh_code(REPORT_SRC),
]

nb["cells"] = new_cells

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Wrote {len(new_cells)} cells to {NB_PATH}")
for i, c in enumerate(new_cells):
    src_preview = "".join(c["source"])[:70].replace("\n", " ")
    ec = c.get("execution_count", "-")
    print(f"  Cell {i:2d} ({c['cell_type'][:4]}) ec={str(ec):>4} | {src_preview}")
