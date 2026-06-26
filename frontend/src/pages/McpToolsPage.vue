<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { listConnections } from "@/api/connections";
import { listMcpTools, patchTool, type ToolManifest } from "@/api/mcp";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import SkeletonLoader from "@/components/SkeletonLoader.vue";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const ui = useUiStore();

const connectionId = ref("");
const connections = ref<{ id: string; name: string }[]>([]);
const tools = ref<ToolManifest[]>([]);
const builtins = ref<{ name: string; description: string }[]>([]);
const selectedName = ref("");
const search = ref("");
const editDesc = ref("");
const editLocked = ref(false);
const editKeywords = ref("");
const editAgentNotes = ref("");
const editLockedFields = ref("");
const loading = ref(true);
const saving = ref(false);

const selected = computed((): ToolManifest | { name: string; description: string; enhanced: boolean; locked: boolean } | null => {
  const t = tools.value.find((x) => x.name === selectedName.value);
  if (t) return t;
  const b = builtins.value.find((x) => x.name === selectedName.value);
  if (b) return { name: b.name, description: b.description, enhanced: false, locked: false };
  return null;
});

const isCatalogTool = computed(
  () => !!selected.value && tools.value.some((t) => t.name === selected.value!.name),
);

const filteredTools = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return tools.value;
  return tools.value.filter((t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q));
});

const filteredBuiltins = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return builtins.value;
  return builtins.value.filter((b) => b.name.toLowerCase().includes(q));
});

onMounted(async () => {
  const data = await listConnections();
  connections.value = data.items;
  connectionId.value = (route.query.connection_id as string) || data.items[0]?.id || "";
  if (connectionId.value) await loadTools();
  loading.value = false;
});

watch(connectionId, () => void loadTools());

async function loadTools() {
  selectedName.value = "";
  try {
    const data = await listMcpTools(connectionId.value);
    tools.value = data.items;
    builtins.value = data.builtins || [];
    if (tools.value.length) {
      selectTool(tools.value[0].name);
    } else if (builtins.value.length) {
      selectTool(builtins.value[0].name);
    }
  } catch (e) {
    tools.value = [];
    builtins.value = [];
    ui.showMessage(errMsg(e), "error");
  }
}

function selectTool(name: string) {
  selectedName.value = name;
  const t = tools.value.find((x) => x.name === name);
  if (t) {
    editDesc.value = t.description;
    editLocked.value = t.locked;
    editKeywords.value = (t.keywords || []).join(", ");
    editAgentNotes.value = t.agent_notes || "";
    editLockedFields.value = (t.locked_fields || []).join(", ");
  } else {
    editDesc.value = builtins.value.find((b) => b.name === name)?.description || "";
    editLocked.value = false;
  }
}

