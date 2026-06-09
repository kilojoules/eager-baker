"""pilot_setup.py — materialise pilot tasks + per-regime prompts to results/pilot/."""
import os, json
from slicer import make_task
from model_harness import PILOT_TASKS, build_prompt
from dataclasses import asdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "results", "pilot"))
os.makedirs(OUT, exist_ok=True)


def main():
    index = []
    for rid, i, j in PILOT_TASKS:
        t = make_task(rid, i, j)
        key = f"{rid}__{i}_{j}"
        with open(os.path.join(OUT, key + ".task.json"), "w") as f:
            json.dump(asdict(t), f, indent=2)
        for regime in ("cautious", "eager"):
            p = build_prompt(t, regime)
            with open(os.path.join(OUT, f"{key}__{regime}.prompt.txt"), "w") as f:
                f.write(p)
        index.append({"key": key, "recipe_id": rid, "i": i, "j": j,
                      "n_in": len(t.in_scope_ops), "n_out": len(t.out_of_scope_ops)})
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(index, f, indent=2)
    print(f"wrote {len(index)} tasks x 2 regimes to {OUT}")
    for e in index:
        print(" ", e["key"], f"(in={e['n_in']}, out={e['n_out']})")


if __name__ == "__main__":
    main()
