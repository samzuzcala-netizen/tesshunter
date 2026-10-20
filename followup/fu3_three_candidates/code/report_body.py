import sys
"""Report body (HTML) for build_report.py.  All numbers come from results/facts.json and other result files."""
from build_report import *  # noqa: F401,F403


def loc_summary(tic):
    d = read(RES / f"s07c_localize_{tic}.json")
    comb = d.get("combined", {})
    excl, not_inj, ambiguous = [], [], []
    for gid, v in comb.items():
        dist = v["injection_distributions"]
        nb = [dist[k] for k in dist if k.startswith("true_neighbour")]
        if not nb:
            not_inj.append(gid)
        elif all(v["observed_sum_delta_chi2_diag"] > x["p95"] and x["frac_ge_observed"] == 0 for x in nb):
            excl.append(gid)
        else:
            ambiguous.append(gid)
    tgt_ok = [gid for gid, v in comb.items() if v["injection_distributions"].get("true_target_mission")
              and v["observed_sum_delta_chi2_diag"] >= v["injection_distributions"]["true_target_mission"]["p05"]]
    n_sect = max((v["n_sectors"] for v in comb.values()), default=0)
    impossible = {}
    for s in d["sectors"]:
        for H, iv in s["injections"].items():
            if iv.get("status") == "IMPOSSIBLE_DEPTH":
                impossible[H] = min(impossible.get(H, 9e9), iv.get("required_eclipse_fraction") or 9e9)
    return dict(n=len(comb), excluded=excl, not_injected=not_inj, ambiguous=ambiguous, n_sectors=n_sect,
                consistent_with_target=len(tgt_ok), impossible=impossible)


def head():
    s270, s262, s193 = loc_summary(T270), loc_summary(T262), loc_summary(T193)
    f270, f262, f193 = F[T270], F[T262], F[T193]
    return f"""
<header class="prose" style="display:flex;flex-direction:column;gap:10px">
  <p class="eyebrow">TESS archival follow-up &middot; 18-19 October 2026 &middot; conditional results, nothing validated</p>
  <h1>Three TESS candidates: TIC 270573718, TIC 262843927, TIC 193718989</h1>
  <p class="lede">A skeptical, reproducible re-examination of three long-period signals from the S1 survey batch 1,
  using every accessible local product and public archive. No new observing epoch exists for any of them:
  no TESS sector after 98 contains these stars, so every result below re-reduces the discovery photons or
  tests them against external catalogues and ground photometry.</p>
  <nav class="toc" aria-label="Contents"><a href="#summary">Summary</a><a href="#inputs">Inputs and provenance</a>
  <a href="#census">Archive census</a><a href="#methods">Methods</a><a href="#tic270">TIC 270573718</a><a href="#tic262">TIC 262843927</a>
  <a href="#tic193">TIC 193718989</a><a href="#selection">Selection replay</a><a href="#luminosity">Luminosity for colour</a><a href="#synthesis">Synthesis</a>
  <a href="#matrix">Test matrix</a><a href="#failures">Failures and limits</a><a href="#repro">Reproduction</a></nav>
</header>"""


def summary(replay_meta, replay_tbl):
    f270, f262, f193 = F[T270], F[T262], F[T193]
    fp = F["fpp"]
    card = lambda tic, title, sig, host, pl, line: f"""
<div class="vcard"><h4>TIC {tic}</h4><p class="note">{title}</p>
<div class="vrow"><span>Repeating astrophysical dip</span>{chip(sig)}</div>
<div class="vrow"><span>Named target is the host</span>{chip(host)}</div>
<div class="vrow"><span>Planet-sized, planet-mass body</span>{chip(pl)}</div>
<p class="note">{line}</p></div>"""
    return f"""
<section id="summary" style="display:flex;flex-direction:column;gap:14px">
<h2>Summary</h2>
<div class="verdict">
{card(T262, "P = 24.1089 d, 1.2-1.3 ppt, early M dwarf", "HIGH", "MODERATE", "MODERATE",
      "Join the top tier, narrowly first. Likely unresolved companion: image it first.")}
{card(T193, "P = 24.5329 d, 2.3 ppt, early M dwarf", "HIGH", "MODERATE", "LOW TO MODERATE",
      "Host attribution improved. Join the top tier, close behind 262.")}
{card(T270, "P = 41.3837 d, 1.7-2.1 ppt, early M dwarf", "HIGH", "MODERATE", "LOW",
      "Retain in the second tier. Timing structure unresolved.")}
</div>
<div class="prose" style="display:flex;flex-direction:column;gap:10px">
<p><b>TIC 270573718.</b> The earlier &ldquo;corrected 0.29 versus aperture 8.19&rdquo; contradiction reproduces exactly and is
not a disagreement between data products. Only the corrected series' early half spans 2018 and 2020. Its fitted
period drift of {fx(f270['decomposition']['corrected']['early_dP_min_per_cycle'], 2)} min per cycle, extrapolated over 45 cycles,
moves the predicted late transits off the real ones. At the reference ephemeris the late events give S/N
{fx(f270['decomposition']['corrected']['late_at_reference'], 2)} (corrected) and
{fx(f270['decomposition']['aperture']['late_at_reference'], 2)} (aperture). Underneath it is a season-level timing
pattern. All six 2020-21 transits arrive about 50-64 min early in every reduction, including two
independent pixel extractions. Strictly periodic injections into the same data never produce that much
coherence (tail p &asymp; 0.04 per reduction). A free-shape fit with physically bounded shapes reproduces the early 2020-21
arrival in both PDCSAP and pixel data (unbounded, it is weaker in PDCSAP and unstable in the pixel series). Heavy-tailed timing
errors still keep the protocol's claim rule from being met, so a transit-timing variation is suggestive, not established. With the
season offsets removed, the transit is flat-bottomed and consistent with the catalogue density. The grazing,
e&nbsp;&asymp;&nbsp;0.87 alternative was largely a product of folding misaligned transits. The high nearby-source
FPP is reconciled: injection-calibrated difference images exclude every catalogued neighbour that TRICERATOPS
weighted, and this holds with a deliberately broadened PRF.</p>
<p><b>TIC 262843927.</b> Sectors 31 and 88 failed because the star was off the CCD's science pixels (CCD columns
about 2112 and 31, outside 45-2092). Nothing there can be salvaged, and nothing there is a non-detection.
The transit shape is central (b&nbsp;&asymp;&nbsp;0.2-0.4) at the catalogue density. Undiluted brown-dwarf or stellar
occultors, and equal twins at 2P, are disfavoured by &Delta;&chi;&sup2; &asymp; {fx(f262['shape']['linear']['dchi2_occultor'], 1)}-{fx(f262['shape']['season']['dchi2_occultor'], 1)}
and would need e&nbsp;&asymp;&nbsp;0.9. Gaia's RV constancy over 23 epochs limits a companion to the target to M&nbsp;sin&nbsp;i &lt;
{fx(F['rv'][T262]['cases']['circular_P']['Mmin95_mjup'], 0)}-{fx(F['rv'][T262]['cases']['ecc0.8_2P']['Mmin95_mjup'], 0)} M<sub>J</sub>.
The reported NFPP&nbsp;=&nbsp;0 holds only for small apertures. In a 3-pixel aperture two wide neighbours could
supply the depth, so the protection comes from the image test, not the flux budget. Two findings weigh against it. The star sits
about 0.2 mag above the single-star sequence for its colour, and it also shows Gaia astrometric excess noise (15.2&sigma;) and RUWE
1.31, so an unresolved companion carrying roughly 15-20% of the light is likely. That would raise the radius about 10% if the
transit is on the primary, or move it to the companion. Its 24.11-d signal also ranked only ninth in its own search (stitch S/N
8.86), although Stage C's blind search ranked it first.</p>
<p><b>TIC 193718989.</b> The 9.8&Prime; neighbour would need an 83-90% eclipse with the actual PRF throughput, beyond
what a main-sequence pair can produce. ZTF DR24 detects it at normal brightness inside the predicted eclipse
window at both period parities, and the calibrated image test disfavours it. The &ldquo;4.91 versus 2.31&rdquo;
statistic was again a drift extrapolation driven by one partly covered 2020 event. The shape is
planet-like but only mildly disfavours eccentric grazing brown dwarfs (&Delta;&chi;&sup2; {fx(f193['shape']['linear']['dchi2_occultor'], 1)}-{fx(f193['shape']['season']['dchi2_occultor'], 1)}),
and Gaia RVs allow companions up to {fx(F['rv'][T193]['cases']['circular_P']['Mmin95_mjup'], 0)}-{fx(F['rv'][T193]['cases']['ecc0.8_2P']['Mmin95_mjup'], 0)} M<sub>J</sub>.</p>
<p><b>Luminosity for colour.</b> Against 71,717 Gaia stars within 100 pc, only TIC 262843927 is over-luminous for its colour
(about 0.2 mag). TIC 270573718 and TIC 193718989 sit on or slightly below the single-star sequence. The test cannot see companions
fainter than about 2-2.5 mag (<a href="#luminosity">details</a>).</p>
<p><b>Across all three.</b> Public archival work has reached diminishing returns. The remaining alternatives
(unresolved companions inside about 1-2&Prime;, diluted or eccentric eclipsing systems that fit the shape,
and for 270 the timing question) need new observations. The smallest useful ones are named in the
<a href="#synthesis">synthesis</a>.</p>
</div>
</section>"""


def inputs():
    pf = read(MAN / "protocol_freeze.json")
    dc = read(MAN / "discovery_config.json")
    rows = []
    for tic in (T270, T262, T193):
        f = F[tic]
        a = f["adopted"]
        fe = f["frozen_ephemeris"]
        secs = f["sectors_used"]
        fam = {}
        for s, au, cad in secs:
            fam.setdefault(f"{au} {cad} s", []).append(str(s))
        rows.append([f"TIC {tic}", f'{fx(a["period"], 6)} &plusmn; {fx(a["period_err"], 6)}' if a["period_err"] else f'{fx(a["period"], 6)} (no formal error: singular fit)',
                     f'{fx(a["t0_btjd"], 5)} &plusmn; {fx(a["t0_err"], 5)}' if a["t0_err"] else f'{fx(a["t0_btjd"], 5)} (no formal error)', fx(a["t14_hours"], 2),
                     f'{fx(fe["P"], 6)} &plusmn; {fx(fe["sig_P"], 6)}; T(n={int(fe["nref"])}) = {fx(fe["T_nref"], 5)} &plusmn; {fx(fe["sig_T_min"], 1)} min (&times;{fx(fe["inflation"], 2)})',
                     "; ".join(f"{k}: {','.join(v)}" for k, v in fam.items())])
    return f"""
<section id="inputs" style="display:flex;flex-direction:column;gap:12px">
<h2>Inputs, provenance and the frozen protocol</h2>
<div class="prose" style="display:flex;flex-direction:column;gap:10px">
<p>Both prior reports were read in full: <i>SEVEN CANDIDATES / CONTINUATION AUDIT</i> (26 pp., Codex bundle
<span class="mono">continue-the-seven-candidate-tess-analysis</span>) and <i>THREE TESS CANDIDATES / Further archival
constraints</i> (22 pp.). The 22-page report was not attached to the request; it was found after the protocol
freeze in <span class="mono">.claude\\tess_three_audit</span>. It concerns TIC 382098683, 188830138 and 201247574,
the current top tier, and supplied the QLP and TGLC product caveats and the TRICERATOPS source audit used here.
The original batch-1 deep-vetting report (19 pp.) and its bundle were also read. The prior numbers quoted in the
request were verified against those bundles. Every value checked reproduces, including the 0.29 / 8.19, 4.91 / 2.31
and 9.09 / 4.11 retrospective statistics, which were recomputed with the continuation's own code. The request
described one point imprecisely: the TIC 270573718 &ldquo;aperture&rdquo; series is the survey's Stage-D TESScut 1-pixel
aperture in eight sectors, not a freshly extracted series.</p>
<p>Discovery code: repository commit <span class="mono">{dc["head"][:12]}</span> (branch <span class="mono">{dc["branch"]}</span>), preset
<span class="mono">survey_k1</span>: periods 0.5-50 d, durations 0.02-0.35 d in 14 log steps, sectors &le; 98 at
native cadence, at least 3 transits, an 8,100-s search budget, then pre-gate, Stage A, S (bound_alias), B, C and D.
All inputs were opened read-only and hashed (<span class="mono">manifests/input_manifest.csv</span>; 41 groups).
The analysis protocol was frozen at {pf["frozen_utc_v1_0"]} (SHA-256 <span class="mono">{pf["sha256_v1_0"][:16]}&hellip;</span>)
before any post-discovery epoch was looked for. Four amendments are recorded in the file: A1 (report found;
TGLC and free-shape timing added), A2 (post-hoc: the empirical timing null, a neighbour-selection fix and
an RV-statistic fix), A3 (a bounded free-shape timing variant, a read-only tabulation of the discovery funnel,
and the replay's summary statistics, fixed before any injected search had run) and A4 (the colour-magnitude
over-luminosity check, added at the reader's request).</p>
<p>Times are BTJD = BJD<sub>TDB</sub> &minus; 2457000 throughout; ZTF times were converted from MJD<sub>UTC</sub> to BJD<sub>TDB</sub>
at Palomar. The packet fit stores marginal errors at cycle 0 only (none for TIC 262843927, whose central-transit
covariance is singular). The &ldquo;frozen&rdquo; column below is a conditional linear ephemeris refit to per-event
times from the discovery products, with errors inflated by &radic;&chi;&sup2;<sub>red</sub>, and fixed before any later
data were searched.</p>
</div>
{table(["Target", "packet P (d)", "packet T0 (BTJD)", "T14 (h)", "FU3 frozen linear ephemeris", "discovery products (sectors)"], rows)}
</section>"""


