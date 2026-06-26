import type { ToolManifest } from "@/api/mcp";

export type QualityTier = "ok" | "warn" | "err";

export type QualityRule = {
  id: string;
  minCount?: number;
  minLength?: number;
  nonEmpty?: boolean;
  score: number;
  getter: (tool: ToolManifest) => number | string;
};

export const QUALITY_RULES: QualityRule[] = [
  {
    id: "keywords",
    minCount: 3,
    score: 20,
    getter: (t) => t.keywords?.length ?? 0,
  },
  {
    id: "join_hints",
    minCount: 1,
    score: 25,
    getter: (t) => t.join_hints?.length ?? 0,
  },
  {
    id: "usage_examples",
    minCount: 1,
    score: 20,
    getter: (t) => t.usage_examples?.length ?? 0,
  },
  {
    id: "filter_hints",
    minCount: 1,
    score: 15,
    getter: (t) => t.filter_hints?.length ?? 0,
  },
  {
    id: "description",
    minLength: 40,
    score: 10,
    getter: (t) => t.description?.length ?? 0,
  },
  {
    id: "agent_notes",
    nonEmpty: true,
    score: 10,
    getter: (t) => t.agent_notes ?? "",
  },
];

function rulePasses(rule: QualityRule, value: number | string): boolean {
  if (rule.nonEmpty) return typeof value === "string" && value.trim().length > 0;
  if (rule.minLength !== undefined && typeof value === "number") {
    return value >= rule.minLength;
  }
  if (rule.minCount !== undefined && typeof value === "number") {
    return value >= rule.minCount;
  }
  return false;
}

export function computeQualityScore(tool: ToolManifest): number {
  return QUALITY_RULES.reduce((sum, rule) => {
    const value = rule.getter(tool);
    return sum + (rulePasses(rule, value) ? rule.score : 0);
  }, 0);
}

export function qualityTier(score: number): QualityTier {
  if (score >= 80) return "ok";
  if (score >= 50) return "warn";
  return "err";
}

export function qualityTierLabel(tier: QualityTier): string {
  if (tier === "ok") return "优";
  if (tier === "warn") return "中";
  return "低";
}
