"""Design provider — generates UI design drafts as HTML/Tailwind code."""

from __future__ import annotations

import os
from typing import Any

import httpx

from agent_ops.types import WorkerConfig, WorkerProvider


class CodeDesignProvider(WorkerProvider):
    """
    Design worker that generates UI design drafts as runnable HTML/CSS/JS code.
    
    "Code as design" — instead of static mockup images, this worker produces
    live, viewable HTML/Tailwind pages that serve as the design contract.
    
    UI/SDE workers then implement directly based on this code.
    Review workers compare implementation against this visual reference.
    """

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        token = os.environ.get(self.config.api_key_env or "MINIMAX_AUTH_TOKEN", "")
        model = self.config.model or "MiniMax-M3"
        base_url = self.config.base_url or "https://api.minimax.chat"

        design_prompt = (
            "You are a senior UI/UX designer who codes. Generate a COMPLETE, "
            "runnable HTML design draft using Tailwind CSS (via CDN).\n\n"
            "Requirements:\n"
            "- Single HTML file, self-contained, opens in browser\n"
            "- Use Tailwind CSS via <script src='https://cdn.tailwindcss.com'></script>\n"
            "- Include all pages/views as sections\n"
            "- Show hover states, transitions, animations\n"
            "- Use placeholder images from https://placehold.co\n"
            "- Make it responsive (mobile + desktop)\n"
            "- Include 3D effects if specified (use CSS transforms or Three.js)\n"
            "- Add comments marking each component/section\n\n"
            f"Project: {prompt}\n\n"
            "Output ONLY the HTML code, no explanations."
        )

        if context and "system" in context:
            design_prompt = context["system"] + "\n\n" + design_prompt

        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "origin": "https://hailuoai.com",
            "referer": "https://hailuoai.com/",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": design_prompt}],
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


class MidjourneyProvider(WorkerProvider):
    """
    Midjourney-based design provider via third-party API proxy.
    Optional — for when you need high-fidelity image mockups instead of code.
    """

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        api_key = os.environ.get(self.config.api_key_env or "MIDJOURNEY_API_KEY", "")
        base_url = self.config.base_url or "https://api.goapi.ai/mj/v2"

        headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

        design_prompt = (
            f"UI design mockup, modern interface, clean layout, "
            f"professional wireframe style: {prompt}"
        )

        payload = {
            "prompt": design_prompt,
            "process_mode": "fast",
        }

        async with httpx.AsyncClient() as client:
            # Submit generation task
            resp = await client.post(
                f"{base_url}/imagine", headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            task_id = resp.json().get("task_id", "")

            # Poll for result (simplified)
            for _ in range(60):
                import asyncio
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"{base_url}/tasks/{task_id}", headers=headers, timeout=10
                )
                status_data = status_resp.json()
                if status_data.get("status") == "completed":
                    return status_data.get("output", "")

            return "Design generation timed out"

    async def health_check(self) -> bool:
        api_key = os.environ.get(self.config.api_key_env or "MIDJOURNEY_API_KEY", "")
        return bool(api_key)