def census():
    z = F["ztf"]
    nb = z.get("1346023547768414976", {})
    return f"""
<section id="census" style="display:flex;flex-direction:column;gap:12px">
<h2>Public-archive census</h2>
<div class="prose" style="display:flex;flex-direction:column;gap:10px">
<p>659 receipted requests (MAST, TESScut, TCE bulk files, ExoFOP, VizieR, Gaia TAP and DataLink, IRSA ZTF, ASAS-SN,
LAMOST, RAVE, ESO, KOA, NASA Exoplanet Archive, SIMBAD and web search). Full notes and receipts are in
<span class="mono">results/census/</span>.</p>
<ul>
<li><b>No new epochs.</b> MAST holds SPOC FFIs through S109, TICA through S107 and QLP through S104. No sector after
98 contains any of the three stars. TIC 193718989 next falls on silicon in S117-S119 (May-July 2027). TIC 270573718's
S97 appears only in a TICA footprint and is off the SPOC footprint by 27 px. TIC 262843927's S31 and S88 are off the
science pixels (pixel check below). The retrospective splits are therefore the only &ldquo;recurrence&rdquo; tests possible.</li>
<li><b>Other reductions of the same photons</b> (sensitivity tests only): QLP, TARS, TGLC (fetched by direct path for
sectors 1-55, which the MAST index omits), GSFC-ELEANOR-LITE, T16, TASOC. TIC 262843927 also has SPOC 2-min data in
S1-S3.</li>
<li><b>Catalogues.</b> No SPOC TCE in 57 single- and multi-sector files (only TIC 262843927 was ever a SPOC 2-min target,
in S1-S3, where each sector holds at most two transits of low S/N). No TOI or CTOI within 2&prime;. No match in seven
TESS eclipsing-binary catalogues, ASAS-SN, ATLAS, ZTF periodic, WISE or CSS variables, or the Gaia DR3 eclipsing-binary
and non-single-star tables. Absences are not treated as negative science.</li>
<li><b>Gaia DR3 flags.</b> TIC 262843927: RUWE 1.31 and astrometric excess-noise significance 15.2, a hint of an
unresolved companion. TIC 193718989: the Discrete Source Classifier returns P(binary star) = 0.999999; its reliability
for single M dwarfs is not established here, so it is recorded as a flag only. TIC 270573718 and 193718989 are
flagged VARIABLE (SOLAR_LIKE). No Gaia source lies within 5&Prime; of any target.</li>
<li><b>Spectroscopy.</b> TIC 262843927 has two RAVE velocities (7.5 &plusmn; 2.0 and 3.1 &plusmn; 3.5 km/s) consistent
with Gaia (8.25 &plusmn; 0.51). TIC 193718989 has one LAMOST DR11 spectrum (dM0, about &minus;7.4 &plusmn; 2.0 km/s)
consistent with Gaia (&minus;5.44 &plusmn; 1.07). No high-resolution imaging or contrast curve exists for any target.</li>
<li><b>Gaia epochs.</b> {gaia_epochs_note()}</li>
<li><b>Ground time series.</b> ZTF DR24 (TIC 193718989 and eight neighbours within 60&Prime;; the 9.8&Prime; star has
{nb.get("n_clean")} clean detections). ZTF and ATLAS forced photometry need accounts and were not used. ASAS-SN light
curves were unavailable (service down since 13 October 2026).</li>
<li><b>Access failures</b> (not negative results): every ExoFOP per-target endpoint returns the literal body
&ldquo;Array&rdquo; with HTTP 200 (the bulk TOI/CTOI tables do download); the NASA Exoplanet Archive cone search was
blocked by Cloudflare (403).</li>
<li><b>Product caveats.</b> The QLP S99-S104 timing error affects none of these stars. The QLP S74-S79 fix touches only
TIC 193718989's S79 file, which is the corrected v02 and was not used by discovery.</li>
<li><b>Prior public analysis.</b> TIC 193718989 is a candidate in github.com/eumemic/exoplanets (added 2026-10-08):
P = 24.5329228 d, R<sub>p</sub> 2.58 R<sub>&#8853;</sub>, TRICERATOPS FPP 0.029 (0.011 with Gaia/MOLUSC
constraints). It uses the same TESS-SPOC photons and is not independent confirmation, but it matters for
novelty and attribution.</li>
</ul>
</div>
</section>"""


def methods():
    return """
<section id="methods" style="display:flex;flex-direction:column;gap:12px">
<h2>Methods common to all three targets</h2>
<div class="prose" style="display:flex;flex-direction:column;gap:10px">
<p><b>Events.</b> An event is admitted by coverage only (at least half the in-transit interval sampled, at least 3
in-transit and 4 baseline bins on each side). It is never admitted by its fitted sign. Each admitted event gets a
signed depth from a fixed-shape, exposure-integrated batman template with a local linear baseline (quadratic as a
check). Errors are white out-of-transit scatter times a time-averaging &beta; factor, and pooled errors are inflated by
&radic;&chi;&sup2;<sub>red</sub>.</p>
<p><b>Reductions of the same photons.</b> The discovery input (biweight-flattened); the same TESS-SPOC/QLP flux with
local baselines; pipeline SAP; the survey's Stage-D TESScut aperture; TGLC aperture and PSF; and nine predeclared FU3
TESScut extractions (radius 1.0, 1.5 and 2.0 px circles and a neighbour-excluding aperture, each with an annulus or a
plane sky, plus PRF scene photometry, run only when the scene residual is at most 10% of the target peak). These are
sensitivity tests, never independent detections.</p>
<p><b>Calibration.</b> Injections at shifted epochs with the real transits masked measure depth and timing errors per
cadence group. Random null epochs measure how often a single epoch shows a dip as deep as the median real event. For
timing, strictly periodic copies of the transit were injected at 24 phases and timed with the identical method. This
showed heavy-tailed timing errors that a robust-scatter calibration underestimates.</p>
<p><b>Host tests.</b> Per-pixel transit-decrement maps are pooled per sector, with empirical per-pixel noise from 48
off-transit control maps. The tested sources are the target, every Gaia source within 2.5 px or brighter than
G<sub>target</sub>&nbsp;+&nbsp;6 within 4 px, every TRICERATOPS nearby-scenario host, and every neighbour the flux budget finds
capable in a 1.5-3 px aperture. Each is scored by a non-negative PRF amplitude fit. The score is calibrated by injecting
the dip into the real cubes on the target and on each neighbour, using both the mission PRF and a PRF broadened by a
0.35-px Gaussian.</p>
<p><b>Flux budget.</b> Gaia G/BP/RP give TESS magnitudes (Stassun et al. 2019). Mission-PRF throughput in apertures of
1.5-3 px gives the eclipse depth each neighbour would need. A main-sequence pair removes at most about 50% of its
light, and an unresolved contaminant must lie within &Delta;T = &minus;2.5&nbsp;log<sub>10</sub>(depth/f<sub>max</sub>).</p>
<p><b>Physical models.</b> Profile-likelihood and MCMC shape fits use per-event baselines profiled analytically, with
(k, b, &rho;<sub>eff</sub>), an optional dilution and optional per-season timing offsets. The minimum eccentricity
follows from &rho;<sub>eff</sub>/&rho;<sub>&#9733;</sub> (Dawson &amp; Johnson 2012). Gaia DR3 RV constancy statistics
were converted to companion-mass limits with a relative Monte Carlo statistic. TRICERATOPS scenario weights come
from the continuation's four existing runs and 27 prior reweightings; no new draws were made.</p>
</div>
</section>"""


