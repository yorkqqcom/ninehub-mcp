import { ref, watch } from "vue";
import { getContextPack } from "@/api/connections";
import type { ContextPackTable, ForeignKeyRef } from "@/api/types";

export type TableDetail = {
  foreignKeys: ForeignKeyRef[];
  inferredJoins: ForeignKeyRef[];
  samples: Record<string, unknown>[];
  columnCount: number;
  primaryKeys: string[];
  rowCountEstimate: number | null;
};

type PackCache = {
  packVersion: string;
  byQualified: Map<string, TableDetail>;
};

const packCaches = new Map<string, PackCache>();
const loadingPromises = new Map<string, Promise<PackCache>>();

/** exposed_count ≤ 30: preload on mount; 31+: load on first select — both use single getContextPack. */
export const TABLE_DETAIL_PRELOAD_THRESHOLD = 30;
export const TABLE_DETAIL_WARN_THRESHOLD = 80;

function tableToDetail(t: ContextPackTable): TableDetail {
  return {
    foreignKeys: t.foreign_keys ?? [],
    inferredJoins: t.inferred_joins ?? [],
    samples: (t.sample_rows_resource ?? t.sample_rows_build ?? []).slice(0, 3),
    columnCount: t.columns?.length ?? 0,
    primaryKeys: t.primary_keys ?? [],
    rowCountEstimate: t.row_count_estimate ?? null,
  };
}

async function ensurePackCache(connectionId: string): Promise<PackCache> {
  const existing = packCaches.get(connectionId);
  if (existing) return existing;

  const inflight = loadingPromises.get(connectionId);
  if (inflight) return inflight;

  const promise = getContextPack(connectionId).then((pack) => {
    const byQualified = new Map<string, TableDetail>();
    for (const t of pack.tables) {
      if (!t.exposed) continue;
      byQualified.set(`${t.schema}.${t.name}`, tableToDetail(t));
    }
    const cache: PackCache = { packVersion: pack.version, byQualified };
    packCaches.set(connectionId, cache);
    loadingPromises.delete(connectionId);
    return cache;
  });

  loadingPromises.set(connectionId, promise);
  return promise;
}

export function clearTableDetailCache(connectionId?: string) {
  if (connectionId) {
    packCaches.delete(connectionId);
    loadingPromises.delete(connectionId);
    return;
  }
  packCaches.clear();
  loadingPromises.clear();
}

export function useTableDetail(connectionId: () => string | null, exposedCount: () => number) {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const detail = ref<TableDetail | null>(null);
  const selectedKey = ref<string | null>(null);

  async function preloadIfSmall() {
    const cid = connectionId();
    if (!cid || exposedCount() > TABLE_DETAIL_PRELOAD_THRESHOLD) return;
    loading.value = true;
    error.value = null;
    try {
      await ensurePackCache(cid);
    } catch (e) {
      error.value = errMsg(e);
    } finally {
      loading.value = false;
    }
  }

  async function loadTable(qualifiedName: string) {
    selectedKey.value = qualifiedName;
    const cid = connectionId();
    if (!cid) {
      detail.value = null;
      return;
    }
    loading.value = true;
    error.value = null;
    try {
      const cache = await ensurePackCache(cid);
      detail.value = cache.byQualified.get(qualifiedName) ?? null;
      if (!detail.value) error.value = "未找到表详情";
    } catch (e) {
      detail.value = null;
      error.value = errMsg(e);
    } finally {
      loading.value = false;
    }
  }

  watch(
    () => connectionId(),
    () => {
      detail.value = null;
      selectedKey.value = null;
      error.value = null;
    },
  );

  return {
    loading,
    error,
    detail,
    selectedKey,
    preloadIfSmall,
    loadTable,
    showLargeTableHint: () => exposedCount() > TABLE_DETAIL_WARN_THRESHOLD,
  };
}

function errMsg(e: unknown): string {
  return e && typeof e === "object" && "message" in e
    ? String((e as { message: string }).message)
    : "加载失败";
}
