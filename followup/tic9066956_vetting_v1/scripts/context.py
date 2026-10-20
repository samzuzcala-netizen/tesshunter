"""Context checks for TIC 9066956: TESS sectors, Gaia kinematics, XP metallicity, VizieR cone."""
import json, sys, socket
import numpy as np
import requests

socket.setdefaulttimeout(60)
RA, DEC = 356.609026, -11.797127
out = {}

# 1. TESScut sector coverage (all sectors with FFI cutouts available)
try:
    r = requests.get("https://mast.stsci.edu/tesscut/api/v0.1/sector",
                     params=dict(ra=RA, dec=DEC, radius="0m"), timeout=60)
    out["tesscut_sectors"] = r.json()
except Exception as e:
    out["tesscut_sectors"] = f"ERR {e}"

# 2. Gaia DR3 row + kinematics via VizieR
from astroquery.vizier import Vizier
Vizier.TIMEOUT = 90
v = Vizier(columns=["**"], row_limit=50)
from astropy.coordinates import SkyCoord
import astropy.units as u
c = SkyCoord(RA * u.deg, DEC * u.deg)
try:
    g = v.query_object("Gaia DR3 2432763248476007296", catalog="I/355/gaiadr3")
    row = None
    for t in g:
        m = t[t["Source"] == 2432763248476007296]
        if len(m):
            row = m[0]
    keep = ["Plx", "e_Plx", "pmRA", "pmDE", "RV", "e_RV", "Gmag", "BPmag", "RPmag", "RUWE",
            "IPDfmp", "IPDgofha", "Dup", "NSS", "VarFlag", "Teff", "logg", "[Fe/H]", "PQSO", "PGal", "PSS",
            "ipd_frac_multi_peak", "ipd_gof_harmonic_amplitude", "phot_bp_rp_excess_factor", "E(BP/RP)"]
    out["gaia"] = {k: (None if row is None or k not in row.colnames else
                       (str(row[k]) if not np.issubdtype(type(row[k]), np.number) else float(row[k])))
                   for k in keep}
    out["gaia_colnames"] = list(row.colnames) if row is not None else None
except Exception as e:
    out["gaia"] = f"ERR {e}"

# 3. UVW (heliocentric, U toward GC) from Gaia astrometry + RV
try:
    from astropy.coordinates import Galactic, ICRS
    gd = out["gaia"]
    sc = SkyCoord(ra=RA * u.deg, dec=DEC * u.deg, distance=(1000 / gd["Plx"]) * u.pc,
                  pm_ra_cosdec=gd["pmRA"] * u.mas / u.yr, pm_dec=gd["pmDE"] * u.mas / u.yr,
                  radial_velocity=gd["RV"] * u.km / u.s, frame="icrs")
    gal = sc.galactic
    vel = gal.velocity.d_xyz.to(u.km / u.s).value  # U,V,W heliocentric
    out["UVW_helio_kms"] = [float(x) for x in vel]
    # LSR (Schoenrich 2010)
    lsr = np.array(vel) + np.array([11.1, 12.24, 7.25])
    out["UVW_lsr_kms"] = [float(x) for x in lsr]
    out["vtot_lsr"] = float(np.linalg.norm(lsr))
    out["vtan_kms"] = float(4.74047 * np.hypot(gd["pmRA"], gd["pmDE"]) / gd["Plx"])
    # Bensby+2014 TD/D relative probability (UVW wrt LSR)
    def gauss(U, V, W, sU, sV, sW, Va):
        k = 1 / ((2 * np.pi) ** 1.5 * sU * sV * sW)
        return k * np.exp(-U**2 / (2 * sU**2) - (V - Va)**2 / (2 * sV**2) - W**2 / (2 * sW**2))
    U, V, W = lsr
    fD = gauss(U, V, W, 35, 20, 16, -15) * 0.85
    fTD = gauss(U, V, W, 67, 38, 35, -46) * 0.09
    fH = gauss(U, V, W, 160, 90, 90, -220) * 0.0015
    out["TD_over_D"] = float(fTD / fD)
    out["H_over_TD"] = float(fH / fTD)
except Exception as e:
    out["UVW"] = f"ERR {e}"

# 4. Gaia XP metallicity catalogues (Andrae+2023; Zhang, Green & Rix 2023)
for cat in ["J/ApJS/267/8", "J/MNRAS/524/1855"]:
    try:
        t = v.query_region(c, radius=5 * u.arcsec, catalog=cat)
        out[cat] = [{k: str(tt[k][0]) for k in tt.colnames} for tt in t] if len(t) else "no rows"
    except Exception as e:
        out[cat] = f"ERR {e}"

# 5. Every VizieR catalogue with an entry within 3 arcsec (catalogue IDs + titles)
try:
    vv = Vizier(columns=["*"], row_limit=5)
    t = vv.query_region(c, radius=3 * u.arcsec)
    out["vizier_cone_3as"] = sorted(set(t.keys()))
except Exception as e:
    out["vizier_cone_3as"] = f"ERR {e}"

json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in out if k not in ("gaia_colnames",)}, indent=1, default=str)[:7000])
