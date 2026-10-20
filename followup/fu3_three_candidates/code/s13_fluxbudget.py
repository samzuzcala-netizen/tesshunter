"""PROTOCOL 6 / 7 / 11: flux budget of every catalogued neighbour and of hypothetical unresolved contaminants.

* Gaia DR3 (VizieR I/355/gaiadr3) within 150 arcsec: G, BP, RP, parallax, pm, RUWE, BP/RP excess.
* TESS magnitude: Stassun et al. (2019) colour relation T = G - 0.00522555 c^3 + 0.0891337 c^2 - 0.633923 c
  + 0.0324473 (c = BP - RP, valid -0.2..3.0); fallback T = RP - 0.25 when BP is missing (stated per source).
* Per sector (FU3 cutouts): mission-PRF fraction of each source inside the FU3 1.5-px aperture (scene offset),
  aperture flux shares from the TESS magnitudes, and the eclipse depth each source would need,
      need = depth_obs * F_ap,total / F_ap,source,
  with depth_obs the FU3 annulus circ1.5 pooled (raw, undiluted) depth.
* Main-sequence pair ceiling: an eclipse of a main-sequence binary removes at most ~50 % of the pair's light
  (equal twins); need > 0.5 is labelled 'excluded under the MS-pair assumption', need > 1 'flux-impossible'.
* Unresolved contaminant: brightness needed, Delta T <= -2.5 log10(depth / f_max) for f_max = 1 and 0.5.
Outputs: results/s13_fluxbudget_<tic>.json
"""
import sys

from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u

from fu3_common import *
import pixels as PX
from prf import PRF

GAIA = {270573718: "4792202879700135040", 262843927: "4673750877131752832", 193718989: "1346023547769345792"}
COORD = {270573718: (86.722905, -52.816629), 262843927: (52.573211, -63.501800), 193718989: (267.554464, 42.109629)}


def tmag(G, BP, RP):
    if BP is not None and RP is not None and np.isfinite(BP) and np.isfinite(RP):
        c = BP - RP
        if -0.2 <= c <= 3.0:
            return G - 0.00522555 * c ** 3 + 0.0891337 * c ** 2 - 0.633923 * c + 0.0324473, "stassun2019"
    if RP is not None and np.isfinite(RP):
        return RP - 0.25, "RP-0.25 fallback"
    return G - 0.6, "G-0.6 fallback"


def gaia_cone(tic, radius=150):
    v = Vizier(columns=["Source", "RA_ICRS", "DE_ICRS", "Gmag", "BPmag", "RPmag", "Plx", "e_Plx", "pmRA", "pmDE",
                        "RUWE", "E(BP/RP)", "Dup"], row_limit=-1, timeout=120)
    r = v.query_region(SkyCoord(*COORD[tic], unit="deg"), radius=radius * u.arcsec, catalog="I/355/gaiadr3")
    t = r[0]
    out = []
    for row in t:
        f = lambda k: (float(row[k]) if (k in t.colnames and row[k] is not np.ma.masked and np.isfinite(float(row[k]))) else None)  # noqa: E731
        T, how = tmag(f("Gmag"), f("BPmag"), f("RPmag"))
        out.append(dict(id=str(row["Source"]), G=f("Gmag"), BP=f("BPmag"), RP=f("RPmag"), plx=f("Plx"), e_plx=f("e_Plx"),
                        pmra=f("pmRA"), pmdec=f("pmDE"), ruwe=f("RUWE"), bprp_excess=f("E(BP/RP)"), T=T, T_method=how))
    return out


