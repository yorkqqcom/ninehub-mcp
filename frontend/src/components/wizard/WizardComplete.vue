<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import WizardStepShell from "@/components/wizard/WizardStepShell.vue";
import WizardStatStrip from "@/components/wizard/WizardStatStrip.vue";
import CopyButton from "@/components/CopyButton.vue";
import { getPlatformSettings, type PlatformSettings } from "@/api/platform";
import { exportMcpConfig } from "@/api/mcp";
import { useWizardStore } from "@/stores/wizardStore";
import { useUiStore } from "@/stores/ui";

const props = defineProps<{
  isQuickMode?: boolean;
}>();

const emit = defineEmits<{
  "new-build": [];
}>();

const store = useWizardStore();
const ui = useUiStore();
const platform = ref<PlatformSettings | null>(null);
const exporting = ref(false);

const durationLabel = computed(() => {
  const j = store.job;
  if (!j || !("created_at" in j) || !("updated_at" in j)) return "—";
  const created = (j as { created_at?: string }).created_at;
  const updated = (j as { updated_at?: string }).updated_at;
  if (!created || !updated) return "—";
  const ms = new Date(updated).getTime() - new Date(created).getTime();
  if (ms < 0) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
});

const statItems = computed(() => [
  { label: "Job ID", value: store.jobId?.slice(0, 8) ?? "—", hint: store.jobId ?? undefined },
  { label: "耗时", value: durationLabel.value },
  {
    label: "LLM / 规则",
    value: `${store.job?.enhanced_count ?? 0} / ${store.job?.fallback_count ?? 0}`,
  },
  { label: "Config 版本", value: store.readiness?.context_pack_version ?? "—" },
]);

const hermesUrl = computed(() => {
  if (!platform.value) return "";
  const host = platform.value.mcp_http_host || "127.0.0.1";
  const port = platform.value.mcp_http_port || 8000;
  return `http://${host}:${port}/mcp`;
});

const lockedCount = computed(() => store.tools.filter((t) => t.locked).length);

onMounted(async () => {
  try {
    platform.value = await getPlatformSettings();
  } catch {
    platform.value = null;
  }
});

async function downloadConfig() {
  if (!store.connectionId) return;
  exporting.value = true;
  try {
    const cfg = await exportMcpConfig(store.connectionId);
    const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mcp-config-${store.connectionId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ui.showMessage("已导出 config", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    exporting.value = false;
  }
}

function errMsg(e: unknown) {
  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";
}
</script>

<template>
  <WizardStepShell
    title="MCP 构建完成"
    :subtitle="isQuickMode ? '快速模式构建已完成' : '高级向导 6 步流程已完成'"
  >
    <div class="complete-success">
      <span class="complete-success__icon" aria-hidden="true">✓</span>
      <p>共 {{ store.tools.length }} 个 browse_* tools 已写入 runtime config</p>
    </div>

    <WizardStatStrip :items="statItems" />

    <ul class="complete-summary">
      <li>catalog:// v1 Resource 可随 MCP Serve 暴露给 Agent</li>
      <li v-if="!isQuickMode">已按高级策略完成 Pass1 + Pass2 构建</li>
      <li v-if="lockedCount">locked tools（{{ lockedCount }}）未被本次构建覆盖</li>
    </ul>

    <div class="complete-cta">
      <router-link
        class="complete-cta__card"
        :to="{ path: '/mcp/tools', query: { connection_id: store.connectionId } }"
      >
        <strong>接口清单</strong>
        <span>浏览与锁定 manifest</span>
      </router-link>
      <router-link
        class="complete-cta__card"
        :to="{ path: '/mcp/test', query: { connection_id: store.connectionId } }"
      >
        <strong>接口测试</strong>
        <span>Admin 内调用 browse_*</span>
      </router-link>
      <router-link class="complete-cta__card" to="/mcp/serve">
        <strong>服务管控</strong>
        <span>启动 streamable-http Serve</span>
      </router-link>
    </div>

    <div class="panel hermes-panel">
      <div class="panel__header">Hermes / Cursor 接入</div>
      <div class="panel__body">
        <template v-if="platform?.mcp_api_key_set">
          <p class="wizard-shell__hint">streamable-http URL（复制到 MCP 客户端配置）：</p>
          <div class="hermes-row">
            <code>{{ hermesUrl }}</code>
            <CopyButton :text="hermesUrl" />
          </div>
          <p class="wizard-shell__hint">MCP_API_KEY 已在平台设置中配置（界面不展示明文）。</p>
        </template>
        <template v-else>
          <p class="wizard-shell__hint">尚未设置 MCP_API_KEY，Serve 启动后无法通过密钥鉴权。</p>
          <router-link class="btn btn--primary btn--sm" to="/settings">前往设置生成密钥</router-link>
        </template>
      </div>
    </div>

    <template #actions>
      <button type="button" class="btn btn--ghost" @click="emit('new-build')">新建构建</button>
      <button type="button" class="btn btn--secondary" :disabled="exporting" @click="downloadConfig">
        {{ exporting ? "导出中…" : "导出 config JSON" }}
      </button>
    </template>
  </WizardStepShell>
</template>

<style scoped>
.complete-success {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  background: var(--color-ok-bg, var(--color-primary-muted));
  border-radius: var(--radius-sm);
}

.complete-success__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  font-weight: 700;
}

.complete-success p {
  margin: 0;
  font-weight: 600;
}

.complete-summary {
  margin: 0;
  padding-left: var(--space-lg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  line-height: 1.6;
}

.complete-cta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-md);
}

.complete-cta__card {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  text-decoration: none;
  color: inherit;
  background: var(--color-surface-muted);
  transition: border-color var(--transition-fast);
}

.complete-cta__card:hover {
  border-color: var(--color-primary);
}

.complete-cta__card span {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.hermes-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin: var(--space-sm) 0;
}

.hermes-row code {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-sm);
}

.wizard-shell__hint {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}
</style>
