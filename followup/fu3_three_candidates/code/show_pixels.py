"""Summaries of the FU3 pixel extractions: pooled depth per extraction and O-C statistics (formal errors)."""
import sys

from fu3_common import *
from s04_oc import oc_stats


def main(tic):
    d = read(RES / f"s07b_pixels_{tic}.json")
    reds = sorted({e["reduction"] for e in d["events"]})
    out = {}
    for red in reds:
        adm = [e for e in d["events"] if e["reduction"] == red and e["admitted"]]
        p = d["summary"][red]["pooled"]
        timed = [e for e in adm if e.get("timing_status") in ("ok", "multimodal") and e.get("oc_err_d")]
        line = f"{red:32s} n={p.get('n', 0):2d} depth {p.get('depth_ppt', float('nan')):5.2f}+-{p.get('err_ppt', float('nan')):4.2f} " \
               f"S/N {p.get('snr', float('nan')):5.1f} pconst {p.get('p_const', float('nan')):.3f} pos {p.get('n_positive')}"
        if len(timed) >= 4:
            st = oc_stats(timed, "oc_err_d")
            line += f" | O-C lin {st['linear']['chi2']:.1f}/{st['linear']['dof']} seasons dchi2 {st['delta_chi2_seasons_vs_linear']:.1f} " \
                    f"offsets {[round(x, 0) for x in st['season_offsets']['params']]}"
            out[red] = dict(pooled=p, oc=st)
        else:
            out[red] = dict(pooled=p)
        print(line)
    save(RES / f"s07b_summary_{tic}.json", out)


if __name__ == "__main__":
    main(int(sys.argv[1]))