def chapter_270():
    t = T270
    f = F[t]
    L = loc_summary(t)
    d = f["decomposition"]
    sp = f["shape"]
    spx = f["shape_pixel"]
    mc = f["mcmc"]
    nul = f["ttv_null"]
    sec = f["secondary"]
    fpp = F["fpp"][t]["envelope"]
    excl_tics = F["fpp"][t]["image_excluded_neighbour_tics"]
    ts = F["timestamp_control"]
    y3 = [v for k, v in ts.items() if k in ("27", "28", "31", "33", "34", "37") and v]
    return f"""
<section id="tic270" style="display:flex;flex-direction:column;gap:12px">
<h2>TIC 270573718 &middot; P = 41.3837 d</h2>
<p class="prose"><b>Bottom line.</b> A real, repeating dip in the discovery data on the named target, with all catalogued
neighbours excluded as hosts by the calibrated image test. Its nature is unresolved. It is classified under
protocol rule 5.7 as <b>(ii) persistent astrophysical dip, host and nature not resolved</b>. It is not (i), a processing
artefact, because the dip is present in every target-centred raw-pixel extraction. It is not (iii), planet-favoured,
because binary alternatives are disfavoured by &Delta;&chi;&sup2; of only {fx(sp['season']['dchi2_occultor'], 1)} (PDCSAP) and
{fx(spx['season']['dchi2_occultor'], 1)} (pixel series), short of the predeclared 10.</p>

<h3>(a) Initial claim and checked provenance</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Packet fit: P = {fx(f['adopted']['period'], 6)} &plusmn; {fx(f['adopted']['period_err'], 6)} d, T0 = BTJD {fx(f['adopted']['t0_btjd'], 4)},
T14 = {fx(f['adopted']['t14_hours'], 2)} h, R<sub>&#9733;</sub> = {fx(f['stellar']['radius'], 3)} R<sub>&#9737;</sub> (TIC; Gaia GSP-Phot gives 0.509).
The discovery used 23 sectors: TESS-SPOC PDCSAP at 1800 s (S1-S11), 600 s (S27-S37) and 200 s (S61-S68), and
QLP det_flux at 200 s (S87-S98). Of 16 predicted events, 15 are admitted. S95's event is fully quality-flagged in
QLP. The QLP files are v01 and are not among the sectors with documented timing errors.</p>
<p>The contradiction, decomposed (<span class="mono">s01_270_reproduce.py</span>): the continuation's own code reproduces
0.2927 and 8.1926 exactly. Of the two series, only the corrected one has early events from 2018 (S1, S4, S5, S7) as well as
2020 (S27-S33). The aperture series' early half is S5, S27, S33 and S65. The corrected early fit finds a period
correction of {fx(d['corrected']['early_dP_min_per_cycle'], 2)} min per cycle, robust to dropping any single early sector
(S/N 0.27-0.74). Extrapolated to cycles 22-65, it shifts the predicted late transits by 1-4 h. On a common event
set the corrected value rises to 3.63. With an epoch-only early fit it is {fx(d['corrected']['epoch_only'], 2)}, and at the
reference ephemeris {fx(d['corrected']['late_at_reference'], 2)}. The aperture series gives {fx(d['aperture']['late_at_reference'], 2)}
at the reference ephemeris. The two reductions agree; the statistic does not, because it extrapolates a drift that
the data constrain poorly.</p>
</div>
{img("F8_270_decomposition.png", "decomposition of the early-predicts-late statistic",
     "Left: pooled S/N of the seven late corrected events versus a uniform timing shift; red lines mark the shifts implied by the early-half fit. Right: measured O&minus;C (PDCSAP) and the early-half linear fit extrapolated forward.")}

<h3>(b) Tests executed, data sets and results</h3>
{depth_table(t)}
{img(f"F1_{t}_event_depths.png", "event depths", "Every coverage-admitted event in six reductions, signs retained. Grey band: PDCSAP pooled depth &plusmn;1&sigma;.")}
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p><b>Timing.</b> Per-event mid-times were measured in nine reductions. All of them show the same seasonal pattern
relative to the reference ephemeris: 2018 &asymp; +8 min, 2020-21 &asymp; &minus;50 to &minus;64 min, 2023 &asymp; +20-37 min,
2024-25 &asymp; +3 to +13 min. The pipeline products, SAP, the survey TESScut aperture, TGLC aperture and PSF, and the
FU3 pixel series all agree. A timestamp control rules out the FFI clock. WASP-62 b, in the same southern-CVZ cameras,
has TESS-SPOC 600-s FFI transit times that match its SPOC 2-min times to within
{fx(min(v['weighted_mean_min'] for v in y3), 2)} to {fx(max(v['weighted_mean_min'] for v in y3), 2)} min in each 2020-21 sector.</p>
<p>Significance depends on the error model. With formal errors, a linear ephemeris fails badly
(&chi;&sup2; {fx(f['oc']['pdc_raw']['formal_lin'][0], 1)}/{f['oc']['pdc_raw']['formal_lin'][1]}). Injection-calibrated
errors reduce this to {fx(f['oc']['pdc_raw']['cal_adopted_lin'], 1)} (adopted shape) or {fx(f['oc']['pdc_raw']['cal_grazing_lin'], 1)}
(grazing shape). Strictly periodic injections into the same light curve, timed identically, reveal heavy-tailed errors:
the null season &Delta;&chi;&sup2; reaches up to {fx(nul['pdc_raw']['null_dchi2']['max'], 0)}, so the observed {fx(nul['pdc_raw']['obs_dchi2'], 1)}
has tail p = {fx(nul['pdc_raw']['tail_dchi2'], 2)}. Coherence is a different matter. The largest season-median offset in any
null run is {fx(nul['pdc_raw']['null_coh_max'], 0)} min (PDCSAP), against {fx(nul['pdc_raw']['obs_coh'], 0)} min observed with 6/6
events sharing the sign (tail p {fx(nul['pdc_raw']['tail_coh'], 2)}; similar in SAP and the pixel series). Under the predeclared rule
(section 4: &Delta;&chi;&sup2; &ge; 11.8 after inflation, the same pattern in an independent extraction, survival of
leave-one-out), the timing variation is <b>not established</b>. The grazing-calibrated leave-one-out minimum is
{fx(f['oc']['pdc_raw']['loo_min_grazing'], 1)} once S34 is dropped.</p>
{freeshape_270()}
</div>
{oc_null_table(t)}
{img(f"F2_{t}_oc.png", "O-C diagram", "Transit times relative to the reference linear ephemeris in six reductions (formal errors). Grey band: the largest season-median offset produced by 24 strictly periodic injections into the PDCSAP light curve.")}

<h3>(c) Primary-signal reliability and selection limits</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>All 15 admitted events are positive in the pipeline products, and 14-15 of 15 in every FU3 pixel extraction. Pooled
S/N is 8-12 and depths are consistent across events (p<sub>const</sub> 0.02-0.47). Random null epochs reach the median
event depth in {pct(f['null_single_event']['pdc_raw']['frac_ge_median_real'])} (PDCSAP) to
{pct(f['null_single_event']['sap_raw']['frac_ge_median_real'])} (SAP) of trials. No event lies within 0.8 d of a segment edge
or near a momentum dump or scattered-light flag. These are all re-reductions of the discovery photons. Discovery
selected the period and these events, and no later epoch exists. The selection replay is in the
<a href="#selection">Selection replay</a> section.</p>
</div>

<h3>(d) Host attribution</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>The difference images tested {L['n']} sources across {L['n_sectors']} sectors. For every neighbour with a calibrated
neighbour-hosted injection set, the observed summed &Delta;&chi;&sup2; lies above the 95th percentile of that set, under the
mission PRF and the broadened PRF alike ({len(L['excluded'])} of {len(L['excluded']) + len(L['ambiguous'])} excluded). Each observed value
falls inside the target-hosted injection range. The 34.4&Prime; G = 14.71 star needs only a 1% eclipse and
carried most of the nearby-source FPP. Its observed score is {fx(f['localization'].get('4792202914059873280', {}).get('obs'), 1)},
against a neighbour-hosted distribution centred near {fx((f['localization'].get('4792202914059873280', {}).get('nb') or {}).get('median'), 0)}.</p>
<p>The earlier &ldquo;conflict&rdquo; between image tests and FPP is explained. TRICERATOPS computes NFPP from each
neighbour's flux share in the aperture and never uses where the dimming sits in the image. Removing only the
nearby scenarios whose hosts the image test excludes (TICs {", ".join(map(str, excl_tics))}) moves the FPP from
{pct(fpp['fpp'][0])}-{pct(fpp['fpp'][1])} to {pct(fpp['image_conditioned_fpp'][0])}-{pct(fpp['image_conditioned_fpp'][1])}, and NFPP to
{fx(fpp['image_conditioned_nfpp'][0], 4)}-{fx(fpp['image_conditioned_nfpp'][1], 4)}. This is a conditional sensitivity bound, not a joint
posterior. The image test and the light curve share photons, and the image test is calibrated only for the PRF
family and perturbation tested. Unresolved companions within a few arcseconds behave like the target in these maps and
remain open. Gaia RUWE is 1.12, and Gaia finds no source within 5&Prime;.</p>
</div>
{loc_rows(t)}

<h3>(e) Planet versus binary and brown-dwarf alternatives</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Folded on a linear ephemeris, the transit looks V-shaped (best b = {fx(sp['linear']['b'], 2)}, &rho;<sub>eff</sub>
{fx(sp['linear']['rho_eff'], 2)} versus {fx(f['stellar']['rho_cgs'], 2)} g cm<sup>-3</sup>). That shape is what allowed the earlier
e&nbsp;&asymp;&nbsp;0.87 grazing companion and the 2P twins to fit as well as a planet. Freeing one timing offset per season
improves the fit by &Delta;&chi;&sup2; = {fx(sp['linear']['chi2'] - sp['season']['chi2'], 0)} for four parameters and gives a flat-bottomed
central transit: b = {fx(sp['season']['b'], 2)}, &rho;<sub>eff</sub> = {fx(sp['season']['rho_eff'], 2)}, catalogue density acceptable at
&Delta;&chi;&sup2; {fx(sp['season']['dchi2_rho_cat'], 1)}. Large occultors (k &ge; 0.3 diluted, or undiluted 0.08-0.20 R<sub>&#9737;</sub>
bodies needing e &ge; {fx(sp['season']['e_min_occultor'], 2)}) are then disfavoured by &Delta;&chi;&sup2; {fx(sp['season']['dchi2_occultor'], 1)}
in PDCSAP but only {fx(spx['season']['dchi2_occultor'], 1)} in the noisier pixel series. The shape argument therefore rests on the
timing offsets being real, and is not independent evidence for them.</p>
<p>Odd and even depths agree within 1.2&sigma; in all nine reductions, which says nothing against equal twins. A
0.52 &plusmn; 0.19 ppt dip at phase 0.5 appears in PDCSAP (phase-shift null p = {fx(sec['pdc_raw']['p_half'], 3)}). It falls to
{fx(sec['sap_raw']['half'], 2)} in SAP and to {fx(sec['fu3pix_prf']['half'], 2)}-{fx(sec['fu3pix_annulus_circ1p5']['half'], 2)} in the FU3
pixel series (p &ge; 0.07). It is not a robust secondary eclipse. If it were real it would require an eclipsing star,
because no 2 R<sub>&#8853;</sub> planet at 41 d produces a 0.5 ppt occultation. Gaia publishes no RV-constancy test at this
brightness, so there is no RV limit.</p>
</div>
{shape_table(t)}
{img(f"F3_{t}_fold.png", "folded transit", "PDCSAP/QLP events folded on the reference linear ephemeris (left) and after removing the fitted per-season timing offsets (right). Black points: 15-min bins.")}

<h3>(f) Model and prior sensitivity</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Conditional on the named target hosting an undiluted transit, with the season offsets free: {mcmc_line(t)}.
Without the offsets the geometry is grazing-ambiguous and the radius is poorly bounded. TRICERATOPS (four runs, 27
prior reweightings each) gives package FPP {pct(fpp['fpp'][0])}-{pct(fpp['fpp'][1])}, NFPP {fx(fpp['nfpp'][0], 3)}-{fx(fpp['nfpp'][1], 3)},
target-host planet weight {pct(fpp['target_planet'][0])}-{pct(fpp['target_planet'][1])} and any-host planet-label weight
{pct(fpp['any_host_planet'][0])}-{pct(fpp['any_host_planet'][1])}. Prior reweighting alone spans 1.1-98.6% FPP. None of these is a
probability that a planet exists.</p>
</div>
{fpp_rows(t)}

<h3>(g) What changed since the prior reports</h3>
<ul>
<li>The 0.29 / 8.19 contradiction is resolved: a drift extrapolation plus different event sets, not inconsistent reductions.</li>
<li>New: a season-coherent timing structure in nine reductions, not produced by strictly periodic injections and not a
clock error, but short of the claim rule.</li>
<li>New: the grazing / e&nbsp;&asymp;&nbsp;0.87 and 2P-twin shape solutions are largely produced by timing smearing. With the offsets
removed, the shape is central and planet-like.</li>
<li>New: calibrated difference images exclude every catalogued neighbour behind the 19-44% NFPP.</li>
<li>Unchanged: no new epoch exists, no RV constraint, and the half-phase dip is not robust.</li>
</ul>

<h3>(h) Viable, disfavoured and excluded-only-under-assumptions</h3>
<ul>
<li><b>Viable:</b> a sub-Neptune on the target (R<sub>p</sub> &asymp; 2.2-2.3 R<sub>&#8853;</sub>), possibly with transit-timing
variations from a non-transiting companion; a planet on an unresolved bound companion (STP); a diluted eclipsing pair
within a few arcseconds with a small radius ratio; an eclipsing pair in a hierarchical triple whose timing variations
match the pattern.</li>
<li><b>Disfavoured:</b> an undiluted grazing brown dwarf or low-mass star on the target needing e &ge; 0.8, and equal
twins at 82.77 d, but only if the season offsets are real (&Delta;&chi;&sup2; 2-8).</li>
<li><b>Excluded only under stated assumptions:</b> eclipses on any catalogued neighbour (mission and broadened PRF,
real-cube injections); a light-travel-time explanation of the timing pattern (a &plusmn;40-min amplitude over about 5 yr
needs a companion of several solar masses).</li>
</ul>

<h3>(i) Further public-data work</h3>
<p class="prose">Little remains. Re-reductions agree, and a TESS clock error is excluded. Further reprocessing of the same
photons would not test the timing structure. The next informative data are a resolved ground or space transit at the
predicted epoch with a window of at least &plusmn;2 h (linear-ephemeris 1&sigma; &asymp; {fx(f['frozen_ephemeris']['sig_T_min'], 0)} min
near the reference epoch, larger with drift), which would measure the next O&minus;C and the shape. RV monitoring would
test stellar-mass companions.</p>
</section>"""


