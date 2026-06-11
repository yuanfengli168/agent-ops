"""TUI Proxy providers — call internal APIs from subscription-based TUI apps."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from agent_ops.design import CodeDesignProvider, MidjourneyProvider
from agent_ops.types import WorkerConfig, WorkerProvider


class ClaudeTUIProvider(WorkerProvider):
    """
    Claude TUI internal API provider.
    
    Uses the Claude app's internal API endpoints (the same ones the TUI uses),
    so you only need your subscription — no separate API key.
    
    Setup:
    1. Open Claude app (desktop or web)
    2. Extract session cookies / auth token from DevTools
    3. Set CLAUDE_SESSION_TOKEN env var
    
    Or use claude-proxy (https://github.com/khorsh/claude-proxy) to run
    a local gateway that forwards TUI requests.
    """

    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.base_url = config.base_url or "https://claude.ai"
        self.session_token = ""
        self._conversation_id = ""

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        token = self.session_token or os.environ.get(
            self.config.api_key_env or "CLAUDE_SESSION_TOKEN", ""
        )
        org_id = os.environ.get("CLAUDE_ORG_ID", "")

        headers = {
            "cookie": f"sessionKey={token}",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0",
        }
        if org_id:
            headers["x-organization-id"] = org_id

        # Create conversation
        payload: dict[str, Any] = {
            "prompt": prompt,
            "timezone": "Asia/Kuala_Lumpur",
            "model": self.config.model or "claude-sonnet-4-20250514",
        }

        async with httpx.AsyncClient() as client:
            # Start new conversation
            resp = await client.post(
                f"{self.base_url}/api/organizations/{org_id}/conversations",
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            # Parse SSE stream for the response
            return self._parse_claude_response(resp.text)

    def _parse_claude_response(self, raw: str) -> str:
        """Parse Claude's SSE/JSON response format."""
        chunks = []
        for line in raw.split("\n"):
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                    if data.get("type") == "assistant" and "content" in data:
                        for block in data["content"]:
                            if block.get("type") == "text":
                                chunks.append(block["text"])
                except (json.JSONDecodeError, KeyError):
                    continue
        return "".join(chunks) if chunks else raw

    async def health_check(self) -> bool:
        token = os.environ.get(self.config.api_key_env or "CLAUDE_SESSION_TOKEN", "")
        return bool(token)


class MiniMaxTUIProvider(WorkerProvider):
    """
    MiniMax TUI internal API provider.
    
    Uses MiniMax's web/TUI internal endpoints, leveraging your
    subscription instead of pay-per-call API.
    
    Setup:
    1. Log into MiniMax web app
    2. Extract auth token from browser DevTools (Network tab)
    3. Set MINIMAX_AUTH_TOKEN env var
    
    The internal API typically uses different endpoints than the public API.
    """

    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.base_url = config.base_url or "https://api.minimax.chat"
        self.auth_token = ""

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        token = self.auth_token or os.environ.get(
            self.config.api_key_env or "MINIMAX_AUTH_TOKEN", ""
        )

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0",
            "origin": "https://hailuoai.com",
            "referer": "https://hailuoai.com/",
        }

        messages = [{"role": "user", "content": prompt}]
        if context and "system" in context:
            messages.insert(0, {"role": "system", "content": context["system"]})

        payload = {
            "model": self.config.model or "MiniMax-M1",
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/text/chatcompletion_v2",
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


class OpenClawTUIProvider(WorkerProvider):
    """
    OpenClaw local gateway provider.
    
    Uses OpenClaw's local gateway API — this is already running on your
    machine and uses your existing subscriptions/configured models.
    
    No extra auth needed beyond what OpenClaw already manages.
    """

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        base_url = self.config.base_url or "http://localhost:3100"
        model = self.config.model or "claude-sonnet-4-20250514"

        headers = {"content-type": "application/json"}
        if self.config.api_key_env:
            api_key = os.environ.get(self.config.api_key_env, "")
            if api_key:
                headers["authorization"] = f"Bearer {api_key}"

        messages = [{"role": "user", "content": prompt}]
        system_msg = None
        if context and "system" in context:
            system_msg = context["system"]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
        }
        if system_msg:
            payload["system"] = system_msg

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        base_url = self.config.base_url or "http://localhost:3100"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{base_url}/health", timeout=5)
                return resp.status_code == 200
        except Exception:
            return False


class BrowserSessionProvider(WorkerProvider):
    """
    Generic browser session provider.
    
    For TUI apps that don't expose a clean API, this provider
    uses browser automation (Playwright) to interact with the UI
    and extract responses.
    
    Setup:
        pip install playwright && playwright install
    """

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "playwright not installed. Run: pip install playwright && playwright install"
            )

        url = self.config.base_url
        if not url:
            raise ValueError("BrowserSessionProvider requires base_url in config")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url)

            # Wait for page load
            await page.wait_for_load_state("networkidle")

            # Find input and type prompt
            # This is a generic implementation — override per TUI
            input_sel = self.config.extra.get("input_selector", "textarea, [contenteditable]")
            submit_sel = self.config.extra.get("submit_selector", "button[type=submit]")

            await page.fill(input_sel, prompt)
            await page.click(submit_sel)

            # Wait for response
            response_sel = self.config.extra.get("response_selector", ".response, .message:last-child")
            await page.wait_for_selector(response_sel, timeout=60000)
            response = await page.text_content(response_sel)

            await browser.close()
            return response or ""

    async def health_check(self) -> bool:
        try:
            from playwright.async_api import async_playwright  # noqa: F401
            return True
        except ImportError:
            return False


# Provider registry — includes both direct API and TUI proxy providers
PROVIDERS: dict[str, type[WorkerProvider]] = {
    # Direct API providers (pay per call)
    "claude": ClaudeTUIProvider,  # default now uses TUI session
    "openclaw": OpenClawTUIProvider,
    "minimax": MiniMaxTUIProvider,
    # TUI proxy providers
    "claude-tui": ClaudeTUIProvider,
    "openclaw-tui": OpenClawTUIProvider,
    "minimax-tui": MiniMaxTUIProvider,
    # Browser automation fallback
    "browser": BrowserSessionProvider,
    # Design providers (code-as-design: HTML/Tailwind drafts)
    "design": CodeDesignProvider,
    "midjourney": MidjourneyProvider,
}


def get_provider(config: WorkerConfig) -> WorkerProvider:
    """Instantiate a worker provider from config."""
    cls = PROVIDERS.get(config.provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {config.provider}. Available: {list(PROVIDERS)}")
    return cls(config)