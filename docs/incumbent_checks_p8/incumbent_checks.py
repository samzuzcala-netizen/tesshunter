"""Read-only incumbent checks. Writes only into the scratchpad checks/ directory."""
import json, math, sys
import numpy as np, pandas as pd
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # repo root, relative to docs/incumbent_checks_p8/
OUT = Path(__file__).parent
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 40)

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-h)/d, (c+h)/d)

def logistic(snr, a, b):
    return 1.0/(1.0+np.exp(-(a + b*np.log(np.clip(snr, 1e-3, None)))))

# ---------- inputs ----------
pool = pd.read_csv(REPO/"data/survey/cache/p8/pool_after_xmatch.csv", low_memory=False)
tg = pd.read_csv(REPO/"data/survey/targets_p8.csv", low_memory=False)
yl = json.load(open(REPO/"data/survey/p8/expected_yield_p8.json"))
toi = pd.read_csv(OUT/"toi_exofop.csv", low_memory=False)
ctoi = pd.read_csv(REPO/"data/cache/catalogs/ctoi/ctoi.normalized.csv", low_memory=False)
cf = yl["recovery_curves"]["central_through_funnel"]; cs = yl["recovery_curves"]["search_only"]
ps = pd.DataFrame(yl["per_star"])
print("pool", len(pool), "targets", len(tg), "per_star", len(ps), "toi", len(toi), "ctoi", len(ctoi))
print("gaia_dwarf_check values:", pool["gaia_dwarf_check"].value_counts(dropna=False).to_dict())

# ---------- domain (POPULATION_P8 cuts, before the hard stop) ----------
dom = pool[(pool.Teff < 3600) & (pool["rad"] < 0.45) & pool.Tmag.between(12.5, 14.0)
           & (pool.gallat.abs() >= 20) & (pool.n_sectors_200s >= 3)
           & (pool.n_sectors_2min_in_search < pool.n_sectors_200s/2)].copy()
print("\nDOMAIN before hard stop:", len(dom), "| gaia pass:", (dom.gaia_dwarf_check.astype(str).str.lower()=="pass").sum())
print("xmatch_status in domain:", dom.xmatch_status.value_counts().to_dict())
rej = dom[dom.xmatch_status=="REJECT"]
src = rej.xmatch_tic_sources.fillna("")
print("REJECT sources in domain: any toi %d | toi only via spoc_tce %d | spoc_tce only %d | ctoi(any) %d | tess_eb(any) %d | nasa(any) %d" % (
    src.str.contains("toi").sum(), 0, (src=="spoc_tce").sum(), src.str.contains("ctoi").sum(), src.str.contains("tess_eb").sum(), src.str.contains("nasa").sum()))

# ---------- noise model from the 2,000 ----------
m = ps.merge(tg[["tic_id","tmag","n_sectors_200s"]], on="tic_id")
m = m[m.available]
A = np.vstack([np.ones(len(m)), m.tmag]).T
coef, *_ = np.linalg.lstsq(A, np.log(m.sigma_ppt), rcond=None)
resid = np.log(m.sigma_ppt) - A@coef
cad_per_sector = np.median(m.n_cadences/m.n_sectors)
print("\nsigma model: ln sigma_ppt = %.3f + %.3f*Tmag ; resid sd %.3f dex-e ; cadences/sector median %.0f" % (coef[0], coef[1], resid.std(), cad_per_sector))
def sigma_of(tmag): return np.exp(coef[0]+coef[1]*tmag)
# sensitivity metric -> detectable planets (fit on the 2,000, used to extrapolate to the domain)
m["metric"] = m.n_cadences/m.sigma_ppt**2
for col in ["detectable_through_funnel","detectable_search_only"]:
    X = np.vstack([np.ones(len(m)), np.log(m.metric), np.log(m.metric)**2]).T
    c2, *_ = np.linalg.lstsq(X, np.log(m[col]), rcond=None)
    r = np.log(m[col]) - X@c2
    m[col+"_fit"] = np.exp(X@c2)
    print("%s: sum actual %.2f, sum fit %.2f, resid sd %.3f" % (col, m[col].sum(), m[col+"_fit"].sum(), r.std()))
    if col=="detectable_through_funnel": cF=c2
    else: cS=c2
def det_model(metric, c):
    lm=np.log(metric); return np.exp(c[0]+c[1]*lm+c[2]*lm**2)