def chapter_262():
    t = T262
    f = F[t]
    L = loc_summary(t)
    sp = f["shape"]
    sec = f["secondary"]
    fpp = F["fpp"][t]["envelope"]
    rv = F["rv"][t]["cases"]
    off = {r["sector"]: r for r in F["s262_offsilicon"]}
    p387 = read(RES / "s10b_phase0387_262843927.json")["reductions"]
    nul = f["ttv_null"]
    return f"""
<section id="tic262" style="display:flex;flex-direction:column;gap:12px">
<h2>TIC 262843927 &middot; P = 24.1089 d</h2>
<p class="prose"><b>Bottom line.</b> The cleanest of the three. The dip is real in the discovery data, and every catalogued
neighbour is excluded as host by the calibrated image test. The shape is a central transit at the catalogue density,
and Gaia RVs exclude stellar and heavy brown-dwarf companions to the target. What remains is the generic unresolved-companion
family (planet or eclipsing pair on a star within about 1-2&Prime;), which Gaia's astrometric excess noise leaves
plausible. Recommendation: join the top follow-up tier.</p>

<h3>(a) Initial claim and checked provenance</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Packet fit: P = {fx(f['adopted']['period'], 6)} d, T0 = BTJD {fx(f['adopted']['t0_btjd'], 4)}, T14 = {fx(f['adopted']['t14_hours'], 2)} h,
b &asymp; 0. No formal P or T0 error exists because the covariance is singular at b = 0. The FU3 linear refit gives
P = {fx(f['frozen_ephemeris']['P'], 6)} &plusmn; {fx(f['frozen_ephemeris']['sig_P'], 6)} d. Discovery used 15 sectors: TESS-SPOC
1800 s (S1-S4), 600 s (S28-S34) and 200 s (S61-S69), and QLP 200 s (S95-S97). The &ldquo;early-to-late 9.09 versus
4.11&rdquo; difference is a noise difference, not a timing effect: at the reference ephemeris the late halves give
{fx(f['decomposition']['corrected']['late_at_reference'], 2)} (corrected) and {fx(f['decomposition']['aperture']['late_at_reference'], 2)}
(the survey's smaller, noisier TESScut aperture), and the early fits imply negligible drift.</p>
<p><b>Sectors 31 and 88</b> (<span class="mono">s09_262_s31_s88.py</span>). Through the cutout WCS the star falls on CCD
column {fx(off[31]['target_ccd_col'], 1)} (S31, camera 4 CCD 2) and {fx(off[88]['target_ccd_col'], 1)} (S88, camera 4 CCD 3). Both
lie outside the science columns 45-2092, in the virtual overclock and underclock regions. The median image at the
target position is {fx(off[31]['ref_peak_3x3'], 2)} and {fx(off[88]['ref_peak_3x3'], 2)} e<sup>-</sup>/s, against about
{fx(off[31]['expected_peak_pixel'], 0)} e<sup>-</sup>/s expected for a T = 12.0 star. tess-point agrees that the star was not
on silicon, and no pipeline light curve exists for either sector. The prior &ldquo;gross failures&rdquo; were geometric. No
repair is possible, and these sectors are neither detections nor non-detections.</p>
</div>

<h3>(b) Tests executed, data sets and results</h3>
{depth_table(t)}
{img(f"F1_{t}_event_depths.png", "event depths", "Every coverage-admitted event in six reductions, signs retained. Grey band: PDCSAP pooled depth &plusmn;1&sigma;.")}
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p><b>Timing.</b> Formal O&minus;C scatter is large (linear &chi;&sup2; {fx(f['oc']['pdc_raw']['formal_lin'][0], 1)}/{f['oc']['pdc_raw']['formal_lin'][1]}),
driven by single events, chiefly S61 at about &minus;170 min in the pipeline products but &minus;25 min in the survey TESScut
aperture. The strictly periodic injection null reproduces this level (tail p {fx(nul['pdc_raw']['tail_dchi2'], 2)};
coherence tail {fx(nul['pdc_raw']['tail_coh'], 2)}), so there is no timing signal. The per-season offsets in the shape fit are
within &plusmn;9 min.</p>
<p><b>Phase 0.387.</b> The earlier nominal 8.9&sigma; feature re-measures at {fx(p387['pdc_raw']['pooled']['depth_ppt'], 3)} &plusmn;
{fx(p387['pdc_raw']['pooled']['err_ppt'], 3)} ppt (PDCSAP) and between 0.01 and 0.15 ppt in all nine reductions. Individual epochs
are inconsistent with a constant depth. The earlier calibrated global p = 0.493 stands, and no secondary is claimed.</p>
</div>

<h3>(c) Primary-signal reliability and selection limits</h3>
{spoc2min_262()}
<p class="prose">13-15 of 13-15 admitted events are positive in the pipeline products, and 15-16 of 16 in the FU3 pixel series.
Pooled S/N is 10-12.6 (pipeline) and 6.7-11.8 (pixel series). Random null epochs reach the median event depth in
{pct(f['null_single_event']['survey_detrended']['frac_ge_median_real'])}-{pct(f['null_single_event']['survey_tesscut_aperture']['frac_ge_median_real'])}
of trials. The S1-S3 SPOC 2-min data are the same epochs and add no independent test. No later epoch exists.</p>

<h3>(d) Host attribution</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>The reported NFPP = 0 came from TRICERATOPS's admission rule: no catalogued neighbour can make the 1.2 ppt dip in its
aperture. That is true in small apertures. In the FU3 1.5-px aperture the nearest capable neighbour would need more than a
100% eclipse. In a 3-px aperture, two wide stars could supply it (65&Prime;, &Delta;T 3.9, about 9%; 103&Prime;,
&Delta;T 1.9, about 20%). The calibrated image test settles this. All {L['n']} tested sources score
&Sigma;&Delta;&chi;&sup2; +42 to +62 over {L['n_sectors']} sectors, inside the target-hosted injection range. Every neighbour-hosted
injection set lies far below, for both PRF versions ({len(L['excluded'])} of {L['n']} excluded).</p>
<p>The open family is unresolved companions. Gaia DR3 gives RUWE 1.31 and an astrometric excess-noise significance of
15.2, which is suggestive of a companion but not proof. TRICERATOPS's residual FPP is almost entirely STP (a planet on an
unresolved bound companion). An unresolved eclipsing contaminant must have &Delta;T &le; {fx(f['flux_budget']['unresolved']['f_max_1'], 2)}
(&le; {fx(f['flux_budget']['unresolved']['f_max_0p5'], 2)} for a main-sequence pair). No contrast curve exists.</p>
</div>
{loc_rows(t)}

<h3>(e) Planet versus binary and brown-dwarf alternatives</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Shape: k = {fx(sp['linear']['k'], 4)}, central (b {fx(sp['linear']['b'], 2)}-{fx(sp['season']['b'], 2)}), &rho;<sub>eff</sub>
{fx(sp['linear']['rho_eff'], 2)} versus {fx(f['stellar']['rho_cgs'], 2)} catalogue (e<sub>min</sub> {fx(sp['linear']['e_min'], 2)}). Large occultors are disfavoured:
diluted k &ge; 0.3 at &Delta;&chi;&sup2; {fx(sp['linear']['dchi2_k_ge_0p3'], 1)}, undiluted 0.08-0.20 R<sub>&#9737;</sub> bodies at
{fx(sp['linear']['dchi2_occultor'], 1)}-{fx(sp['season']['dchi2_occultor'], 1)}, which would need e &ge; {fx(sp['linear']['e_min_occultor'], 2)}. Equal twins at
48.218 d imply k &asymp; 1 and fall in the same disfavoured region. Odd and even depths agree within 1.9&sigma;.</p>
<p>The phase-0.5 depth is {fx(sec['pdc_raw']['half'], 3)} &plusmn; {fx(sec['pdc_raw']['half_err'], 3)} ppt (PDCSAP). A circular eclipsing
binary at P would therefore need a secondary below about 0.17 ppt, roughly 14% of the primary, which requires a companion
much cooler than the eclipsed star. The earlier 2-ppt secondary-search sensitivity could not constrain diluted eclipses of
this depth at all. Gaia RV constancy (23 transits, p = 0.977) limits a companion to the target, for the named target as
host: M&nbsp;sin&nbsp;i &lt; {fx(rv['circular_P']['Mmin95_mjup'], 0)} M<sub>J</sub> (circular, P), {fx(rv['ecc0.8_P']['Mmin95_mjup'], 0)} (e = 0.8),
{fx(rv['circular_2P']['Mmin95_mjup'], 0)}-{fx(rv['ecc0.8_2P']['Mmin95_mjup'], 0)} at 2P. This excludes stellar and heavy brown-dwarf occultors on the
target. It says nothing about a blended pair, whose lines would not move the target's.</p>
</div>
{shape_table(t)}
{img(f"F3_{t}_fold.png", "folded transit", "PDCSAP events folded on the reference ephemeris. Black points: 15-min bins; red: best free-geometry model.")}

<h3>(f) Model and prior sensitivity</h3>
<p class="prose">Conditional on the target hosting an undiluted transit: {mcmc_line(t)}. TRICERATOPS: FPP
{pct(fpp['fpp'][0])}-{pct(fpp['fpp'][1])}, NFPP 0, target-host planet weight {pct(fpp['target_planet'][0])}-{pct(fpp['target_planet'][1])},
any-host planet-label weight about 100%. Prior reweighting spans 0.15-28.7% FPP. These are conditional scenario weights,
not a validation: the STP prior and Gaia completeness at small separations dominate them.</p>
{fpp_rows(t)}

<h3>(g) What changed since the prior reports</h3>
<ul>
<li>The S31/S88 failures are explained as off-silicon geometry, not PRF, noise or crowding problems.</li>
<li>NFPP = 0 is aperture-dependent. In a 3-px aperture two wide neighbours could supply the depth. The calibrated image test,
not the flux rule, excludes them.</li>
<li>New: Gaia RV mass limits on the target (M&nbsp;sin&nbsp;i &lt; 20-28 M<sub>J</sub>) and the large-occultor shape penalty with timing
nuisance parameters.</li>
<li>Radius now has a finite posterior: about 1.9-2.0 R<sub>&#8853;</sub>, consistent with the prior 1.82-2.41 profile range.</li>
<li>The phase-0.387 feature stays unsupported, and the 9.09 / 4.11 split is explained by aperture noise.</li>
</ul>

<h3>(h) Viable, disfavoured and excluded-only-under-assumptions</h3>
<ul>
<li><b>Viable:</b> a 1.9-2.0 R<sub>&#8853;</sub> planet on the target in a low-eccentricity orbit; a planet on an unresolved bound companion
(STP, favoured by the astrometric noise if the companion is real); a diluted eclipsing pair with a small radius ratio on a
star within about 1-2&Prime;.</li>
<li><b>Disfavoured:</b> grazing or eccentric brown dwarfs and low-mass stars on the target (shape &Delta;&chi;&sup2; &asymp; 11, RV); diluted
pairs with radius ratio &ge; 0.3, including equal twins at 2P (&Delta;&chi;&sup2; &asymp; 11).</li>
<li><b>Excluded only under stated assumptions:</b> any catalogued neighbour as host (mission and broadened PRF injections); a
companion to the target above about 20-28 M<sub>J</sub> (Gaia RV error model).</li>
</ul>

<h3>(i) Further public-data work</h3>
<p class="prose">Little remains. The SPOC 2-min S1-S3 light curves could refine the ingress shape slightly, but cover the
same epochs. The decisive next data are high-resolution imaging (to test the companion that Gaia's excess noise hints at)
and a ground transit with resolved photometry, followed by RVs.</p>
</section>"""


