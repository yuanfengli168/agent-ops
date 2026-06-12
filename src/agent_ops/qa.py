"""QA worker provider — runs checks against a built task and reports pass/fail.

This is a *placeholder* provider. It does not run real automated checks
(those will be added in P2 — see docs/TODO.md § 2.3). It currently wraps any
LLM-backed provider (e.g. `copilot`, `minimax-tui`) and prompts it to act as
a QA reviewer.

The user is expected to configure a real provider, e.g.:

    qa:
      provider: copilot
      model: gpt-4o-mini       # or qwen3 / glm5.1 via a different provider

If no QA worker is registered, the orchestrator simply skips the QA phase
when a task is tagged `@qa` — see `core.OpsAgent.dispatch()` for the
"disabled → skip" behavior.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from agent_ops.types import WorkerConfig, WorkerProvider


class QAProvider(WorkerProvider):
    """
    Placeholder QA provider.

    Acts as a thin LLM wrapper. Real check execution (coverage, a11y, design
    diff) is planned for P2 — see docs/TODO.md § 2.3.
    """

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        token = os.environ.get(self.config.api_key_env or "MINIMAX_AUTH_TOKEN", "")
        model = self.config.model or "MiniMax-M1"
        base_url = self.config.base_url or "https://api.minimax.chat"

        qa_prompt = (
            "You are a QA engineer. Review the implementation against the "
            "checklist and the project spec.\n\n"
            "Output a structured report:\n"
            "- PASS / FAIL per check\n"
            "- Severity (blocker / major / minor) per failure\n"
            "- Specific fix instructions for the implementer\n"
            "- A final verdict: APPROVE or REQUEST_CHANGES\n\n"
            f"--- Implementation to review ---\n{prompt}\n"
        )

        if context and "system" in context:
            qa_prompt = context["system"] + "\n\n" + qa_prompt

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "origin": "https://hailuoai.com",
            "referer": "https://hailuoai.com/",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": qa_prompt}],
            "stream": False,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/v1/text/chatcompletion_v2",
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        token = os.environ.get(self.config.api_key_env or "MINIMAX_AUTH_TOKEN", "")
        return bool(token)
