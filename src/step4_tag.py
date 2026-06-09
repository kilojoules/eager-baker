"""
step4_tag.py — §4 destructive-next-step tagging via the SIMULATOR (not a heuristic).

For each task: DAS(prefix+slice) is the baseline. For each individual next-step
(out-of-scope) op, DAS(prefix+slice+op). If an op LOWERS the slice-target DAS it
is destructive -> task tagged `coupled`; else `benign`. Records das_baseline and
per-next-op deltas. Model-independent (uses gold ops), one-time per task.
"""
import os, sys, json, csv, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
from slicer import make_task

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
BIN = os.path.normpath(os.path.join(
    HERE, "..", "reb_extracted/recipe-execution-benchmark/executables/mac/"
    "cookingbot-evaluator.app/Contents/MacOS/cookingbot-evaluator"))
EPS = 0.01   # DAS drop beyond this counts as destructive


def networks_for_task(rid, i, j):
    """Return (labels, list_of_network_text). Each network prefixed with #rid.
    Order: baseline, then prefix+slice+op_k for each out-of-scope op k."""
    t = make_task(rid, i, j)
    prefix = t.kitchen_state["prefix_network"]
    slice_sexps = [o["sexp"] for o in t.in_scope_ops]
    base = prefix + slice_sexps
    nets = [("baseline", base)]
    for k, o in enumerate(t.out_of_scope_ops):
        nets.append((f"op{k}", base + [o["sexp"]]))
    labels = [n[0] for n in nets]
    texts = []
    for _, ops in nets:
        texts.append(f"#{rid}\n" + "\n".join(ops))
    return labels, texts, t


def run_eval_single(text, timeout=120):
    """Run the evaluator on ONE network (unique-id requirement); return DAS or None."""
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.solution")
        out = os.path.join(d, "out.csv")
        with open(inp, "w") as f:
            f.write(text + "\n")
        try:
            subprocess.run([BIN, "-input", inp, "-output", out], cwd=d,
                           timeout=timeout, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return None
        if not os.path.exists(out):
            return None
        with open(out) as f:
            for row in csv.reader(f):
                if row and row[0] != "recipe-id":
                    try:
                        return float(row[2])
                    except (ValueError, IndexError):
                        return None
    return None


def main():
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))
    # flatten all networks across all tasks into one job list
    jobs = []      # (task_idx, kind_idx[-1=baseline], text)
    meta = []
    for ti, c in enumerate(tasks):
        _, texts, t = networks_for_task(c["recipe_id"], c["i"], c["j"])
        jobs.append((ti, -1, texts[0]))
        for k in range(1, len(texts)):
            jobs.append((ti, k - 1, texts[k]))
        meta.append(c)
    print(f"running {len(jobs)} evaluator invocations (parallel)...", flush=True)

    das_map = {}
    def work(job):
        ti, k, text = job
        return (ti, k, run_eval_single(text))
    done = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for ti, k, das in ex.map(work, jobs):
            das_map[(ti, k)] = das
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(jobs)} done", flush=True)

    results = []
    n_coupled = 0
    for ti, c in enumerate(tasks):
        base = das_map.get((ti, -1))
        n_out = c["n_out"]
        rec = {**c}
        if base is None:
            rec.update({"das_baseline": None, "tag": "unknown", "deltas": None})
            results.append(rec)
            print(f"[{ti+1}] {c['recipe_id']} {c['i']}-{c['j']}: BASELINE FAIL")
            continue
        deltas = []
        for k in range(n_out):
            d = das_map.get((ti, k))
            deltas.append(None if d is None else round(d - base, 3))
        destructive = [k for k, dl in enumerate(deltas) if dl is not None and dl < -EPS]
        tag = "coupled" if destructive else "benign"
        n_coupled += tag == "coupled"
        rec.update({"das_baseline": round(base, 3), "tag": tag,
                    "deltas": deltas, "destructive_ops": destructive})
        results.append(rec)
        worst = min([d for d in deltas if d is not None], default=0.0)
        print(f"[{ti+1}] {c['recipe_id']} {c['i']}-{c['j']}: base={base:.2f} "
              f"tag={tag} worst_delta={worst:+.2f} n_destructive={len(destructive)}")

    with open(os.path.join(RES, "step3_taskset_tagged.json"), "w") as f:
        json.dump(results, f, indent=2)
    nb = sum(1 for r in results if r.get("tag") == "benign")
    nu = sum(1 for r in results if r.get("tag") == "unknown")
    print(f"\nTAGGED {len(results)} tasks: coupled={n_coupled} benign={nb} unknown={nu}")


if __name__ == "__main__":
    main()
