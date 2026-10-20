"""In-event / guard / reference frame selection (same recipe for events and controls)."""
from __future__ import annotations

import json

import common as C
import numpy as np

CFG = json.load(open(C.WS / "config.json"))
GUARD_D = CFG["windows"]["guard_h"] / 24.0
REF_D = CFG["windows"]["reference_span_h"] / 24.0
MIN_IN = CFG["windows"]["min_good_fraction_in_event"]
MIN_REF = CFG["windows"]["min_good_fraction_each_reference_side"]
CADENCE_D = 200.0 / 86400.0

ROLE_NONE, ROLE_IN, ROLE_GUARD, ROLE_REF_L, ROLE_REF_R, ROLE_REF_CUT = 0, 1, 2, 3, 4, 5


def full_half_span(duration_d: float) -> float:
    return 0.5 * duration_d + GUARD_D + REF_D


def select(time, good, dump, tc, duration_d):
    """Return role array and a status dict for one window.

    Roles: 1 in-event, 2 guard, 3/4 reference left/right, 5 reference frames
    dropped because a momentum dump lies between them and the event.
    Only good frames are assigned roles 1/3/4; bad frames keep 0.
    """
    hw = 0.5 * duration_d
    dt = time - tc
    a = np.abs(dt)
    role = np.zeros(len(time), np.int8)
    inw = a <= hw
    grd = (a > hw) & (a <= hw + GUARD_D)
    refl = (dt < -(hw + GUARD_D)) & (dt >= -(hw + GUARD_D + REF_D))
    refr = (dt > (hw + GUARD_D)) & (dt <= (hw + GUARD_D + REF_D))
    span = a <= hw + GUARD_D + REF_D
    dumps_t = time[dump & span]
    # truncate reference sides at the dump closest to the event on that side
    cut_l = dumps_t[dumps_t < tc - hw]
    cut_r = dumps_t[dumps_t > tc + hw]
    refl_ok = refl.copy(); refr_ok = refr.copy()
    if cut_l.size:
        refl_ok &= time > cut_l.max()
    if cut_r.size:
        refr_ok &= time < cut_r.min()
    role[inw & good] = ROLE_IN
    role[grd] = ROLE_GUARD
    role[refl_ok & good] = ROLE_REF_L
    role[refr_ok & good] = ROLE_REF_R
    role[(refl & ~refl_ok) | (refr & ~refr_ok)] = ROLE_REF_CUT
    n_in_nom = max(1, int(round(duration_d / CADENCE_D)))
    n_ref_nom = max(1, int(round(REF_D / CADENCE_D)))
    st = {
        "tc": float(tc), "duration_d": float(duration_d),
        "n_in_good": int((role == ROLE_IN).sum()), "n_in_frames": int(inw.sum()), "n_in_nominal": n_in_nom,
        "n_ref_left_good": int((role == ROLE_REF_L).sum()), "n_ref_right_good": int((role == ROLE_REF_R).sum()),
        "n_ref_nominal_each": n_ref_nom,
        "n_dumps_in_span": int(dumps_t.size),
        "dump_in_event_or_guard": bool(np.any(dump & (a <= hw + GUARD_D))),
        "n_frames_in_span": int(span.sum()),
    }
    reasons = []
    if st["n_in_frames"] == 0:
        reasons.append("no frames in the in-event window")
    if st["n_in_good"] < MIN_IN * n_in_nom:
        reasons.append(f"in-event good frames {st['n_in_good']} < {MIN_IN:.0%} of nominal {n_in_nom}")
    if st["n_ref_left_good"] < MIN_REF * n_ref_nom:
        reasons.append(f"left reference good frames {st['n_ref_left_good']} < {MIN_REF:.0%} of nominal {n_ref_nom}")
    if st["n_ref_right_good"] < MIN_REF * n_ref_nom:
        reasons.append(f"right reference good frames {st['n_ref_right_good']} < {MIN_REF:.0%} of nominal {n_ref_nom}")
    if st["dump_in_event_or_guard"]:
        reasons.append("momentum dump inside the in-event or guard span")
    st["usable"] = not reasons
    st["unusable_reasons"] = reasons
    return role, st
