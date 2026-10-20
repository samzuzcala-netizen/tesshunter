"""Build the FU3 report (report/FU3_three_candidates.html) from results/facts.json, the tables and the figures.

Every number in the text is read from a result file at build time.  Run facts.py and build_tables.py first.
"""
import base64
import html

from fu3_common import *

F = read(RES / "facts.json")
T270, T262, T193 = "270573718", "262843927", "193718989"


def fx(x, n=2):
    if x is None:
        return "n/a"
    try:
        if not np.isfinite(x):
            return "n/a"
    except TypeError:
        return str(x)
    return f"{x:.{n}f}"


def pct(x, n=1):
    return "n/a" if x is None else f"{100 * x:.{n}f}%"


def img(name, alt, caption):
    p = FIG / name
    if not p.exists():
        return f'<p class="missing">Figure {html.escape(name)} not available.</p>'
    b64 = base64.b64encode(p.read_bytes()).decode()
    return (f'<figure class="plate"><img src="data:image/png;base64,{b64}" alt="{html.escape(alt)}">'
            f'<figcaption>{caption}</figcaption></figure>')


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tbl {cls}"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def chip(level):
    cls = {"HIGH": "hi", "MODERATE": "mod", "LOW": "low", "VERY LOW": "vlow"}.get(level.split(" ")[0] if level.split(" ")[0] != "VERY" else "VERY LOW", "mod")
    return f'<span class="chip {cls}">{level}</span>'


def pooled_row(f, red, label):
    p = f["pooled"].get(red) or {}
    return [label, str(p.get("n")), f'{fx(p.get("depth_ppt"))} &plusmn; {fx(p.get("err_ppt"))}', fx(p.get("snr"), 1),
            fx(p.get("p_const"), 3), f'{p.get("n_positive")}/{p.get("n")}']


def depth_table(tic):
    f = F[tic]
    rows = [pooled_row(f, r, l) for r, l in (
        ("survey_detrended", "Discovery input (TESS-SPOC PDCSAP / QLP, biweight 0.75 d)"),
        ("pdc_raw", "Same product, local linear baselines, no biweight"),
        ("sap_raw", "Pipeline SAP (no crowding correction)"),
        ("survey_tesscut_aperture", "Survey Stage-D TESScut 1-px aperture"),
        ("tglc_aperture", "TGLC aperture (sectors &le; 55 only)"),
        ("tglc_psf", "TGLC PSF (sectors &le; 55 only)"),
        ("fu3pix_annulus_circ1p5", "FU3 TESScut 1.5-px aperture, annulus sky"),
        ("fu3pix_plane_circ1p5", "FU3 TESScut 1.5-px aperture, plane sky"),
        ("fu3pix_prf", "FU3 PRF scene photometry")) if f["pooled"].get(r)]
    return table(["Reduction (same photons)", "events", "pooled depth (ppt)", "S/N", "p(constant depth)", "positive"], rows)


def oc_null_table(tic):
    f = F[tic]
    rows = []
    for red, v in f["ttv_null"].items():
        rows.append([red, str(v["n_null"]), fx(v["obs_dchi2"], 1), fx(v["tail_dchi2"], 3), fx(v["obs_coh"], 1),
                     fx(v["null_coh_max"], 1), fx(v["tail_coh"], 3)])
    return table(["Reduction", "null injections", "season &Delta;&chi;&sup2; (obs.)", "tail p", "max |season median O&minus;C| (obs., min)",
                  "null maximum (min)", "tail p"], rows)


