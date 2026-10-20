import pandas as pd

try:
    import tabulate as _tab
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "tabulate", "-q"], check=True)

try:
    _planets = planets_df
except NameError:
    _planets = pd.DataFrame()

# ── Guard: nothing to report when no candidates were accepted ─────────────────
if best is None or vet is None:
    print("No accepted candidates — skipping report and CSV entry.")

else:
    # TIC_ID may be None (K2/Kepler without resolved TIC); fall back to 0
    _report_tic = TIC_ID or 0

    # Generate the markdown report.
    # candidates = raw first-pass BLS peaks (for the periodogram-peaks reference).
    # _planets   = alias-resolved multi-planet list (drives Section 2 table).
    report_path = reporting.generate_report(
        target_id          = TARGET_LABEL,
        tic_id             = _report_tic,
        sectors            = sectors,
        prep_record        = prep_record,
        candidates_df      = candidates,
        vetting            = vet,
        crossmatch_summary = xmatch["summary_str"],
        plot_paths         = plot_paths,
        planets_df         = _planets,
        mission            = MISSION,
    )
    print(f"Report written: {report_path}")

    # Append one CSV row per accepted planet.
    for _, p in _planets.iterrows():
        pnum = int(p.get("planet_num", 1))
        reporting.append_to_candidate_summary(
            tic_id             = _report_tic,
            target_id          = f"{TARGET_LABEL} P{pnum}",
            sectors            = sectors,
            period_days        = p["period_days"],
            depth_ppt          = p["depth_ppt"],
            duration_hours     = p["duration_days"] * 24,
            bls_power          = float(p.get("power", 0.0)),
            snr                = p["snr"],
            verdict            = vet.verdict if pnum == 1 else "candidate",
            crossmatch_summary = xmatch["summary_str"],
            summary_csv        = CANDIDATES_DIR / "candidate_summary.csv",
        )
