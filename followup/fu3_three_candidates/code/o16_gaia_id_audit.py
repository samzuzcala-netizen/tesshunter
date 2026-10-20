"""Audit of the survey's Gaia target association (found while triaging TIC 18229070, 2026-10-19).

The S1 targets table stores TIC 'GAIA' IDs; read through a numeric column with missing values they become float64,
which cannot hold 19-digit integers (spacing 512 near 4.6e18).  The packet's neighbours.json then looks up a
rounded ID.  For every batch-1 packet this script compares the neighbours.json 'target' with the TIC record:
the separation from the TIC position (propagated to 2016.0) and G - Tmag (about 0.4-1.5 for these stars).
Output: results/gaia_id_audit_b1.json
"""
import math

import pandas as pd

from fu3_common import *

PK = S1 / "packets" / "s1_b1"


def main():
    tg = pd.read_csv(REPO / "s1" / "survey" / "targets_s1.csv", low_memory=False, dtype={"GAIA": str}).set_index("tic_id")
    out = []
    for d in sorted(PK.glob("tic*_P*")):
        tic = int(d.name.split("_")[0][3:])
        nb = read(d / "neighbours.json")
        t = (nb.get("gaia") or {}).get("target") or {}
        row = tg.loc[tic]
        ra16 = row.ra + (row.pmRA if pd.notna(row.pmRA) else 0) * 16 / 3.6e6 / math.cos(math.radians(row.dec))
        de16 = row.dec + (row.pmDEC if pd.notna(row.pmDEC) else 0) * 16 / 3.6e6
        sep = (math.hypot((t["ra"] - ra16) * math.cos(math.radians(de16)), t["dec"] - de16) * 3600) if t.get("ra") is not None else None
        g_t = (t.get("phot_g_mean_mag") or float("nan")) - row.Tmag
        ok = sep is not None and sep < 2.0 and -0.5 < g_t < 2.5
        out.append(dict(tic=tic, packet=d.name, tic_gaia=str(row.GAIA), packet_target_id=str(t.get("source_id")),
                        id_diff=(int(t["source_id"]) - int(row.GAIA)) if t.get("source_id") and str(row.GAIA).isdigit() else None,
                        sep_arcsec=sep, G_minus_Tmag=g_t, consistent=ok))
    bad = [x for x in out if not x["consistent"]]
    save(RES / "gaia_id_audit_b1.json", dict(generated_utc=utc(), n_packets=len(out), n_inconsistent=len(bad), rows=out))
    log("gaia_audit", f"{len(out)} packets, {len(bad)} inconsistent: " + "; ".join(
        f"{x['tic']} sep {x['sep_arcsec']:.1f}\" G-T {x['G_minus_Tmag']:+.1f} diff {x['id_diff']}" for x in bad if x["sep_arcsec"] is not None))


if __name__ == "__main__":
    main()
