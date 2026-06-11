# PHASE 1 — Oracle Validation (HARD GATE)

**Verdict: ✅ PASS.** The MUHAI representation cleanly and programmatically
separates *precondition* edges ("required-for") from *sequence* edges
("followed-by"). The scope boundary (in-scope closure vs. out-of-scope set) can
be computed automatically with no hand-labeling. **Proceed to Phase 2.**

This conclusion is backed by (1) the official documentation, (2) an empirical
sweep over all 30 gold recipes, and (3) a hand-checked worked example. All three
are reproducible from this repo.

---

## 1. What the representation is

Each recipe is a network of MUHAI Cooking Language (MCL) primitives. Every
primitive is an s-expression following a **fixed, documented argument convention**
(documentation.pdf §3.1):

```
(name  <output-object(s)>  <kitchen-state-out>  <kitchen-state-in>  <inputs...>)
```

Two relations between operations are encoded *in different argument channels*:

| Relation | Channel | Meaning |
|---|---|---|
| **Sequence** ("followed-by") | the **kitchen-state thread**: each op's `kitchen-state-in` variable equals the previous op's `kitchen-state-out` | the recipe timeline (a total order) |
| **Precondition** ("required-for") | **object variables**: an op consumes, in a non-kitchen-state *input* slot, a variable that another op produced as an *object output* | true data dependency (a sparse DAG) |

