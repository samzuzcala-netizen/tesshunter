"""Record of the WebSearch-tool queries made for census task 12 (2026-10-18).  The searches were run through
the assistant's WebSearch tool (standard mode), not from this machine, so they have no HTTP receipts here; the
queries, run date and the returned result titles/URLs are recorded verbatim as the audit trail.  Repository and
bibliographic follow-ups were then fetched with receipts (c09_github, c09b_github_ephem, c12_simbad,
c12b_cloutier2019)."""
import census_common as C

LOG = {
    "tool": "WebSearch (standard mode)", "run_date_utc": "2026-10-18",
    "queries": [
        {"query": "\"TIC 270573718\"", "relevant_results": [],
         "note": "no result mentions the identifier; results were other TIC objects/TOI-715 etc."},
        {"query": "\"TIC 262843927\"", "relevant_results": [],
         "note": "no result mentions the identifier"},
        {"query": "\"TIC 193718989\"", "relevant_results": [],
         "note": "no result mentions the identifier"},
        {"query": "\"4792202879700135040\" OR \"4673750877131752832\" OR \"1346023547769345792\" Gaia",
         "relevant_results": [], "note": "no result mentions any of the Gaia DR3 source_ids"},
        {"query": "eumemic exoplanets github TIC 193718989 candidate", "relevant_results": [],
         "note": "search engine did not index the repository; it was then read directly via the GitHub API (c09)"},
        {"query": "ASAS-SN Sky Patrol v2 python client pyasassn skypatrol cone_search documentation",
         "relevant_results": ["https://github.com/asas-sn/skypatrol", "https://arxiv.org/abs/2304.03791v1"],
         "note": "used to identify the documented client (pip package 'skypatrol', module 'pyasassn')"},
        {"query": "\"The independent discovery of planet candidates around low-mass stars and astrophysical false "
                  "positives from the first two TESS sectors\"",
         "relevant_results": ["https://arxiv.org/pdf/1812.08145",
                              "https://cdsarc.cds.unistra.fr/VizieR/cats/ftp/cati/J/AJ/158/81/ReadMe"],
         "note": "follow-up of the SIMBAD reference list of TIC 262843927 (Cloutier 2019, AJ 158, 81)"},
    ],
}

if __name__ == "__main__":
    C.save_json(C.PARTS / "c14_web_search_log.json", LOG)
    print("saved")
