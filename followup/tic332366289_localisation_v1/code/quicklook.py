"""Quick inspection figure of the real difference images (signed D, D/sigma)."""
from __future__ import annotations

import json

import common as C
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import core
import scene as Sc

SCENE = json.load(open(C.RESULTS / "scene.json"))
REAL = json.load(open(C.RESULTS / "real_events.json"))


def main(tag="primary", out="quicklook_diffimages.png"):
    cat = Sc.load_catalogue()
    fig, axes = plt.subplots(3, 4, figsize=(17, 12.5))
    for j, eid in enumerate(["E00", "E32", "E33", "E39"]):
        z = np.load(C.ARRAYS / "real" / f"{eid}_{tag}.npz")
        ctx = core.EventContext(eid, cat=cat, scene_json=SCENE)
        D, s = z["D"], z["sigma"]
        r0, r1, c0, c1 = z["box"]
        v = np.nanpercentile(np.abs(D[r0:r1 + 1, c0:c1 + 1]), 99)
        for i, (img, ttl, cm, lim) in enumerate([(z["out"], "out-of-event (e-/s)", "viridis", None),
                                                  (D, "signed D = out - in (e-/s)", "RdBu_r", v),
                                                  (D / s, "D / sigma", "RdBu_r", 5)]):
            ax = axes[i, j]
            if lim is None:
                im = ax.imshow(np.log10(np.clip(img, 1, None)), origin="lower", cmap=cm)
            else:
                im = ax.imshow(img, origin="lower", cmap=cm, vmin=-lim, vmax=lim)
            plt.colorbar(im, ax=ax, fraction=0.046)
            ax.add_patch(plt.Rectangle((c0 - 0.5, r0 - 0.5), c1 - c0 + 1, r1 - r0 + 1, fill=False, ec="k", lw=0.8, ls="--"))
            for k in range(len(cat)):
                x, y = ctx.x[k], ctx.y[k]
                if -0.5 < x < 20.5 and -0.5 < y < 20.5 and np.isfinite(cat[k]["tmag"]) and cat[k]["tmag"] < 19.8:
                    is_t = cat[k]["source_id"] == C.GAIA_TARGET
                    ax.plot(x, y, marker="*" if is_t else "o", ms=11 if is_t else max(2.5, 9 - 0.45 * (cat[k]["tmag"] - 10)),
                            mfc="none", mec="m" if is_t else ("orange" if cat[k]["source_id"] in C.LISTED_NEIGHBOURS else "k"), mew=1.2)
            rb = REAL[eid]
            ax.plot(rb["best_x"], rb["best_y"], "x", color="lime" if rb["best_A"] > 0 else "cyan", ms=10, mew=2)
            ax.set_title(f"{eid} s{ctx.sector}: {ttl}", fontsize=9)
    fig.suptitle("Quick look: TIC 332366289 events (magenta star = target; orange = listed neighbours; x = signed free best)")
    fig.tight_layout()
    fig.savefig(C.FIGURES / out, dpi=80)
    print("saved", C.FIGURES / out)


if __name__ == "__main__":
    main()