The documentation states the precondition rule verbatim (§3, "MUHAI Cooking
Language"):

> "Through argument sharing a notion of dependencies between steps is encoded …
> Such dependencies are derivable from the network by realizing that a shared
> argument used as input in one predicate is only available once it is provided
> as output in the other predicate."

And it confirms that **file order is irrelevant** to execution — the dependency
network alone drives the simulator (§6.1, on `perfect-permuted-sequence.solution`):

> "The sequence of the primitives in the file itself are unimportant, since all
> metrics are [computed from the dependency network]."

This is the crux: because the kitchen-state variables sit in **fixed argument
positions** for every primitive, we can *exclude* them and recover the
object-dependency DAG — which is a strict, sparse subset of the timeline. The two
are therefore separable.

### Why "exclude the kitchen-state thread" is essential

If one naively treated *every* shared variable as a dependency, the kitchen-state
thread (which links each op to its immediate predecessor) would make the
dependency graph collapse onto the timeline — everything would look like it
"requires" its predecessor. The separation works precisely because the
kitchen-state channel is identifiable and removable. We identify it from the
per-primitive signature table (below), not from variable *names* (names are not
trustworthy in model output; argument *positions* are).

---

## 2. The signature table (and its three exceptions)

The vast majority of primitives are single-output: `out=[0]`, `ks_out=1`,
`ks_in=2`. There are exactly three documented departures, all handled in
`src/mcl.py`:

1. **Multi-output ops** put a *second* object output at index 1, shifting the
   kitchen-state args to indices 2 and 3:
   `drain`, `peel`, `seed`, `uncover`, `separate-eggs`, `transfer-contents`.
   (e.g. `transfer-contents` returns both the destination container *and* the
   leftover container.)
2. **`get-kitchen/1`** is a pure getter: its single argument *is* the initial
   kitchen-state output; it has no kitchen-state-in and no object output. It is
   the root of the timeline.
3. Cosmetic PDF typos (e.g. `grease` lists `?thing-to-grease` twice; some entries
   drop a comma between the two kitchen-state args) do not affect arity-based
   role assignment.

All 38 primitives that appear in the gold data are covered — verified below with
zero "unknown predicate" failures across 986 operations.

---

## 3. The query/traversal that yields the in-scope closure

Implemented in `src/mcl.py`:

- `build_graph(ops)` computes two edge sets:
  - `prec[B]` = `{A : B consumes, in a non-KS input slot, a variable A produced as an object output}`
  - `seq[B]`  = `{A : B.kitchen_state_in == A.kitchen_state_out}`
- **In-scope closure** of a requested slice `i..j`:
  `Graph.precondition_closure({i..j})` — the transitive closure over `prec`
  (the slice ops plus all their required-for ancestors).
- **Out-of-scope set**: operations reachable from `j` *only* via the sequence
  thread / that *depend on* the slice's outputs — i.e. temporal successors that
  are **not** in the precondition closure. (Computed in the Phase-2 slicer.)

---

## 4. Empirical evidence — all 30 gold recipes

Run: `cd src && python3 phase1_verify.py`

```
TOTAL                             986  956   920  956       405  (ops/seq/prec/adj/decoupled)

Unknown primitives anywhere?          False     <- full parse coverage, all 38 primitives
Any non-linear kitchen-state thread?  False     <- every recipe's timeline is a single clean chain
Precondition edges are 96.2% of sequence edges (count) — BUT they connect different pairs:
405/956 (42.4%) of adjacent-in-time pairs have NO precondition link
  => 'follows' does NOT imply 'requires'.
```

Interpretation:

- **Coverage:** 0 unknown primitives; every operation parsed and role-assigned.
- **Timeline is well-formed:** in all 30 recipes the kitchen-state thread is a
  single linear chain (each non-getter op has exactly one sequence predecessor).
  So "the operations that merely come after in time" is unambiguous.
- **The two relations are genuinely different:** 42.4% of all
  adjacent-in-timeline pairs have *no* precondition edge in either direction.
  Each such pair is a concrete instance of "B follows A but B does not require A."
  (The two edge *counts* being similar is incidental — precondition edges are
  often long-range, reaching back across many timeline steps, while many adjacent
  timeline steps are data-independent. The *pair sets* differ substantially.)

---

## 5. Worked example (hand-checked) — `easy-banana-bread`

Run: `cd src && python3 phase1_worked_example.py`

Target operation = **"Cream together butter, eggs and sugar"** = the `beat`
operation (op #11). The brief asks: is "crack eggs" a *required-for* dependency,
while the *next recipe step* is a temporal successor (out of scope)?

**Precondition closure of the cream step** (in-scope) =
`{#1 fetch butter, #2 fetch eggs, #3 fetch sugar, #8 transfer butter→bowl,`
`#9 crack, #10 transfer sugar→bowl, #11 beat}`

```
crack (#9) in precondition closure of beat (#11)?  True   <-- REQUIRED-FOR confirmed
```

Crucially, the closure pulls in `crack` (an *implicit precondition* — "crack
eggs" is never an instruction sentence, it lives inside the cream step's meaning)
and the three ingredient fetches it needs, but **does not** pull in the
bananas/vanilla/flour fetches (not needed) or any later step.

**The next recipe step** — "Add bananas and vanilla; beat well." (ops #12,13,14):

```
#12 transfer-contents  in_precondition_closure=False  depends_on_beat=True
#13 transfer-contents  in_precondition_closure=False  depends_on_beat=True
#14 beat               in_precondition_closure=False  depends_on_beat=True
```

Each *follows* the cream step and in fact *consumes its output* — so it is a
temporal successor, **not** a precondition. Executing it = over-eagerness.

**Cleanest "follows but does not require" pair** (two adjacent ingredient fetches):

```
#3 sugar -> #4 banana   (sequence edge: True, precondition edge: False)
```

Two operations adjacent in the timeline with zero data dependency — the
representation keeps them apart exactly as required.

---

## 6. Caveats / assumptions carried forward (honest notes)

1. **`get-kitchen` / prefix state is not a precondition edge.** The initial
   kitchen state is threaded via the kitchen-state channel, so `get-kitchen` does
   *not* appear in object-precondition closures. This is correct for our design:
   when a slice starts mid-recipe, the kitchen state produced by ops `1..i-1` is
   supplied by the **Phase-2 prefix executor** (a snapshot), not by precondition
   edges. The closure only needs to capture *object* preconditions of the slice.
2. **"First producer wins"** for a variable. Gold networks use each object-output
   variable exactly once as a producer; this held across all 30 recipes. Model
   output (Phase 4) may reuse/rebind variables — the harness will need to
   tolerate or normalize that, noted for Phase 4.
3. **Shared tools (e.g. `?mixing-tool`, `?oven`) are correctly *not*
   preconditions.** They are unbound default variables reused across ops but never
   produced as an object output, so the rule excludes them — matching intuition
   (reusing the same whisk is not a data dependency between cooking steps).
4. The separability claim relies on the **documented argument convention being
   followed**. It is, perfectly, across all gold data. Model-emitted networks that
   violate the convention would degrade precondition extraction; the harness
   should validate predicate arity on ingest (Phase 4).

---

## 7. Reproduce

```
cd src
python3 phase1_verify.py          # all-recipe sweep (table + totals)
python3 phase1_worked_example.py  # the banana-bread worked example
python3 mcl.py "<path>/easy-banana-bread.solution"   # per-op prec/seq dump
```

Core implementation: `src/mcl.py` (signature table, parser, `build_graph`,
`precondition_closure`).