def shape_table(tic):
    f = F[tic]
    rows = []
    for mode, lab in (("linear", "linear ephemeris"), ("season", "per-season timing offsets free")):
        s = f["shape"][mode]
        rows.append([lab, fx(s["k"], 4), fx(s["b"], 2), f'{fx(s["rho_eff"], 2)} (cat. {fx(f["stellar"]["rho_cgs"], 2)})', fx(s["e_min"], 2),
                     fx(s["dchi2_rho_cat"], 1), fx(s["dchi2_k_ge_0p3"], 1), f'{fx(s["dchi2_occultor"], 1)} (needs e &ge; {fx(s["e_min_occultor"], 2)})'])
    if "shape_pixel" in f:
        for mode, lab in (("linear", "FU3 pixel series, linear"), ("season", "FU3 pixel series, season offsets")):
            s = f["shape_pixel"][mode]
            rows.append([lab, fx(s["k"], 4), fx(s["b"], 2), fx(s["rho_eff"], 2), "", fx(s["dchi2_rho_cat"], 1), fx(s["dchi2_k_ge_0p3"], 1),
                         fx(s["dchi2_occultor"], 1)])
    return table(["Fit (PDCSAP/QLP unless noted)", "k", "b", "&rho;<sub>eff</sub> (g cm<sup>-3</sup>)", "e<sub>min</sub>",
                  "&Delta;&chi;&sup2; at catalogue &rho;", "&Delta;&chi;&sup2; k &ge; 0.3 (diluted)", "&Delta;&chi;&sup2; undiluted 0.08-0.20 R<sub>&#9737;</sub> occultor"], rows)


def mcmc_line(tic):
    m = F[tic]["mcmc"]
    a, c = m["free"], m["catalog"]
    return (f'R<sub>p</sub> = {fx(a["rp"]["p50"])} [{fx(a["rp"]["p16"])}, {fx(a["rp"]["p84"])}] R<sub>&#8853;</sub> '
            f'(68 %; density free), {fx(c["rp"]["p50"])} [{fx(c["rp"]["p16"])}, {fx(c["rp"]["p84"])}] R<sub>&#8853;</sub> '
            f'(circular orbit at the catalogue density); b = {fx(a["b"]["p50"])} [{fx(a["b"]["p16"])}, {fx(a["b"]["p84"])}] / '
            f'{fx(c["b"]["p50"])} [{fx(c["b"]["p16"])}, {fx(c["b"]["p84"])}]; P(b &gt; 0.8) = {fx(a["P_b_gt_0p8"])} / {fx(c["P_b_gt_0p8"])}')


def fpp_rows(tic):
    v = F["fpp"][tic]
    rows = []
    for run, x in v["runs"].items():
        f, ic = x["families"], x["image_conditioned"]
        rows.append([run, pct(x["package_fpp"]), fx(x["package_nfpp"], 4), pct(f["target_planet"]), pct(f["other_planets"]["STP"]),
                     pct(f["any_host_planet"]), pct(f["stellar_eclipse"]), pct(ic["fpp"]), fx(ic["nfpp"], 4),
                     f'{pct(x["prior_sensitivity_fpp_range"][0])} - {pct(x["prior_sensitivity_fpp_range"][1])}'])
    return table(["TRICERATOPS run", "package FPP", "NFPP", "target-host planet (TP+PTP+DTP)", "STP", "any-host planet label",
                  "stellar-eclipse scenarios", "image-conditioned FPP", "image-conditioned NFPP", "27 prior reweights (FPP)"], rows)


def loc_rows(tic):
    f = F[tic]
    fb = {r["id"]: r for r in f["flux_budget"]["ranked"]}
    rows = []
    for gid, v in sorted(f["localization"].items(), key=lambda kv: kv[1]["obs"]):
        tg, nb, nbb = v["tgt"], v["nb"], v["nb_broad"]
        r = fb.get(gid, {})
        rows.append([f"Gaia DR3 {gid}", fx(r.get("sep_arcsec"), 1) if r else "", fx(r.get("eclipse_needed"), 2) if r else "",
                     str(v["n_sectors"]), fx(v["obs"], 1),
                     f'{fx(tg["median"], 1)} [{fx(tg["p05"], 1)}, {fx(tg["p95"], 1)}]' if tg else "",
                     f'{fx(nb["median"], 1)} (p95 {fx(nb["p95"], 1)})' if nb else "not injected",
                     fx(nbb["p95"], 1) if nbb else ""])
    return table(["Tested source", "sep. (arcsec)", "eclipse needed", "sectors", "observed &Sigma;&Delta;&chi;&sup2;",
                  "target-hosted injections median [5-95 %]", "neighbour-hosted injections median", "neighbour-hosted, broadened PRF (p95)"], rows)


