"""Record which native P8 products can require the biweight precision guard; no search."""
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))


def inspect(tic):
    from tesshunter import audit_prep, biweight_precision, survey_p8
    hits = []
    products = survey_p8.load_audit_products(tic, sector_min=56)
    products, _ = survey_p8.harmonise_cadence(products, 200 / 60)
    for product in products:
        for column in ("flux", "sap_flux"):
            values = product[column]
            ok = (np.isfinite(product["time"]) & np.isfinite(values) & (values > 0)
                  & ((product["quality"] & audit_prep.product_bitmask(product)) == 0))
            if not ok.any():
                continue
            normalized = values[ok] / np.median(values[ok])
            if biweight_precision.needs_precision_guard(normalized):
                hits.append({"tic_id": tic, "sector": product["sector"], "author": product["author"],
                             "column": column, "max_normalized_flux": float(normalized.max())})
    return hits


def main():
    rows = list(csv.DictReader(open(REPO / "data/survey/targets_p8.csv", newline="", encoding="utf-8")))
    sample = {int(r["tic_id"]) for r in csv.DictReader(open(REPO / "data/survey/completeness_sample_p8.csv", newline="", encoding="utf-8"))}
    hits = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, records in enumerate(pool.map(inspect, [int(r["tic_id"]) for r in rows]), 1):
            hits.extend(records)
            if i % 200 == 0:
                print(f"checked {i}/{len(rows)}, {len(hits)} affected product/column pairs", flush=True)
    result = {"n_targets_checked": len(rows), "n_injection_sample_stars_checked": len(sample),
              "hits": hits, "hits_on_injection_sample": [r for r in hits if r["tic_id"] in sample]}
    (REPO / "data/survey/p8/numerical_inputs_p8.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
