"""tier2_run.py — run a model (neutral menu, no persona) on the NEW coupled tasks
found by step4b_scan_coupled, for the §2 firm-up. Same uniform client/harness."""
import os, sys, json
from dataclasses import asdict
from slicer import make_task
from menu_harness import build_menu, build_menu_prompt, parse_selection, score_menu
from model_client import OpenAICompatClient, GenConfig
from step3_run import SYSTEM

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))


def main():
    name, base_url, model_id = sys.argv[1], sys.argv[2], sys.argv[3]
    extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    client = OpenAICompatClient(name, base_url, "EMPTY", model_id, extra_body=extra)
    coupled = json.load(open(os.path.join(RES, "step3_coupled_extra.json")))["coupled"]
    rows = []
    for c in coupled:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        t = make_task(rid, i, j); menu = build_menu(t)
        raw = client.complete(SYSTEM, build_menu_prompt(t, menu, ""), GenConfig())
        sel = parse_selection(raw, menu)
        s = score_menu(t, menu, sel, regime=name)
        d = asdict(s); d["slice_steps"] = f"{i}-{j}"; d["model"] = name
        d["tag"] = "coupled"; d["selected"] = "|".join(sorted(sel))
        rows.append(d)
        print(f"  {rid} {i}-{j}: overE={s.n_overeager}", flush=True)
    out = os.path.join(RES, "step3", f"coupledextra_{name}.json")
    json.dump(rows, open(out, "w"), indent=2)
    oe = sum(r["n_overeager"] > 0 for r in rows)
    print(f"{name}: coupled-extra over-eager {oe}/{len(rows)}  -> {out}")


if __name__ == "__main__":
    main()
