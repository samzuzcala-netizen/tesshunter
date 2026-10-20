"""One explicit final C implementation, never fall back to a prior attempt."""
from common import ROOT

C_STAGE='C_v2'

def stage_path(candidate_id,stage):
    return ROOT/f'results/funnel/{C_STAGE if stage=="C" else stage}/{candidate_id}.json'

def storage_receipt(logical_archive):
    version='C_v2' if logical_archive.parent.name=='c_models_v2' else 'C'
    return ROOT/f'results/model_storage/{version}/{logical_archive.stem}.json' if version=='C_v2' else ROOT/f'results/model_storage/{logical_archive.stem}.json'
