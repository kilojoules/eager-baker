"""
score.py — implements the FROZEN metric in SCORING.md (2026-06-09).

Performance = conditional-correctness (of in-scope ops attempted, fraction correct).
Scope = signed(over_eagerness - timidity), each reported separately.

The hard part is matching a model's free-form MUHAI network to the gold slice
WITHOUT relying on variable names (the model invents its own). We use an
**ingredient-content signature**: every operation is identified by

    (predicate-class, frozenset of base ingredients/items in its RESULT)

computed from the data-dependency graph (mcl.build_graph). This is invariant to
variable naming and to which fresh container/tool the model happens to pick.

  * "attempted" an in-scope slot  = model emits an op whose (pred-class, content)
        matches that gold slot.
  * "correct"                     = additionally the exact predicate and the
        salient constant args agree.
  * "omitted"                     = gold in-scope slot with no model match
        (counts as timidity, NOT as a performance failure).
  * "over-eager"                  = model op matching an out-of-scope gold slot.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from mcl import Op, build_graph, is_var, parse_solution, SIGNATURES

# ---- predicate equivalence classes (documented tolerance, SCORING.md §2) ----
# "cream together" may be realised as beat OR mix OR mingle; treat as one class
# for SLOT matching (attempted), but exact predicate still required for CORRECT.
_COMBINE = {"beat", "mix", "mingle", "stir", "shake"}


def pred_class(name: str) -> str:
    return "combine" if name in _COMBINE else name


# tokens that are NOT material identities (units, numbers, patterns, settings)
_UNITS = {"g", "ml", "l", "piece", "teaspoon", "tablespoon", "percent",
          "minute", "hour", "degrees-celsius", "low-heat", "medium-heat",
          "medium-high-heat", "high-heat"}


def _is_number(tok: str) -> bool:
    try:
        float(tok)
        return True
    except ValueError:
        return False


def _materials_introduced(op: Op) -> set:
    """Base ingredient/item identities this op brings into existence.
    Only fetch-and-proportion (ingredients) and fetch (items) introduce new
    material; every other primitive transforms existing material."""
    out = set()
    if op.name == "fetch-and-proportion" and len(op.args) >= 5:
        if not is_var(op.args[4]):          # arg4 = ingredient
            out.add(op.args[4])
    elif op.name == "fetch" and len(op.args) >= 4:
        if not is_var(op.args[3]):          # arg3 = thing-to-fetch (item)
            out.add(op.args[3])
    return out


def content_closures(ops: list[Op]) -> dict:
    """For every OBJECT-output variable, the set of base materials flowed into it.
    Computed over the producer graph (object inputs only, ks excluded)."""
    g = build_graph(ops)
    # producer map: variable -> op idx
    producer = {}
    for op in ops:
        for v in op.object_outputs():
            if is_var(v):
                producer.setdefault(v, op.idx)
    memo_op: dict = {}      # op idx -> content set of its result

    def op_content(idx, stack):
        if idx in memo_op:
            return memo_op[idx]
        if idx in stack:           # cycle guard (shouldn't happen)
            return set()
        stack = stack | {idx}
        op = ops[idx]
        content = set(_materials_introduced(op))
        for v in op.input_vars():
            src = producer.get(v)
            if src is not None and src != idx:
                content |= op_content(src, stack)
        memo_op[idx] = content
        return content

    return {op.idx: op_content(op.idx, set()) for op in ops}


# qualitative modifiers that change WHAT is produced (not how much / which tool).
# Ingredient identity is already captured in the content signature, and quantities
# / tool choices / add-order are intentionally NOT correctness criteria (MUHAI
# treats those as taste-neutral; see docs §6.1 perfect-switched-operations).
_MODIFIERS = {
    "chopped", "finely-chopped", "slices", "fine-slices", "squares",
    "two-cm-cubes", "halved", "shredded", "minced", "diced",
    "ball-shape", "crescent-shape",
}


def _salient_constants(op: Op) -> frozenset:
    """Discriminating modifier constants used for the CORRECTNESS check:
    cut-patterns and shapes. (Quantities, units, temps, tool/container choices,
    and add-order are deliberately excluded — they are not taste-determining.)
    Limitation logged in FINDINGS: a wrong bake temperature is NOT penalised."""
    return frozenset(a for a in op.args if a in _MODIFIERS)


@dataclass
class OpSig:
    idx: int
    name: str
    pclass: str
    content: frozenset
    constants: frozenset

    def slot_key(self):
        return (self.pclass, self.content)


def _primary_input_var(op: Op):
    """The main object an op transforms/handles (its 'direct material' source).
    transfer-contents handles its SOURCE (arg5), not the destination bowl, so the
    signature is order-invariant (adding ingredients in any order looks the same).
    """
    if op.name == "transfer-contents" and len(op.args) > 5 and is_var(op.args[5]):
        return op.args[5]
    ins = op.input_vars()
    return ins[0] if ins else None


def op_sigs(ops: list[Op], subset_idxs=None) -> list[OpSig]:
    """Signatures using DIRECT materials each op handles (order-invariant):
    content = materials of the op's primary input ∪ materials it introduces."""
    closures = content_closures(ops)
    producer = {}
    for op in ops:
        for v in op.object_outputs():
            if is_var(v):
                producer.setdefault(v, op.idx)

    def var_content(v):
        p = producer.get(v)
        return set(closures.get(p, set())) if p is not None else set()

    idxs = subset_idxs if subset_idxs is not None else [op.idx for op in ops]
    sigs = []
    for i in idxs:
        op = ops[i]
        pin = _primary_input_var(op)
        content = var_content(pin) | _materials_introduced(op)
        sigs.append(OpSig(idx=i, name=op.name, pclass=pred_class(op.name),
                          content=frozenset(content),
                          constants=_salient_constants(op)))
    return sigs