async function saveTool() {
  if (!selectedName.value || !tools.value.some((t) => t.name === selectedName.value)) {
    ui.showMessage("内置 tool 不可编辑", "warn");
    return;
  }
  saving.value = true;
  try {
    const updated = await patchTool(selectedName.value, {
      connection_id: connectionId.value,
      description: editDesc.value,
      locked: editLocked.value,
      keywords: editKeywords.value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      agent_notes: editAgentNotes.value,
      locked_fields: editLockedFields.value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    });
    const idx = tools.value.findIndex((t) => t.name === selectedName.value);
    if (idx >= 0) tools.value[idx] = updated;
    ui.showMessage("已保存", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    saving.value = false;
  }
}

function errMsg(e: unknown) {
  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";
}
</script>

<template>
  <PageHeader title="接口清单" description="Rich catalog manifests · catalog:// v1 · 字段级锁定">
    <template #actions>
      <router-link
        class="btn btn--secondary"
        :to="{ path: '/mcp/test', query: { connection_id: connectionId } }"
      >
        接口测试
      </router-link>
    </template>
  </PageHeader>

  <div v-if="loading" class="panel"><SkeletonLoader :rows="4" /></div>

  <div v-else-if="!connections.length" class="panel">
    <EmptyState title="无连接" description="请先创建数据源。" />
  </div>

  <div v-else class="page-split page-split--tools">
    <div class="panel">
      <div class="panel__header tools-list__header">
        <select v-model="connectionId" class="input--sm" @change="loadTools">
          <option v-for="c in connections" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <span class="badge badge--muted">{{ tools.length + builtins.length }} tools</span>
      </div>
      <div class="panel__body tools-list__search">
        <input v-model="search" type="search" class="input input--sm input-w-full" placeholder="搜索 tool 名称" />
      </div>
      <div class="panel__body list-scroll">
        <div v-if="filteredBuiltins.length" class="list-section">
          <div class="list-section__title">内置 · {{ filteredBuiltins.length }}</div>
          <button
            v-for="b in filteredBuiltins"
            :key="b.name"
            type="button"
            class="list-item btn btn--ghost"
            :class="{ 'list-item--active': selectedName === b.name }"
            @click="selectTool(b.name)"
          >
            {{ b.name }}
          </button>
        </div>
        <div class="list-section">
          <div class="list-section__title">Browse · {{ filteredTools.length }}</div>
          <p v-if="!filteredTools.length" class="empty-hint">无匹配或尚未构建</p>
          <button
            v-for="t in filteredTools"
            :key="t.name"
            type="button"
            class="list-item btn btn--ghost"
            :class="{ 'list-item--active': selectedName === t.name }"
            @click="selectTool(t.name)"
          >
            <span class="list-item__name">{{ t.name }}</span>
            <span class="badge badge--catalog">catalog</span>
          </button>
        </div>
      </div>
    </div>

    <div class="panel">
      <div v-if="selected" class="panel__body">
        <h3 class="tools-detail__title">{{ selected.name }}</h3>
        <p class="tools-detail__badges">
          <span v-if="isCatalogTool" class="badge" :class="(selected as ToolManifest).enhanced ? 'badge--ok' : 'badge--warn'">
            {{ (selected as ToolManifest).enhanced ? "LLM" : "规则" }}
          </span>
          <span v-else class="badge badge--muted">内置</span>
          <span v-if="isCatalogTool && (selected as ToolManifest).locked" class="badge badge--muted">locked</span>
        </p>
        <label class="form-field">
          <span class="form-field__label">Description</span>
          <textarea v-model="editDesc" rows="4" :disabled="!isCatalogTool" />
        </label>
        <label v-if="isCatalogTool" class="form-field">
          <span class="form-field__label">Keywords（逗号分隔）</span>
          <input v-model="editKeywords" type="text" :disabled="!isCatalogTool" />
        </label>
        <label v-if="isCatalogTool" class="form-field">
          <span class="form-field__label">Agent notes（catalog:// 纯文本）</span>
          <textarea v-model="editAgentNotes" rows="5" :disabled="!isCatalogTool" />
        </label>
        <label v-if="isCatalogTool" class="form-field">
          <span class="form-field__label">locked_fields（逗号分隔字段名）</span>
          <input v-model="editLockedFields" type="text" placeholder="keywords,join_hints,..." />
        </label>
        <label v-if="isCatalogTool" class="form-field form-field--checkbox">
          <input v-model="editLocked" type="checkbox" />
          锁定（rescan/build 不覆盖）
        </label>
        <div class="page-actions">
          <button type="button" class="btn btn--primary" :disabled="saving || !isCatalogTool" @click="saveTool">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
      <div v-else class="panel__body">
        <EmptyState title="选择 Tool" description="从左侧列表选择，或先 scan + 构建 MCP。" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-split--tools {
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
}

@media (max-width: 900px) {
  .page-split--tools {
    grid-template-columns: 1fr;
  }
}

.tools-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.tools-list__search {
  padding-top: 0;
  border-bottom: 1px solid var(--color-border);
}

.list-scroll {
  max-height: 65vh;
  overflow: auto;
}

.list-section {
  margin-bottom: var(--space-md);
}

.list-section__title {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-xs);
}

.list-item {
  display: flex;
  width: 100%;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  text-align: left;
  gap: var(--space-sm);
}

.list-item__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-item--active {
  border-color: var(--color-primary);
  background: var(--color-primary-muted);
}

.tools-detail__title {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-lg);
  word-break: break-all;
}

.tools-detail__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin: 0 0 var(--space-md);
}

.form-field--checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-md);
}

.empty-hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  padding: var(--space-sm) 0;
}
</style>
