<script setup lang="ts">
import { computed, ref } from "vue";
import type { PromptTemplate } from "@/api/mcp";

const props = defineProps<{
  templates: PromptTemplate[];
  editHref?: string;
}>();

const selected = ref(props.templates[0]?.name ?? "");

const current = computed(() => props.templates.find((t) => t.name === selected.value));

const previewLines = computed(() => {
  const content = current.value?.content ?? "";
  const lines = content.split("\n");
  return lines.length > 24 ? [...lines.slice(0, 24), "…"] : lines;
});
</script>

<template>
  <div v-if="templates.length" class="prompt-preview panel">
    <div class="panel__header prompt-preview__header">
      <span>Prompt 模板预览</span>
      <router-link v-if="editHref" class="btn btn--ghost btn--sm" :to="editHref">在设置中编辑</router-link>
    </div>
    <div class="panel__body">
      <div class="filter-tabs">
        <button
          v-for="t in templates"
          :key="t.name"
          type="button"
          class="filter-tab"
          :class="{ 'filter-tab--active': selected === t.name }"
          @click="selected = t.name"
        >
          {{ t.name }}
        </button>
      </div>
      <pre class="prompt-preview__content">{{ previewLines.join("\n") }}</pre>
    </div>
  </div>
</template>

<style scoped>
.prompt-preview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.prompt-preview__content {
  margin: var(--space-md) 0 0;
  padding: var(--space-md);
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
  font-size: 12px;
  line-height: 1.45;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>