def chapter_193():
    t = T193
    f = F[t]
    L = loc_summary(t)
    sp = f["shape"]
    sec = f["secondary"]
    fpp = F["fpp"][t]["envelope"]
    rv = F["rv"][t]["cases"]
    z = F["ztf"]["1346023547768414976"]
    zc = z.get("core_weighted_flux_ratio") or {}
    nb98 = f["localization"].get("1346023547768414976", {})
    nul = f["ttv_null"]
    fb = {r["id"]: r for r in read(RES / f"s13_fluxbudget_{t}.json")["neighbours_ranked"]}
    need98 = fb.get("1346023547768414976", {}).get("eclipse_needed")
    bands = ", ".join(f"{k} {v}" for k, v in z["bands"].items())
    return f"""
<section id="tic193" style="display:flex;flex-direction:column;gap:12px">
<h2>TIC 193718989 &middot; P = 24.5329 d</h2>
<p class="prose"><b>Bottom line.</b> The archival ground data and the blend analysis improve host attribution materially.
The 9.8&Prime; neighbour is disfavoured by three lines: it would need an 83-90% eclipse, ZTF sees it at normal brightness
inside the eclipse window, and the calibrated image test favours the target. The planet interpretation is weaker
than for TIC 262843927, because the transit shape only mildly disfavours eccentric grazing brown dwarfs and Gaia
RVs allow companions up to about 70-124 M<sub>J</sub>. Recommendation: join the top tier, ranked below TIC 262843927. A
resolved transit is no longer needed for the 9.8&Prime; star, but is still the cleanest test of everything closer.</p>

<h3>(a) Initial claim and checked provenance</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Packet fit: P = {fx(f['adopted']['period'], 6)} &plusmn; {fx(f['adopted']['period_err'], 6)} d, T0 = BTJD {fx(f['adopted']['t0_btjd'], 4)},
T14 = {fx(f['adopted']['t14_hours'], 2)} h. Discovery used 7 sectors: TESS-SPOC 1800 s (S25, S26), 600 s (S40, S52, S53) and 200 s
(S79, S80). All 8 events are admitted. The &ldquo;4.91 versus 2.31&rdquo; retrospective values reproduce exactly. Both are depressed by
the early-half drift fit ({fx(f['decomposition']['corrected']['early_dP_min_per_cycle'], 2)} min per cycle), which is driven by
the partly covered S26 event; dropping S26 restores 9.35. At the reference ephemeris the late halves give
{fx(f['decomposition']['corrected']['late_at_reference'], 2)} and {fx(f['decomposition']['aperture']['late_at_reference'], 2)}. An independent public
analysis (eumemic) finds the same signal in the same photons.</p>
</div>

<h3>(b) Tests executed, data sets and results</h3>
{depth_table(t)}
{img(f"F1_{t}_event_depths.png", "event depths", "Every coverage-admitted event in six reductions, signs retained. Grey band: PDCSAP pooled depth &plusmn;1&sigma;.")}
<p class="prose">Timing scatter in individual events (S26 &minus;44 min, S52 +45 min) depends on the reduction. The FU3 1.5-px
series is perfectly linear (&chi;&sup2; 2.5/5), and the strictly periodic null reproduces the PDCSAP scatter (tail p
{fx(nul['pdc_raw']['tail_dchi2'], 2)}). There is no timing signal.</p>

<h3>(c) Primary-signal reliability and selection limits</h3>
<p class="prose">8 of 8 events are positive in every pipeline product, and 7-8 of 8 in the pixel series. Pooled S/N is 11.4-11.8
(pipeline) and 5-10 (pixel series). Random null epochs reach the median event depth in 0-2% of trials. These are the
discovery photons only; the next TESS epoch is in 2027.</p>

<h3>(d) Host attribution: the 9.8&Prime; neighbour and others</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p><b>Flux budget.</b> Gaia DR3 1346023547768414976 (G 19.59, BP&minus;RP 1.85, 9.8&Prime;) has T &asymp; 18.8, &Delta;T 6.4 from the
target. With mission-PRF throughput it would need to lose {pct(need98, 0)} of its own light in the most favourable
aperture and sector (0.83-0.90 across sectors with an RP-band flux ratio instead of T). That is beyond the roughly 50% a main-sequence pair can produce. The earlier
74% came from equal throughput and the RP band. TRICERATOPS assigned this star no weight, consistent with that physics.</p>
<p><b>ZTF DR24</b> (detections only; forced photometry is account-gated and was not used). The star has {z['n_clean']} clean
detections ({bands}). Using the frozen ephemeris and its inflated covariance, propagated to each ZTF timestamp,
{z['n_nominal_in_window']} detections fall inside the nominal eclipse window, against
{fx(z['censoring']['expected_in_window_if_no_eclipse'], 1)} expected if the star never dims. There is no censoring deficit,
although a deep eclipse would push it below the single-epoch limit. Two detections lie robustly inside the window even
after a 3&sigma; timing allowance. Both are even-parity cycles, at flux {fx(zc.get('mean'), 3)} &plusmn; {fx(zc.get('err'), 3)} of normal,
so any eclipse there is shallower than {pct(zc.get('depth_upper95'), 0)} (95%). Odd-parity detections 0.6-1.1 h from
predicted mid-eclipse are also at normal brightness, apart from one 0.46-mag-faint point next to a normal one in
the same visit. Of the grid of eclipse models (depth 50-100%, durations 0.8-1.2 T14, &plusmn;3&sigma; timing),
{pct(z['grid_excluded_fraction_f_ge_0p5'], 0)} are contradicted by at least one detection.</p>
<p><b>Image test.</b> The observed &Sigma;&Delta;&chi;&sup2; for this star is {fx(nb98.get('obs'), 1)}. Target-hosted injections give a
median of {fx((nb98.get('tgt') or {}).get('median'), 1)}, and dips injected on the neighbour give a median of
{fx((nb98.get('nb') or {}).get('median'), 1)} (95th percentile {fx((nb98.get('nb') or {}).get('p95'), 1)};
{fx((nb98.get('nb_broad') or {}).get('p95'), 1)} with the broadened PRF). At 0.5 px separation the two hypotheses overlap more
than for distant stars, so this line is the weakest of the three. The fitted single-source centroids scatter 2.5-9.3&Prime;
in directions unrelated to the neighbour (mean cosine about &minus;0.05).</p>
<p>Across all {L['n']} tested sources over {L['n_sectors']} sectors, including the brighter stars at 65&Prime; and 117&Prime;
that could supply the depth in large apertures, {len(L['excluded'])} of {len(L['excluded']) + len(L['ambiguous'])} with a neighbour-hosted
injection set are excluded under both PRF versions. The rest are consistent with a target host. Remaining: unresolved
companions within about 1-2&Prime; (Gaia RUWE 1.04, no Gaia source within 5&Prime;, DSC binary flag recorded, no
contrast curve).</p>
</div>
{img("F6_ztf_193_neighbour.png", "ZTF neighbour", "ZTF DR24 detections of the 9.8&Prime; neighbour within 6 h of predicted events, as flux relative to its own median. Horizontal bars: propagated 1&sigma; timing. Black line: the eclipse it would need, at nominal timing. Detections only; non-detections are not available.")}
{loc_rows(t)}

<h3>(e) Planet versus binary and brown-dwarf alternatives</h3>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Shape: k = {fx(sp['linear']['k'], 4)}, b {fx(sp['linear']['b'], 2)}-{fx(sp['season']['b'], 2)}, &rho;<sub>eff</sub> {fx(sp['linear']['rho_eff'], 2)} versus
{fx(f['stellar']['rho_cgs'], 2)} catalogue (e<sub>min</sub> {fx(sp['linear']['e_min'], 2)}). Undiluted 0.08-0.20 R<sub>&#9737;</sub> occultors are
disfavoured only by &Delta;&chi;&sup2; {fx(sp['linear']['dchi2_occultor'], 1)}-{fx(sp['season']['dchi2_occultor'], 1)} and would need
e &ge; {fx(sp['linear']['e_min_occultor'], 2)}. Diluted k &ge; 0.3 pairs, including equal twins at 49.066 d, are disfavoured by
{fx(sp['linear']['dchi2_k_ge_0p3'], 1)}-{fx(sp['season']['dchi2_k_ge_0p3'], 1)}. Odd and even depths agree within 1&sigma;. The phase-0.5 depth is
{fx(sec['pdc_raw']['half'], 2)} &plusmn; {fx(sec['pdc_raw']['half_err'], 2)} ppt (null p {fx(sec['pdc_raw']['p_half'], 2)}), not significant
and not reproduced in the PRF series. Gaia RV constancy (21 transits, p = 0.18) limits a companion to the target to
M&nbsp;sin&nbsp;i &lt; {fx(rv['circular_P']['Mmin95_mjup'], 0)} M<sub>J</sub> (circular), {fx(rv['ecc0.8_P']['Mmin95_mjup'], 0)} (e = 0.8),
{fx(rv['circular_2P']['Mmin95_mjup'], 0)}-{fx(rv['ecc0.8_2P']['Mmin95_mjup'], 0)} at 2P. This excludes most stars but not brown dwarfs.</p>
<p>Weighing population priors: the surviving target-host brown-dwarf solutions need e &asymp; 0.83 and a grazing chord. Brown
dwarfs around M dwarfs at 25-50 d are rare (the &ldquo;desert&rdquo;), and the grazing geometry occupies a small fraction of
transiting orientations. These solutions exist geometrically but carry low prior weight. Two caveats: this is not a
calibrated probability, and the Gaia RV limit does not reach them.</p>
</div>
{shape_table(t)}
{img(f"F3_{t}_fold.png", "folded transit", "PDCSAP events folded on the reference ephemeris. Black points: 15-min bins; red: best free-geometry model.")}

<h3>(f) Model and prior sensitivity</h3>
<p class="prose">Conditional on an undiluted transit of the target: {mcmc_line(t)}. TRICERATOPS: FPP {pct(fpp['fpp'][0])}-{pct(fpp['fpp'][1])},
NFPP {fx(fpp['nfpp'][0], 4)}-{fx(fpp['nfpp'][1], 4)}, target-host planet weight {pct(fpp['target_planet'][0])}-{pct(fpp['target_planet'][1])}.
Prior reweighting spans 0.17-42.3% FPP. The residual FPP is almost entirely STP.</p>
{fpp_rows(t)}

<h3>(g) What changed since the prior reports</h3>
<ul>
<li>The 9.8&Prime; neighbour moves from &ldquo;needs about 74%, ZTF limit from three nights&rdquo; to disfavoured by three
largely independent lines (main-sequence depth ceiling, timing-propagated ZTF detections at both parities, calibrated image injections).</li>
<li>The 4.91 / 2.31 values are explained by one event's timing and the drift extrapolation.</li>
<li>New: Gaia RV mass limits, finite radius posterior (about 2.6-2.7 R<sub>&#8853;</sub>), and the brightness limit for an unresolved contaminant.</li>
<li>Unchanged: no independent epoch, and eccentric grazing brown dwarfs survive at low prior weight.</li>
</ul>

<h3>(h) Viable, disfavoured and excluded-only-under-assumptions</h3>
<ul>
<li><b>Viable:</b> a 2.6-2.7 R<sub>&#8853;</sub> planet on the target; a planet on an unresolved bound companion (STP); a diluted
small-radius-ratio pair within about 1-2&Prime;; an eccentric (e &asymp; 0.83) grazing brown dwarf on the target.</li>
<li><b>Disfavoured:</b> equal twins at 2P and other diluted pairs with radius ratio &ge; 0.3 (&Delta;&chi;&sup2; 2.4-5).</li>
<li><b>Excluded only under stated assumptions:</b> the 9.8&Prime; neighbour (main-sequence pair, ZTF timing propagation, PRF
injections); other catalogued neighbours (image injections); stellar-mass companions to the target above about 70-90
M<sub>J</sub> in circular orbits (Gaia RV error model).</li>
</ul>

<h3>(i) Further public-data work</h3>
<p class="prose">Little remains. ZTF forced photometry would extend the neighbour test to non-detections, but needs an account.
Better is a resolved multiband transit, which measures the target's depth directly (the neighbour is 9.8&Prime;
away), followed by RVs reaching the brown-dwarf regime (K &asymp; 1-7 km/s) and high-resolution imaging.</p>
</section>"""


