import { describe, expect, it } from "vitest";
import type { BuildJob } from "@/api/mcp";
import { mapBuildProgressRows } from "@/utils/buildProgressRows";

describe("mapBuildProgressRows", () => {
  it("maps completed rows", () => {
    const job: BuildJob = {
      id: "1",
      connection_id: "c",
      status: "running",
      progress: 50,
      enhanced_count: 1,
      fallback_count: 0,
      error: null,
      per_table_results: [
        {
          schema: "public",
          table: "a",
          enhanced: true,
          keywords_count: 3,
          join_hints_count: 1,
        },
      ],
    };
    const rows = mapBuildProgressRows(job);
    expect(rows).toHaveLength(1);
    expect(rows[0].key).toBe("public.a");
    expect(rows[0].status).toBe("done");
  });

  it("appends running row for current_table", () => {
    const job: BuildJob = {
      id: "1",
      connection_id: "c",
      status: "running",
      progress: 60,
      enhanced_count: 1,
      fallback_count: 0,
      error: null,
      current_table: "public.b",
      per_table_results: [
        {
          schema: "public",
          table: "a",
          enhanced: true,
          keywords_count: 3,
          join_hints_count: 1,
        },
      ],
    };
    const rows = mapBuildProgressRows(job);
    expect(rows).toHaveLength(2);
    expect(rows[1].key).toBe("public.b");
    expect(rows[1].status).toBe("running");
  });
});
