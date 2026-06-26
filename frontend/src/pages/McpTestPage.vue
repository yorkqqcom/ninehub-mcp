<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { listConnections } from "@/api/connections";
import { callTool, listMcpTools } from "@/api/mcp";
import PageHeader from "@/components/PageHeader.vue";
import EmptyState from "@/components/EmptyState.vue";
import { useUiStore } from "@/stores/ui";

type HistoryItem = {
  tool: string;
  arguments: string;
  ok: boolean;
  duration_ms: number;
  at: string;
  preview: string;
};

const HISTORY_KEY = "ninehub_mcp.test_history";
const MAX_HISTORY = 20;

const route = useRoute();
const ui = useUiStore();

const connectionId = ref("");
const connections = ref<{ id: string; name: string }[]>([]);
const toolOptions = ref<string[]>([]);
const tool = ref("");
const argsText = ref('{\n  "limit": 5\n}');
const busy = ref(false);
const resultText = ref("");
const lastMeta = ref<{ ok: boolean; duration_ms: number } | null>(null);
const history = ref<HistoryItem[]>([]);

const argsValid = computed(() => {
  try {
    JSON.parse(argsText.value || "{}");
    return true;
  } catch {
    return false;
  }
});

onMounted(async () => {
  history.value = loadHistory();
  const data = await listConnections();
  connections.value = data.items;
  connectionId.value = (route.query.connection_id as string) || data.items[0]?.id || "";
  if (connectionId.value) await refreshTools();
});

watch(connectionId, () => void refreshTools());

function loadHistory(): HistoryItem[] {
  try {
    return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]") as HistoryItem[];
  } catch {
    return [];
  }
}

function saveHistory() {
  sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history.value.slice(0, MAX_HISTORY)));
}

async function refreshTools() {
  if (!connectionId.value) return;
  try {
    const data = await listMcpTools(connectionId.value);
    const names = [
      ...(data.builtins || []).map((b) => b.name),
      ...data.items.map((i) => i.name),
    ];
    toolOptions.value = names;
    if (!tool.value && names.length) tool.value = names.find((n) => n.startsWith("browse_")) || names[0];
  } catch {
    toolOptions.value = [];
  }
}

async function run() {
  if (!argsValid.value) {
    ui.showMessage("JSON 参数无效", "error");
    return;
  }
  busy.value = true;
  resultText.value = "";
  try {
    const args = JSON.parse(argsText.value || "{}") as Record<string, unknown>;
    const res = await callTool({
      connection_id: connectionId.value,
      tool: tool.value,
      arguments: args,
    });
    lastMeta.value = { ok: res.ok, duration_ms: res.duration_ms };
    resultText.value = JSON.stringify(res.result, null, 2);
    const item: HistoryItem = {
      tool: tool.value,
      arguments: argsText.value,
      ok: res.ok,
      duration_ms: res.duration_ms,
      at: new Date().toLocaleTimeString(),
      preview: resultText.value.slice(0, 120),
    };
    history.value.unshift(item);
    history.value = history.value.slice(0, MAX_HISTORY);
    saveHistory();
    ui.showMessage(res.ok ? "执行成功" : "返回 error 字段", res.ok ? "success" : "warn");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    busy.value = false;
  }
}

function applyHistory(item: HistoryItem) {
  tool.value = item.tool;
  argsText.value = item.arguments;
}

function resetArgs() {
  argsText.value = '{\n  "limit": 5\n}';
}

function errMsg(e: unknown) {
  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";
}
</script>

<template>
  <PageHeader title="接口测试" description="Admin 内直连执行 tool（无需 Serve 运行）" />

  <div v-if="!connectionId" class="panel">
    <EmptyState title="无连接" description="请先创建数据源并 scan。" />
  </div>

  <template v-else>
    <div class="page-toolbar">
      <label class="form-field">
        <span class="form-field__label">连接</span>
        <select v-model="connectionId">
          <option v-for="c in connections" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </label>
      <label class="form-field">
        <span class="form-field__label">Tool</span>
        <select v-model="tool">
          <option v-for="n in toolOptions" :key="n" :value="n">{{ n }}</option>
        </select>
      </label>
    </div>

    <div class="page-split">
      <div class="panel">
        <div class="panel__header"><h2 class="panel__title">Arguments (JSON)</h2></div>
        <div class="panel__body">
          <textarea v-model="argsText" class="code-input" rows="12" spellcheck="false" />
          <p v-if="!argsValid" class="form-field__error">JSON 格式错误</p>
          <div class="page-actions">
            <button type="button" class="btn btn--primary" :disabled="busy || !tool" @click="run">
              {{ busy ? "执行中…" : "执行" }}
            </button>
            <button type="button" class="btn btn--ghost btn--sm" @click="resetArgs">
              重置参数
            </button>
          </div>
          <p v-if="lastMeta" class="meta">
            耗时 {{ lastMeta.duration_ms }}ms
            <span class="badge" :class="lastMeta.ok ? 'badge--ok' : 'badge--err'">
              {{ lastMeta.ok ? "ok" : "err" }}
            </span>
          </p>
        </div>
      </div>

      <div class="panel">
        <div class="panel__header"><h2 class="panel__title">结果</h2></div>
        <div class="panel__body">
          <pre class="result-pre">{{ resultText || "—" }}</pre>
        </div>
      </div>
    </div>

    <div v-if="history.length" class="panel panel--spaced">
      <div class="panel__header"><h2 class="panel__title">历史（session 最多 20 条）</h2></div>
      <div class="panel__body">
        <table class="data-table">
          <thead>
            <tr><th>时间</th><th>Tool</th><th>耗时</th><th>状态</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(h, i) in history" :key="i">
              <td>{{ h.at }}</td>
              <td>{{ h.tool }}</td>
              <td class="numeric">{{ h.duration_ms }}ms</td>
              <td><span class="badge" :class="h.ok ? 'badge--ok' : 'badge--err'">{{ h.ok ? "ok" : "err" }}</span></td>
              <td><button type="button" class="btn btn--sm btn--ghost" @click="applyHistory(h)">填充</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>
</template>

<style scoped>
.code-input {
  width: 100%;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-md);
}
.result-pre {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
}
.meta {
  margin-top: var(--space-md);
  font-size: var(--font-size-md);
}
.form-field__error {
  color: var(--color-err-text);
  font-size: var(--font-size-sm);
}

.panel--spaced {
  margin-top: var(--space-lg);
}
</style>