def selection(replay_tbl, meta):
    s18 = {}
    for tic in (T270, T262, T193):
        p = RES / f"s18_longp_{tic}.json"
        if p.exists():
            s18[tic] = read(p)
    lp_rows = []
    for tic, d in s18.items():
        for red, v in d["reductions"].items():
            top = v["long_band_peaks"][:3]
            res = v["masked_residual_peaks"][:3]
            lp_rows.append([f"TIC {tic}", red, f'{d["band"][0]:.0f}-{d["band"][1]:.0f} d',
                            "; ".join(f'{q["period"]:.3f} d ({q["ratio_to_P"]:.3f} P, SDE {q["sde_like"]:.1f})' for q in top),
                            "; ".join(f'{q["period"]:.3f} d (SDE {q["sde_like"]:.1f}, {q["depth_ppt"]:.2f} ppt)' for q in res)])
    lp = table(["Target", "series", "band", "top long-period peaks", "top peaks after masking the candidate's transits"], lp_rows) if lp_rows else \
        "<p class='note'>The targeted long-period searches had not finished when this version was built.</p>"
    done_note = (f"Finished {meta.get('finished')}: {meta.get('n_done')} of {meta.get('n_planned')} searches, "
                 f"{fx(meta.get('cpu_h'), 1)} CPU-h used" + (", stopped by the budget" if meta.get("budget_hit") else "") + "."
                 if meta.get("finished") else
                 f"<b>In progress when this version was built</b> ({meta.get('n_done')} of {meta.get('n_planned')} searches finished, "
                 f"{meta.get('n_complete')} of them with all Stage A jobs finished; {fx(meta.get('cpu_h'), 1)} CPU-h of 24 used). "
                 f"The tables count only stars whose Stage A jobs have finished; all counts are partial.")
    not_run = meta.get("not_run") or []
    nr_note = (f" Not run because of the budget: {len(not_run)} searches ({', '.join(not_run)})." if not_run and meta.get("finished") else "")
    ctx = read(RES / "s08b_discovery_context.json")
    ps, ss = ctx["per_stage_decisions"], ctx["star_stats"]
    f_rows = []
    for tic in (T270, T262, T193):
        for c in ctx["targets"][tic]["candidates"]:
            fate = c["fate"]
            f_rows.append([f"TIC {tic}", str(c["search_rank"]), fx(c["period_d"], 4), fx(c["stitch_snr"], 2), str(c["stitch_n_transits"]),
                           " &rarr; ".join(f"{st} {fate[st]}" for st in ("A", "S", "B", "C") if st in fate)])
    t_funnel = table(["Star", "search rank", "period (d)", "stitch S/N", "transits", "discovery funnel"], f_rows)
    inv, inj = meta.get("inv") or {}, meta.get("inj") or {}
    g = inv.get("all") or {}
    if g.get("done"):
        surv = ps["C"].get("PASS", 0) / max(ps["A"].get("PASS", 1), 1)
        inv_txt = (f"<p><b>Null result.</b> The {g['done']} inverted light curves searched gave {g['pregate']} pre-gate candidates, "
                   f"with stitch S/N up to {fx(g['max_pregate_snr'], 1)}, well above the three real candidates (8.9-10.4). Search S/N alone "
                   f"therefore does not separate these signals from noise. Stage A does: "
                   + (f"none of the {g['n_A']} inverted candidates passed it. With {g['done']} stars and no passes, the per-star rate of noise-only "
                      f"Stage A passes is below {pct(g['ul95_star_A_rate'], 0)} (95%). That bound is too weak to make the batch's survivors secure by "
                      f"itself: at the bound, the {ss['A']['stars_with_job']:,} batch-1 stars with a pre-gate candidate could yield up to about "
                      f"{g['ul95_star_A_rate'] * ss['A']['stars_with_job'] * surv:.0f} noise signals reaching Stage C (using the observed "
                      f"{pct(surv, 0)} Stage A&rarr;C survival of real-data passes, an assumption for noise), against "
                      f"{ps['C'].get('PASS', 0)} actual Stage C survivors. The replay shows that Stage A is not easily fooled by the same noise; each signal's "
                      f"security still rests on its own per-event and per-reduction evidence."
                      if g["n_A_pass"] == 0 else
                      f"{g['n_A_pass']} of the {g['n_A']} inverted candidates passed it, on {g['stars_with_A_pass']} of {g['done']} stars "
                      f"(periods: {'; '.join(', '.join(f'{x:.2f} d' for x in a['periods']) for a in g['a_pass_list'])}). Noise and inverted "
                      f"systematics can pass Stage A at that rate, so a Stage A pass by itself carries little weight.") + "</p>")
    else:
        inv_txt = ""
    inj_bits = []
    for tic in (T270, T262, T193):
        q = inj.get(tic) or {}
        if not q.get("done"):
            continue
        d = q["discovery"]
        frac = q["frac_A"]
        txt = (f"TIC {tic}'s transit was recovered through Stage A on {q['recovered_A']} of {q['done']} matched stars "
               f"(pre-gate match {q['recovered_pregate']} of {q['done']})")
        if q["matched_stitch_snr"]:
            above = q["n_matched_above_discovery"]
            txt += (f"; recovered stitch S/N median {fx(q['median_matched_snr'], 1)} against the real candidate's {fx(d['stitch_snr'], 2)}"
                    f" ({above} of {len(q['matched_stitch_snr'])} recoveries at or above it)")
        if frac is not None and frac < 0.5:
            txt += (". Most injections of this signal were missed, so the real detection was partly fortunate, and its measured depth "
                    "is more likely to be biased high by selection")
        inj_bits.append(txt + ".")
    inj_txt = (f"<p><b>Recovery.</b> {' '.join(inj_bits)} Recovery of 5-6 in 8 means the search finds signals like these most of "
               f"the time but not always. Each real candidate's discovery S/N lies inside the range its injections reached, so the "
               f"replay shows no sign that the measured depths are strongly inflated by selection. With 8 injections per candidate "
               f"this is a coarse check.</p>") if inj_bits else ""
    return f"""
<section id="selection" style="display:flex;flex-direction:column;gap:12px">
<h2>Discovery selection: the funnel and a bounded replay</h2>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p><b>The funnel that chose these signals.</b> S1 batch 1 searched {ctx['n_searched']:,} stars. {ss['A']['stars_with_job']:,} stars produced at least one
pre-gate candidate ({sum(ps['A'].values()):,} in all). Stage A passed {ps['A'].get('PASS', 0)} of them on {ss['A']['stars_with_pass']} stars
({ss['A']['stars_with_2plus_pass']} stars had two or more), Stages S and B passed {ps['S'].get('PASS', 0)} and {ps['B'].get('PASS', 0)}, and Stage C's blind
search passed {ps['C'].get('PASS', 0)}, one per star. Review then kept 23 SUBMIT/HOLD stars, the earlier continuation took seven, and these three come
from those seven. All three passed every stage. The table lists each pre-gate candidate on the three stars.</p>
<p>The unfavourable fact is TIC 262843927. Its 24.11-d signal ranked only ninth in its own search (stitch S/N 8.86, the lowest of the
three), behind eight others on the same star, including several stronger but spurious ones. Two other periods on that star (14.52 d and
30.23 d) also passed Stages A, S and B and failed only at Stage C, because the blind TLS's strongest peak was at 106.67 d. For the
24.11-d candidate the blind TLS's strongest peak was the candidate itself (SDE 25.9). The light curve of this star is busy, and the
signal was found near the search threshold. TIC 270573718 and TIC 193718989 were their stars' top-ranked signals.</p>
</div>
{t_funnel}
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>The frozen search (<span class="mono">survey.run_job</span>, preset survey_k1, 8,100-s budget, identical pre-gate) and Stage A
(<span class="mono">funnel_k2.py</span>, S mode bound_alias, C variant V3) were run in an isolated data root on fixed sets,
chosen before any flux was read. The sets are the three targets' light curves with the sign inverted (dips become bumps),
24 inverted matched controls from batch 1 (same slice, |&Delta;Tmag| &le; 0.5, usable sectors within &plusmn;30%), and 24
other matched controls with each candidate's own transit injected by the frozen injection code at a random epoch.
Limits: 24 CPU-h and 4 workers, with no extension. {done_note}{nr_note}</p>
<p>What this covers: the search's look-elsewhere space over 0.5-50 d, its grids, gaps and budget, and the pre-gate and
Stage A cuts, on matched noise. What it does not cover: the S/B/C/D stages, the human/Codex review that picked seven of
the 23 SUBMIT/HOLD stars, and batch-to-batch choices. Inverted light curves are only a partial null, because
asymmetric systematics (PDC-made dips) do not invert symmetrically. The survey's own K1 calibration on 250 uninjected
stars found 0.088 natural candidates per star surviving Stage S. Those are real-star false alarms (systematics,
variables, binaries), not pure noise.</p>
</div>
{replay_tbl}
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
{inv_txt}
{inj_txt}
<p>Twice-period and long-period checks (targeted; not part of the survey's look-elsewhere space): Stage C's blind TLS (0.5-110 d)
already ranked P first for all three, with 2P peaks lower (TIC 270573718: 82.77 d at SDE 40.3 versus 58.2 at P; TIC 193718989:
49.07 d at SDE 16.4 versus 37.9). The targeted box searches beyond the 50-day ceiling are below.</p>
</div>
{lp}
<p class="note">Reading the table: in the discovery input, the long-band peaks are aliases of P (2P, 3P, 1.5P) or weak
(SDE about 6). No long-period solution beats the reported period, and no 2P alias stands out where odd/even depths agree.
After the candidate's transits are masked, no residual peak exceeds SDE about 7. In the FU3 pixel series (outliers not
clipped), the residual peaks are driven by isolated outlier points (implied depths above 100 ppt) and are not interpreted.</p>
</section>"""


