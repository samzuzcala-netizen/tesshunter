"""Timestamp control: are TESS FFI-product times in the year-3 sectors (S27-S37, 600 s) biased at the
tens-of-minutes level?  WASP-62 b (TIC 149603524, southern CVZ, P ~ 4.4119 d) has TESS-SPOC 600-s FFI light
curves and SPOC 2-min target-pixel light curves in the same sectors.  Its transit mid-times are measured in both
products with the same fixed-shape profile method (events.py), per sector; FFI minus 2-min differences test the
FFI time stamps directly (the 2-min SPOC timing is independently established).
Outputs: results/s06_timestamp_control.json
"""
import lightkurve as lk

from fu3_common import *
from events import Template, measure

TIC = 149603524
SECTORS = (27, 28, 31, 33, 34, 37, 1, 4, 65, 88)
DL = CACHE / "control_wasp62"
DL.mkdir(parents=True, exist_ok=True)
# WASP-62 b geometry (literature-scale values; only the shape template matters for timing)
EPH = dict(P=4.411953, T0=None, T14=3.81 / 24, k=0.1109, a_rs=9.53, b=0.29, inc=88.3, u=[0.3, 0.25])


def series_from(lc, label, sector, cad_s):
    t = np.asarray(lc.time.value, float)
    f = np.asarray(lc.flux.value, float)
    q = np.asarray(lc.quality.value if hasattr(lc.quality, "value") else lc.quality, np.int64)
    ok = np.isfinite(f) & np.isfinite(t) & (q == 0)
    y = (f / np.nanmedian(f[ok]) - 1.0) * 1000.0
    return dict(label=label, sector=sector, t=t, y=y, cad_s=cad_s, quality_ok=ok, t_all=t, quality_all=q, bkg_all=None)


def main():
    out = dict(tic=TIC, generated_utc=utc(), sectors={}, note=__doc__)
    tmpl = None
    for s in SECTORS:
        rec = {}
        prods = {}
        for author, exptime in (("TESS-SPOC", None), ("SPOC", 120)):
            try:
                sr = lk.search_lightcurve(f"TIC {TIC}", sector=s, author=author, exptime=exptime)
                if len(sr) == 0:
                    rec[author] = "NO_PRODUCT"
                    continue
                lc = sr[0].download(download_dir=str(DL), flux_column="pdcsap_flux")
                cad = float(np.nanmedian(np.diff(lc.time.value)) * 86400)
                prods[author] = series_from(lc, author, s, round(cad))
                rec[author] = dict(n=len(lc), cadence_s=round(cad))
            except Exception as exc:   # noqa: BLE001
                rec[author] = f"ERROR {exc!r}"[:300]
        if "SPOC" in prods and "TESS-SPOC" in prods:
            ref = prods["SPOC"]
            if EPH["T0"] is None:
                # anchor the template epoch on the 2-min data of the first usable sector (BLS-free: deepest dip fold)
                t, y, ok = ref["t"], ref["y"], ref["quality_ok"]
                grid = np.arange(t[ok].min(), t[ok].min() + EPH["P"], 2 / 1440)
                ph = [np.nanmean(y[ok][np.abs(((t[ok] - g) / EPH["P"] + 0.5) % 1 - 0.5) * EPH["P"] < EPH["T14"] / 3]) for g in grid]
                EPH["T0"] = float(grid[int(np.nanargmin(ph))])
                tmpl = Template(EPH)
            rows = []
            n0 = int(np.ceil((ref["t"].min() - EPH["T0"]) / EPH["P"]))
            n1 = int(np.floor((ref["t"].max() - EPH["T0"]) / EPH["P"]))
            for n in range(n0, n1 + 1):
                tc = EPH["T0"] + n * EPH["P"]
                a = measure(ref, tc, EPH, tmpl, grid_half=0.06, step_min=0.25)
                b = measure(prods["TESS-SPOC"], tc, EPH, tmpl, grid_half=0.06, step_min=0.25)
                if a.get("timing_status") == "ok" and b.get("timing_status") == "ok":
                    rows.append(dict(cycle=n, tc_2min=a["tc_fit"], tc_ffi=b["tc_fit"],
                                     diff_min=(b["tc_fit"] - a["tc_fit"]) * 1440,
                                     err_min=np.hypot(a["oc_err_d"], b["oc_err_d"]) * 1440))
            if rows:
                d = np.array([r["diff_min"] for r in rows])
                e = np.array([r["err_min"] for r in rows])
                w = 1 / e ** 2
                rec["ffi_minus_2min"] = dict(n=len(rows), weighted_mean_min=float(np.sum(w * d) / np.sum(w)),
                                             err_min=float(1 / np.sqrt(np.sum(w))), median_min=float(np.median(d)),
                                             rows=rows)
        out["sectors"][str(s)] = rec
        log("s06", f"WASP-62 s{s}: {json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'rows'}) for k, v in rec.items()})[:400]}")
        save(RES / "s06_timestamp_control.json", out)


if __name__ == "__main__":
    main()
