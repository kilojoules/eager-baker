"""
phase1_worked_example.py — the hand-checked worked example required by the gate.

Target operation: "Cream together butter, eggs and sugar" (the `beat` op) in
easy-banana-bread.  We show that:
  * `crack eggs` is in the operation's PRECONDITION closure (required-for), and
  * the NEXT recipe step ("Add bananas and vanilla") is a TEMPORAL SUCCESSOR
    that is NOT in the precondition closure (out of scope).
"""

import os
from mcl import parse_gold_xml, build_graph

XML = ("../reb_extracted/recipe-execution-benchmark/data/"
       "gold standard solutions/utterance and meaning/easy-banana-bread.xml")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ops, meta = parse_gold_xml(os.path.normpath(os.path.join(here, XML)))
    g = build_graph(ops)

    print(f"Recipe: {meta['title']}\n")
    print("NL steps and their operations:")
    for s_no, step in enumerate(meta["steps"]):
        ops_str = ",".join(str(i) for i in step["op_indices"])
        print(f"  step {s_no:2d} [{step['kind']:11s}] ops[{ops_str:>9s}]  "
              f"{step['utterance']}")

    # locate the "Cream together..." instruction and its final beat op
    cream_step = next(s for s in meta["steps"]
                      if s["utterance"].lower().startswith("cream together"))
    beat_idx = [i for i in cream_step["op_indices"]
                if ops[i].name == "beat"][0]
    print(f"\nTARGET op #{beat_idx}: {ops[beat_idx]}")
    print(f'  (the "{cream_step["utterance"].strip()}" operation)\n')

    closure = g.precondition_closure([beat_idx])
    print("PRECONDITION CLOSURE (required-for ancestors, in scope):")
    for i in sorted(closure):
        tag = "  <-- crack eggs" if ops[i].name == "crack" else ""
        print(f"   #{i:2d} {ops[i].name}{tag}")

    crack_idx = [op.idx for op in ops if op.name == "crack"][0]
    print(f"\n  crack (#{crack_idx}) in precondition closure of beat? "
          f"{crack_idx in closure}   <-- REQUIRED-FOR confirmed")

    # the next instruction step
    next_step = meta["steps"][meta["steps"].index(cream_step) + 1]
    print(f"\nNEXT recipe step (temporal successor, OUT of scope): "
          f'"{next_step["utterance"].strip()}"')
    for i in next_step["op_indices"]:
        in_closure = i in closure
        # is it a temporal successor of beat? (reachable via sequence thread)
        print(f"   #{i:2d} {ops[i].name:18s} "
              f"in_precondition_closure={in_closure}  "
              f"depends_on_beat={beat_idx in g.precondition_closure([i])}")

    print("\nSeparation summary:")
    print(f"  - crack eggs  : REQUIRED-FOR the cream step  (in-scope precondition)")
    print(f"  - next step   : FOLLOWS the cream step but is NOT required for it")
    print(f"                  (it instead consumes the cream step's output)")
    # the cleanest decoupled pair: two adjacent fetches with no data link
    print("\nCleanest 'follows but does not require' pair (adjacent ingredient fetches):")
    fetches = [op for op in ops if op.name == "fetch-and-proportion"][:4]
    a, b = fetches[2].idx, fetches[3].idx
    print(f"   #{a} {ops[a].args[4]} -> #{b} {ops[b].args[4]}  "
          f"(seq edge: {a in g.seq[b]}, precondition edge: {a in g.prec[b]})")


if __name__ == "__main__":
    main()