def replay_section():
    """Two tables from results/s08_summary.json (s08_summarize.py): the inverted null and the injected recovery."""
    p = RES / "s08_summary.json"
    if not p.exists():
        return "<p>The replay summary was not produced.</p>", {}
    s = read(p)
    inv, inj = s["inverted"], s["injected"]
    rows = []
    for key, label in (("targets", "The three targets"), (f"controls_{T270}", "Controls matched to TIC 270573718"),
                       (f"controls_{T262}", "Controls matched to TIC 262843927"), (f"controls_{T193}", "Controls matched to TIC 193718989"),
                       ("all", "All inverted stars")):
        g = inv[key]
        rows.append([label, f'{g["done"]} / {g["planned"]}', str(g["pregate"]), fx(g["max_pregate_snr"], 1) if g["max_pregate_snr"] else "",
                     str(g["n_A"]), f'<b>{g["n_A_pass"]}</b>', f'&lt; {pct(g["ul95_star_A_rate"], 0)}' if g["ul95_star_A_rate"] is not None else "",
                     f'{g["real_pregate"]} / {g["real_A_pass"]}' if key != "all" else ""])
    t_inv = table(["Inverted (null) group", "stars searched / planned", "pre-gate passes", "largest pre-gate stitch S/N", "Stage A jobs",
                   "Stage A passes", "stars with a pass: 95% upper limit", "same stars, real data: pre-gate / Stage A passes"], rows)
    rows = []
    for tic in (T270, T262, T193):
        g = inj[tic]
        d = g["discovery"]
        ci = g["ci68_A"]
        rows.append([f"TIC {tic} transit", f'{g["done"]} / {g["planned"]}',
                     fx(float(np.median(g["expected_snr"])), 1) if g["expected_snr"] else "",
                     f'{g["recovered_pregate"]} / {g["done"]}' if g["done"] else "",
                     (f'<b>{g["recovered_A"]} / {g["done"]}</b> ({pct(ci[0], 0)}-{pct(ci[1], 0)})' if g["done"] else ""),
                     (f'{fx(g["median_matched_snr"], 1)} [{fx(min(g["matched_stitch_snr"]), 1)}-{fx(max(g["matched_stitch_snr"]), 1)}]'
                      if g["matched_stitch_snr"] else ""),
                     f'{fx(d["stitch_snr"], 2)} (rank {d["search_rank"]})'])
    t_inj = table(["Injected signal", "stars searched / planned", "expected S/N (median)", "found at P, P/2 or 2P (pre-gate)",
                   "passed Stage A (68% interval)", "recovered stitch S/N, median [range]", "real candidate's discovery stitch S/N"], rows)
    meta = dict(cpu_h=s.get("cpu_h"), budget_hit=s.get("budget_hit"), not_run=s.get("not_run", []), a_not_run=s.get("a_not_run", []),
                finished=s.get("finished"), n_done=s.get("n_done"), n_complete=s.get("n_complete"), n_planned=s.get("n_planned"),
                inv=inv, inj=inj)
    return t_inv + t_inj, meta


