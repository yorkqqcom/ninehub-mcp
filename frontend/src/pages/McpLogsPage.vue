<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import { createSseToken, getLogs, openLogStream, type LogLine } from "@/api/serve";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
const lines = ref<LogLine[]>([]);
const level = ref("");
const autoScroll = ref(true);
const paused = ref(false);
const viewer = ref<HTMLElement | null>(null);
let es: EventSource | null = null;

const errorCount = computed(() => lines.value.filter((l) => l.level === "error").length);
const warnCount = computed(() => lines.value.filter((l) => l.level === "warn").length);

onMounted(() => void boot());

onUnmounted(() => {
  es?.close();
});

async function boot() {
  try {
    lines.value = (await getLogs(100, level.value || undefined)).items;
    const token = await createSseToken();
    es = openLogStream(token, (line) => {
      if (paused.value) return;
      lines.value.push(line);
      if (lines.value.length > 500) lines.value.shift();
      if (autoScroll.value && viewer.value) {
        viewer.value.scrollTop = viewer.value.scrollHeight;
      }
    });
  } catch {
    ui.showMessage("日志流连接失败", "error");
  }
}

async function reload() {
  lines.value = (await getLogs(200, level.value || undefined)).items;
}

function clearView() {
  lines.value = [];
}
</script>

<template>
  <PageHeader title="监控日志" description="Serve 子进程 stdout（已脱敏）">
    <template #actions>
      <span v-if="lines.length" class="logs-stats">
        <span class="badge badge--sm badge--err">{{ errorCount }} err</span>
        <span class="badge badge--sm badge--warn">{{ warnCount }} warn</span>
      </span>
      <router-link class="btn btn--secondary" to="/mcp/serve">服务管控</router-link>
    </template>
  </PageHeader>

  <div class="page-toolbar">
    <label class="form-field">
      <span class="form-field__label">Level</span>
      <select v-model="level" @change="reload">
        <option value="">全部</option>
        <option value="info">info</option>
        <option value="warn">warn</option>
        <option value="error">error</option>
      </select>
    </label>
    <label class="form-field form-field--checkbox">
      <input v-model="autoScroll" type="checkbox" />
      自动滚动
    </label>
    <label class="form-field form-field--checkbox">
      <input v-model="paused" type="checkbox" />
      暂停接收
    </label>
    <button type="button" class="btn btn--secondary btn--sm" @click="reload">刷新</button>
    <button type="button" class="btn btn--ghost btn--sm" @click="clearView">清空视图</button>
  </div>

  <div v-if="!lines.length" class="panel">
    <EmptyState title="暂无日志" description="启动 MCP Serve 后，日志将在此实时显示。">
      <router-link class="btn btn--primary" to="/mcp/serve">去启动 Serve</router-link>
    </EmptyState>
  </div>

  <div v-else ref="viewer" class="log-viewer panel" role="log" aria-live="polite">
    <div v-for="(line, i) in lines" :key="i" class="log-line" :class="`log-line--${line.level}`">
      <span class="log-line__ts">{{ line.ts }}</span>
      <span class="log-line__src">{{ line.source }}</span>
      <span class="log-line__msg">{{ line.message }}</span>
    </div>
  </div>
</template>

<style scoped>
.logs-stats {
  display: inline-flex;
  gap: var(--space-xs);
  margin-right: var(--space-sm);
}

.form-field--checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  font-size: var(--font-size-md);
}

.log-viewer {
  max-height: 70vh;
  overflow: auto;
  padding: var(--space-md);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  background: var(--color-surface-muted);
}

.log-line {
  display: flex;
  gap: var(--space-sm);
  padding: 2px 0;
  border-bottom: 1px solid var(--color-border);
}

.log-line--error {
  color: var(--color-err-text);
}

.log-line--warn {
  color: var(--color-warn-text);
}

.log-line__ts {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.log-line__src {
  color: var(--color-primary);
  flex-shrink: 0;
  width: 80px;
}

.log-line__msg {
  word-break: break-all;
}
</style>
