"""
step5_intervene.py — run intervention arms on the FIXED model (phi-3.5-mini),
paired over the n=50 menu tasks. Baseline reuses cached step-3 phi selections.

Usage: python3 step5_intervene.py <base_url> <model_id> arm1 arm2 ...
(omit arms to run the default ladder minus baseline.)
"""
import os, sys, json
from dataclasses import asdict
from slicer import make_task
from menu_harness import build_menu, score_menu
from model_client import OpenAICompatClient, GenConfig
from intervention import build_arm, parse_arm, ALL_ARMS

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RES, "step5"); os.makedirs(OUT, exist_ok=True)


def tasks():
    return json.load(open(os.path.join(RES, "step3_taskset.json")))


def run_arm(client, arm):
    rows = []
    raw_dir = os.path.join(OUT, "raw"); os.makedirs(raw_dir, exist_ok=True)
    for c in tasks():
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        t = make_task(rid, i, j)
        menu = build_menu(t)
        system, user, extra = build_arm(t, menu, arm)
        cfg = GenConfig(max_tokens=1500) if arm in ("guided", "ballot") else GenConfig()
        raw = client.complete(system, user, cfg) if extra is None else \
            _complete_extra(client, system, user, extra, cfg)
        sel, flagged = parse_arm(raw, menu, arm)
        s = score_menu(t, menu, sel, regime=f"phi:{arm}")
        d = asdict(s); d["slice_steps"] = f"{i}-{j}"; d["arm"] = arm
        d["selected"] = "|".join(sorted(sel)); d["flagged"] = "|".join(sorted(flagged))
        d["n_flagged"] = len(flagged)
        rows.append(d)
        key = f"{rid}__{i}_{j}"
        open(os.path.join(raw_dir, f"{key}__{arm}.txt"), "w").write(
            f"SEL={sorted(sel)} FLAG={sorted(flagged)}\n---\n{raw}")
        pf = "NA" if s.performance is None else f"{s.performance:.2f}"
        print(f"  [{arm}] {key:28s} overE={s.n_overeager} flag={len(flagged)} "
              f"recall={s.coverage:.2f} perf={pf}", flush=True)
    json.dump(rows, open(os.path.join(OUT, f"results_{arm}.json"), "w"), indent=2)
    oe = sum(r["n_overeager"] > 0 for r in rows)
    rc = sum(r["coverage"] for r in rows)/len(rows)
    print(f"ARM {arm}: over-eager {oe}/{len(rows)}={oe/len(rows):.0%}  "
          f"mean_recall={rc:.2f}\n", flush=True)
    return rows


def _complete_extra(client, system, user, extra, cfg):
    """complete() with extra_body merged (for guided_json)."""
    saved = client.extra_body
    client.extra_body = {**saved, **extra}
    try:
        return client.complete(system, user, cfg)
    finally:
        client.extra_body = saved


if __name__ == "__main__":
    base_url, model_id = sys.argv[1], sys.argv[2]
    arms = sys.argv[3:] or [a for a in ALL_ARMS if a != "baseline"]
    client = OpenAICompatClient("phi-3.5-mini", base_url, "EMPTY", model_id)
    for arm in arms:
        print(f"=== running arm: {arm} ===", flush=True)
        run_arm(client, arm)