CSS = """
<title>Three-Candidate TESS Follow-up</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<style>
/* Layout: one reading column (~72ch) for prose; tables and figure plates may run wider inside their own scrollers. */
:root{
  --paper:#f5f7f9; --ink:#17212b; --muted:#566271; --rule:#d3d9e0; --accent:#0e6a74; --plate:#ffffff; --plate-ink:#3d4753;
  --ok:#2c7a4b; --warn:#9a6400; --bad:#a63737; --tint:#e8eef2;
  --f-display:"IBM Plex Sans Condensed","Arial Narrow",system-ui,sans-serif;
  --f-body:"Source Serif 4",Georgia,"Times New Roman",serif;
  --f-data:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#11161c; --ink:#e2e8ee; --muted:#9aa7b5; --rule:#2a333e; --accent:#55b9c3; --plate:#f7f8fa;
  --ok:#5fb886; --warn:#e0a640; --bad:#e27b7b; --tint:#1a222b; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#11161c; --ink:#e2e8ee; --muted:#9aa7b5; --rule:#2a333e; --accent:#55b9c3; --plate:#f7f8fa;
  --ok:#5fb886; --warn:#e0a640; --bad:#e27b7b; --tint:#1a222b; color-scheme:dark}
body{background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:16px;line-height:1.58;
  padding-inline:clamp(16px,4vw,48px);padding-block:28px 64px}
main{max-width:1040px;margin-inline:auto;display:flex;flex-direction:column;gap:14px}
.prose{max-width:72ch}
h1,h2,h3,h4{font-family:var(--f-display);text-wrap:balance;line-height:1.15;margin:0}
h1{font-size:clamp(1.9rem,4.4vw,2.7rem);font-weight:700;letter-spacing:-.01em}
h2{font-size:1.55rem;font-weight:700;margin-top:34px;padding-top:14px;border-top:2px solid var(--ink)}
h3{font-size:1.12rem;font-weight:600;margin-top:18px;color:var(--accent)}
h4{font-size:.98rem;font-weight:600;margin-top:10px}
p{margin:0}
.eyebrow{font-family:var(--f-display);font-weight:600;text-transform:uppercase;letter-spacing:.09em;font-size:.78rem;color:var(--muted)}
.lede{font-size:1.08rem;max-width:72ch}
.mono,code{font-family:var(--f-data);font-size:.86em}
a{color:var(--accent)}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
ul{margin:0;padding-left:1.2em;display:flex;flex-direction:column;gap:4px;max-width:74ch}
.tbl{overflow-x:auto;border:1px solid var(--rule);border-radius:4px;background:var(--paper)}
table{border-collapse:collapse;width:100%;font-size:.84rem;font-variant-numeric:tabular-nums}
th,td{padding:6px 9px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
th{font-family:var(--f-display);font-weight:600;font-size:.78rem;letter-spacing:.02em;background:var(--tint);color:var(--ink)}
td:first-child{font-weight:600}
.plate{margin:6px 0;background:var(--plate);border:1px solid var(--rule);border-radius:4px;padding:10px;display:flex;flex-direction:column;gap:6px;max-width:100%}
.plate img{display:block;width:100%;height:auto}
.plate figcaption{font-size:.82rem;color:var(--plate-ink);font-family:var(--f-body)}
.chip{display:inline-block;font-family:var(--f-display);font-weight:600;font-size:.74rem;letter-spacing:.06em;padding:2px 8px;border-radius:999px;border:1.5px solid currentColor;white-space:nowrap}
.chip.hi{color:var(--ok)} .chip.mod{color:var(--accent)} .chip.low{color:var(--warn)} .chip.vlow{color:var(--bad)}
.verdict{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}
.vcard{border:1px solid var(--rule);border-top:4px solid var(--accent);padding:12px 14px;display:flex;flex-direction:column;gap:8px;min-width:0;background:var(--paper)}
.vcard h4{margin:0;font-size:1.05rem}
.vrow{display:flex;justify-content:space-between;gap:10px;align-items:baseline;font-size:.88rem}
.note{font-size:.88rem;color:var(--muted);max-width:76ch}
.callout{border-left:3px solid var(--accent);padding:8px 14px;background:var(--tint);max-width:80ch}
.missing{color:var(--bad)}
nav.toc{font-family:var(--f-display);font-size:.9rem;display:flex;flex-wrap:wrap;gap:6px 16px}
nav.toc a{text-decoration:none}
dl.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0;font-size:.9rem;max-width:80ch}
dl.kv dt{font-family:var(--f-display);font-weight:600;color:var(--muted)} dl.kv dd{margin:0;min-width:0}
@media (max-width:520px){dl.kv{grid-template-columns:1fr} body{font-size:15px}}
@media (prefers-reduced-motion: reduce){*{scroll-behavior:auto}}
</style>
"""