dom["sigma_ppt"] = sigma_of(dom.Tmag); dom["n_cad"] = dom.n_sectors_200s*cad_per_sector
dom["metric"] = dom.n_cad/dom.sigma_ppt**2
dom["det_funnel"] = det_model(dom.metric, cF); dom["det_search"] = det_model(dom.metric, cS)
print("\nModel extrapolated to the domain: funnel-detectable planets = %.1f over %d stars (%.4f/star); search-only %.1f" % (
    dom.det_funnel.sum(), len(dom), dom.det_funnel.mean(), dom.det_search.sum()))
print("  2,000 selected stars actual: funnel %.1f (%.4f/star) ; metric median 2000=%.0f domain=%.0f" % (
    m.detectable_through_funnel.sum(), m.detectable_through_funnel.mean(), m.metric.median(), dom.metric.median()))

# ---------- Check 1: TOIs on domain stars ----------
toi = toi.rename(columns={"TIC ID":"tic_id","TFOPWG Disposition":"tfop","TESS Disposition":"tdisp","Period (days)":"P",
      "Duration (hours)":"T14h","Depth (ppm)":"depth_ppm","Planet Radius (R_Earth)":"rp","Planet SNR":"snr_pipe","TESS Mag":"tmag_toi",
      "Date TOI Alerted (UTC)":"alerted"})
t = toi.merge(dom[["tic_id","Tmag","Teff","rad","n_sectors_200s","n_sectors_2min_list","sigma_ppt","n_cad","xmatch_status","xmatch_tic_sources"]], on="tic_id")
t["planet_like"] = t.tfop.isin(["PC","APC","CP","KP"])
t["in_band"] = t.P.between(0.5, 30)
t["snr_p8"] = (t.depth_ppm/1e6)/(t.sigma_ppt/1e3)*np.sqrt(t.n_cad*(t.T14h/24)/t.P)
t["p_funnel"] = logistic(t.snr_p8, cf["a"], cf["b"]); t["p_search"] = logistic(t.snr_p8, cs["a"], cs["b"])
print("\nTOIs on domain stars: %d rows on %d hosts | planet-like %d | FP/FA %d | in 0.5-30 d & planet-like %d" % (
    len(t), t.tic_id.nunique(), t.planet_like.sum(), t.tfop.isin(["FP","FA"]).sum(), (t.planet_like&t.in_band).sum()))
print("  Detection:", t.Detection.value_counts().to_dict()); print("  tfop:", t.tfop.value_counts().to_dict())
print("  hosts' xmatch_status:", t.drop_duplicates("tic_id").xmatch_status.value_counts().to_dict())
late = t[pd.to_datetime(t.alerted, errors="coerce") > pd.Timestamp("2026-09-04")]
print("  TOIs alerted after 2026-09-04 on domain stars:", len(late), late[["tic_id","TOI","tfop","P","alerted","xmatch_status"]].to_string(index=False) if len(late) else "")
pl = t[t.planet_like & t.in_band].copy()
pl["snr_bin"] = pd.cut(pl.snr_p8, [0,7.1,12,20,50,1e9], labels=["<7.1","7.1-12","12-20","20-50",">50"])
print("\nPlanet-like in-band TOIs on domain stars by P8-condition SNR:")
g = pl.groupby("snr_bin", observed=False).agg(n=("TOI","size"), p_funnel=("p_funnel","sum"), p_search=("p_search","sum"), snr_pipe_med=("snr_pipe","median"))
print(g.to_string())
CF = pl.p_funnel.sum(); CS = pl.p_search.sum()
print("\nCLAIMED funnel-grade planets (sum p_funnel) = %.1f ; search-grade = %.1f ; raw count %d ; hosts %d" % (CF, CS, len(pl), pl.tic_id.nunique()))
print("  by disposition: " + ", ".join("%s %.1f/%d" % (d, pl[pl.tfop==d].p_funnel.sum(), (pl.tfop==d).sum()) for d in ["KP","CP","PC","APC"]))
DF = dom.det_funnel.sum(); DS = dom.det_search.sum()
print("  MODEL funnel-detectable in the same %d stars = %.1f -> claimed/model = %.2f (search-grade: %.1f/%.1f = %.2f)" % (len(dom), DF, CF/DF, CS, DS, CS/DS))
# sensitivity to the noise model: +/- 1 resid sd on sigma
for f,lab in [(np.exp(-resid.std()),"sigma low"),(np.exp(resid.std()),"sigma high")]:
    s2 = pl.snr_p8/f; print("  %s: claimed funnel %.1f" % (lab, logistic(s2, cf["a"], cf["b"]).sum()))
