"""
cli_client.py — a ModelClient backend that drives a local AGENTIC CLI in headless
mode. Two flavors are used here (see step3_run_cli.py):
  * Antigravity `agy` — serves Gemini/Claude/GPT-OSS behind a Google login;
  * Claude Code `claude` — serves Claude behind a personal subscription
    (CLAUDE_CONFIG_DIR=~/.claude-personal).

IMPORTANT — this is NOT the clean OpenAI-compatible decoding path that
OpenAICompatClient uses for the vLLM models. Each CLI wraps the model in a full
agent stack (its own system prompt, tools, memory) and exposes NO temperature /
seed / logprobs / max_tokens control. Any result obtained through it is therefore
HARNESS-CONFOUNDED relative to the vLLM models and MUST be labelled as such in the
writeups. These paths are used only because no API key / OpenAI-compatible
endpoint is available for these models.

The prompt rendering, parser (menu_harness.parse_selection) and scorer are
otherwise IDENTICAL to step3_run.py — only the backend differs.
"""
from __future__ import annotations
import os
import subprocess
import tempfile
from model_client import ModelClient, strip_think, _retry


class CLIModelClient(ModelClient):
    def __init__(self, name, argv, model=None, model_flag="--model",
                 extra_flags=None, prompt_flag="-p", out_message_flag=None,
                 env=None, cwd=None, timeout=300):
        self.name = name                # filesystem/label-safe, e.g. "gemini-3.5-flash"
        self.argv = list(argv)          # the CLI invocation, e.g. ["agy"] or ["codex","exec"]
        self.model = model              # backend model string passed via model_flag (or None)
        self.model_flag = model_flag
        self.extra_flags = list(extra_flags or [])   # flavor-specific headless flags
        self.prompt_flag = prompt_flag  # "-p" (agy/claude); None => prompt is a positional arg (codex)
        # if set, the CLI writes its FINAL message to a file (codex `-o`); read that
        # instead of stdout, which otherwise carries the agent's event log
        self.out_message_flag = out_message_flag
        # env vars merged over os.environ for the subprocess; a None value UNSETS
        # that var (e.g. drop ANTHROPIC_API_KEY so `claude` uses the subscription)
        self.env = env
        # a fresh, file-free working dir so the agent picks up NO project context
        self.cwd = cwd or tempfile.mkdtemp(prefix="cli_eval_")
        self.timeout = timeout          # hard subprocess timeout (s)

    def _build_env(self):
        if not self.env:
            return None
        e = dict(os.environ)
        for k, v in self.env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return e

    def complete(self, system, user, cfg=None):
        # the agentic CLI has no separate system role -> fold system into the prompt
        prompt = f"{system}\n\n{user}" if system else user
        cmd = list(self.argv)
        cmd += [self.prompt_flag, prompt] if self.prompt_flag else [prompt]
        cmd += self.extra_flags
        if self.model:
            cmd += [self.model_flag, self.model]
        out_path = None
        if self.out_message_flag:        # capture the final message in a file, not stdout
            fd, out_path = tempfile.mkstemp(prefix="cli_out_", suffix=".txt", dir=self.cwd)
            os.close(fd)
            cmd += [self.out_message_flag, out_path]
        run_env = self._build_env()

        def call():
            r = subprocess.run(cmd, cwd=self.cwd, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True,
                               timeout=self.timeout, env=run_env)
            if r.returncode != 0:
                raise RuntimeError(f"{self.argv[0]} rc={r.returncode}: "
                                   f"{(r.stderr or '').strip()[-300:]}")
            if out_path:
                with open(out_path) as f:
                    return f.read()
            return r.stdout or ""
        try:
            return strip_think(_retry(call, attempts=3))
        finally:
            if out_path and os.path.exists(out_path):
                os.remove(out_path)
