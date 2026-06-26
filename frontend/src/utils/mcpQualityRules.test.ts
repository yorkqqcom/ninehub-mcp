import { describe, expect, it } from "vitest";
import type { ToolManifest } from "@/api/mcp";
import { computeQualityScore, qualityTier } from "@/utils/mcpQualityRules";

function emptyTool(): ToolManifest {
  return {
    name: "browse_public_t",
    schema: "public",
    table: "t",
    description: "",
    enhanced: false,
    locked: false,
  };
}

describe("computeQualityScore", () => {
  it("returns 0 for empty manifest", () => {
    expect(computeQualityScore(emptyTool())).toBe(0);
    expect(qualityTier(0)).toBe("err");
  });

  it("returns full score when all rules pass", () => {
    const tool: ToolManifest = {
      ...emptyTool(),
      keywords: ["a", "b", "c"],
      join_hints: [{ target_schema: "public", target_table: "x", via_column: "id" }],
      usage_examples: ["example"],
      filter_hints: [{ column: "id", kind: "equality" }],
      description: "x".repeat(40),
      agent_notes: "notes",
    };
    expect(computeQualityScore(tool)).toBe(100);
    expect(qualityTier(100)).toBe("ok");
  });

  it("tiers at boundaries", () => {
    expect(qualityTier(80)).toBe("ok");
    expect(qualityTier(79)).toBe("warn");
    expect(qualityTier(50)).toBe("warn");
    expect(qualityTier(49)).toBe("err");
  });
});
