"""TIC 262843927 SPOC 2-min light curves (S1-S3; a D-alt product of the same epochs, not used by discovery):
event depths and timing at the reference ephemeris with the common machinery, compared with the TESS-SPOC 1800-s
FFI measurements of the same events.  Output: results/s21_spoc2min_262.json
"""
import lightkurve as lk

from fu3_common import *
from events import adopted, Template, measure, pool

TIC = 262843927
DL = CACHE / "spoc2min"
DL.mkdir(parents=True, exist_ok=True)


def main():
    eph = adopted(TIC)
    tmpl = Template(eph)
    out = dict(tic=TIC, generated_utc=utc(), sectors={}, events=[])
    for col in ("pdcsap_flux", "sap_flux"):
        for s in (1, 2, 3):
            try:
                sr = lk.search_lightcurve(f"TIC {TIC}", sector=s, author="SPOC", exptime=120)
                lc = sr[0].download(download_dir=str(DL), flux_column=col, quality_bitmask="default")
            except Exception as exc:   # noqa: BLE001
                out["sectors"][f"{s}_{col}"] = f"ERROR {exc!r}"[:300]
                continue
            t = np.asarray(lc.time.value, float)
            f = np.asarray(lc.flux.value, float)
            ok = np.isfinite(t) & np.isfinite(f)
            from reductions import _norm
            y = (_norm(t, np.where(ok, f, np.nan)) - 1) * 1000
            seg = dict(label=f"spoc2min:{col}", sector=s, t=t, y=y, cad_s=120.0, quality_ok=ok & np.isfinite(y), t_all=t,
                       quality_all=np.asarray(lc.quality.value if hasattr(lc.quality, "value") else lc.quality), bkg_all=None)
            out["sectors"][f"{s}_{col}"] = dict(n=int(ok.sum()), header_version=str(lc.meta.get("PROCVER")), crowdsap=lc.meta.get("CROWDSAP"),
                                                flfrcsap=lc.meta.get("FLFRCSAP"))
            n0 = int(np.ceil((t[ok].min() - eph["T0"]) / eph["P"]))
            n1 = int(np.floor((t[ok].max() - eph["T0"]) / eph["P"]))
            for n in range(n0, n1 + 1):
                r = measure(seg, eph["T0"] + n * eph["P"], eph, tmpl)
                r.update(cycle=n, sector=s, column=col)
                out["events"].append({k: r.get(k) for k in ("sector", "cycle", "column", "admitted", "reason", "depth_ppt", "depth_err_ppt",
                                                             "oc_d", "oc_err_d", "timing_status", "beta")})
    for col in ("pdcsap_flux", "sap_flux"):
        out[f"pooled_{col}"] = pool([e for e in out["events"] if e["column"] == col and e["admitted"]])
    ffi = read(RES / f"s02_events_{TIC}.json")
    out["tess_spoc_1800s_same_events"] = [dict(sector=r["sector"], cycle=r["cycle"], depth=r.get("depth_ppt"), err=r.get("depth_err_ppt"),
                                               oc_min=(r["oc_d"] * 1440 if r.get("oc_d") is not None else None))
                                          for r in ffi["events"] if r["reduction"] == "pdc_raw" and r["sector"] in (1, 2, 3) and r.get("admitted")]
    save(RES / "s21_spoc2min_262.json", out)
    for e in out["events"]:
        if e["admitted"]:
            log("s21", f"S{e['sector']} n={e['cycle']} {e['column']}: {e['depth_ppt']:.2f} +- {e['depth_err_ppt']:.2f} ppt, O-C "
                       f"{(e['oc_d'] or 0) * 1440:+.0f} +- {(e['oc_err_d'] or 0) * 1440:.0f} min ({e['timing_status']})")
    log("s21", f"pooled 2-min PDCSAP {out['pooled_pdcsap_flux']}; SAP {out['pooled_sap_flux']}")


if __name__ == "__main__":
    main()
