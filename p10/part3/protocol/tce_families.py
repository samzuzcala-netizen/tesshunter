"""Deterministic ephemeris grouping, independent of recovery outcomes."""
import math


def families(rows, tolerance=0.01):
    rows = sorted(rows, key=lambda r:(int(r["ticid"]),float(r["tce_period"]),
                                     r["source_filename"],int(r["source_row"])))
    result = []
    for row in rows:
        p = float(row["tce_period"])
        if not math.isfinite(p) or p<=0:
            raise ValueError("Nonpositive/nonfinite TCE period")
        if (not result or result[-1]["tic_id"]!=int(row["ticid"])
                or abs(p/result[-1]["anchor_period"]-1)>=tolerance):
            result.append(dict(tic_id=int(row["ticid"]),anchor_period=p,rows=[]))
        result[-1]["rows"].append(row)
    for i,family in enumerate(result):
        family["family_id"] = f"tic{family['tic_id']}_family{i:06d}"
    return result


def likely_in_band(row):
    return (float(row["tce_model_snr"])>=12 and float(row["tce_num_transits"])>=3
            and 0.5<=float(row["tce_period"])<=30)


def counts(rows):
    grouped = families(rows)
    result = {}
    for stratum in ("INDEPENDENT","OVERLAPPING","UNION"):
        subset = [r for r in rows if stratum=="UNION" or r["independence"]==stratum]
        qualifying = [r for r in subset if likely_in_band(r)]
        qualifying_families = [f for f in grouped if any(likely_in_band(r) and
            (stratum=="UNION" or r["independence"]==stratum) for r in f["rows"])]
        result[stratum] = dict(rows=len(subset), hosts=len({int(r["ticid"]) for r in subset}),
            families=sum(any(stratum=="UNION" or r["independence"]==stratum for r in f["rows"]) for f in grouped),
            likely_periodic_in_band_rows=len(qualifying),
            likely_periodic_in_band_families=len(qualifying_families),
            likely_periodic_in_band_hosts=len({int(r["ticid"]) for r in qualifying}))
    return result
