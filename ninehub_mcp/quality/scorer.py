"""MCP manifest and runtime config quality scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ninehub_mcp.context.models import McpRuntimeConfig, ToolManifest
from ninehub_mcp.naming import browse_tool_name
from ninehub_mcp.runtime.catalog_schema import CATALOG_HINT_FORMAT, build_catalog_payload


@dataclass
class ManifestScore:
    name: str
    score: int
    issues: list[str] = field(default_factory=list)
    enhanced: bool = False

    @property
    def passed(self) -> bool:
        return self.score >= 70 and not any(i.startswith("critical:") for i in self.issues)


@dataclass
class ConfigQualityReport:
    connection_id: str
    version: str
    tool_count: int
    manifest_scores: list[ManifestScore]
    aggregate_score: float
    pass_rate: float
    issues_summary: dict[str, int]

    @property
    def passed(self) -> bool:
        return self.aggregate_score >= 75.0 and self.pass_rate >= 0.85


def score_manifest(manifest: ToolManifest) -> ManifestScore:
    """Score a single tool manifest (0–100)."""
    issues: list[str] = []
    score = 100

    expected_name = browse_tool_name(manifest.schema, manifest.table)
    if manifest.name != expected_name:
        issues.append("critical:wrong_tool_name")
        score -= 30

    desc = (manifest.description or "").strip()
    if len(desc) < 8:
        issues.append("short_description")
        score -= 15
    elif len(desc) > 500:
        issues.append("long_description")
        score -= 5

    if len(manifest.keywords) < 2:
        issues.append("few_keywords")
        score -= 10
    elif len(manifest.keywords) > 20:
        issues.append("many_keywords")
        score -= 3

    if not manifest.usage_examples:
        issues.append("no_usage_examples")
        score -= 12

    schema = manifest.input_schema or {}
    if schema.get("type") != "object":
        issues.append("invalid_input_schema")
        score -= 15
    elif "filters" not in schema.get("properties", {}):
        issues.append("missing_filters_schema")
        score -= 8

    try:
        payload = build_catalog_payload(manifest, [{"_probe": 1}])
        if payload.get("hint_format") != CATALOG_HINT_FORMAT:
            issues.append("catalog_hint_format")
            score -= 10
        if not payload.get("description"):
            issues.append("catalog_empty_description")
            score -= 5
    except Exception:
        issues.append("critical:catalog_build_failed")
        score -= 25

    return ManifestScore(
        name=manifest.name,
        score=max(0, score),
        issues=issues,
        enhanced=manifest.enhanced,
    )


def score_runtime_config(config: McpRuntimeConfig) -> ConfigQualityReport:
    """Score all manifests in a runtime config."""
    scores = [score_manifest(m) for m in config.tool_manifests]
    names = [m.name for m in config.tool_manifests]
    if len(names) != len(set(names)):
        for s in scores:
            s.issues.append("critical:duplicate_names_in_batch")
            s.score = max(0, s.score - 20)

    total = len(scores) or 1
    aggregate = sum(s.score for s in scores) / total
    passed = sum(1 for s in scores if s.passed)

    summary: dict[str, int] = {}
    for s in scores:
        for issue in s.issues:
            summary[issue] = summary.get(issue, 0) + 1

    return ConfigQualityReport(
        connection_id=config.connection_id,
        version=config.version,
        tool_count=len(config.tool_manifests),
        manifest_scores=scores,
        aggregate_score=round(aggregate, 1),
        pass_rate=round(passed / total, 3),
        issues_summary=summary,
    )


def report_to_dict(report: ConfigQualityReport) -> dict[str, Any]:
    return {
        "connection_id": report.connection_id,
        "version": report.version,
        "tool_count": report.tool_count,
        "aggregate_score": report.aggregate_score,
        "pass_rate": report.pass_rate,
        "passed": report.passed,
        "issues_summary": report.issues_summary,
        "manifests": [
            {
                "name": s.name,
                "score": s.score,
                "enhanced": s.enhanced,
                "passed": s.passed,
                "issues": s.issues,
            }
            for s in report.manifest_scores
        ],
    }