pl.sort_values("snr_p8", ascending=False)[["tic_id","TOI","tfop","Detection","P","rp","depth_ppm","T14h","Tmag","n_sectors_200s","snr_pipe","snr_p8","p_funnel"]].to_csv(OUT/"domain_tois.csv", index=False)
print("  full list -> domain_tois.csv (top 12 by P8 SNR):")
print(pl.sort_values("snr_p8", ascending=False)[["TOI","tfop","Detection","P","rp","depth_ppm","Tmag","n_sectors_200s","snr_pipe","snr_p8","p_funnel"]].head(12).to_string(index=False))

# TOIs on P8's own 2,000 (alerted after the crossmatch => searched by P8)
on2000 = toi.merge(tg[["tic_id"]], on="tic_id")
print("\nTOIs on the 2,000 searched stars:", len(on2000), on2000[["tic_id","TOI","tfop","P","depth_ppm","alerted"]].to_string(index=False) if len(on2000) else "")

# CTOIs on domain stars
cc = ctoi.merge(dom[["tic_id"]], on="tic_id") if "tic_id" in ctoi else pd.DataFrame()
print("CTOI columns:", list(ctoi.columns)[:12]); print("CTOIs on domain stars:", len(cc))

# ---------- Check 2: capture-recapture from the Detection column ----------
print("\n=== CHECK 2: joint SPOC/QLP detection among TOIs (all sky) ===")
tt = toi[toi.tfop.isin(["PC","APC","CP","KP"]) & toi.P.between(0.5,30)].copy()
tt["det"] = tt.Detection.fillna("UNKNOWN").str.upper()
tt["spoc"] = tt.det.str.contains("SPOC"); tt["qlp"] = tt.det.str.contains("QLP") | tt.det.str.contains("FAINT")
tt["mdwarf"] = tt["Stellar Eff Temp (K)"] < 4000
def cr(d, label):
    nS = d.spoc.sum(); nQ = d.qlp.sum(); both = (d.spoc & d.qlp).sum()
    cq = both/nS if nS else float("nan"); lo,hi = wilson(both, nS)
    print("  %-38s SPOC-found %4d | QLP-found %4d | both %4d | c_QLP|SPOC-found = %.2f (%.2f-%.2f)" % (label, nS, nQ, both, cq, lo, hi))
for tm_lo, tm_hi in [(0,10.5),(10.5,12.5),(12.5,13.5),(13.5,15)]:
    d = tt[tt.tmag_toi.between(tm_lo, tm_hi)]
    cr(d, "all stars Tmag %.1f-%.1f" % (tm_lo, tm_hi))
    cr(d[d.mdwarf], "  M dwarfs (Teff<4000) same Tmag")
print("  by pipeline SNR, M dwarfs Tmag<13.5:")
d = tt[tt.mdwarf & (tt.tmag_toi<13.5)]
for lo, hi in [(0,10),(10,15),(15,20),(20,50),(50,1e9)]:
    cr(d[d.snr_pipe.between(lo,hi)], "    SNR %g-%g" % (lo, hi))
print("\n  Reverse direction inside the pool (2-min coverage known): QLP/FAINT-found TOIs on pool stars with >=1 2-min sector")
tp = tt.merge(pool[["tic_id","n_sectors_2min_list"]], on="tic_id")
d = tp[tp.qlp & (tp.n_sectors_2min_list>=1)]
k = d.spoc.sum(); print("    n=%d, also SPOC-found %d -> c_SPOC|QLP-found = %.2f (%.2f-%.2f)" % (len(d), k, k/len(d) if len(d) else float("nan"), *wilson(k, len(d))))
print("\n  Pipeline SNR of planet-like in-band TOIs on domain stars: quantiles 10/25/50/75/90 =",
      np.round(pl.snr_pipe.quantile([.1,.25,.5,.75,.9]).values,1), "| fraction with SNR<15: %.2f" % (pl.snr_pipe<15).mean())
