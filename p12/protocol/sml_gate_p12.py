"""Part 2b gate [A, registered before the inventory ran]: arm B runs only if >= 100 E_cal hosts
have >= 1 SML-usable sector AND SML-usable sectors are >= 15% of the selected sector products on
E_cal. Otherwise ``photometry_decision.json`` records ``KEEP_ARCHIVAL (NOT_TESTABLE)`` with the counts.
Writes ``p12/manifests/sml_gate.json`` (``run_arm_b``).
"""
from p12_common import REPO, ROOT, read, write, sha, utc
import csv
import json
from pathlib import Path


def gate():
    configuration = read(ROOT / 'protocol/config.json')['sml']
    inventory_path = ROOT / 'manifests/sml_inventory.json'
    inventory = read(inventory_path)
    with (ROOT / 'manifests/part2/e_cal_hosts.csv').open(newline='', encoding='utf-8') as stream:
        e_cal = {int(r['tic_id']) for r in csv.DictReader(stream)}
    products = [p for p in inventory['products'] if int(p['tic_id']) in e_cal]
    hosts_with = {int(p['tic_id']) for p in products if p['uses_sml']}
    usable = sum(1 for p in products if p['uses_sml'])
    fraction = usable / len(products) if products else 0.0
    run = len(hosts_with) >= configuration['minimum_hosts'] and fraction >= configuration['minimum_product_fraction']
    result = dict(utc=utc(), run_arm_b=run, e_cal_hosts=len(e_cal), hosts_with_sml_sector=len(hosts_with),
                  selected_products_on_e_cal=len(products), sml_usable_products=usable, sml_usable_fraction=fraction,
                  thresholds=dict(minimum_hosts=configuration['minimum_hosts'], minimum_product_fraction=configuration['minimum_product_fraction']),
                  inventory_sha256=sha(inventory_path),
                  generations={g: sum(1 for p in products if p['generation'] == g) for g in sorted({p['generation'] for p in products})})
    write(ROOT / 'manifests/sml_gate.json', result)
    if not run:
        write(ROOT / 'results/part2/photometry_decision.json', dict(utc=utc(), decision='KEEP_ARCHIVAL', reason='NOT_TESTABLE',
              gate=result, median_wall_ratio=None, rule='PROMPT_P12.md 2b: below either gate threshold arm B does not run'))
    print(json.dumps({k: result[k] for k in ('run_arm_b', 'hosts_with_sml_sector', 'sml_usable_fraction')}), flush=True)
    return result


def main(argv=None):
    gate()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