def luminosity():
    """Amendment A4 (user request 2026-10-19): position of each target relative to the single-star sequence."""
    p = RES / "s22_cmd.json"
    if not p.exists():
        return ""
    d = read(p)
    lab = {"MG_vs_BPRP": "M<sub>G</sub> vs BP&minus;RP", "MG_vs_GRP": "M<sub>G</sub> vs G&minus;RP",
           "MKs_vs_BPRP": "M<sub>Ks</sub> vs BP&minus;RP", "MKs_vs_GKs": "M<sub>Ks</sub> vs G&minus;Ks"}
    rows = []
    for tic in (T270, T262, T193):
        v = d["targets"][tic]
        for k, name in lab.items():
            r = v.get(k) or {}
            if "dM" not in r:
                continue
            q = r["clean_quantiles"]
            rows.append([f"TIC {tic}" if k == "MG_vs_BPRP" else "", name, f"{r['dM']:+.2f}", pct(r["frac_clean_as_bright"], 0),
                         f"{q['16']:+.2f} to {q['84']:+.2f}", pct(r["frac_clean_faint_enough_for_twin"], 0),
                         f"{v['ruwe']:.2f} / {v['aen_sig']:.1f}" if k == "MG_vs_BPRP" else ""])
    t = table(["Target", "diagram", "&Delta;M (mag; negative = brighter than the ridge)", "clean stars at this colour at least as bright",
               "clean-star 16-84% range", "clean stars faint enough to be half of an equal-mass pair", "Gaia RUWE / excess-noise significance"], rows)
    g = d["targets"][T262]
    dms = [g[k]["dM"] for k in lab if "dM" in g.get(k, {})]
    dmag = [g[k]["implied_companion_dmag"] for k in lab if g.get(k, {}).get("implied_companion_dmag")]
    frac = [10 ** (-0.4 * x) / (1 + 10 ** (-0.4 * x)) for x in dmag]
    tw = [g[k]["frac_clean_faint_enough_for_twin"] for k in lab]
    tw_o3 = [d["targets"][x][k]["frac_clean_faint_enough_for_twin"] for x in (T270, T193) for k in ("MG_vs_BPRP", "MG_vs_GRP", "MKs_vs_BPRP")]
    tw_o = tw_o3 + [d["targets"][x]["MKs_vs_GKs"]["frac_clean_faint_enough_for_twin"] for x in (T270, T193)]
    return f"""
<section id="luminosity" style="display:flex;flex-direction:column;gap:12px">
<h2>Is each star over-luminous for its colour?</h2>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>An unresolved companion of similar brightness lifts a star above the single-star main sequence at its colour. An
equal-mass pair sits 0.75 mag above it, a companion 1.5 mag fainter about 0.24 mag above, and one 3 mag fainter only
0.07 mag above. This check was added at the reader's request (amendment A4). Each target was placed on four empirical
colour-magnitude diagrams built from Gaia DR3 stars within 100 pc ({d['n_pass_cstar']:,} after the BP/RP flux-excess cut), with
2MASS Ks from Gaia's own cross-match. The reference is the single-star ridge, the most common absolute magnitude at each colour
among {d['n_clean']:,} clean stars (RUWE &lt; 1.2, no Gaia binary solution, no multi-peak flag). Metallicity spreads single stars
around that ridge, and the spread measured from the same clean stars is given below. Extinction is neglected at 85 pc.</p>
</div>
{t}
{img("F10_cmd_luminosity.png", "colour-magnitude diagrams", "The three targets against Gaia DR3 stars within 100 pc. Teal: single-star ridge (most common absolute magnitude of clean stars at each colour). Red dashed: where an equal-mass pair of ridge stars would sit.")}
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p><b>TIC 262843927 is mildly over-luminous</b> in all four diagrams (&Delta;M {max(dms):+.2f} to {min(dms):+.2f} mag). Only
{pct(min(g[k]['frac_clean_as_bright'] for k in lab), 0)}-{pct(max(g[k]['frac_clean_as_bright'] for k in lab), 0)} of clean stars at its
colour are as bright. On its own that is inside the single-star spread, because a metal-rich single star can sit there. It does not
stand alone. This is also the only target with an elevated RUWE ({g['ruwe']:.2f}) and a significant astrometric excess noise
({g['aen_sig']:.1f}&sigma;), and those measure the image's motion and shape, not its brightness. Together they make an unresolved
companion the most economical reading, though not a proven one. If the primary sits on the ridge, the companion is about
{min(dmag):.1f}-{max(dmag):.1f} mag fainter in G and carries {pct(min(frac), 0)}-{pct(max(frac), 0)} of the light. An equal-mass pair is
disfavoured but not excluded: {pct(min(tw), 0)}-{pct(max(tw), 0)} of clean single stars at this colour are faint enough to make
one look like this star. The consequences for the transit are as follows. If it is on the primary, the depth is diluted and the radius rises by about
{100 * (1 / np.sqrt(1 - min(frac)) - 1):.0f}-{100 * (1 / np.sqrt(1 - max(frac)) - 1):.0f}% (up to about 41% for an equal pair). If it is on the companion,
the undiluted depth is about {1.2 / max(frac):.0f}-{1.2 / min(frac):.0f} ppt on an M2-M3 dwarf, a body of roughly 3-4 R<sub>&oplus;</sub>.
The transit duration's agreement with the primary's density would then be a coincidence. The diluted-pair cases are
already inside the dilution-free k-profiles. High-resolution imaging, already the recommended first observation for this star,
tests the companion directly.</p>
<p><b>TIC 270573718 and TIC 193718989 are not over-luminous.</b> TIC 270573718 sits slightly below the ridge
(&Delta;M {min(d['targets'][T270][k]['dM'] for k in lab):+.2f} to {max(d['targets'][T270][k]['dM'] for k in lab):+.2f} mag) and TIC 193718989
on it ({min(d['targets'][T193][k]['dM'] for k in lab):+.2f} to {max(d['targets'][T193][k]['dM'] for k in lab):+.2f} mag). Both have RUWE near 1
and no astrometric excess noise. An equal-mass pair would need the primary to lie in the faintest
{pct(min(tw_o), 0)}-{pct(max(tw_o), 0)} of single stars at those colours ({pct(max(tw_o3), 0)} or less in the three diagrams with the
narrower single-star spread). For TIC 193718989 this does not support Gaia's
DSC &ldquo;binary&rdquo; probability (0.999999), which is derived from the low-resolution spectra rather than the colour-magnitude position.</p>
<p><b>Limit.</b> The test cannot see companions more than about 2-2.5 mag fainter in G, because their lift (&lt; 0.1-0.15 mag) is
inside the single-star spread. Those faint companions are the ones that matter for most blended-eclipse scenarios, so a normal
colour-magnitude position does not exclude them.</p>
</div>
</section>"""


def synthesis():
    rows = [
        ["TIC 262843927", chip("HIGH"), chip("MODERATE"), chip("MODERATE"),
         "Unresolved companion (excess noise 15.2&sigma;, RUWE 1.31, about 0.2 mag over-luminous for its colour); planet on the companion; diluted small-k pair inside about 1-2&Prime;",
         "Top tier. High-resolution imaging first (it tests the likely companion); resolved transit at 24.1089 d; RVs to about 1 km/s."],
        ["TIC 193718989", chip("HIGH"), chip("MODERATE"), chip("LOW TO MODERATE"),
         "Eccentric grazing brown dwarf on the target (RV-allowed); STP; unresolved companion",
         "Top tier, close behind 262. Resolved multiband transit; RVs to the brown-dwarf regime; imaging."],
        ["TIC 270573718", chip("HIGH"), chip("MODERATE"), chip("LOW"),
         "Timing structure (TTV versus eclipsing pair in a triple versus noise); diluted pair; STP",
         "Retain, second tier. A transit with a &ge;&plusmn;2 h window measures the next O&minus;C and the shape; RVs."],
    ]
    t = table(["Target", "repeating dip", "target is host", "planet-like body", "main surviving alternatives", "tier and smallest decisive observation"], rows)
    return f"""
<section id="synthesis" style="display:flex;flex-direction:column;gap:12px">
<h2>Cross-candidate synthesis</h2>
{t}
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>The confidence labels are qualitative and conditional on the stated assumptions: Gaia completeness outside about
1-2&Prime;, the mission-PRF family with the tested perturbation, main-sequence physics for blended pairs, and the Gaia RV error
model. They are not probabilities. &ldquo;Repeating dip: HIGH&rdquo; means present in 5-9 re-reductions of the discovery photons
with low null false-dip rates. No independent epoch exists, and the replay is reported separately.</p>
<p><b>Should TIC 262843927 or TIC 193718989 join the top tier?</b> Both should. TIC 262843927 has the strongest planet-versus-binary
case of the three: a planet-like central shape at the catalogue density, and RVs that exclude stellar and heavy brown-dwarf
companions to the target. Its host case is weaker than first stated. The star is about 0.2 mag over-luminous for its colour and
has significant astrometric excess noise, so an unresolved companion is likely, and the transit could be on it. Its signal was
also found near the search threshold. TIC 193718989 has the cleaner host case: no sign of a companion, and its 9.8&Prime;
neighbour is excluded (its host attribution is now about as good as 201247574's in the prior report). Its planet-versus-brown-dwarf
separation is weaker. 262 keeps a narrow lead because a companion would change its radius and host star, not its planetary
character, whereas 193's brown-dwarf alternative would remove the planet. The order between the two is close.</p>
<p><b>TIC 270573718: retain, downgrade below both.</b> It should not be dropped, because the dip is real in the discovery data,
its host is the target among catalogued stars, and the earlier contradiction and NFPP conflict are both resolved. Its
planet interpretation depends on whether the season timing structure is real. If it is, the shape favours a small central
transiter and the system may be dynamically interesting. If it is not, the shape is grazing-ambiguous and the
binary alternatives come back. Future epochs need wider windows than the linear ephemeris suggests.</p>
<p><b>Diminishing returns.</b> For all three, further work on existing public data would re-reduce the same photons or
re-weight the same scenarios. The remaining alternatives (unresolved companions within about 1-2&Prime;, small-radius-ratio
diluted pairs, the 270 timing question, and brown dwarfs for 193) need new data. The single smallest observations: for
262, one high-resolution image (AO or speckle reaching &Delta;mag about 6-7 at 0.1-2&Prime;); for 193, one resolved
multiband transit; for 270, one transit with a wide window (it tests timing and shape together). No observing requests were
made.</p>
</div>
</section>"""


def matrix():
    prior = [x for x in read(CONT / "analysis" / "test_matrix.json") if str(x["tic"]) in (T270, T262, T193)]
    act = {
        "Independent recurrence": ("Census of all archives: no sector &gt; 98 for any target; S31/S88 off-silicon; S97 off SPOC footprint", "CONFIRMED BLOCKED (no new epoch)"),
        "Localization robustness": ("15/14/7-sector difference images; injections on target and neighbours; broadened-PRF misspecification; flux-capable wide neighbours added", "EXTENDED: catalogued neighbours excluded"),
        "Resolved ground / multiband": ("193: ZTF DR24 re-analysed with propagated covariance, censoring and parity; 270/262: ZTF cannot observe these southern stars, ASAS-SN down", "EXTENDED (193); BLOCKED (270, 262)"),
        "Planet / binary / brown dwarf / triple": ("Shape fits with timing nuisance; k-profiles; Gaia RV mass limits; MCMC radius", "EXTENDED"),
        "Doubled period / eccentric": ("Odd/even in 9 reductions; 2P twins via k-profile; e_min from &rho;<sub>eff</sub>; long-period box search", "EXTENDED (262 disfavoured; 193 mild; 270 timing-dependent)"),
        "Secondary / injection recovery": ("Half-phase in 9 reductions with phase-shift null; 262 phase 0.387 re-measured", "REPRODUCED: no robust secondary"),
        "Stellar / SED / Gaia": ("SED not re-fitted; Gaia DR3 flags added; colour-magnitude position against 71,717 stars within 100 pc (A4)",
                                 "EXTENDED: 262 about 0.2 mag over-luminous (with RUWE 1.31, excess noise 15&sigma;); 270, 193 not"),
        "Archival imaging": ("Not repeated: no new contrast data exist", "NOT REPEATED"),
        "Spectra / RVs": ("RAVE (262) and LAMOST (193) epochs located; Gaia RV constancy converted to limits", "EXTENDED (summary-statistic limits)"),
        "Activity / orbital modulation": ("Not repeated", "NOT REPEATED"),
        "FPP sensitivity": ("Scenario families audited; image-conditioned bound; no new draws", "AUDITED"),
    }
    rows = [[f"TIC {x['tic']}", x["test"], x["status"], act.get(x["test"], ("", ""))[0], act.get(x["test"], ("", ""))[1]] for x in prior]
    new = [["all", "Retrospective-split contradiction", "prior: unexplained (270)", "Exact reproduction and decomposition", "RESOLVED (drift extrapolation)"],
           ["all", "Timestamp control (WASP-62 b)", "new", "FFI vs 2-min transit times, 9 sectors", "FFI clock good to &lt; 1 min"],
           ["all", "Empirical timing null", "new", "24 periodic injections per reduction", "270 coherence p &asymp; 0.04; 262/193 none"],
           ["all", "TGLC and FU3 pixel extractions", "new", "11 extra reductions", "dip present in all"],
           ["all", "Flux budget, 1.5-3 px apertures", "new", "Gaia T mags, mission PRF", "262 NFPP=0 aperture-dependent"],
           ["all", "Discovery replay", "new", "Inverted and injected search + Stage A", "see Selection section"]]
    return f"""
<section id="matrix" style="display:flex;flex-direction:column;gap:12px">
<h2>Test matrix keyed to the prior reports</h2>
{table(["Target", "Test family", "Prior status", "FU3 action", "FU3 outcome"], rows + new)}
</section>"""


