"""
slicer.py — Phase 2: slicing + prefix kitchen-state setup.

make_task(recipe_id, i, j) takes a gold recipe and a contiguous slice of
INSTRUCTION steps (i..j, 1-indexed over instruction steps -- the natural
"do steps i through j" framing) and returns:

  {
    nl_instruction   : the natural-language text for ONLY steps i..j,
    kitchen_state    : a symbolic snapshot of the kitchen after the prefix
                       (ops before step i) -- available objects + the prefix
                       network (so scoring can prepend it),
    in_scope_ops     : the operations the model SHOULD emit (slice + any
                       necessary preconditions not already in the prefix),
    out_of_scope_ops : operations that merely FOLLOW step j (doing these =
                       over-eagerness),
  }

Design notes (see PHASE1_ORACLE.md and SETUP.md):
  * The slice is defined over instruction steps; ingredient "steps" (fetch /
    proportion) are treated as prefix/preconditions, never as a requested slice.
  * Because data flows forward, every precondition of the slice lies in the
    prefix or inside the slice itself -- so in_scope_ops = slice ops, with
    implicit preconditions (e.g. `crack`) already included from the gold meaning.
    We TAG which in-scope ops are "implicit" (verb not named in the NL) so Phase 3
    can weight timidity on dropped preconditions.
  * The standalone evaluator does not expose a live kitchen-state object, so
    `kitchen_state` is symbolic (derived from the gold prefix network). For
    performance scoring we prepend the gold prefix to model output and run the
    simulator on the concatenation (kitchen_state.prefix_network).
"""

from __future__ import annotations
import os
import re
import glob
from dataclasses import dataclass, asdict
from mcl import parse_gold_xml, build_graph, Op, Graph, is_var

XML_DIR = ("../reb_extracted/recipe-execution-benchmark/data/"
           "gold standard solutions/utterance and meaning")


def _xml_path(recipe_id: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, XML_DIR, recipe_id + ".xml"))


def list_recipes() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.normpath(os.path.join(here, XML_DIR))
    return sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(d, "*.xml")))


def op_to_sexp(op: Op) -> str:
    return f"({op.name} {' '.join(map(str, op.args))})"


def _describe_object(var: str, producer_op: Op) -> str:
    """Human-readable label for an available object variable."""
    label = var.lstrip("?").replace("-", " ")
    # add provenance: the producing verb + any constant ingredient/arg
    consts = [a for a in producer_op.args if not is_var(a)]
    prov = producer_op.name.replace("-", " ")
    if consts:
        prov += " " + " ".join(consts)
    return f"{label}  (from: {prov})"


@dataclass
class Task:
    recipe_id: str
    recipe_title: str
    slice_steps: tuple          # (i, j) instruction-step numbers, 1-indexed
    nl_instruction: str
    kitchen_state: dict         # {available_objects, prefix_network, summary}
    in_scope_ops: list          # [{idx,name,sexp,implicit}]
    out_of_scope_ops: list      # [{idx,name,sexp}]


