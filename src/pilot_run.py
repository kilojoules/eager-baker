"""pilot_run.py — score every (task, regime) and emit the per-task results table."""
import os, csv, json
from dataclasses import asdict
from slicer import make_task
from score import score_task
from model_harness import PILOT_TASKS

HERE = os.path.dirname(os.path.abspath(__file__))
PD = os.path.normpath(os.path.join(HERE, "..", "results", "pilot"))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
REGIMES = ("cautious", "eager")


def run():
    rows = []
    for rid, i, j in PILOT_TASKS:
        key = f"{rid}__{i}_{j}"
        for regime in REGIMES:
            sol = os.path.join(PD, f"{key}__{regime}.solution")
            if not os.path.exists(sol):
                continue
            t = make_task(rid, i, j)
            s = score_task(t, open(sol).read(), regime)
            rows.append(s)
    # write CSV
    out = os.path.join(RES, "pilot_results.csv")
    cols = ["recipe_id", "slice_steps", "regime", "performance", "coverage",
            "n_inscope_attempted", "n_correct_attempts", "n_omitted",
            "n_inscope_total", "timidity_norm", "over_eagerness_norm",
            "signed_scope", "dropped_preconditions", "n_overeager",
            "n_outscope_total", "n_emitted_ops", "n_unclassified", "category"]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for s in rows:
            d = asdict(s)
            d["slice_steps"] = f"{s.slice_steps[0]}-{s.slice_steps[1]}"
            w.writerow([d[c] for c in cols])
    print(f"wrote {out}  ({len(rows)} rows)")
    return rows


def fmt(p):
    return " NA " if p is None else f"{p:.2f}"


def print_table(rows):
    print(f"\n{'task':28s} {'regime':8s} {'perf':>5} {'signed':>6} "
          f"{'timid':>5} {'overE':>5} {'dropP':>5} {'emit':>4} {'cat':>11}")
    print("-" * 90)
    for s in rows:
        task = f"{s.recipe_id[:20]} {s.slice_steps[0]}-{s.slice_steps[1]}"
        print(f"{task:28s} {s.regime:8s} {fmt(s.performance):>5} "
              f"{s.signed_scope:6.2f} {s.timidity_norm:5.2f} "
              f"{s.over_eagerness_norm:5.2f} {s.dropped_preconditions:5d} "
              f"{s.n_emitted_ops:4d} {s.category:>11}")

    # regime means (performance over non-NA)
    print("\nREGIME SUMMARY (means):")
    for regime in REGIMES:
        rs = [s for s in rows if s.regime == regime]
        perfs = [s.performance for s in rs if s.performance is not None]
        mp = sum(perfs) / len(perfs) if perfs else float("nan")
        ms = sum(s.signed_scope for s in rs) / len(rs)
        moe = sum(s.over_eagerness_norm for s in rs) / len(rs)
        mt = sum(s.timidity_norm for s in rs) / len(rs)
        noe = sum(1 for s in rs if s.category == "over-eager")
        print(f"  {regime:8s} mean_perf={mp:.2f}  mean_signed_scope={ms:+.2f}  "
              f"mean_overE={moe:.2f}  mean_timid={mt:.2f}  "
              f"over-eager_tasks={noe}/{len(rs)}")


if __name__ == "__main__":
    rows = run()
    print_table(rows)
