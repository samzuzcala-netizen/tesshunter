"""PROTOCOL 5.4 (and 6, 7): predeclared FU3 pixel extractions for every available cutout of each target.

Per sector: scene fit (mission PRF, plane sky); backgrounds {annulus, plane} x apertures {circ1.0, circ1.5,
circ2.0, neighbour_excl}; PRF photometry when the scene residual rms <= 0.1 of the target peak.  Every admitted
event is measured with events.measure.  Aperture throughputs of every scene source are recorded.
Outputs: results/s07b_pixels_<tic>.json, CACHE/fu3pix/<tic>_s<sector>.npz (series)
"""
import sys
import traceback

from fu3_common import *
from events import adopted, Template, measure, context, pool
import pixels as PX
from prf import PRF

GAIA = {270573718: "4792202879700135040", 262843927: "4673750877131752832", 193718989: "1346023547769345792"}
OUT = CACHE / "fu3pix"
OUT.mkdir(parents=True, exist_ok=True)


def cutouts(tic):
    files = {}
    for p in sorted((CACHE / "cutouts").glob(f"{tic}_s*.fits")):
        files[int(p.stem.split("_s")[1])] = (p, "fu3_21px")
    for base in (DEEP / "analysis" / "cutouts", CONT / "analysis" / "cutouts"):
        for p in sorted(base.glob(f"{tic}_s*.fits")):
            s = int(p.stem.split("_s")[1])
            files.setdefault(s, (p, "prior_15px"))
    return files


def one(tic, sector, path, origin, eph, tmpl):
    rec = dict(tic=tic, sector=sector, file=str(path), origin=origin, sha256=sha256(path))
    c = PX.load_cube(path)
    rec.update(camera=c["camera"], ccd=c["ccd"], n_cadences_good=int(len(c["t"])), n_cadences_all=int(len(c["t_all"])),
               shape=list(c["shape"]), row0=c["row0"], col0=c["col0"])
    pos = PX.positions(c, tic)
    try:
        tgt = PX.target_of(pos, GAIA[tic])
    except KeyError:
        rec["status"] = "TARGET_NOT_IN_CUTOUT"
        return rec, {}
    ny, nx = c["shape"]
    rec["target_xy"] = [tgt["x"], tgt["y"]]
    rec["target_edge_distance_px"] = float(min(tgt["x"] + 0.5, tgt["y"] + 0.5, nx - 0.5 - tgt["x"], ny - 0.5 - tgt["y"]))
    rec["target_ccd_rowcol"] = [c["row0"] + tgt["y"], c["col0"] + tgt["x"]]
    bgs, bmeta = PX.backgrounds(c, pos, tgt)
    rec["background_meta"] = bmeta
    prf = PRF(sector, c["camera"], c["ccd"], row=c["row0"] + tgt["y"], col=c["col0"] + tgt["x"])
    rec["prf"] = prf.meta
    if "plane" not in bgs:
        rec["status"] = "NO_BACKGROUND"
        return rec, {}
    scene = PX.scene_model(c, pos, tgt, prf, bgs["plane"])
    rec["scene"] = dict(offset=scene["offset"], frac_rms=scene["frac_rms"], n_stars=scene["n_stars"],
                        fluxes=scene["fluxes"], target_flux=scene["fluxes"].get(tgt["id"]))
    scene_pass = scene["frac_rms"] <= 0.1
    rec["scene_pass"] = bool(scene_pass)
    masks, frac = PX.aperture_masks(c, tgt, scene, prf)
    rec["apertures"] = {k: dict(n_pix=int(m.sum()), throughput=PX.throughput(c, scene, prf, m)) for k, m in masks.items()}
    series = {}
    for bname, sub in bgs.items():
        for aname, m in masks.items():
            if m.sum() == 0:
                continue
            flux = (c["cube"] - sub)[:, m].sum(axis=1)
            series[f"{bname}:{aname}"] = flux
    if scene_pass:
        f_prf, pmeta = PX.prf_photometry(c, bgs["plane"], scene, prf, tgt)
        series["prf"] = f_prf
        rec["prf_photometry"] = pmeta
    ev = []
    n0 = int(np.ceil((c["t"].min() - eph["T0"]) / eph["P"]))
    n1 = int(np.floor((c["t"].max() - eph["T0"]) / eph["P"]))
    for name, flux in series.items():
        seg = PX.series_from_flux(c, flux, f"fu3pix:{name}")
        for n in range(n0, n1 + 1):
            tc = eph["T0"] + n * eph["P"]
            r = measure(seg, tc, eph, tmpl, deg=1)
            r.update(cycle=n, reduction=f"fu3pix:{name}", sector=sector, scene_pass=bool(scene_pass))
            if r["admitted"]:
                r.update(context(seg, tc, eph))
            ev.append(r)
    rec["status"] = "OK" if scene_pass else "SCENE_FAIL"
    rec["n_events_admitted_circ1.5_annulus"] = sum(1 for r in ev if r["reduction"] == "fu3pix:annulus:circ1.5" and r["admitted"])
    save_npz(OUT / f"{tic}_s{sector}.npz", t=c["t"], **{k.replace(":", "__").replace(".", "p"): v for k, v in series.items()})
    return rec, ev


def run(tic):
    eph = adopted(tic)
    tmpl = Template(eph)
    sectors, events = [], []
    for s, (p, origin) in sorted(cutouts(tic).items()):
        try:
            rec, ev = one(tic, s, p, origin, eph, tmpl)
        except Exception as exc:   # noqa: BLE001
            rec, ev = dict(tic=tic, sector=s, file=str(p), status="ERROR", error=repr(exc)[:400],
                           traceback=traceback.format_exc()[-1500:]), []
        sectors.append(rec)
        events.extend(ev)
        log("s07b", f"{tic} s{s} {rec.get('status')} scene_rms {rec.get('scene', {}).get('frac_rms', float('nan')):.3f} "
                    f"edge {rec.get('target_edge_distance_px', float('nan')):.1f}px events(c1.5/ann) {rec.get('n_events_admitted_circ1.5_annulus')}")
    summary = {}
    for red in sorted({e["reduction"] for e in events}):
        adm = [e for e in events if e["reduction"] == red and e["admitted"]]
        summary[red] = dict(pooled=pool(adm), sectors=sorted({e["sector"] for e in adm}), n=len(adm))
        summary[red + "|scene_pass_only"] = dict(pooled=pool([e for e in adm if e["scene_pass"]]))
    save(RES / f"s07b_pixels_{tic}.json", dict(tic=tic, generated_utc=utc(), ephemeris=eph, sectors=sectors,
                                               summary=summary, events=events))


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
