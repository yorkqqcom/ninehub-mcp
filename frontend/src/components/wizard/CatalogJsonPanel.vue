<script setup lang="ts">
import { computed, ref } from "vue";
import type { ToolManifest } from "@/api/mcp";
import { buildCatalogPreview, catalogResourceUri } from "@/utils/catalogPreview";
import CopyButton from "@/components/CopyButton.vue";

const props = defineProps<{
  tool: ToolManifest;
  sampleRows?: Record<string, unknown>[];
}>();

const open = ref(false);

const uri = computed(() => catalogResourceUri(props.tool.schema, props.tool.table));

const jsonText = computed(() =>
  JSON.stringify(buildCatalogPreview(props.tool, props.sampleRows ?? []), null, 2),
);
</script>

<template>
  <div class="catalog-panel">
    <button type="button" class="btn btn--ghost btn--sm" @click="open = !open">
      {{ open ? "隐藏" : "查看" }} catalog:// JSON
    </button>
    <div v-if="open" class="catalog-panel__body">
      <div class="catalog-panel__header">
        <code>{{ uri }}</code>
        <CopyButton :text="jsonText" />
      </div>
      <pre class="catalog-panel__json">{{ jsonText }}</pre>
    </div>
  </div>
</template>

<style scoped>
.catalog-panel__body {
  margin-top: var(--space-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.catalog-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
  background: var(--color-surface-muted);
  font-size: var(--font-size-sm);
}

.catalog-panel__json {
  margin: 0;
  padding: var(--space-md);
  max-height: 320px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.45;
  background: var(--color-surface);
}
</style>
