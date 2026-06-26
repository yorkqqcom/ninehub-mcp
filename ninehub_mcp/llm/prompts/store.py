"""Persist LLM prompt templates in Admin SQLite (platform_settings)."""

from __future__ import annotations

from ninehub_mcp.admin.db import AdminDatabase
from ninehub_mcp.llm.prompts import loader as prompt_loader

_PROMPT_PREFIX = "prompt_tpl:"


def _storage_key(name: str) -> str:
    return f"{_PROMPT_PREFIX}{name}"


def load_templates(admin_db: AdminDatabase) -> dict[str, str]:
    """Load all custom templates from SQLite into the in-memory loader cache."""
    loaded: dict[str, str] = {}
    for name in prompt_loader.get_template_names():
        stored = admin_db.get_platform_setting(_storage_key(name))
        if stored is not None and stored.strip():
            loaded[name] = stored
            prompt_loader.set_custom_template(name, stored)
    return loaded


def save_template(admin_db: AdminDatabase, name: str, content: str) -> None:
    if name not in prompt_loader.get_template_names():
        raise ValueError(f"Unknown template: {name}")
    admin_db.set_platform_setting(_storage_key(name), content)
    prompt_loader.set_custom_template(name, content)


def reset_template(admin_db: AdminDatabase, name: str) -> None:
    """Remove custom override; revert to built-in default."""
    if name not in prompt_loader.get_template_names():
        raise ValueError(f"Unknown template: {name}")
    admin_db.delete_platform_setting(_storage_key(name))
    prompt_loader.clear_custom_template(name)


def configure_prompt_store(admin_db: AdminDatabase) -> None:
    load_templates(admin_db)
