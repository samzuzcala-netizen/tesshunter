import re

# ── Resolve TIC ID for catalog cross-match ─────────────────────────────────
# For TESS:     set TIC_ID = <int> in the config cell above.
# For K2/Kepler: leave TIC_ID = None; this cell resolves it from the target name.
if TIC_ID is not None:
    _resolved_tic = TIC_ID
else:
    _m = re.match(r"TIC\s*(\d+)", str(TARGET), re.IGNORECASE)
    if _m:
        _resolved_tic = int(_m.group(1))
    else:
        print(f"Resolving TIC ID for {TARGET!r} via MAST (may take a few seconds)...")
        _resolved_tic = download.get_tic_id_from_name(str(TARGET))
        if _resolved_tic:
            print(f"  Resolved TIC ID: {_resolved_tic}")
        else:
            print("  Could not resolve TIC ID — cross-match will be skipped.")

# Update TIC_ID so downstream cells can reference it consistently
TIC_ID = _resolved_tic  # may be None if resolution failed

if TIC_ID is not None:
    xmatch = catalog_crossmatch.crossmatch(TIC_ID)
else:
    xmatch = {
        "tic_metadata":      None,
        "toi_entries":       None,
        "confirmed_planets": None,
        "is_known_toi":      False,
        "is_confirmed_planet": False,
        "summary_str": (
            f"No TIC ID could be resolved for {TARGET!r} — "
            "catalog cross-match skipped."
        ),
    }

print("Cross-match summary:")
print(xmatch["summary_str"])
print(f"Is known TOI       : {xmatch['is_known_toi']}")
print(f"Is confirmed planet: {xmatch['is_confirmed_planet']}")

tic_meta = xmatch.get("tic_metadata") or {}
stellar_radius = tic_meta.get("stellar_radius_rsun")
if stellar_radius:
    print(f"Stellar radius from TIC: {stellar_radius:.3f} R_Sun")
else:
    print("Stellar radius not available -- planet radius estimate will be skipped.")