def make_task(recipe_id: str, i: int, j: int) -> Task:
    """Build a scope-calibration task for instruction steps i..j (1-indexed)."""
    ops, meta = parse_gold_xml(_xml_path(recipe_id))
    g = build_graph(ops)

    # instruction steps only, in order
    instr_steps = [s for s in meta["steps"] if s["kind"] == "instruction"]
    if not (1 <= i <= j <= len(instr_steps)):
        raise ValueError(f"slice {i}..{j} out of range "
                         f"(recipe has {len(instr_steps)} instruction steps)")

    slice_steps = instr_steps[i - 1:j]
    slice_op_idxs = [oi for s in slice_steps for oi in s["op_indices"]]
    if not slice_op_idxs:
        raise ValueError("selected steps contain no operations")
    first, last = min(slice_op_idxs), max(slice_op_idxs)

    # prefix = all ops before the first slice op (ingredients + earlier instrs)
    prefix_idxs = [op.idx for op in ops if op.idx < first]
    out_idxs = [op.idx for op in ops if op.idx > last]

    # ---- validate the Phase-1 invariant: preconditions ⊆ prefix ∪ slice ----
    closure = g.precondition_closure(slice_op_idxs)
    stray = [k for k in closure
             if k not in set(slice_op_idxs) and k not in set(prefix_idxs)]
    # (stray should be empty; surfaced in the dump if not)

    # ---- in-scope ops: the slice itself; tag implicit preconditions ----
    # "Implicit precondition" = a preparatory sub-action that recipe text
    # routinely assumes rather than states (the brief's "crack eggs" case).
    # Defined structurally by predicate class (documented heuristic), not by
    # lexical match -- MCL verbs (beat/mix) rarely appear literally in NL ("cream").
    PREP_PREDICATES = {
        "crack", "separate-eggs", "fetch", "fetch-and-proportion", "peel",
        "seed", "sift", "preheat-oven", "grease", "line", "wash", "drain",
    }
    nl = " ".join(s["utterance"].strip() for s in slice_steps)
    in_scope = []
    for k in sorted(slice_op_idxs):
        op = ops[k]
        implicit = op.name in PREP_PREDICATES
        in_scope.append({"idx": k, "name": op.name, "sexp": op_to_sexp(op),
                         "implicit_precondition": implicit})

    out_of_scope = [{"idx": k, "name": ops[k].name, "sexp": op_to_sexp(ops[k])}
                    for k in sorted(out_idxs)]

    # ---- symbolic kitchen state after the prefix ----
    prefix_network = [op_to_sexp(ops[k]) for k in sorted(prefix_idxs)]
    # "live" objects = object outputs produced in prefix, not consumed by a later
    # prefix op (i.e. things currently sitting available on the counter/in bowls)
    consumed_in_prefix = set()
    for k in prefix_idxs:
        for v in ops[k].input_vars():
            consumed_in_prefix.add(v)
    available = []
    for k in sorted(prefix_idxs):
        for v in ops[k].object_outputs():
            if is_var(v) and v not in consumed_in_prefix:
                available.append(_describe_object(v, ops[k]))

    kitchen_state = {
        "summary": (f"You are mid-recipe. Operations for the first {i-1} "
                    f"instruction step(s) and all ingredient prep are already "
                    f"done. The following objects are available:"),
        "available_objects": available,
        "prefix_network": prefix_network,   # for scoring (prepend to model output)
        "stray_preconditions": stray,       # should be empty (Phase-1 invariant)
    }

    return Task(
        recipe_id=recipe_id,
        recipe_title=meta["title"],
        slice_steps=(i, j),
        nl_instruction=nl,
        kitchen_state=kitchen_state,
        in_scope_ops=in_scope,
        out_of_scope_ops=out_of_scope,
    )


def render_task_for_human(t: Task) -> str:
    lines = []
    lines.append("=" * 74)
    lines.append(f"RECIPE: {t.recipe_title}  ({t.recipe_id})")
    lines.append(f"SLICE : instruction steps {t.slice_steps[0]}..{t.slice_steps[1]}")
    lines.append("-" * 74)
    lines.append("NL INSTRUCTION GIVEN TO MODEL:")
    lines.append(f"  \"{t.nl_instruction}\"")
    lines.append("")
    lines.append("KITCHEN STATE (symbolic, after prefix):")
    lines.append(f"  {t.kitchen_state['summary']}")
    if t.kitchen_state["available_objects"]:
        for o in t.kitchen_state["available_objects"]:
            lines.append(f"    - {o}")
    else:
        lines.append("    (no live intermediate objects; ingredients fetched as needed)")
    lines.append(f"  [prefix network: {len(t.kitchen_state['prefix_network'])} ops, "
                 f"used for scoring]")
    if t.kitchen_state["stray_preconditions"]:
        lines.append(f"  !! STRAY PRECONDITIONS (Phase-1 invariant broken): "
                     f"{t.kitchen_state['stray_preconditions']}")
    lines.append("")
    lines.append(f"IN-SCOPE OPS (model SHOULD emit these, {len(t.in_scope_ops)}):")
    for o in t.in_scope_ops:
        tag = "  <-- IMPLICIT precondition" if o["implicit_precondition"] else ""
        lines.append(f"    #{o['idx']:2d} {o['sexp']}{tag}")
    lines.append("")
    lines.append(f"OUT-OF-SCOPE OPS (emitting these = OVER-EAGER, "
                 f"{len(t.out_of_scope_ops)}):")
    for o in t.out_of_scope_ops[:12]:
        lines.append(f"    #{o['idx']:2d} {o['sexp']}")
    if len(t.out_of_scope_ops) > 12:
        lines.append(f"    ... (+{len(t.out_of_scope_ops) - 12} more)")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4:
        t = make_task(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
        print(render_task_for_human(t))
    else:
        print("usage: python3 slicer.py <recipe_id> <i> <j>")
        print("recipes:", ", ".join(list_recipes()))
