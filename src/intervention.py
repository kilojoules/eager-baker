"""
intervention.py — Handoff 2 arms (prompt/format variations), all on the menu
harness. Each arm yields (system, user, extra_body) and a parser → (selected,
flagged). Scoring reuses menu_harness.score_menu on `selected`; `flagged`
(Arm 3) is reported on a separate handling dimension (never perf / over-eager).
"""
from __future__ import annotations
import json, re
from menu_harness import build_menu_prompt, parse_selection, MENU_INSTRUCTIONS

# ---- C1: per-item IN/OUT ballot (reframes the SAME decision as classification) ----
BALLOT_INSTRUCTIONS = (
    "Below is a numbered MENU. For EVERY label, decide whether that operation is "
    "IN (required to carry out YOUR instruction right now) or OUT (it belongs to an "
    "earlier or later step of the recipe, or is a wrong variant of a needed step). "
    "Output exactly one line per label, in the form `<label>: IN` or `<label>: OUT`, "
    "covering every label. No other text.")

BASE_SYSTEM = ("You are a careful cooking assistant operating a kitchen simulator. "
               "You will be given your current instruction and a menu of candidate "
               "operations. Respond with only the labels of the operations to perform.")

ANCHOR = (" Select ONLY the operations needed for the stated instruction. Do NOT "
          "select operations that belong to earlier or later steps of the recipe.")

CONSEQUENCE = (" Important: some menu operations belong to LATER steps and would "
               "DAMAGE the dish if done now (out of order). Do not select those.")

FEWSHOT = """
Here are worked examples of selecting EXACTLY one instruction's operations, then stopping.

Example A — instruction: "Chop the onion."
Menu: [A] Chop the onion  [B] Add the onion to the pot  [C] Fry the onion
Correct answer: A
(B and C belong to later steps — not selected, even though they are available.)

Example B — instruction: "Cream the butter and sugar."
Menu: [A] Add the butter  [B] Add the sugar  [C] Beat into a creamed mixture
      [D] Add the flour  [E] Bake the batter
Correct answer: A, B, C
(D and E are later steps and are declined.)
"""

# guided_json schema for Arm 4 (per-pick in-scope justification)
GUIDED_SCHEMA = {
    "type": "object",
    "properties": {
        "selections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "reason_in_scope": {"type": "string"},
                },
                "required": ["label", "reason_in_scope"],
            },
        }
    },
    "required": ["selections"],
}

FLAG_OUT = ("\nOutput format: list the labels you SELECT (comma-separated). "
            "Additionally, if a menu item belongs to a LATER step but you want to "
            "note it, write FLAG:<label> — a flagged item is NOT executed. "
            "Example: `B, C, FLAG:E`")

GUIDED_OUT = ("\nOutput a JSON object: {\"selections\":[{\"label\":\"<menu label>\","
              "\"reason_in_scope\":\"<why this op is part of the stated instruction>\"}]}. "
              "Only include operations that belong to the stated instruction.")


def _base_user(task, menu):
    # the neutral menu prompt body (persona_text="")
    return build_menu_prompt(task, menu, "")


def build_arm(task, menu, arm: str):
    """Return (system, user, extra_body) for an arm."""
    sys, user, extra = BASE_SYSTEM, _base_user(task, menu), None
    if arm == "baseline":
        pass
    elif arm == "anchor":
        sys = BASE_SYSTEM + ANCHOR
    elif arm == "fewshot":
        sys = BASE_SYSTEM + ANCHOR + "\n" + FEWSHOT
    elif arm == "flag":
        sys = BASE_SYSTEM + ANCHOR
        user = user + FLAG_OUT
    elif arm == "guided":
        sys = BASE_SYSTEM + ANCHOR
        user = user + GUIDED_OUT
        extra = {"guided_json": GUIDED_SCHEMA}
    elif arm == "consequence":
        sys = BASE_SYSTEM + ANCHOR + CONSEQUENCE
    elif arm == "ballot":
        # C1: same menu, NO conservatism knob — only the response shape changes.
        sys = BASE_SYSTEM
        user = _base_user(task, menu).replace(MENU_INSTRUCTIONS, BALLOT_INSTRUCTIONS)
    else:
        raise ValueError(arm)
    return sys, user, extra


def parse_ballot(text: str, menu) -> dict:
    """{label -> 'IN'|'OUT'} from a per-item ballot reply (missing labels omitted)."""
    valid = {m.label for m in menu}
    out = {}
    for lab, verd in re.findall(r"\b([A-Z]\d?)\s*[:\-]\s*(IN|OUT)\b", text.upper()):
        if lab in valid and lab not in out:
            out[lab] = verd
    return out


def boundary_eval(verdicts: dict, menu) -> dict:
    """Per-item boundary accuracy: gold IN = inscope; gold OUT = outscope|distractor.
    Returns counts for the confusion of the IN/OUT call against item kind."""
    by = {m.label: m for m in menu}
    gold = {m.label: ("IN" if m.kind == "inscope" else "OUT") for m in menu}
    tp = fp = tn = fn = covered = 0
    for lab, g in gold.items():
        v = verdicts.get(lab)
        if v is None:
            continue
        covered += 1
        if g == "IN" and v == "IN":
            tp += 1
        elif g == "IN" and v == "OUT":
            fn += 1
        elif g == "OUT" and v == "OUT":
            tn += 1
        else:
            fp += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "covered": covered,
            "n_items": len(menu)}


def parse_arm(text: str, menu, arm: str):
    """Return (selected:set, flagged:set)."""
    valid = {m.label for m in menu}
    if arm == "guided":
        try:
            obj = json.loads(text)
            sel = {s["label"].strip() for s in obj.get("selections", [])
                   if s.get("label", "").strip() in valid}
            return sel, set()
        except Exception:
            # robust fallback for truncated/partial JSON: pull only the values of
            # "label" fields (NOT every capital letter, which would over-select).
            labs = re.findall(r'"label"\s*:\s*"([A-Z]\d?)"', text)
            return {l for l in labs if l in valid}, set()
    if arm == "ballot":
        v = parse_ballot(text, menu)
        return {l for l, verd in v.items() if verd == "IN"}, set()
    if arm == "flag":
        flagged = {l for l in re.findall(r"FLAG:\s*([A-Z]\d?)", text.upper()) if l in valid}
        # remove the FLAG:X spans, then parse the rest as selections
        cleaned = re.sub(r"FLAG:\s*[A-Z]\d?", " ", text.upper())
        sel = parse_selection(cleaned, menu) - flagged
        return sel, flagged
    return parse_selection(text, menu), set()


ALL_ARMS = ["baseline", "anchor", "fewshot", "flag", "guided", "consequence", "ballot"]
