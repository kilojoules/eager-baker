"""
phase2_dump.py — (a) validate the slicer over MANY slices, (b) dump 5 example
tasks for human review (Phase-2 acceptance: spot-check in/out scope by hand).
"""
import os
from slicer import make_task, render_task_for_human, list_recipes


def validate_all():
    """Slice every recipe at every single-step and a few multi-step windows;
    assert the Phase-1 invariant (no stray preconditions) and basic sanity."""
    n_tasks = stray = empty_out = skipped = 0
    for rid in list_recipes():
        # how many instruction steps?
        from mcl import parse_gold_xml
        from slicer import _xml_path
        _, meta = parse_gold_xml(_xml_path(rid))
        n_instr = len([s for s in meta["steps"] if s["kind"] == "instruction"])
        windows = [(k, k) for k in range(1, n_instr + 1)]
        windows += [(k, min(k + 1, n_instr)) for k in range(1, n_instr)]
        for i, j in windows:
            try:
                t = make_task(rid, i, j)
            except ValueError:
                skipped += 1   # degenerate slice (instruction step with no ops)
                continue
            n_tasks += 1
            if t.kitchen_state["stray_preconditions"]:
                stray += 1
                print(f"  STRAY: {rid} {i}..{j} -> "
                      f"{t.kitchen_state['stray_preconditions']}")
            if not t.out_of_scope_ops and j < n_instr:
                empty_out += 1
                print(f"  EMPTY-OUT (non-final slice): {rid} {i}..{j}")
    print(f"\nValidated {n_tasks} slices across {len(list_recipes())} recipes.")
    print(f"  stray-precondition violations: {stray}  (expect 0)")
    print(f"  non-final slices with empty out-of-scope: {empty_out}  (expect 0)")
    print(f"  degenerate slices skipped (instruction step w/ no ops): {skipped}")
    return stray == 0


EXAMPLES = [
    ("easy-banana-bread", 1, 1),   # cream step: implicit `crack` precondition
    ("broccoli-salad", 1, 2),      # salad slice ending before refrigerate (coupling cand.)
    ("afghan-biscuits", 3, 4),     # mid-recipe multi-step
    ("best-brownies", 1, 2),       # has bring-to-temperature in the recipe
    ("classic-greek-salad", 4, 6), # middle slice of a long recipe
]


def main():
    print("#" * 74)
    print("# VALIDATION SWEEP")
    print("#" * 74)
    ok = validate_all()
    print("\n" + "#" * 74)
    print("# 5 EXAMPLE TASKS FOR HUMAN REVIEW")
    print("#" * 74 + "\n")
    for rid, i, j in EXAMPLES:
        print(render_task_for_human(make_task(rid, i, j)))
    print(f"\n[validation passed: {ok}]")


if __name__ == "__main__":
    main()
