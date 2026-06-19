"""
model_client.py — uniform model interface (Step 3 RunPod addendum §C).

THE rule: every model in a comparison goes through this SAME interface, so
"model difference" is never contaminated by "harness difference". Backends here
are all HTTP/SDK calls (NOT the in-session subagent path). Same prompt rendering,
same parser (menu_harness.parse_selection), same frozen scorer.
"""
from __future__ import annotations
import re
import time
from dataclasses import dataclass


@dataclass
class GenConfig:
    temperature: float = 0.0     # selection task -> modal choice, not variety
    max_tokens: int = 512
    seed: int = 0


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove Qwen-style <think>...</think> preambles (belt & suspenders even if
    thinking is disabled server-side)."""
    t = _THINK.sub("", text or "")
    # also drop an unterminated leading <think> with no close
    if "<think>" in t and "</think>" not in t:
        t = t.split("<think>", 1)[0]
    return t.strip()


def _retry(fn, attempts=6):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa
            last = e
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    raise last


class ModelClient:
    name: str

    def complete(self, system: str, user: str, cfg: GenConfig) -> str:
        raise NotImplementedError


class OpenAICompatClient(ModelClient):
    """vLLM (Qwen on RunPod) or any OpenAI-compatible endpoint."""

    def __init__(self, name, base_url, api_key, model_id, extra_body=None,
                 omit_seed=None):
        from openai import OpenAI
        self.name = name
        self.model_id = model_id
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=120)
        self.extra_body = extra_body or {}
        # Gemini's OpenAI-compatibility endpoint rejects `seed`; auto-omit it
        # there. vLLM (RunPod) keeps seed=0 exactly as the cached runs used it.
        self._omit_seed = (("googleapis" in (base_url or ""))
                           if omit_seed is None else omit_seed)

    def complete(self, system, user, cfg):
        def call():
            kwargs = dict(
                model=self.model_id,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                extra_body=self.extra_body,
            )
            if not self._omit_seed:
                kwargs["seed"] = cfg.seed
            r = self.client.chat.completions.create(**kwargs)
            return r.choices[0].message.content or ""
        return strip_think(_retry(call))

    def classify(self, system, user, choices, cfg=None):
        """Constrained single-choice classification with first-token logprobs.
        Returns (chosen:str, probs:dict[choice->prob]). Used for C3 (logprob
        boundary read-out): choices=["IN","OUT"] -> probs["IN"] is P(in-scope)."""
        cfg = cfg or GenConfig(max_tokens=4)

        def call():
            kwargs = dict(
                model=self.model_id,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=cfg.temperature, max_tokens=cfg.max_tokens,
                logprobs=True, top_logprobs=20,
                extra_body={**self.extra_body, "guided_choice": list(choices)},
            )
            if not self._omit_seed:
                kwargs["seed"] = cfg.seed
            return self.client.chat.completions.create(**kwargs)
        r = _retry(call)
        chosen = (r.choices[0].message.content or "").strip()
        probs = {c: 0.0 for c in choices}
        try:
            top = r.choices[0].logprobs.content[0].top_logprobs
            import math
            lp = {}
            for c in choices:
                # match the first generated token to a choice by leading char(s)
                best = None
                for e in top:
                    tok = e.token.strip().upper()
                    if tok and c.upper().startswith(tok):
                        best = e.logprob if best is None else max(best, e.logprob)
                lp[c] = best
            present = {c: v for c, v in lp.items() if v is not None}
            if present:
                floor = min(present.values()) - 6.0
                ex = {c: math.exp(lp.get(c) if lp.get(c) is not None else floor)
                      for c in choices}
                z = sum(ex.values()) or 1.0
                probs = {c: ex[c] / z for c in choices}
            else:
                probs = {c: (1.0 if c == chosen else 0.0) for c in choices}
        except Exception:
            probs = {c: (1.0 if c == chosen else 0.0) for c in choices}
        return chosen, probs


class AnthropicClient(ModelClient):
    """Claude through the SAME interface (NOT subagents). Requires ANTHROPIC_API_KEY."""

    def __init__(self, name, model_id):
        import anthropic
        self.name = name
        self.model_id = model_id
        self.client = anthropic.Anthropic()

    def complete(self, system, user, cfg):
        def call():
            r = self.client.messages.create(
                model=self.model_id,
                system=system,
                messages=[{"role": "user", "content": user}],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            return "".join(b.text for b in r.content if b.type == "text")
        return strip_think(_retry(call))
