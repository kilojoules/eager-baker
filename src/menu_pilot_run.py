"""menu_pilot_run.py — score the menu-selection pilot."""
import os, json, csv
from dataclasses import asdict
from slicer import make_task
from model_harness import PILOT_TASKS
from menu_harness import MenuItem, parse_selection, score_menu

HERE = os.path.dirname(os.path.abspath(__file__))
MP = os.path.normpath(os.path.join(HERE, "..", "results", "menu_pilot"))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
REGIMES = ("cautious", "eager")


def load_menu(key):
    with open(os.path.join(MP, key + ".menu.json")) as f:
        return [MenuItem(**d) for d in json.load(f)]


def run():
    rows = []
    for rid, i, j in PILOT_TASKS:
        key = f"{rid}__{i}_{j}"
        menu = load_menu(key)
        t = make_task(rid, i, j)
        for regime in REGIMES:
            sel_file = os.path.join(MP, f"{key}__{regime}.selection.txt")
            if not os.path.exists(sel_file):
                continue
            selected = parse_selection(open(sel_file).read(), menu)
            s = score_menu(t, menu, selected, regime)
            rows.append(s)
    cols = ["recipe_id", "slice_steps", "regime", "performance", "coverage",
            "n_inscope_attempted", "n_correct_attempts", "n_omitted",
            "n_inscope_total", "timidity_norm", "over_eagerness_norm",
            "signed_scope", "dropped_preconditions", "n_overeager",
            "n_outscope_total", "n_emitted_ops", "category"]
    out = os.path.join(RES, "menu_pilot_results.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for s in rows:
            d = asdict(s); d["slice_steps"] = f"{s.slice_steps[0]}-{s.slice_steps[1]}"
            w.writerow([d[c] for c in cols])
    print(f"wrote {out} ({len(rows)} rows)")
    return rows


def fmt(p): return " NA " if p is None else f"{p:.2f}"


def table(rows):
    print(f"\n{'task':28s} {'regime':8s} {'perf':>5} {'signed':>6} {'timid':>5} "
          f"{'overE':>5} {'dropP':>5} {'sel':>3} {'cat':>11}")
    print("-" * 88)
    for s in rows:
        task = f"{s.recipe_id[:20]} {s.slice_steps[0]}-{s.slice_steps[1]}"
        print(f"{task:28s} {s.regime:8s} {fmt(s.performance):>5} {s.signed_scope:6.2f} "
              f"{s.timidity_norm:5.2f} {s.over_eagerness_norm:5.2f} "
              f"{s.dropped_preconditions:5d} {s.n_emitted_ops:3d} {s.category:>11}")
    print("\nREGIME SUMMARY:")
    for regime in REGIMES:
        rs = [s for s in rows if s.regime == regime]
        perfs = [s.performance for s in rs if s.performance is not None]
        mp = sum(perfs) / len(perfs) if perfs else float("nan")
        ms = sum(s.signed_scope for s in rs) / len(rs)
        moe = sum(s.over_eagerness_norm for s in rs) / len(rs)
        mt = sum(s.timidity_norm for s in rs) / len(rs)
        noe = sum(1 for s in rs if s.category == "over-eager")
        print(f"  {regime:8s} mean_perf={mp:.2f}  signed_scope={ms:+.2f}  "
              f"overE={moe:.2f}  timid={mt:.2f}  over-eager_tasks={noe}/{len(rs)}")


if __name__ == "__main__":
    rows = run()
    table(rows)
