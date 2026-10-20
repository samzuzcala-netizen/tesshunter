from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest
path=Path(__file__).resolve().parents[1]/"p10/protocol/decide_c_adoption.py"
spec=importlib.util.spec_from_file_location("c_adoption",path)
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)


def inputs():
    return dict(n_injections=30,n_adversarial_candidates=41,n_adversarial_hosts=18,
        half_double_case_ids=list(range(7)),adversarial_a_to_b_flips={"installed":[],"with_fallback":[]},
        injection_b_pass_rate_at_least_a={"installed":True,"with_fallback":True},
        half_double_passes={"b_installed":[],"b_with_fallback":[]},
        adversarial_fallback_fail_to_pass={"a":[],"b":[]}),dict(n=37,TOI_1470_c_flips=True,
        n_alias_case_flips_among_all_37=0,fallback_flip_keys=["tic237222864_P10.2888"])


def test_adopts_only_when_comparative_and_absolute_alias_requirements_pass():
    controls,native=inputs()
    assert A.choose(controls,native)["significant_peak_adopted"]
    controls["half_double_passes"]["b_installed"]=["old_baseline_pass"]
    result=A.choose(controls,native)
    assert result["comparative_conditions_met"] and not result["prompt_required_all_half_double_cases_fail"]
    assert result["selected_peak_rule"]=="strongest" and result["robust_fallback_enabled"]


@pytest.mark.parametrize("failure",["toi","native_alias","eb_flip","retention"])
def test_each_comparative_failure_keeps_a(failure):
    c,n=inputs()
    if failure=="toi":n["TOI_1470_c_flips"]=False
    elif failure=="native_alias":n["n_alias_case_flips_among_all_37"]=1
    elif failure=="eb_flip":c["adversarial_a_to_b_flips"]["installed"]=["negative"]
    else:c["injection_b_pass_rate_at_least_a"]["installed"]=False
    assert A.choose(c,n)["selected_peak_rule"]=="strongest"


@pytest.mark.parametrize("source",["native","eb_a","eb_b"])
def test_any_new_negative_fallback_pass_withdraws_fallback(source):
    c,n=inputs()
    if source=="native":n["fallback_flip_keys"].append("negative")
    else:c["adversarial_fallback_fail_to_pass"][source[-1]]=["negative"]
    result=A.choose(c,n)
    assert result["robust_fallback_withdrawn"] and not result["robust_fallback_enabled"]