def run(tic):
    gaia = gaia_cone(tic)
    by = {g["id"]: g for g in gaia}
    tgt_g = by[GAIA[tic]]
    summ = read(RES / f"s07b_summary_{tic}.json")
    depth = summ["fu3pix:annulus:circ1.5"]["pooled"]["depth_ppt"] / 1000.0
    px = read(RES / f"s07b_pixels_{tic}.json")
    sectors = []
    for srec in px["sectors"]:
        if srec.get("status") != "OK" or not srec.get("scene_pass"):
            continue
        c = PX.load_cube(Path(srec["file"]))
        pos = PX.positions(c, tic)
        tgt = PX.target_of(pos, GAIA[tic])
        prf = PRF(srec["sector"], c["camera"], c["ccd"], row=c["row0"] + tgt["y"], col=c["col0"] + tgt["x"])
        off = srec["scene"]["offset"]
        ny, nx = c["shape"]
        yy, xx = np.indices((ny, nx))
        rr = np.hypot(xx - tgt["x"] - off[0], yy - tgt["y"] - off[1])
        imgs = {}
        for p in pos:
            g = by.get(p["id"])
            if g is None or g["T"] is None:
                continue
            imgs[p["id"]] = (p, g, 10 ** (-0.4 * (g["T"] - tgt_g["T"])), prf.image(p["x"] + off[0], p["y"] + off[1], (ny, nx)))
        rows = []
        tshare = {}
        # apertures of radius 1.5 (FU3 primary), 2.0, 2.5 and 3.0 px: larger apertures favour wide neighbours, so
        # the minimum need over apertures (and sectors) is the conservative (neighbour-friendly) number
        for rad in (1.5, 2.0, 2.5, 3.0):
            ap = rr <= rad
            tot = sum(f * im[ap].sum() for _, _, f, im in imgs.values())
            tshare[str(rad)] = float(imgs[GAIA[tic]][2] * imgs[GAIA[tic]][3][ap].sum() / tot) if tot > 0 else None
            for gid, (p, g, f, im) in imgs.items():
                if gid == GAIA[tic]:
                    continue
                fr = float(im[ap].sum())
                share = f * fr / tot if tot > 0 else 0
                need = depth / share if share > 0 else np.inf
                sep = float(np.hypot(p["x"] - tgt["x"], p["y"] - tgt["y"]) * 21.0)
                if share > 1e-5 or sep < 60:
                    rows.append(dict(id=gid, aperture_radius_px=rad, sep_arcsec=sep, G=g["G"], T=g["T"], T_method=g["T_method"],
                                     dT=g["T"] - tgt_g["T"], frac_psf_in_aperture=fr, aperture_flux_share=share, eclipse_needed=need))
        best_rows = {}
        for r in rows:
            b = best_rows.get(r["id"])
            if b is None or r["eclipse_needed"] < b["eclipse_needed"]:
                best_rows[r["id"]] = r
        rows = sorted(best_rows.values(), key=lambda r: r["eclipse_needed"])
        sectors.append(dict(sector=srec["sector"], target_share_by_aperture=tshare, neighbours=rows[:15]))
    # per-neighbour minimum need across sectors (most favourable sector for the neighbour)
    best = {}
    for s in sectors:
        for r in s["neighbours"]:
            b = best.get(r["id"])
            if b is None or r["eclipse_needed"] < b["eclipse_needed"]:
                best[r["id"]] = dict(r, sector=s["sector"])
    ranked = sorted(best.values(), key=lambda r: r["eclipse_needed"])
    for r in ranked:
        r["verdict"] = ("flux-impossible (need > 1)" if r["eclipse_needed"] > 1 else
                        "excluded under MS-pair assumption (0.5 < need <= 1)" if r["eclipse_needed"] > 0.5 else
                        "physically possible (need <= 0.5)")
    out = dict(tic=tic, generated_utc=utc(), depth_obs_raw_ppt=depth * 1000, target_gaia=tgt_g,
               unresolved_contaminant_max_dT=dict(f_max_1=float(-2.5 * np.log10(depth)), f_max_0p5=float(-2.5 * np.log10(depth / 0.5))),
               neighbours_ranked=ranked[:15], sectors=sectors, n_gaia_150arcsec=len(gaia),
               note=__doc__)
    save(RES / f"s13_fluxbudget_{tic}.json", out)
    log("s13", f"{tic}: depth {depth*1000:.2f} ppt; unresolved contaminant needs dT <= {out['unresolved_contaminant_max_dT']['f_max_1']:.2f} "
               f"(100% eclipse) / {out['unresolved_contaminant_max_dT']['f_max_0p5']:.2f} (50%); best neighbours: "
               + "; ".join(f"{r['sep_arcsec']:.1f}\" dT {r['dT']:.2f} need {r['eclipse_needed']:.2f} [{r['verdict']}]" for r in ranked[:4]))


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
