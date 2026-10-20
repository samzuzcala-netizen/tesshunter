lcc = download.search_and_download_lc(
    target   = TARGET,
    mission  = MISSION,
    sector   = SECTOR,
    campaign = CAMPAIGN,
    quarter  = QUARTER,
    author   = AUTHOR,
)
if lcc is None:
    raise RuntimeError(f"No data found for {TARGET!r} ({MISSION})")

lc_raw  = download.stitch_collection(lcc)
sectors = download.observing_units_available(lcc, MISSION)

_ulabels = {"TESS": "Sector", "K2": "Campaign", "KEPLER": "Quarter"}
_ulabel  = _ulabels.get(MISSION.upper(), "Unit")
print(f"Mission: {MISSION}  |  {_ulabel}(s): {sectors}  |  Cadences: {len(lc_raw)}")
