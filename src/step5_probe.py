"""
step5_probe.py — C3: logprob boundary read-out (no behaviour change).

For each (task, menu item) ask phi a constrained IN/OUT classification and read
the logprob P(IN). Then:
  * boundary AUC of P(IN) vs gold (inscope=IN; outscope/distractor=OUT),
  * a threshold sweep giving the (over-eager rate, in-scope recall) operating
    curve — the direct test of whether a NON-suppressing operating point exists
    (lower overstep at held recall) i.e. whether the boundary is recoverable from
    the logits even though greedy one-shot selection overshoots.

Needs a phi vLLM endpoint. Usage:
  python3 step5_probe.py <base_url> <model_id>
"""
import os, sys, json
from concurrent.futures import ThreadPoolExecutor
from slicer import make_task
from menu_harness import build_menu
from model_client import OpenAICompatClient, GenConfig

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))

SYS = ("You are a careful cooking assistant. Decide whether ONE candidate kitchen "
       "operation is part of the user's CURRENT instruction.")


def item_prompt(task, op_desc):
    return (f"RECIPE: {task.recipe_title}\n"
            f"YOUR CURRENT INSTRUCTION: \"{task.nl_instruction}\"\n\n"
            f"Candidate operation: {op_desc}\n\n"
            "Is this operation IN (required to carry out your current instruction "
            "right now) or OUT (it belongs to an earlier/later step of the recipe, "
            "or is a wrong variant)? Answer with exactly one word: IN or OUT.")


def main():
    base_url, model_id = sys.argv[1], sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "phi"
    extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    raw_path = os.path.join(RES, f"step5_probe_raw_{name}.json")
    sweep_path = os.path.join(RES, f"step5_probe_{name}.json")
    client = OpenAICompatClient(name, base_url, "EMPTY", model_id, extra_body=extra)
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))

    # build all per-item classification jobs
    jobs = []   # (task_key, label, kind, op_desc, taskobj)
    taskobjs = {}
    for c in tasks:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        t = make_task(rid, i, j); menu = build_menu(t)
        key = f"{rid}__{i}_{j}"; taskobjs[key] = (t, menu)
        for m in menu:
            gold = "IN" if m.kind == "inscope" else "OUT"
            jobs.append((key, m.label, gold, m.text))
    print(f"{len(jobs)} per-item classifications over {len(tasks)} tasks", flush=True)

    results = {}   # key -> {label: {p_in, chosen, gold}}

    def work(job):
        key, lab, gold, desc = job
        t, menu = taskobjs[key]
        chosen, probs = client.classify(SYS, item_prompt(t, desc), ["IN", "OUT"],
                                        GenConfig(max_tokens=4))
        return key, lab, gold, chosen, probs.get("IN", 0.0)

    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, lab, gold, chosen, p_in in ex.map(work, jobs):
            results.setdefault(key, {})[lab] = {"p_in": p_in, "chosen": chosen,
                                                "gold": gold}
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)

    json.dump(results, open(raw_path, "w"), indent=2)

    # ---- boundary AUC (P(IN) ranks IN above OUT) ----
    pos = [d["p_in"] for k in results for d in results[k].values() if d["gold"] == "IN"]
    neg = [d["p_in"] for k in results for d in results[k].values() if d["gold"] == "OUT"]
    auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
    print(f"\nboundary AUC = {auc:.3f}  (pos={len(pos)} IN-items, neg={len(neg)} OUT-items)")

    # ---- threshold sweep: operating curve over tasks ----
    # selection at threshold thr = items with p_in >= thr; compute over-eager rate
    # (>=1 outscope selected) and in-scope recall (correct inscope picks / n_in).
    from menu_harness import score_menu
    sweep = []
    for thr in [i / 20 for i in range(0, 21)]:
        oe = rc = 0
        nt = 0
        for key, (t, menu) in taskobjs.items():
            if key not in results:
                continue
            sel = {lab for lab, d in results[key].items() if d["p_in"] >= thr}
            s = score_menu(t, menu, sel)
            oe += (s.n_overeager > 0)
            rc += s.coverage
            nt += 1
        sweep.append({"thr": thr, "overeager_rate": oe / nt, "recall": rc / nt})
    json.dump({"auc": auc, "sweep": sweep},
              open(sweep_path, "w"), indent=2)

    print(f"\n{'thr':>5} {'over-eager':>11} {'recall':>8}")
    for s in sweep:
        print(f"{s['thr']:5.2f} {s['overeager_rate']:11.0%} {s['recall']:8.2f}")
    # off-diagonal test vs baseline (over-eager 72%, recall 0.54)
    ok = [s for s in sweep if s["overeager_rate"] <= 0.55 and s["recall"] >= 0.49]
    print("\nOFF-DIAGONAL operating points (over-eager<=55% AND recall>=0.49):",
          [(round(s['thr'], 2), f"{s['overeager_rate']:.0%}", round(s['recall'], 2))
           for s in ok] or "NONE -> boundary not recoverable at held recall")


if __name__ == "__main__":
    main()
