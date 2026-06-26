"""Default and custom prompt templates for manifest building."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_PROMPTS_DIR = Path(__file__).resolve().parent

_DEFAULTS: dict[str, str] = {
    "schema_graph_system": (
        "You analyze PostgreSQL schemas and output JSON only. "
        "Identify domain, table roles, and join relationships."
    ),
    "schema_graph": (
        "Analyze these PostgreSQL tables and infer business domain and join graph.\n"
        "Domain hint from user: {{ domain_hint or 'none' }}\n\n"
        "Tables:\n{{ tables_summary }}\n\n"
        "{{ custom_suffix }}\n"
        'Reply JSON only: {"domain_summary":"...", "table_roles":{"schema.table":"role"}, '
        '"join_edges":[{"from":"schema.table","column":"col","to":"schema.table2","note":"..."}]}'
    ),
    "table_manifest_system": (
        "You write MCP tool manifests for PostgreSQL browse tools. Output JSON only. "
        "description max 120 chars. Include practical keywords, join hints, filter hints, "
        "usage_examples, and agent_notes (plain text, no markdown)."
    ),
    "table_manifest": (
        "Write MCP manifest for table {{ table }}.\n"
        "Domain: {{ domain_summary }}\n"
        "Columns: {{ columns }}\n"
        "Primary keys: {{ primary_keys }}\n"
        "Sample rows: {{ samples }}\n"
        "Join context: {{ join_context }}\n"
        "Filter hints (use stats, not only examples): {{ filter_hints }}\n"
        "{{ custom_suffix }}\n"
        'Reply JSON: {"description":"...", "keywords":[], "join_hints":[], '
        '"filter_hints":[], "usage_examples":[], "agent_notes":"..."}'
    ),
}

_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=select_autoescape(default=False),
)

_custom_templates: dict[str, str] = {}


def set_custom_template(name: str, content: str) -> None:
    _custom_templates[name] = content


def clear_custom_template(name: str) -> None:
    _custom_templates.pop(name, None)


def has_custom_template(name: str) -> bool:
    return name in _custom_templates


def get_template_names() -> list[str]:
    return list(_DEFAULTS.keys())


def get_template_content(name: str) -> str:
    if has_custom_template(name):
        return _custom_templates[name]
    path = _PROMPTS_DIR / f"{name}.j2"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return _DEFAULTS.get(name, "")


def render_prompt(name: str, **kwargs: object) -> str:
    if has_custom_template(name):
        from jinja2 import Template

        return Template(_custom_templates[name]).render(**kwargs)
    path = _PROMPTS_DIR / f"{name}.j2"
    if path.is_file():
        return _env.get_template(f"{name}.j2").render(**kwargs)
    template = _DEFAULTS.get(name, "")
    from jinja2 import Template

    return Template(template).render(**kwargs)
