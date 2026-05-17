"""LLM provider client. Callers pass intent (role + body + tier); provider,
flags, model, channel are config. One chain: default -> emergency, generic
over an ordered list so a fallback link is a config edit, not code.

claude_cli isolation is built in and non-negotiable: a pipeline call must
never inherit persona / user MCP / output-style.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request

from . import config

_ISOLATION = ["--setting-sources", "", "--strict-mcp-config"]


class LLMError(Exception):
    pass


def _claude_bin() -> str:
    b = shutil.which("claude")
    if not b:
        raise LLMError("claude CLI not found on PATH")
    return b


class LLMClient:
    def __init__(self, cfg: dict | None = None, on_alert=None):
        self.cfg = cfg or config.load()
        llm = self.cfg.get("llm", {})
        self.chain = [llm[k] for k in ("default", "fallback", "emergency")
                      if llm.get(k)]
        self.specs = llm
        self.tiers = self.cfg.get("tiers", {})
        self._on_alert = on_alert

    def _alert(self, severity, atype, message, source):
        if self._on_alert:
            try:
                self._on_alert(severity, atype, message, source)
            except Exception:
                pass

    def call(self, role: str, body: str, *, tier: str = "cheap") -> str:
        model = self.tiers.get(tier) or self.tiers.get("cheap")
        last = None
        for i, name in enumerate(self.chain):
            spec = self.specs.get(name)
            if not spec:
                continue
            try:
                return self._run(spec, model, body)
            except Exception as e:
                last = e
                terminal = i == len(self.chain) - 1
                self._alert(
                    "critical" if terminal else "warn",
                    "llm_provider",
                    f"{role}: provider {name} failed ({e}); "
                    + ("chain exhausted" if terminal else "rotating"),
                    f"llm.py:{name}",
                )
        raise LLMError(f"{role}: all providers failed; last: {last}")

    def _run(self, spec: dict, model: str, prompt: str) -> str:
        kind = spec.get("kind")
        if kind == "claude_cli":
            return self._run_claude_cli(spec, model, prompt)
        if kind == "ollama":
            return self._run_ollama(spec, prompt)
        raise LLMError(f"unknown provider kind: {kind}")

    def _run_claude_cli(self, spec: dict, model: str, prompt: str) -> str:
        mode = spec.get("mode", "json")
        fmt = "stream-json" if mode == "stream_json" else "json"
        cmd = [_claude_bin(), "-p", prompt, "--model", model,
               *_ISOLATION, "--output-format", fmt]
        if fmt == "stream-json":
            cmd.append("--verbose")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=spec.get("timeout_s", 120))
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"claude_cli timeout {spec.get('timeout_s',120)}s") from e
        if r.returncode != 0:
            raise LLMError(f"claude_cli rc{r.returncode}: {r.stderr.strip()[:200]}")
        return self._parse_claude(r.stdout, fmt)

    @staticmethod
    def _parse_claude(out: str, fmt: str) -> str:
        if fmt == "stream-json":
            rec = None
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "result":
                    rec = ev
            if rec is None:
                raise LLMError("claude_cli stream-json: no result event")
        else:
            j = json.loads(out)
            recs = [x for x in j if x.get("type") == "result"] \
                if isinstance(j, list) else [j]
            if not recs:
                raise LLMError("claude_cli json: no result event")
            rec = recs[0]
        if rec.get("is_error"):
            raise LLMError(f"claude_cli is_error: {str(rec.get('result'))[:200]}")
        text = rec.get("result")
        if not text:
            raise LLMError("claude_cli: empty result")
        return text

    def _run_ollama(self, spec: dict, prompt: str) -> str:
        payload = json.dumps({
            "model": spec.get("model", "qwen2.5:7b"),
            "prompt": prompt,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=spec.get("timeout_s", 180)) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LLMError(f"ollama unreachable: {e}") from e
        text = data.get("response")
        if not text:
            raise LLMError("ollama: empty response")
        return text
