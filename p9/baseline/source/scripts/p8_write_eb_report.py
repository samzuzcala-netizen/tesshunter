"""Build the TIC 279426256 EB report from the saved P8 follow-up measurements."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8/eb_screen"
DEST = REPO / "docs/eb_reports"


def read(name):
    return json.loads((ROOT / name).read_bytes())


def main():
    aperture = read("tic279426256_aperture.json")
    difference = read("tic279426252_P0.7470_difference.json")
    hardstop = read("tic279426256_hardstop.json")
    catalog = read("tic279426256_catalog_versions.json")
    receipt = read("tic279426256_catalog_refetch.json")
    tic = read("gaia5484242473249094784_tic.json")["objects"][0]
    neighbour_path = ROOT.parent / "neighbours/tic279426252.json"
    neighbour_record = json.loads(neighbour_path.read_bytes())
    source_gaia = next(s for s in neighbour_record["gaia"]["neighbours"]
                       if s["source_id"] == aperture["source_gaia_id"])
    vsx = read("tic279426252_wide_vsx.json")
    simbad = read("tic279426252_wide_simbad.json")
    if hardstop["status"] != "CLEAN" or not hardstop["neighbours_resolved"]:
        raise RuntimeError("The fresh six-source hard stop is not CLEAN")
    if receipt["status"] != "complete" or hardstop["catalog_stamp"] != catalog["stamp"]:
        raise RuntimeError("The catalogue refresh is not complete")
    expected = {f["filename"]: f["sha256"] for f in catalog["sources"]["spoc_tce"]["files"]}
    if expected != {f["filename"]: f["sha256"] for f in receipt["files"]}:
        raise RuntimeError("The TCE raw-download receipt does not match the catalogues")
    if len(catalog["sources"]) != 6 or any(s["fetched_utc"] < receipt["started_utc"] for s in catalog["sources"].values()):
        raise RuntimeError("All six catalogues must have been refreshed in this run")
    for name, digest in aperture["source_sha256"].items():
        if hashlib.sha256((REPO / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Changed aperture input: {name}")
    source = SkyCoord(float(tic["ra"]) * u.deg, float(tic["dec"]) * u.deg)
    field_centre = SkyCoord(vsx["ra"] * u.deg, vsx["dec"] * u.deg)
    separation = float(source.separation(field_centre).arcsec)
    known = []
    for cat, name, ra, dec, label in [(vsx, "VSX", "RAJ2000", "DEJ2000", "Name"),
                                      (simbad, "SIMBAD", "ra", "dec", "main_id")]:
        if cat["status"] != "complete" or cat["radius_arcmin"] * 60 < separation + 21:
            raise RuntimeError("The wide catalogue cone does not cover the source")
        for row in cat["objects"]:
            sep = float(source.separation(SkyCoord(row[ra] * u.deg, row[dec] * u.deg)).arcsec)
            known.append({"catalog": name, "name": row[label], "source_sep_arcsec": sep})
    if any(row["source_sep_arcsec"] < 21 for row in known):
        raise RuntimeError("A VSX/SIMBAD counterpart needs manual review")
    eph = aperture["ephemeris"]
    p, t0 = eph["period"], eph["t0"]
    DEST.mkdir(parents=True, exist_ok=True)
    for input_name, output_name in [("tic279426256_aperture.png", "tic279426256_fold.png"),
                                    ("tic279426252_P0.7470_difference.png", "tic279426256_difference.png")]:
        shutil.copy2(ROOT / input_name, DEST / output_name)
    rows = []
    with np.load(ROOT / "tic279426256_aperture.npz") as z:
        for record in aperture["sectors"]:
            sec = record["sector"]
            time, flux = z[f"s{sec}_time"], z[f"s{sec}_flux"]
            phase = ((time - t0) / p + .25) % 1 - .25
            bins = np.minimum(((phase + .25) * 200).astype(int), 199)
            for i in range(200):
                values = (flux[bins == i] - 1) * 1000
                if len(values):
                    rows.append([sec, i / 200 - .25 + .0025, values.mean(),
                                 values.std(ddof=1) / np.sqrt(len(values)), len(values)])
    np.savetxt(DEST / "tic279426256_fold_binned.txt", rows, fmt=["%d", "%.7f", "%.7f", "%.7f", "%d"],
               header="sector phase observed_relative_flux_ppt point_scatter_sem_ppt n_cadences\n"
                      "200 phase bins per sector, no detrending/dilution correction; point errors omit correlated noise")
    measurement = dict(aperture)
    measurement.update(catalog_status=hardstop, catalog_download_receipt="tic279426256_catalog_refetch.json",
                       source_sep_from_searched_tic_position_arcsec=separation,
                       closest_vsx_simbad=sorted(known, key=lambda r: r["source_sep_arcsec"])[:4],
                       classification="Photometric eclipsing-binary candidate; subtype not fitted",
                       source_association="Both minima's difference-image peaks follow Gaia 5484242473249094784 across three detector orientations. Pixel maxima are not fitted source centroids; unresolved companions remain possible.")
    inputs = ["tic279426256_aperture.json", "tic279426256_aperture.npz", "tic279426252_P0.7470_difference.json",
              "tic279426256_hardstop.json", "tic279426256_catalog_versions.json", "tic279426256_catalog_refetch.json",
              "gaia5484242473249094784_tic.json", "tic279426252_wide_vsx.json", "tic279426252_wide_simbad.json",
              "tic279426252_wide_gaia.json", "tic279426252_centroid.json"]
    measurement["report_input_sha256"] = {str((ROOT / name).relative_to(REPO)): hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs}
    measurement["report_input_sha256"][str(neighbour_path.relative_to(REPO))] = hashlib.sha256(neighbour_path.read_bytes()).hexdigest()
    measurement["source_gaia_ruwe"] = source_gaia["ruwe"]
    (DEST / "tic279426256_measurements.json").write_text(json.dumps(measurement, indent=1) + "\n", encoding="utf-8")
    date = hardstop["checked_utc"][:10]
    ra_text = source.ra.to_string(unit=u.hourangle, sep=" ", precision=2, pad=True)
    dec_text = source.dec.to_string(unit=u.deg, sep=" ", precision=1, pad=True, alwayssign=True)
    lines = ["# TIC 279426256: local eclipsing-binary candidate report", "",
             f"Prepared {date} from the P8 rejected-signal follow-up. Two recurring minima and their pixel differences "
             f"support a photometric eclipsing-binary candidate at TIC 279426256, about {separation:.1f} arcsec from "
             "the searched M dwarf TIC 279426252 [M]. No external submission has been made.", "",
             "[M] denotes measurements made in P8, including catalogue queries; [A] denotes an adopted diagnostic choice. "
             "The binary subtype and any unresolved companion are undetermined.", "",
             "## Identification and fields for human review", "",
             "| Field | Value |", "|---|---|",
             "| Primary identifier | TIC 279426256 [M] |",
             "| Other identifier | Gaia DR3 5484242473249094784 [M] |",
             f"| TIC coordinates, J2000 | {ra_text}, {dec_text}; {tic['ra']:.8f}, {tic['dec']:.8f} deg [M] |",
             "| Classification | Eclipsing-binary candidate; leave a more specific subtype unset |",
             f"| Working period | Approximately {p:.4f} d [M]; no formal uncertainty fitted |",
             f"| Reproduction ephemeris | P = {p:.12f} d, primary epoch BTJD {t0:.9f}, or BJD_TDB {t0 + 2457000:.6f} [M] |",
             f"| Catalogue brightness | TIC Tmag {tic['Tmag']:.4f} [M], a reference magnitude, not a calibrated eclipse maximum |",
             "| Intrinsic maximum/minimum magnitudes | Leave unset: the aperture depths are diluted and no calibrated magnitude range was measured |",
             "| Data | TESS 200-second full-frame TESScut pixels, sectors 61, 87 and 98 [M] |", "",
             "The reproduction digits preserve the saved forced-TLS ephemeris from the contaminated target; "
             "they do not express a period or epoch uncertainty. The signal was followed at this ephemeris rather than fitted "
             f"as a full binary system. The catalogue Teff of {tic['Teff']:.0f} K and radius of {tic['rad']:.4f} solar radii [M] put this "
             "neighbour outside the P8 small-star population. It is a side result of inspecting a rejected target.", "",
             "## Light curve and location", "",
             "![Separate source aperture folds](tic279426256_fold.png)", "",
             "The source aperture uses pixels within one pixel of the propagated Gaia position. A local median sky "
             "annulus spans five to nine pixels, excluding pixels within two pixels of Gaia sources brighter than G=18 [A]. "
             "Each sector is median-normalized; no trend or dilution correction is applied. "
             "Two narrow minima sit on a broader waveform that changes between sectors [M].", "",
             "| Sector | Cadences [M] | Primary depth, ppt [M] | Secondary depth, ppt [M] | Adopted planet-bound calculation, ppt [M under A] |",
             "|---|---:|---:|---:|---:|"]
    for record in aperture["sectors"]:
        primary, secondary = record["primary"], record["secondary"]
        lines.append(f"| {record['sector']} | {record['n_cadences']:,} | {primary['depth_ppt']:.2f} +/- {primary['err_ppt']:.2f} | "
                     f"{secondary['depth_ppt']:.2f} +/- {secondary['err_ppt']:.2f} | {record['planet_secondary_bound']['max_planetary_secondary_ppt']:.2f} |")
    lines += ["", f"Depths use local boxes of width {eph['duration'] * 24:.3f} h [A, the saved search duration]; "
              "this width is not a fitted contact duration. Errors use local point scatter and omit correlated noise. "
              "The inherited planetary-secondary diagnostic uses the TIC source parameters and albedo 0.3 [A]; "
              "the observed secondary is about 5 to 8 times that bound [M]. Catalogue stellar parameters could describe "
              "a composite system, and the bound is supporting evidence rather than a binary model.", "",
              "![Difference images and Gaia positions](tic279426256_difference.png)", "",
              "The Gaia source labelled 8 follows the positive primary and secondary differences through three detector "
              "orientations [M]. Local out-of-event images are interpolated across each event and the event differences "
              "are median-stacked. The stacks contain 32/34, 35/34 and 73/74 primary/secondary events respectively [M]. "
              "The extended sector 98 spans four orbits, accounting for its larger event count. "
              "The searched target is labelled T. These are pixel maxima, not fitted PRF centroids, so a formal localization "
              "uncertainty and unresolved alternatives remain open. Separate whole-cutout centroid shifts are flagged "
              "in sectors 61 and 87; shifts in detector coordinates were not combined to assign a sky position.", "",
              "## Catalogue checks and funnel context", "",
              f"The six-source hard stop is CLEAN as of {date}: no TIC match and no match within 21 arcsec [M]. "
              f"All six payloads were downloaded again, including all {receipt['n_files']} SPOC TCE version files [M]. "
              "The wider VSX and SIMBAD queries cover a five-arcminute cone around the searched target and contain "
              "no entry within 21 arcsec of the implicated source [M]. This establishes absence from the checked "
              "catalogues on this date, not from every catalogue or publication.", "",
              "The target's 0.7470-day signal failed Stage A depth consistency; its 11.2049-day alias passed A and "
              "failed the full-phase secondary gate [M]. No planet gate was relaxed for this follow-up. "
              "The depth changes between apertures and sectors, and the off-target localization, explain why this "
              "signal is unsuitable as a planet candidate on the searched M dwarf.", "",
              "## Remaining measurements", "",
              "Resolve the source with ground-based time-series photometry, determine a binary ephemeris and uncertainty, "
              "measure a calibrated magnitude range, and model the two eclipses before assigning a subtype. "
              f"Gaia RUWE {source_gaia['ruwe']:.3f} [M] is consistent with an imperfect single-source astrometric fit and is not, by itself, "
              "a binary classification. No radial velocities or component parameters were measured here.", "",
              "## Reproduction and saved evidence", "",
              "Run `python scripts/p8_write_eb_report.py` to rebuild this report from the saved follow-up. "
              "The image and aperture measurements are rebuilt by `scripts/p8_eb_difference_image.py` and "
              "`scripts/p8_eb_aperture.py`; their JSON files record the ephemeris, selected pixel files and input SHA-256 hashes.", "",
              "- [Measurements and input hashes](tic279426256_measurements.json)",
              "- [Sector-specific binned folds](tic279426256_fold_binned.txt)",
              "- [Catalogue manifest](../../data/survey/p8/eb_screen/tic279426256_catalog_versions.json)",
              "- [Raw TCE download receipt](../../data/survey/p8/eb_screen/tic279426256_catalog_refetch.json)",
              "- [VSX query](../../data/survey/p8/eb_screen/tic279426252_wide_vsx.json)",
              "- [SIMBAD query](../../data/survey/p8/eb_screen/tic279426252_wide_simbad.json)",
              "- [Gaia query](../../data/survey/p8/eb_screen/tic279426252_wide_gaia.json)",
              "- [Original Gaia neighbour record, including RUWE](../../data/survey/p8/neighbours/tic279426252.json)",
              "- [TIC query matching the exact Gaia identifier](../../data/survey/p8/eb_screen/gaia5484242473249094784_tic.json)", ""]
    path = DEST / "tic279426256_vsx_fields.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
