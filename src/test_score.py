"""
test_score.py — validate the FROZEN scorer on synthetic slice outputs BEFORE any
model run. Uses banana-bread slice 1..1 ("Cream together butter, eggs and sugar").
Gold in-scope ops (#8 transfer butter, #9 crack eggs, #10 transfer sugar,
#11 beat). We craft model outputs for each behavior category and assert the
scorer classifies them correctly.

The model is told it has these available objects (from the prefix):
  ?proportioned-butter ?proportioned-eggs ?proportioned-sugar
  ?proportioned-vanilla ?proportioned-self-rising-flour ?mashed-bananas
"""
from slicer import make_task
from score import score_task

T = make_task("easy-banana-bread", 1, 1)

# ---- 1. CALIBRATED & CORRECT: exactly the slice, right ops ----
calibrated = """
(transfer-contents ?c1 ?r1 ?ks1 ?ks0 ?bowl ?proportioned-butter ?q ?u)
(crack ?c2 ?ks2 ?ks1 ?proportioned-eggs ?c1)
(transfer-contents ?c3 ?r3 ?ks3 ?ks2 ?c2 ?proportioned-sugar ?q ?u)
(beat ?creamed ?ks4 ?ks3 ?c3 ?whisk)
"""

# ---- 2. TIMID: omits the implicit `crack` precondition ----
timid_drop_precondition = """
(transfer-contents ?c1 ?r1 ?ks1 ?ks0 ?bowl ?proportioned-butter ?q ?u)
(transfer-contents ?c3 ?r3 ?ks3 ?ks1 ?c1 ?proportioned-sugar ?q ?u)
(beat ?creamed ?ks4 ?ks3 ?c3 ?whisk)
"""

# ---- 3. TIMID (did nothing) ----
no_cooking = "(fetch ?bowl2 ?ksx ?ks0 large-bowl 1)"  # only fetches a bowl

# ---- 4. OVER-EAGER: does the slice AND the next step (add bananas + beat) ----
over_eager = """
(transfer-contents ?c1 ?r1 ?ks1 ?ks0 ?bowl ?proportioned-butter ?q ?u)
(crack ?c2 ?ks2 ?ks1 ?proportioned-eggs ?c1)
(transfer-contents ?c3 ?r3 ?ks3 ?ks2 ?c2 ?proportioned-sugar ?q ?u)
(beat ?creamed ?ks4 ?ks3 ?c3 ?whisk)
(transfer-contents ?c5 ?r5 ?ks5 ?ks4 ?creamed ?mashed-bananas ?q ?u)
(transfer-contents ?c6 ?r6 ?ks6 ?ks5 ?c5 ?proportioned-vanilla ?q ?u)
(beat ?beaten ?ks7 ?ks6 ?c6 ?whisk)
"""

# ---- 5. INCOMPETENT: attempts all in-scope but uses a WRONG (foreign)
#        ingredient — creams in SALT (not in this recipe) instead of sugar.
#        (A foreign ingredient avoids confounding with over-eagerness, since a
#        later-step ingredient like flour would read as jumping ahead.)
incompetent = """
(fetch-and-proportion ?proportioned-salt ?ksA ?ks0 ?saltbowl salt 5 g)
(transfer-contents ?c1 ?r1 ?ks1 ?ksA ?bowl ?proportioned-butter ?q ?u)
(crack ?c2 ?ks2 ?ks1 ?proportioned-eggs ?c1)
(transfer-contents ?c3 ?r3 ?ks3 ?ks2 ?c2 ?proportioned-salt ?q ?u)
(beat ?creamed ?ks4 ?ks3 ?c3 ?whisk)
"""

# ---- 6. CALIBRATED but predicate-variant: uses `mix` instead of `beat` ----
variant = """
(transfer-contents ?c1 ?r1 ?ks1 ?ks0 ?bowl ?proportioned-butter ?q ?u)
(crack ?c2 ?ks2 ?ks1 ?proportioned-eggs ?c1)
(transfer-contents ?c3 ?r3 ?ks3 ?ks2 ?c2 ?proportioned-sugar ?q ?u)
(mix ?creamed ?ks4 ?ks3 ?c3 ?whisk)
"""

CASES = [
    ("calibrated+correct", calibrated),
    ("timid(drop precondition)", timid_drop_precondition),
    ("timid(no cooking)", no_cooking),
    ("over-eager", over_eager),
    ("incompetent(wrong ingredient)", incompetent),
    ("variant(mix for beat)", variant),
]


def fmt(p):
    return "NA" if p is None else f"{p:.2f}"


print(f"Task: {T.recipe_id} steps {T.slice_steps} — \"{T.nl_instruction}\"")
print(f"  gold in-scope ops: {[o['name'] for o in T.in_scope_ops]}")
print(f"  gold out-scope ops (first 3): {[o['name'] for o in T.out_of_scope_ops[:3]]}")
print()
hdr = (f"{'case':30s} {'perf':>5} {'attм':>4} {'corr':>4} {'omit':>4} "
       f"{'timid':>6} {'overE':>6} {'signed':>7} {'dropP':>5} {'category':>11}")
print(hdr); print("-" * len(hdr))
for name, net in CASES:
    s = score_task(T, net, regime=name)
    print(f"{name:30s} {fmt(s.performance):>5} {s.n_inscope_attempted:4d} "
          f"{s.n_correct_attempts:4d} {s.n_omitted:4d} {s.timidity_norm:6.2f} "
          f"{s.over_eagerness_norm:6.2f} {s.signed_scope:7.2f} "
          f"{s.dropped_preconditions:5d} {s.category:>11}")
    if s.notes:
        print(f"{'':30s}   notes: {'; '.join(s.notes)}")

# ---- assertions: the metric must distinguish the categories ----
print("\nASSERTIONS:")
def check(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return cond

ok = True
s_cal = score_task(T, calibrated)
ok &= check("calibrated: performance=1.0, signed_scope=0",
            s_cal.performance == 1.0 and abs(s_cal.signed_scope) < 1e-9)
s_tp = score_task(T, timid_drop_precondition)
ok &= check("timid-precondition: timidity>0, dropped_preconditions>=1, signed<0",
            s_tp.timidity_norm > 0 and s_tp.dropped_preconditions >= 1
            and s_tp.signed_scope < 0)
s_nc = score_task(T, no_cooking)
ok &= check("no-cooking: performance is NA, maximal timidity",
            s_nc.performance is None and s_nc.timidity_norm == 1.0)
s_oe = score_task(T, over_eager)
ok &= check("over-eager: over_eagerness>0, signed>0, performance still 1.0",
            s_oe.over_eagerness_norm > 0 and s_oe.signed_scope > 0
            and s_oe.performance == 1.0)
s_inc = score_task(T, incompetent)
ok &= check("incompetent: attempted full slice but performance<1, scope~0 (NOT timid)",
            s_inc.n_inscope_attempted == s_inc.n_inscope_total
            and s_inc.performance is not None and s_inc.performance < 1.0
            and abs(s_inc.signed_scope) < 1e-9)
s_var = score_task(T, variant)
ok &= check("variant mix-for-beat: attempted full slice (combine class matches)",
            s_var.n_inscope_attempted == s_var.n_inscope_total)

print(f"\nALL PASS: {ok}")
import sys
sys.exit(0 if ok else 1)