def failures():
    return """
<section id="failures" style="display:flex;flex-direction:column;gap:12px">
<h2>Failures, negative results and access limits</h2>
<ul>
<li>The first replay launch ran its workers at below-normal priority, and they were starved next to the live survey (0-2 CPU-s in 35 min). It was killed and relaunched at normal priority. No result came from the first launch.</li>
<li>A neighbour-selection defect (a G-magnitude cut) dropped TIC 193718989's 9.8&Prime; star from the first localization run. It was fixed and rerun; the old outputs are kept as <span class="mono">*_run1_Gcut.json</span>.</li>
<li>The first Gaia-RV limit used an invalid statistic for p<sub>obs</sub> near 1. It was replaced by a relative statistic (amendment A2).</li>
<li>Timing-null outputs initially overwrote one another. They were rerun per reduction; the stale files are renamed <span class="mono">*_STALE_*</span>.</li>
<li>The PRF loader first picked up 33&times;33 &ldquo;prf-phot&rdquo; files on camera 4 CCD 2. It was fixed before any result was used.</li>
<li>The covariance-weighted image statistic is unstable for some faint hosts (it went negative for one 262 neighbour). The diagonal-error statistic, which the injections calibrate, is the one reported.</li>
<li>TGLC's S27 aperture event for TIC 270573718 reads 12 ppt, against 2-4 ppt in every other reduction and &minus;1.4 ppt in TGLC PSF. It is retained in the tables and treated as a TGLC artefact.</li>
<li>Unbounded single-source centroid fits wander up to about 100&Prime; in low-S/N sectors. They are diagnostics only.</li>
<li>The unbounded free-shape timing fit latched onto outliers in the unclipped pixel series (S1: a 25-ppt, 1.1-h fit at the duration bound). It is reported but not interpreted; a bounded, outlier-clipped variant was added post hoc (A3).</li>
<li>The MCMC chains are short (autocorrelation 60-100 steps against 1,000 kept). Medians and 68% ranges are stable; 95% tails are approximate.</li>
<li>Access: ExoFOP per-target endpoints return &ldquo;Array&rdquo;; the ASAS-SN light-curve service is down; the NASA Exoplanet Archive cone search was blocked (403); ZTF and ATLAS forced photometry are account-gated. None of these is a scientific negative.</li>
<li>Negative results kept: every negative or zero event depth (event table); the half-phase nulls; the TIC 262843927 phase-0.387 null; the TIC 262843927 S31/S88 &ldquo;no information&rdquo; outcome; the non-significant timing &chi;&sup2; nulls.</li>
</ul>
</section>"""


def repro():
    env = {}
    try:
        import numpy, scipy, astropy, batman, emcee, lightkurve
        env = dict(python=sys.version.split()[0], numpy=numpy.__version__, scipy=scipy.__version__, astropy=astropy.__version__,
                   batman=getattr(batman, "__version__", "?"), emcee=emcee.__version__, lightkurve=lightkurve.__version__)
    except Exception:  # noqa: BLE001
        pass
    return f"""
<section id="repro" style="display:flex;flex-direction:column;gap:12px">
<h2>Reproduction</h2>
<div class="prose" style="display:flex;flex-direction:column;gap:8px">
<p>Folder: <span class="mono">C:\\Users\\seanj\\Documents\\TESS_followup_262_193_270</span> (code, results, tables, figures,
manifests, PROTOCOL.md); large caches in <span class="mono">D:\\tess_fu3_cache</span> (TESScut cutouts, TGLC, PRF models,
replay stores and runs). Interpreter: the tesshunter venv ({", ".join(f"{k} {v}" for k, v in env.items())}).</p>
<p>Order: <span class="mono">s00_inventory &rarr; s01_270_reproduce, s01b_decompose_all &rarr; s02_events &rarr; s03_calibrate &rarr;
s04_oc &rarr; s05_tglc &rarr; s06_timestamp_control &rarr; s07a_cutouts &rarr; s07b_extract &rarr; s13_fluxbudget &rarr;
s07c_localize &rarr; s09_262_s31_s88 &rarr; s10_secondary_2p, s10b_phase0387 &rarr; s11_shape &rarr; s12_fpp_audit &rarr; s14_ztf
&rarr; s15_rv_limits &rarr; s16_ttv_null &rarr; s17_mcmc &rarr; s18_longp_bls &rarr; s19_freeshape_timing (plain and --bounded) &rarr;
s20_gaia_epochs &rarr; s21_spoc2min_262 &rarr; s22_cmd_luminosity &rarr; s08_replay (select, build, run) &rarr; s08b_discovery_context &rarr; s08_summarize &rarr;
facts, build_tables, make_figures &rarr; report_body (HTML) &rarr; make_pdf &rarr; make_manifest</span>. Every script writes JSON under <span class="mono">results/</span> and logs under
<span class="mono">logs/</span>. Census scripts are under <span class="mono">code/census/</span>, with receipts in
<span class="mono">results/census/receipts/</span>.</p>
<p>Machine-readable tables: <span class="mono">tables/event_table_all_reductions.csv</span> (every event in every reduction),
pooled_depths, injection_null_calibration, timing_null_tests, model_comparison, host_localization, flux_budget,
fpp_scenario_audit, secondary_odd_even, gaia_rv_limits, ztf_193718989, cmd_luminosity, freeshape_timing, discovery_funnel_targets and replay_summary
(one row per replay search). Input hashes are in
<span class="mono">manifests/input_manifest.csv</span>, the protocol hashes in <span class="mono">manifests/protocol_freeze.json</span>,
the software versions in <span class="mono">manifests/environment.json</span>, and the size and SHA-256 of every output file in
<span class="mono">manifests/output_manifest.csv</span>. A PDF copy of this report is <span class="mono">report/FU3_three_candidates.pdf</span>.</p>
<p>Unit tests: <span class="mono">code/tests/test_fu3.py</span>, {(CODE / "tests" / "test_fu3.py").read_text(encoding="utf-8").count("def test_")} tests on
synthetic data (event admission, unbiased depth and timing recovery, pooling, the Gaia-to-TESS magnitude relation, season
grouping, the RV mass conversion, the replay's binomial limits and the bounded free-shape fit). Run them with the venv
interpreter: <span class="mono">python -m pytest code/tests -q</span>.</p>
</div>
</section>"""


def build():
    replay_tbl, meta = replay_section()
    body = (head() + summary(meta, replay_tbl) + inputs() + census() + methods() + chapter_270() + chapter_262() + chapter_193()
            + selection(replay_tbl, meta) + luminosity() + synthesis() + matrix() + failures() + repro())
    figs = (img("F4_localization.png", "localization summary", "Injection-calibrated difference-image tests for every tested source. Black: observed summed &Delta;&chi;&sup2;; blue: dips injected on the target (5-95%); red: dips injected on the neighbour (5-95%). Symmetric-log axis.")
            + img("F5_flux_budget.png", "flux budget", "Eclipse fraction each catalogued neighbour would need (most favourable aperture 1.5-3 px and sector), against separation. Colour: &Delta;T.")
            + img("F7_k_profiles.png", "radius-ratio profiles", "Profile &Delta;&chi;&sup2; against occultor radius ratio with dilution free, for a linear ephemeris and with per-season timing offsets.")
            + img("F9_half_phase.png", "half-phase depths", "Depth at phase 0.5 in each reduction (black) with the 95th percentile of 300 phase-shifted null measurements (red)."))
    extra = f'<section style="display:flex;flex-direction:column;gap:12px"><h2>Summary figures</h2>{figs}</section>'
    page = CSS + "<main>" + body + extra + f'<footer class="note">Built {utc()} from FU3 results. Conditional analysis; no validation claim.</footer></main>'
    out = REPORT / "FU3_three_candidates.html"
    out.write_text(page, encoding="utf-8")
    log("report", f"report written {out} ({len(page) / 1e6:.2f} MB)")
    return out




def freeshape_270():
    """Free-shape timing (s19): unbounded (A1) and the bounded, outlier-clipped variant (A2, post hoc), PDC and pixel."""
    rows = {}
    for red, lab in (("pdc_raw", "PDCSAP/QLP"), ("fu3pix_annulus_circ1p5", "FU3 pixel series")):
        for sfx, kind in (("", "unbounded"), ("_bounded", "bounded")):
            p = RES / f"s19_freeshape_{T270}_{red}{sfx}.json"
            if not p.exists():
                continue
            d = read(p)
            st, coh = d.get("oc"), d.get("coherence") or {}
            if not st:
                continue
            good = [e for e in d["events"] if e.get("status") == "ok"]
            s1 = next((e for e in good if e["sector"] == 1), None)
            y3 = next((s for s in d.get("seasons") or [] if s["season"] == 1), {})
            rows[(red, kind)] = [lab, kind, ", ".join(f"{x:+.0f}" for x in st["season_offsets"]["params"]),
                                 f"{y3.get('median_min', float('nan')):+.0f} min, {round((y3.get('frac_same_sign') or 0) * y3.get('n', 0))}/{y3.get('n', 0)}",
                                 fx(st["delta_chi2_seasons_vs_linear"], 1),
                                 f"{np.median([e['T14_h'] for e in good]):.2f} / {np.median([e['ingress_frac'] for e in good]):.2f}",
                                 str(d.get("n_at_bound", "")) if kind == "bounded" else "",
                                 (f"{s1['depth']:.1f} ppt over {s1['T14_h']:.1f} h" if s1 else "")]
    if not rows:
        return ""
    t = table(["Series", "shape", "season offsets 2018, 2020-21, 2023, 2024-25 (min)", "2020-21 median, events sharing sign",
               "season &Delta;&chi;&sup2; vs linear", "median T14 (h) / ingress fraction", "fits at a bound", "S1 event fit"], list(rows.values()))
    return ("<p><b>Free-shape cross-check.</b> Each event was refitted with a trapezoid whose depth, duration and ingress are free "
            "(amendment A1). Unbounded, the PDCSAP fit weakens the pattern (2020-21 season offset &minus;28 min, event median &minus;39 min, 4 of 6 events early). "
            "In the unclipped pixel series the unbounded fit latches onto outliers: the S1 fit is a 25-ppt, 1.1-h feature at the "
            "duration bound, so its +108-min 2018 offset is not interpreted. A post-hoc bounded variant (A3: depth 0-3&times; adopted, "
            "duration 0.6-1.6&times; adopted, isolated 5&sigma; points removed from each window) gives the 2020-21 season about "
            "50 min early with all six events sharing the sign in both series. The season pattern is therefore not an artefact of the "
            "fixed template. Its significance still rests on the injection null (p &asymp; 0.04), which was computed for the "
            "template method only, and the 2023 and 2024-25 offsets differ between methods by up to 30 min.</p>" + t)


def spoc2min_262():
    p = RES / "s21_spoc2min_262.json"
    if not p.exists():
        return ""
    d = read(p)
    ev = [e for e in d["events"] if e["column"] == "pdcsap_flux" and e["admitted"]]
    pp = d["pooled_pdcsap_flux"]
    return (f'<p class="prose"><b>SPOC 2-min data (S1-S3; same epochs, different data path).</b> {len(ev)} of {len(ev)} events are positive '
            f'({", ".join(fx(e["depth_ppt"], 2) for e in ev)} ppt), pooled {fx(pp["depth_ppt"], 2)} &plusmn; {fx(pp["err_ppt"], 2)} ppt '
            f'(p<sub>const</sub> {fx(pp["p_const"], 2)}), consistent with the 1800-s FFI measurements of the same transits. This is a '
            f'sensitivity check, not an independent epoch.</p>')


def gaia_epochs_note():
    p = RES / "s20_gaia_epochs.json"
    if not p.exists():
        return ""
    d = read(p)
    return (f"Gaia DR3 epoch photometry, the only pre-TESS time series ({d[T270]['n_epochs']} epochs for TIC 270573718, "
            f"{d[T193]['n_epochs']} for TIC 193718989, 2014-2017), has no epoch within &plusmn;3&sigma; of a predicted transit; TIC 262843927 "
            f"has no Gaia epoch photometry.")


if __name__ == "__main__":
    build()
