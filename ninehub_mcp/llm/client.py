"""Shared LLM HTTP client."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx


def chat_completion(
    llm: dict[str, Any],
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
) -> str:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{str(llm['base_url']).rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {llm['api_key']}"},
            json={
                "model": llm["model"],
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def extract_json(content: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
