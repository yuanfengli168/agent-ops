"""Design provider — generates UI mockups, wireframes, and 3D renders."""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx

from agent_ops.types import WorkerConfig, WorkerProvider


class ImageDesignProvider(WorkerProvider):
    """
    Design worker that generates UI mockups, wireframes, and 3D renders.
    
    Uses image generation models (GPT-4o, DALL-E, Midjourney via API, etc.)
    to produce design artifacts before implementation begins.
    
    These designs become the "contract" that the Review worker checks against.
    """

    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        api_key = os.environ.get(self.config.api_key_env or "OPENAI_API_KEY", "")
        model = self.config.model or "gpt-4o"
        base_url = self.config.base_url or "https://api.openai.com"

        # Build a design-focused prompt
        design_prompt = (
            "You are a senior UI/UX designer. Based on the following request, "
            "create a detailed design specification including:\n\n"
            "1. LAYOUT: Page layout and component placement\n"
            "2. COLORS: Color palette with hex codes\n"
            "3. TYPOGRAPHY: Font choices, sizes, weights\n"
            "4. COMPONENTS: Detailed component descriptions\n"
            "5. SPACING: Margins, padding, gaps\n"
            "6. INTERACTIONS: Animations, transitions, hover states\n"
            "7. 3D ELEMENTS: Any 3D renders or visual effects needed\n"
            "8. RESPONSIVE: Breakpoint behavior\n\n"
            f"Project: {prompt}\n\n"
            "Also suggest image generation prompts for key screens/mocks."
        )

        if context and "system" in context:
            design_prompt = context["system"] + "\n\n" + design_prompt

        headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": design_prompt}],
            "max_tokens": 4096,
        }

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

    async def generate_mockup(self, prompt: str) -> str:
        """Generate an actual image mockup using image generation API."""
        api_key = os.environ.get(self.config.api_key_env or "OPENAI_API_KEY", "")
        image_model = self.config.extra.get("image_model", "dall-e-3")
        base_url = self.config.base_url or "https://api.openai.com"

        headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

        payload = {
            "model": image_model,
            "prompt": f"UI design mockup, clean modern interface: {prompt}",
            "n": 1,
            "size": "1792x1024",
            "quality": "hd",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/v1/images/generations",
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0].get("url", "") or data["data"][0].get("b64_json", "")

    async def health_check(self) -> bool:
        api_key = os.environ.get(self.config.api_key_env or "OPENAI_API_KEY", "")
        return bool(api_key)


class MidjourneyProvider(WorkerProvider):
    """
    Midjourney-based design provider via third-party API proxy.
    
    For high-quality 3D renders and UI mockups.
    Uses services like goapi.ai or similar Midjourney API proxies.
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