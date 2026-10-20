"""Print a compact event x reduction table and the O-C model statistics from s02 results."""
import sys

from fu3_common import *


def main(tic):
    d = read(RES / f"s02_events_{tic}.json")
    reds = list(d["summary"].keys())
    by = {}
    for r in d["events"]:
        by.setdefault((r["cycle"], r["sector"]), {})[r["reduction"]] = r
    print(f"TIC {tic}  P={d['ephemeris']['P']:.6f}  T14={d['ephemeris']['T14']*24:.2f} h")
    print("cycle sec | " + " | ".join(f"{x[:14]:>26s}" for x in reds))
    for (c, s) in sorted(by):
        cells = []
        for x in reds:
            r = by[(c, s)].get(x)
            if r is None:
                cells.append(f"{'':>26s}")
            elif not r["admitted"]:
                cells.append(f"{'not admitted':>26s}")
            else:
                oc = r.get("oc_d")
                ocs = f"{oc*1440:+5.0f}({r['oc_err_d']*1440:3.0f}){r['timing_status'][0]}" if oc is not None else "   no-timing   "
                cells.append(f"{r['depth_ppt']:5.2f}+-{r['depth_err_ppt']:4.2f} {ocs:>14s}")
        print(f"{c:5d} {s:3d} | " + " | ".join(cells))
    for x in reds:
        s = d["summary"][x]
        if s.get("status") != "OK":
            print(x, s.get("status"))
            continue
        p = s["pooled"]
        line = f"{x}: n={p.get('n')} depth {p.get('depth_ppt', float('nan')):.3f}+-{p.get('err_ppt', float('nan')):.3f} p_const {p.get('p_const', float('nan')):.3f} pos {p.get('n_positive')}"
        if s.get("oc"):
            m = s["oc"]["models"]
            le = s["oc"]["linear_ephemeris"]
            line += (f" | O-C chi2 const {m['constant']['chi2']:.1f} lin {m['linear']['chi2']:.1f} quad {m['quadratic']['chi2']:.1f}"
                     f" (n={m['linear']['n']}) dchi2(q-l) {m['delta_chi2_quadratic_vs_linear']:.1f}; lin P {le['P']:.6f}"
                     f" +- {np.sqrt(le['cov'][1][1]):.6f} infl {le['inflation']:.2f}")
            line += " LOO dchi2: " + ",".join(f"{z['omitted_sector']}:{z['delta_chi2_quad_vs_lin']:.1f}" for z in m["loo_quadratic"])
        print(line)


if __name__ == "__main__":
    main(int(sys.argv[1]))
