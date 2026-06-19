"""
step3_run_cli.py — run the 50-task menu benchmark for a model served through a
local AGENTIC CLI, via cli_client.CLIModelClient. Two flavors:
  * agy    — Antigravity (Gemini/Claude/GPT-OSS behind a Google login)
  * claude — Claude Code behind a personal subscription (CLAUDE_CONFIG_DIR)

Same prompt / parser / scorer as step3_run.py; ONLY the backend differs (an agent
stack with no temperature/seed/logprobs control -> results are harness-confounded
vs the vLLM models; see cli_client.py and the writeups).

This loop is RESILIENT + RESUMABLE (the CLIs are slow and can flake): each task is
saved incrementally, failed tasks are recorded and skipped, and a re-run continues
where it left off.

Usage:
  python3 step3_run_cli.py <label> <model|-> [flavor=agy] [bin_override]
  e.g. python3 step3_run_cli.py gemini-3.5-flash "Gemini 3.5 Flash (Medium)"
       python3 step3_run_cli.py claude-opus-4.8 - claude    # '-' => CLI default model
"""
import os, sys, json
from dataclasses import asdict
from slicer import make_task
from menu_harness import build_menu, build_menu_prompt, parse_selection, score_menu
from model_client import GenConfig
from cli_client import CLIModelClient
from step3_run import SYSTEM, load_tasks, OUT

RAW = os.path.join(OUT, "raw")

# flavor -> how to invoke that CLI in headless mode. env values of None UNSET that
# var in the child (drop API key + this session's identity so `claude` starts clean
# on the personal subscription).
FLAVORS = {
    "agy": dict(
        argv=["agy"], model_flag="--model",
        extra_flags=["--print-timeout", "180s", "--dangerously-skip-permissions"],
        env=None,
    ),
    "claude": dict(
        argv=["/Users/julianquick/.local/bin/claude"], model_flag="--model",
        extra_flags=["--dangerously-skip-permissions", "--output-format", "text"],
        env={"CLAUDE_CONFIG_DIR": "/Users/julianquick/.claude-personal",
             "CLAUDE_CODE_SESSION_ID": None, "CLAUDE_CODE_CHILD_SESSION": None,
             "CLAUDE_EFFORT": None, "ANTHROPIC_API_KEY": None},
    ),
    # claude-ponytail = the `claude` flavor with the ponytail skill (a scope-discipline
    # "lazy senior dev / do exactly what's asked" persona) appended to Claude Code's
    # system prompt via --append-system-prompt. This is the ONE controllable harness
    # knob for the with/without-ponytail A/B (same model, same tasks, only this differs).
    "claude-ponytail": "alias:claude+ponytail",
}

PONYTAIL_SKILL = os.path.expanduser(
    "~/.claude-personal/plugins/marketplaces/ponytail/skills/ponytail/SKILL.md")


def ponytail_body():
    raw = open(PONYTAIL_SKILL).read()
    return (raw.split("---", 2)[2].strip() if raw.startswith("---") else raw.strip())


def main():
    label, model = sys.argv[1], sys.argv[2]
    flavor = sys.argv[3] if len(sys.argv) > 3 else "agy"
    spec = dict(FLAVORS["claude" if flavor == "claude-ponytail" else flavor])
    extra = list(spec["extra_flags"])
    if flavor == "claude-ponytail":   # the only difference vs `claude`: + the skill text
        extra += ["--append-system-prompt", ponytail_body()]
        print(f"[ponytail ON: +{len(ponytail_body())} chars to system prompt]", flush=True)
    argv = [sys.argv[4]] if len(sys.argv) > 4 else spec["argv"]
    m = None if model in ("", "-", "default") else model
    client = CLIModelClient(label, argv, model=m, model_flag=spec["model_flag"],
                            extra_flags=extra, env=spec.get("env"))

    os.makedirs(RAW, exist_ok=True)
    out_path = os.path.join(OUT, f"results_{label}.json")
    tasks = load_tasks()
    # resume: keep already-scored rows, skip their keys
    done = {}
    if os.path.exists(out_path):
        for r in json.load(open(out_path)):
            done[f"{r['recipe_id']}__{r['slice_steps'].replace('-', '_')}"] = r
    rows = list(done.values())
    print(f"flavor='{flavor}' model='{m or 'CLI-default'}' label='{label}'  "
          f"{len(done)}/{len(tasks)} already done", flush=True)

    for n, c in enumerate(tasks):
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        key = f"{rid}__{i}_{j}"
        if key in done:
            continue
        t = make_task(rid, i, j)
        menu = build_menu(t)                          # deterministic; same for all models
        user = build_menu_prompt(t, menu, "")         # "" persona -> neutral
        try:
            raw = client.complete(SYSTEM, user, GenConfig())
            err = ""
        except Exception as e:                        # record + continue, never abort
            raw, err = "", f"ERROR: {e}"
        sel = parse_selection(raw, menu)
        s = score_menu(t, menu, sel, regime=label)
        with open(os.path.join(RAW, f"{key}__{label}.txt"), "w") as f:
            f.write(f"SELECTED={sorted(sel)}\n{err}\n---RAW---\n{raw}")
        d = asdict(s)
        d["slice_steps"] = f"{i}-{j}"
        d["model"] = label
        d["selected"] = "|".join(sorted(sel))
        d["coupled_tag"] = c.get("tag", "?")
        rows.append(d)
        json.dump(rows, open(out_path, "w"), indent=2)   # incremental save
        perf = "NA" if s.performance is None else f"{s.performance:.2f}"
        flag = "  <<ERR>>" if err else ""
        print(f"[{n+1}/{len(tasks)}] {key:34s} perf={perf} signed={s.signed_scope:+.2f} "
              f"overE={s.n_overeager} sel={len(sel)}{flag}", flush=True)

    oe = sum(1 for r in rows if r["n_overeager"] > 0)
    perfs = [r["performance"] for r in rows if r["performance"] is not None]
    mp = sum(perfs)/len(perfs) if perfs else float("nan")
    print(f"\nwrote {out_path} ({len(rows)} rows)")
    print(f"  over-eager tasks: {oe}/{len(rows)}  mean_perf={mp:.2f}  "
          f"mean_signed={sum(r['signed_scope'] for r in rows)/len(rows):+.2f}")


if __name__ == "__main__":
    main()
