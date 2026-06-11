"""
step5_probe_task.py — M2 control: read per-label SELECTION logits in the ACTUAL
TASK framing, not the isolated comprehension probe.

The Finding-1 probe (step5_probe.py) showed the model ONE operation at a time and
asked a leading comprehension question ("is this part of the instruction?"). A
reviewer's objection: that prompt may do the boundary work itself. This control
keeps the task framing — the FULL menu is shown and the question is the SELECTION
decision ("should this be selected to carry out your instruction?") — and reads
per-label P(select) logits. Then:
  * boundary AUC of P(YES) vs gold (compare to the isolated probe's 0.877),
  * WITHIN-MECHANISM recalibration: does thresholding these task logits beat the
    TASK-greedy operating point at held recall? (the comparison the review demanded)

Usage: python3 step5_probe_task.py <base_url> <model_id> <name> [extra_json]
"""
import os, sys, json, math
from concurrent.futures import ThreadPoolExecutor
from slicer import make_task
from menu_harness import build_menu, score_menu
from model_client import OpenAICompatClient, GenConfig

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))

SYS = ("You are a careful cooking assistant operating a kitchen simulator. You are "
       "given your current instruction and a menu of candidate operations, and you "
       "decide which operations to select to carry out that instruction.")


def context(task, menu):
    lines = "\n".join(f"  [{m.label}] {m.text}" for m in menu)
    avail = "\n".join("  " + d for d in task.kitchen_state["available_objects"])
    return (f"RECIPE: {task.recipe_title}\nYou are mid-recipe; available objects:\n"
            f"{avail}\n\nYOUR INSTRUCTION: \"{task.nl_instruction}\"\n\nMENU:\n{lines}\n")


def q(task, menu, m):
    return (context(task, menu) +
            f"\nConsidering ONLY your current instruction, should operation "
            f"[{m.label}] (\"{m.text}\") be selected now? A later-step operation or a "
            f"wrong variant should be NO. Answer YES (select it) or NO.")


def logit(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def main():
    base_url, model_id, name = sys.argv[1], sys.argv[2], sys.argv[3]
    extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    client = OpenAICompatClient(name, base_url, "EMPTY", model_id, extra_body=extra)
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))

    jobs, objs = [], {}
    for c in tasks:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        t = make_task(rid, i, j); menu = build_menu(t)
        key = f"{rid}__{i}_{j}"; objs[key] = (t, menu)
        for m in menu:
            jobs.append((key, m.label, "IN" if m.kind == "inscope" else "OUT", m))
    print(f"{len(jobs)} TASK-FRAMED per-label selection reads", flush=True)

    res = {}
    def work(job):
        key, lab, gold, m = job
        t, menu = objs[key]
        chosen, probs = client.classify(SYS, q(t, menu, m), ["YES", "NO"],
                                        GenConfig(max_tokens=4))
        return key, lab, gold, chosen, probs.get("YES", 0.0)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, lab, gold, chosen, p in ex.map(work, jobs):
            res.setdefault(key, {})[lab] = {"p_in": p, "chosen": chosen, "gold": gold}
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    json.dump(res, open(os.path.join(RES, f"step5_probe_task_raw_{name}.json"), "w"), indent=2)

    # AUC
    pos = [d["p_in"] for k in res for d in res[k].values() if d["gold"] == "IN"]
    neg = [d["p_in"] for k in res for d in res[k].values() if d["gold"] == "OUT"]
    auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))

    # within-mechanism: greedy (P>0.5) vs best off-diagonal threshold on THESE logits
    ld = {k: {l: logit(d["p_in"]) for l, d in res[k].items()} for k in res}
    def op_at(thr):
        oe = rc = n = 0
        for key, (t, menu) in objs.items():
            if key not in ld:
                continue
            sel = {l for l, v in ld[key].items() if v >= thr}
            s = score_menu(t, menu, sel); oe += s.n_overeager > 0; rc += s.coverage; n += 1
        return oe / n, rc / n
    g_oe, g_rc = op_at(0.0)
    grid = sorted({v for d in ld.values() for v in d.values()})
    grid = [grid[int(q_ * (len(grid) - 1))] for q_ in [i / 60 for i in range(61)]]
    best = None
    for thr in grid:
        oe, rc = op_at(thr)
        if rc >= g_rc - 0.05 and (best is None or oe < best[1]):   # held vs TASK-greedy recall
            best = (thr, oe, rc)

    print(f"\nTASK-FRAMED boundary AUC = {auc:.3f}   (isolated-probe AUC was 0.877)")
    print(f"task-greedy (P>0.5):           over-eager {g_oe:.0%}  recall {g_rc:.2f}")
    if best:
        print(f"best recalibrated (held vs TASK-greedy recall): over-eager {best[1]:.0%} "
              f"recall {best[2]:.2f}  (thr {best[0]:.1f})")
        print(f"WITHIN-MECHANISM off-diagonal? {'YES' if best[1] < g_oe - 0.05 and best[2] >= g_rc - 0.05 else 'NO'}")
    json.dump({"auc": auc, "task_greedy": [g_oe, g_rc],
               "best_recal_held_vs_taskgreedy": list(best) if best else None},
              open(os.path.join(RES, f"step5_probe_task_{name}.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
