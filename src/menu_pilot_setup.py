"""menu_pilot_setup.py — materialise menu tasks + prompts + label keys."""
import os, json
from dataclasses import asdict
from slicer import make_task
from model_harness import PILOT_TASKS, PERSONAS
from menu_harness import build_menu, build_menu_prompt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "results", "menu_pilot"))
os.makedirs(OUT, exist_ok=True)


def main():
    index = []
    for rid, i, j in PILOT_TASKS:
        t = make_task(rid, i, j)
        key = f"{rid}__{i}_{j}"
        menu = build_menu(t)
        # save the menu (label -> kind/slot/text) for scoring
        with open(os.path.join(OUT, key + ".menu.json"), "w") as f:
            json.dump([asdict(m) for m in menu], f, indent=2)
        n_in = len(t.in_scope_ops)
        n_out = len(t.out_of_scope_ops)
        n_dist = sum(1 for m in menu if m.kind == "distractor")
        for regime in ("cautious", "eager"):
            with open(os.path.join(OUT, f"{key}__{regime}.prompt.txt"), "w") as f:
                f.write(build_menu_prompt(t, menu, PERSONAS[regime]))
        index.append({"key": key, "n_menu": len(menu), "n_in": n_in,
                      "n_out": n_out, "n_distractor": n_dist})
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(index, f, indent=2)
    print(f"wrote {len(index)} menu tasks x 2 regimes to {OUT}")
    for e in index:
        print(f"  {e['key']:34s} menu={e['n_menu']:2d}  in={e['n_in']} "
              f"distract={e['n_distractor']} out={e['n_out']}")


if __name__ == "__main__":
    main()
