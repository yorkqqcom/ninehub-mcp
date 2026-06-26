<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { listConnections } from "@/api/connections";
import CopyButton from "@/components/CopyButton.vue";
import PageHeader from "@/components/PageHeader.vue";
import {
  getServeStatus,
  restartServe,
  startServe,
  stopServe,
  type ServeStatus,
} from "@/api/serve";
import type { ConnectionSummary } from "@/api/types";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
const status = ref<ServeStatus | null>(null);
const connections = ref<ConnectionSummary[]>([]);
const form = ref({
  host: "127.0.0.1",
  port: 8000,
  profile: "all",
  connection_id: "",
});
const busy = ref(false);

const canStart = computed(
  () => status.value?.status !== "running" && form.value.connection_id,
);

const isRunning = computed(() => status.value?.status === "running");

const hermesUrl = computed(() => {
  const host = status.value?.host || form.value.host;
  const port = status.value?.port || form.value.port;
  return `http://${host}:${port}/mcp`;
});

const statusLabel = computed(() => {
  const st = status.value?.status || "unknown";
  if (st === "running") return "运行中";
  if (st === "stopped") return "已停止";
  if (st === "failed" || st === "crashed") return "异常";
  return st;
});

onMounted(() => void refresh());

async function refresh() {
  const [s, c] = await Promise.all([getServeStatus(), listConnections()]);
  status.value = s;
  connections.value = c.items;
  if (c.items.length && !form.value.connection_id) {
    form.value.connection_id = c.items[0].id;
  }
  if (s.host) form.value.host = s.host;
  if (s.port) form.value.port = s.port;
  if (s.profile) form.value.profile = s.profile;
  if (s.connection_id) form.value.connection_id = s.connection_id;
}

async function start() {
  busy.value = true;
  try {
    status.value = await startServe(form.value);
    ui.showMessage("MCP Serve 已启动", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    busy.value = false;
  }
}

async function stop() {
  busy.value = true;
  try {
    status.value = await stopServe();
    ui.showMessage("已停止", "info");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    busy.value = false;
  }
}

async function restart() {
  busy.value = true;
  try {
    status.value = await restartServe(form.value);
    ui.showMessage("已重启", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    busy.value = false;
  }
}

function errMsg(e: unknown) {
  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";
}

function badgeClass(st: string) {
  if (st === "running") return "badge--ok";
  if (st === "failed" || st === "crashed") return "badge--err";
  return "badge--muted";
}
</script>

<template>
  <PageHeader title="服务管控" description="MCP Serve 子进程启停">
    <template #actions>
      <router-link class="btn btn--secondary" to="/mcp/logs">监控日志</router-link>
    </template>
  </PageHeader>

  <div v-if="form.host !== '127.0.0.1' && form.host !== 'localhost'" class="page-banner page-banner--warn">
    非 localhost 绑定可能暴露 MCP 服务，请谨慎使用。
  </div>

  <div class="panel" :class="{ 'serve-panel--running': isRunning }">
    <div class="panel__header">
      <h2 class="panel__title">运行状态</h2>
      <span class="badge" :class="badgeClass(status?.status || '')">{{ statusLabel }}</span>
    </div>
    <div class="panel__body">
      <div v-if="status" class="serve-meta">
        <span v-if="status.pid" class="serve-meta__item">PID <span class="numeric">{{ status.pid }}</span></span>
        <span v-if="isRunning && status.uptime_seconds != null" class="serve-meta__item">
          运行 <span class="numeric">{{ status.uptime_seconds }}s</span>
        </span>
        <span class="serve-meta__item">profile {{ status.profile || form.profile }}</span>
      </div>

      <div class="form-grid serve-form">
        <label class="form-field">
          <span class="form-field__label">Host</span>
          <input v-model="form.host" type="text" :disabled="isRunning" />
        </label>
        <label class="form-field">
          <span class="form-field__label">Port</span>
          <input v-model.number="form.port" type="number" :disabled="isRunning" />
        </label>
        <label class="form-field">
          <span class="form-field__label">Profile</span>
          <select v-model="form.profile" :disabled="isRunning">
            <option value="all">all</option>
            <option value="catalog">catalog</option>
            <option value="query">query</option>
          </select>
        </label>
        <label class="form-field">
          <span class="form-field__label">Connection</span>
          <select v-model="form.connection_id" :disabled="isRunning">
            <option v-for="c in connections" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
      </div>

      <div class="page-actions">
        <button type="button" class="btn btn--primary" :disabled="busy || !canStart" @click="start">启动</button>
        <button type="button" class="btn btn--secondary" :disabled="busy || !isRunning" @click="stop">停止</button>
        <button type="button" class="btn btn--ghost" :disabled="busy" @click="restart">重启</button>
        <button type="button" class="btn btn--ghost" @click="refresh">刷新</button>
      </div>

      <div class="copy-block">
        <div class="copy-block__head">
          <span class="copy-block__label">Hermes streamable-http 端点</span>
          <CopyButton :text="hermesUrl" :disabled="!isRunning" />
        </div>
        <code class="copy-block__value">{{ hermesUrl }}</code>
        <p v-if="!isRunning" class="copy-block__hint">启动 Serve 后可用于 Cursor / Hermes 连接</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.serve-panel--running {
  border-color: var(--color-primary);
}

.serve-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
  margin-bottom: var(--space-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.serve-form {
  margin-bottom: var(--space-sm);
}

.copy-block {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
}

.copy-block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}

.copy-block__label {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.copy-block__value {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  word-break: break-all;
  color: var(--color-text);
}

.copy-block__hint {
  margin: var(--space-sm) 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}
</style>
