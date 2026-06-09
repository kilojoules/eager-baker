"""
phase1_verify.py — empirical test of the Phase-1 gate across ALL gold recipes.

The gate asks: can we, for a given operation, programmatically retrieve
(a) the operations it NECESSARILY REQUIRES (preconditions / data dependencies)
distinctly from (b) the operations that merely come AFTER it in time?

We test this on every gold recipe and report hard numbers:
  - parse coverage (any unknown primitives / arity issues?)
  - is the kitchen-state thread a single linear chain? (the "timeline")
  - precondition edges vs sequence edges
  - the decisive statistic: ADJACENT sequence pairs (i -> i+1 in the timeline)
    that have NO precondition relationship in EITHER direction. Each such pair
    is a concrete case of "B follows A but B does not require A" -- i.e. proof
    that following != requiring.
"""

from __future__ import annotations
import glob
import os
from mcl import (parse_solution_file, parse_gold_xml, build_graph,
                 SIGNATURES, is_var)

GS_DIR = ("../reb_extracted/recipe-execution-benchmark/data/"
          "gold standard solutions/meaning-only")


def analyze(path):
    ops = parse_solution_file(path)
    name = os.path.basename(path).replace(".solution", "")

    # 1. coverage: unknown predicates / arity mismatch
    unknown = sorted({op.name for op in ops if op.name not in SIGNATURES})

    g = build_graph(ops)

    # 2. is the ks thread a single linear chain?
    #    every non-getter op should have exactly one sequence predecessor.
    seq_pred_counts = [len(g.seq[op.idx]) for op in ops if op.name != "get-kitchen"]
    linear = all(c == 1 for c in seq_pred_counts)

    # 3. edge counts
    n_seq = sum(len(s) for s in g.seq.values())
    n_prec = sum(len(s) for s in g.prec.values())

    # 4. decisive statistic: adjacent-in-timeline pairs with no precondition link
    #    Build timeline order from ks thread: op B follows op A if A in seq[B].
    decoupled_adjacent = 0
    total_adjacent = 0
    examples = []
    for op in ops:
        for a in g.seq[op.idx]:           # a immediately precedes op in time
            total_adjacent += 1
            # is there a precondition edge in either direction between a and op?
            linked = (a in g.prec[op.idx]) or (op.idx in g.prec.get(a, set()))
            if not linked:
                decoupled_adjacent += 1
                if len(examples) < 3:
                    examples.append((a, ops[a].name, op.idx, op.name))

    return {
        "name": name, "n_ops": len(ops), "unknown": unknown, "linear": linear,
        "n_seq": n_seq, "n_prec": n_prec,
        "decoupled_adjacent": decoupled_adjacent, "total_adjacent": total_adjacent,
        "examples": examples,
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    gs = os.path.normpath(os.path.join(here, GS_DIR))
    paths = sorted(glob.glob(os.path.join(gs, "*.solution")))
    print(f"Found {len(paths)} gold solutions in {gs}\n")

    tot_ops = tot_seq = tot_prec = tot_dec = tot_adj = 0
    any_unknown = False
    any_nonlinear = False
    print(f"{'recipe':32s} {'ops':>4} {'seq':>4} {'prec':>5} "
          f"{'adj':>4} {'decoupled':>9} linear")
    print("-" * 78)
    for p in paths:
        r = analyze(p)
        tot_ops += r["n_ops"]; tot_seq += r["n_seq"]; tot_prec += r["n_prec"]
        tot_dec += r["decoupled_adjacent"]; tot_adj += r["total_adjacent"]
        any_unknown |= bool(r["unknown"])
        any_nonlinear |= not r["linear"]
        flag = "" if not r["unknown"] else f"  UNKNOWN={r['unknown']}"
        print(f"{r['name']:32s} {r['n_ops']:4d} {r['n_seq']:4d} {r['n_prec']:5d} "
              f"{r['total_adjacent']:4d} {r['decoupled_adjacent']:9d} "
              f"{str(r['linear']):>6}{flag}")

    print("-" * 78)
    print(f"{'TOTAL':32s} {tot_ops:4d} {tot_seq:4d} {tot_prec:5d} "
          f"{tot_adj:4d} {tot_dec:9d}")
    print()
    print(f"Unknown primitives anywhere?      {any_unknown}")
    print(f"Any non-linear kitchen-state thread? {any_nonlinear}")
    pct = 100.0 * tot_prec / tot_seq if tot_seq else 0
    print(f"Precondition edges are {pct:.1f}% of sequence edges "
          f"(sparse subset => separable).")
    pct2 = 100.0 * tot_dec / tot_adj if tot_adj else 0
    print(f"{tot_dec}/{tot_adj} ({pct2:.1f}%) adjacent-in-time pairs have NO "
          f"precondition link\n  => 'follows' does NOT imply 'requires'.")


if __name__ == "__main__":
    main()
