import { describe, expect, it } from "vitest";
import {
  clearTableSelection,
  filterPackTables,
  selectAllTables,
  toggleTableFilter,
} from "@/utils/wizardReviewPack";

const tables = [
  {
    schema: "public",
    name: "a",
    qualified_name: "public.a",
    column_count: 5,
    physical_fk_count: 1,
    inferred_join_count: 0,
    sample_preview: [],
  },
  {
    schema: "public",
    name: "b",
    qualified_name: "public.b",
    column_count: 3,
    physical_fk_count: 0,
    inferred_join_count: 2,
    sample_preview: [],
  },
];

describe("wizardReviewPack utils", () => {
  it("filters by tab and search", () => {
    expect(filterPackTables(tables, "fk", "").map((t) => t.qualified_name)).toEqual(["public.a"]);
    expect(filterPackTables(tables, "inferred", "").map((t) => t.qualified_name)).toEqual([
      "public.b",
    ]);
    expect(filterPackTables(tables, "all", "public.b").map((t) => t.qualified_name)).toEqual([
      "public.b",
    ]);
  });

  it("toggles table filter selection", () => {
    expect(toggleTableFilter([], "public.a")).toEqual(["public.a"]);
    expect(toggleTableFilter(["public.a"], "public.a")).toEqual([]);
  });

  it("select all and clear", () => {
    expect(selectAllTables(tables)).toEqual(["public.a", "public.b"]);
    expect(clearTableSelection()).toEqual([]);
  });
});
