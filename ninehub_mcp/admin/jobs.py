"""Scan job phase and status constants."""

from __future__ import annotations

from typing import Literal

ScanJobStatus = Literal["pending", "running", "completed", "failed"]
ScanJobPhase = Literal["inspect", "sample", "manifest", "done"]

PHASE_LABELS: dict[str, str] = {
    "inspect": "Inspect 元数据",
    "sample": "Sample 采样",
    "manifest": "Manifest 构建",
    "done": "完成",
}
