"""
mcl.py — MUHAI Cooking Language: parser + dependency/sequence graph extraction.

This module is the foundation for the scope-calibration benchmark. It parses
.solution / gold-XML networks of MUHAI Cooking Language (MCL) primitives and
extracts TWO distinct relations between operations:

  * SEQUENCE (temporal "followed-by") edges  -- via the kitchen-state thread
        each op consumes a kitchen-state-in variable that some earlier op produced
        as its kitchen-state-out. This forms a (near-)total order: the recipe's
        timeline.

  * PRECONDITION (data-dependency "required-for") edges -- via OBJECT variables
        op B requires op A iff B uses, in a non-kitchen-state INPUT position, a
        variable that A produced as an OBJECT OUTPUT. (The MUHAI documentation,
        sec. 3, states exactly this rule: "a shared argument used as input in one
        predicate is only available once it is provided as output in the other.")

The whole Phase-1 gate rests on these two being SEPARABLE. They are, because the
kitchen-state variables occupy FIXED, DOCUMENTED argument positions for every
primitive, so we can exclude them from the data-dependency computation. What
remains is a sparse DAG (true preconditions) that is a strict subset of the dense
sequence chain.

Signature convention (MUHAI docs sec. 3.1): every primitive is
    (name <output-object(s)> <kitchen-state-out> <kitchen-state-in> <inputs...>)
with two documented departures from the single-output default:
  - multi-output ops put a SECOND object output at index 1, shifting ks to (2,3)
  - get-kitchen/1 is a pure getter: arg0 IS the (initial) kitchen-state output
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Signature table.  For each primitive we record:
#   out    : indices of OBJECT outputs (excludes the kitchen-state output)
#   ks_out : index of the kitchen-state-out argument (or None)
#   ks_in  : index of the kitchen-state-in argument (or None)
# Every other argument index is an INPUT slot (may hold a ?variable or a constant).
# Values transcribed directly from documentation.pdf section 3.1.
# ---------------------------------------------------------------------------

# Primitives whose object output spans TWO arguments (ks shifted to 2,3).
_MULTI_OUT = {
    "drain": 6,            # ?drained-thing ?remaining-liquid ks-out ks-in ...
    "peel": 6,             # ?peeled-thing ?peel ks-out ks-in ...
    "seed": 6,             # ?seeded-thing ?seed ks-out ks-in ...
    "uncover": 5,          # ?uncovered-thing ?cover ks-out ks-in ?covered-thing
    "separate-eggs": 8,    # ?egg-yolks ?egg-whites ks-out ks-in ...
    "transfer-contents": 8,# ?transferred ?rest ks-out ks-in ...
}

# Standard single-output primitives: out=[0], ks_out=1, ks_in=2.
_SINGLE_OUT = {
    "bake": 9, "boil": 8, "beat": 5, "bring-to-temperature": 6, "cover": 5,
    "cut": 6, "crack": 5, "dip": 5, "fetch": 5, "fetch-and-proportion": 7,
    "flatten": 5, "flour": 5, "fry": 8, "grease": 6, "grind": 5,
    "leave-for-time": 6, "line": 5, "mash": 5, "melt": 5, "mingle": 5,
    "mix": 5, "portion-and-arrange": 8, "preheat-oven": 6, "refrigerate": 7,
    "shake": 4, "shape": 5, "sift": 6, "spread": 6, "sprinkle": 5,
    "transfer-items": 6, "wash": 4,
}


@dataclass(frozen=True)
class Sig:
    out: tuple          # object-output arg indices
    ks_out: int | None
    ks_in: int | None


SIGNATURES: dict[str, Sig] = {}
for _name in _SINGLE_OUT:
    SIGNATURES[_name] = Sig(out=(0,), ks_out=1, ks_in=2)
for _name in _MULTI_OUT:
    SIGNATURES[_name] = Sig(out=(0, 1), ks_out=2, ks_in=3)
# get-kitchen/1: arg0 is the kitchen-state output; no object output, no ks-in.
SIGNATURES["get-kitchen"] = Sig(out=(), ks_out=0, ks_in=None)


def is_var(token: str) -> bool:
    return isinstance(token, str) and token.startswith("?")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

@dataclass
class Op:
    """One primitive operation occurrence."""
    idx: int                       # position in the network (file order)
    name: str
    args: list                     # raw argument tokens (strings)
    step: int | None = None        # NL step index it belongs to (XML only)
    step_kind: str | None = None   # 'ingredient' | 'instruction' | None
    utterance: str | None = None   # NL text of the owning step (XML only)

    # ---- role-aware accessors (raise if predicate unknown) ----
    @property
    def sig(self) -> Sig:
        if self.name not in SIGNATURES:
            raise KeyError(f"Unknown MCL primitive: {self.name!r}")
        return SIGNATURES[self.name]

    def object_outputs(self) -> list:
        s = self.sig
        return [self.args[i] for i in s.out if i < len(self.args)]

    def ks_out_var(self):
        s = self.sig
        return self.args[s.ks_out] if s.ks_out is not None and s.ks_out < len(self.args) else None

    def ks_in_var(self):
        s = self.sig
        return self.args[s.ks_in] if s.ks_in is not None and s.ks_in < len(self.args) else None

    def input_vars(self) -> list:
        """Variable tokens in non-output, non-kitchen-state positions."""
        s = self.sig
        reserved = set(s.out)
        if s.ks_out is not None:
            reserved.add(s.ks_out)
        if s.ks_in is not None:
            reserved.add(s.ks_in)
        return [a for i, a in enumerate(self.args)
                if i not in reserved and is_var(a)]

    def __repr__(self):
        return f"Op#{self.idx}({self.name} {' '.join(map(str, self.args))})"


def _parse_op_strings(text: str) -> list[tuple[str, list]]:
    """Extract (name, args) tuples from a blob of s-expressions, depth-aware.

    Top-level parenthesised forms are the operations. Nested parens inside an
    operation (e.g. a model writing `(beat ... (list ?a ?b) ...)`) are FLATTENED
    into the argument list, dropping a leading `list` keyword — so the inner
    variables still register as inputs. Comments (`;` and `#` header lines) ignored.
    """
    cleaned = "\n".join(
        line.split(";", 1)[0] for line in text.splitlines()
        if not line.strip().startswith("#")
    )
    ops = []
    i, n = 0, len(cleaned)
    while i < n:
        if cleaned[i] != "(":
            i += 1
            continue
        # find the matching close paren for this top-level op
        depth, j = 0, i
        while j < n:
            if cleaned[j] == "(":
                depth += 1
            elif cleaned[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = cleaned[i + 1:j]
        # flatten: drop parens and the `list` keyword, keep all other tokens
        flat = inner.replace("(", " ").replace(")", " ").split()
        flat = [t for t in flat if t != "list"]
        if flat:
            ops.append((flat[0], flat[1:]))
        i = j + 1
    return ops


def parse_solution(text: str) -> list[Op]:
    """Parse a .solution / meaning-only network into a list of Op."""
    ops = []
    for i, (name, args) in enumerate(_parse_op_strings(text)):
        ops.append(Op(idx=i, name=name, args=args))
    return ops


def parse_solution_file(path: str) -> list[Op]:
    with open(path) as f:
        return parse_solution(f.read())


def parse_gold_xml(path: str) -> tuple[list[Op], dict]:
    """Parse a gold 'utterance and meaning' XML.
    Returns (ops, meta) where ops carry step/step_kind/utterance, and meta has
    'id', 'title', and 'steps' (ordered list of {kind, utterance, op_indices})."""
    tree = ET.parse(path)
    root = tree.getroot()
    meta = {
        "id": (root.findtext("id") or "").strip(),
        "title": (root.findtext("title") or "").strip(),
        "steps": [],
    }
    ops: list[Op] = []
    step_no = 0

    def add_section(section_tag, kind):
        nonlocal step_no
        sec = root.find(section_tag)
        if sec is None:
            return
        for node in sec:
            utt = (node.findtext("utterance") or "").strip()
            meaning = node.findtext("meaning") or ""
            op_indices = []
            for name, args in _parse_op_strings(meaning):
                op = Op(idx=len(ops), name=name, args=args,
                        step=step_no, step_kind=kind, utterance=utt)
                ops.append(op)
                op_indices.append(op.idx)
            meta["steps"].append(
                {"kind": kind, "utterance": utt, "op_indices": op_indices})
            step_no += 1

    add_section("ingredients", "ingredient")
    add_section("instructions", "instruction")
    return ops, meta


# ---------------------------------------------------------------------------
# Graph extraction — the heart of the Phase-1 separability claim.
# ---------------------------------------------------------------------------

@dataclass
class Graph:
    ops: list[Op]
    prec: dict                 # op idx -> set of op idxs it DIRECTLY requires
    seq: dict                  # op idx -> set of op idxs that DIRECTLY precede it (ks thread)
    producer: dict = field(default_factory=dict)  # variable -> producing op idx

    def precondition_closure(self, targets) -> set:
        """All ops transitively required-for the given target op idxs (incl. targets)."""
        seen, stack = set(), list(targets)
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.prec.get(n, ()))
        return seen

    def sequence_predecessors_closure(self, targets) -> set:
        seen, stack = set(), list(targets)
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.seq.get(n, ()))
        return seen


def build_graph(ops: list[Op]) -> Graph:
    """Compute precondition (data-dependency) and sequence (kitchen-state) edges.

    precondition edge  A -> B : B has an INPUT variable that A produced as an
                                OBJECT output (kitchen-state excluded).
    sequence edge      A -> B : B's kitchen-state-IN variable == A's
                                kitchen-state-OUT variable.
    """
    # Map each OBJECT-output variable to the op that produced it.
    obj_producer: dict = {}
    ks_producer: dict = {}
    for op in ops:
        for v in op.object_outputs():
            if is_var(v):
                obj_producer.setdefault(v, op.idx)  # first producer wins
        ks = op.ks_out_var()
        if is_var(ks):
            ks_producer.setdefault(ks, op.idx)

    prec = {op.idx: set() for op in ops}
    seq = {op.idx: set() for op in ops}
    for op in ops:
        # precondition edges from object-variable data flow
        for v in op.input_vars():
            src = obj_producer.get(v)
            if src is not None and src != op.idx:
                prec[op.idx].add(src)
        # sequence edge from the kitchen-state thread
        ks_in = op.ks_in_var()
        if is_var(ks_in):
            src = ks_producer.get(ks_in)
            if src is not None and src != op.idx:
                seq[op.idx].add(src)

    g = Graph(ops=ops, prec=prec, seq=seq, producer=obj_producer)
    return g


if __name__ == "__main__":
    import sys
    ops = parse_solution_file(sys.argv[1])
    g = build_graph(ops)
    for op in ops:
        print(f"{op.idx:2d} {op.name:22s} "
              f"prec={sorted(g.prec[op.idx])} seq={sorted(g.seq[op.idx])}")