# ---------------------------------------------------------------------------
# Scoring a task
# ---------------------------------------------------------------------------

@dataclass
class TaskScore:
    recipe_id: str
    slice_steps: tuple
    regime: str = ""
    # performance
    performance: float | None = None     # conditional-correctness, or None (NA)
    n_inscope_attempted: int = 0
    n_correct_attempts: int = 0
    n_omitted: int = 0
    coverage: float = 0.0                 # secondary diagnostic
    # scope
    timidity_norm: float = 0.0
    over_eagerness_norm: float = 0.0
    signed_scope: float = 0.0
    dropped_preconditions: int = 0
    n_overeager: int = 0
    # bookkeeping
    n_inscope_total: int = 0
    n_outscope_total: int = 0
    n_emitted_ops: int = 0
    n_unclassified: int = 0
    category: str = ""
    notes: list = field(default_factory=list)


# in-scope ops considered "implicit preconditions" for the dropped-precondition count
_PREP = {"crack", "separate-eggs", "fetch", "fetch-and-proportion", "peel",
         "seed", "sift", "preheat-oven", "grease", "line", "wash", "drain"}


def score_task(task, model_network_text: str, regime: str = "") -> TaskScore:
    """task: a slicer.Task. model_network_text: the model's emitted MUHAI network
    (s-expressions). Scored per the frozen metric."""
    prefix = task.kitchen_state["prefix_network"]            # list of sexp strings
    in_idx = [o["idx"] for o in task.in_scope_ops]
    out_idx = [o["idx"] for o in task.out_of_scope_ops]

    # --- gold side: rebuild the full gold network for content provenance ---
    gold_ops = parse_solution("\n".join(
        prefix
        + [o["sexp"] for o in task.in_scope_ops]
        + [o["sexp"] for o in task.out_of_scope_ops]))
    # the prefix occupies indices [0..len(prefix)-1]; then in-scope, then out
    base = len(prefix)
    gold_inscope_local = list(range(base, base + len(in_idx)))
    gold_outscope_local = list(range(base + len(in_idx),
                                     base + len(in_idx) + len(out_idx)))
    gold_sigs_all = op_sigs(gold_ops)
    gold_in_sigs = [gold_sigs_all[i] for i in gold_inscope_local]
    gold_out_sigs = [gold_sigs_all[i] for i in gold_outscope_local]

    # map gold in-scope local idx -> whether it's an implicit precondition
    prep_flags = {}
    for li, o in zip(gold_inscope_local, task.in_scope_ops):
        prep_flags[li] = o["name"] in _PREP

    # --- model side: prefix + model output, scored on the combined graph ---
    model_ops_only = parse_solution(model_network_text)
    n_emitted = len([o for o in model_ops_only if o.name in SIGNATURES
                     or True])  # count all emitted (incl. unknown, flagged below)
    unknown = sorted({o.name for o in model_ops_only if o.name not in SIGNATURES})

    combined = parse_solution("\n".join(prefix + [
        f"({o.name} {' '.join(o.args)})" for o in model_ops_only]))
    model_local = list(range(base, len(combined)))
    model_sigs = [s for s in op_sigs(combined) if s.idx in set(model_local)]

    # --- match model ops to gold slots (order of stages matters) ---
    # Stage 1: in-scope EXACT (pred-class, content) -> attempted, correct if exact
    #          predicate + salient constants too.
    # Stage 2: out-of-scope EXACT -> over-eagerness (claimed BEFORE stage 3 so a
    #          genuine next-step op isn't absorbed into an in-scope slot).
    # Stage 3: remaining in-scope slots <- remaining model ops of the SAME class
    #          -> attempted-but-incorrect (INCOMPETENCE, e.g. wrong ingredient).
    #          Omission only if no same-class op remains.
    available = list(model_sigs)
    attempted = correct = omitted = dropped_prec = 0
    unmatched_gold = []

    # stage 1
    for gi_local, gsig in zip(gold_inscope_local, gold_in_sigs):
        exact = next((ms for ms in available
                      if ms.slot_key() == gsig.slot_key()), None)
        if exact is not None:
            available.remove(exact)
            attempted += 1
            if exact.name == gsig.name and exact.constants == gsig.constants:
                correct += 1
        else:
            unmatched_gold.append((gi_local, gsig))

    # stage 2 (over-eagerness)
    overeager = 0
    out_pool = list(gold_out_sigs)
    for ms in list(available):
        hit = next((g for g in out_pool if g.slot_key() == ms.slot_key()), None)
        if hit is not None:
            out_pool.remove(hit)
            available.remove(ms)
            overeager += 1

    # stage 3 (incompetence vs omission)
    for gi_local, gsig in unmatched_gold:
        cands = [ms for ms in available if ms.pclass == gsig.pclass]
        if cands:
            # prefer highest content overlap, then earliest
            cands.sort(key=lambda ms: (-len(ms.content & gsig.content), ms.idx))
            available.remove(cands[0])
            attempted += 1            # attempted but not an exact match -> incorrect
        else:
            omitted += 1
            if prep_flags.get(gi_local):
                dropped_prec += 1

    unclassified = len(available)   # model ops matching neither in nor out

    n_in = len(gold_in_sigs)
    n_out = len(gold_out_sigs)
    ts = TaskScore(
        recipe_id=task.recipe_id, slice_steps=task.slice_steps, regime=regime,
        n_inscope_attempted=attempted, n_correct_attempts=correct,
        n_omitted=omitted, n_inscope_total=n_in, n_outscope_total=n_out,
        dropped_preconditions=dropped_prec, n_overeager=overeager,
        n_emitted_ops=len(model_ops_only), n_unclassified=unclassified,
    )
    ts.performance = (correct / attempted) if attempted > 0 else None
    ts.coverage = (correct / n_in) if n_in else 0.0
    ts.timidity_norm = (omitted / n_in) if n_in else 0.0
    ts.over_eagerness_norm = (overeager / n_out) if n_out else 0.0
    ts.signed_scope = ts.over_eagerness_norm - ts.timidity_norm
    if unknown:
        ts.notes.append(f"unknown predicates: {unknown}")
    # category from the signed scope axis (consistent with the x-axis plotted)
    if ts.signed_scope > 1e-9:
        ts.category = "over-eager"
    elif ts.signed_scope < -1e-9:
        ts.category = "timid"
    else:
        ts.category = "calibrated"   # x≈0; y (performance) tells competence
    if attempted == 0:
        ts.notes.append("performance=NA (no in-scope attempts) — maximally timid")
    return ts
