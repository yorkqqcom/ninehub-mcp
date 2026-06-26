<script setup lang="ts">
import { onMounted, ref } from "vue";
import PageHeader from "@/components/PageHeader.vue";
import SkeletonLoader from "@/components/SkeletonLoader.vue";
import {
  getPlatformSettings,
  patchPlatformSettings,
  randomToken,
  testLlmConnection,
  type PlatformSettings,
} from "@/api/platform";
import { listPromptTemplates, patchPromptTemplate, resetPromptTemplate, type PromptTemplate } from "@/api/mcp";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const activeTab = ref<"llm" | "keys" | "prompts">("llm");
const settings = ref<PlatformSettings | null>(null);
const llmTestResult = ref<{ ok: boolean; message: string } | null>(null);

const llm = ref({
  base_url: "",
  model: "",
  api_key: "",
  build_enabled: true,
});
const keys = ref({ mcp_api_key: "", admin_api_token: "" });
const promptTemplates = ref<PromptTemplate[]>([]);
const selectedPrompt = ref("");
const promptContent = ref("");

onMounted(() => void load());

async function load() {
  loading.value = true;
  try {
    settings.value = await getPlatformSettings();
    llm.value.base_url = settings.value.llm_base_url;
    llm.value.model = settings.value.llm_model;
    llm.value.build_enabled = settings.value.llm_build_enabled;
    const prompts = await listPromptTemplates();
    promptTemplates.value = prompts.items;
    if (prompts.items.length) {
      selectedPrompt.value = prompts.items[0].name;
      promptContent.value = prompts.items[0].content;
    }
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    loading.value = false;
  }
}

function errMsg(e: unknown) {
  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";
}

async function saveLlm() {
  saving.value = true;
  try {
    settings.value = await patchPlatformSettings({
      llm_base_url: llm.value.base_url,
      llm_model: llm.value.model,
      llm_build_enabled: llm.value.build_enabled,
      ...(llm.value.api_key.trim() ? { llm_api_key: llm.value.api_key.trim() } : {}),
    });
    llm.value.api_key = "";
    ui.showMessage("LLM 配置已保存", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    saving.value = false;
  }
}

async function saveKeys() {
  saving.value = true;
  try {
    const body: Record<string, string> = {};
    if (keys.value.mcp_api_key.trim()) body.mcp_api_key = keys.value.mcp_api_key.trim();
    if (keys.value.admin_api_token.trim()) body.admin_api_token = keys.value.admin_api_token.trim();
    settings.value = await patchPlatformSettings(body);
    keys.value = { mcp_api_key: "", admin_api_token: "" };
    ui.showMessage("密钥已更新", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    saving.value = false;
  }
}

async function testLlm() {
  testing.value = true;
  llmTestResult.value = null;
  try {
    const res = await testLlmConnection({
      llm_base_url: llm.value.base_url,
      llm_model: llm.value.model,
      llm_api_key: llm.value.api_key || undefined,
    });
    const message = res.ok ? `连接成功 · ${res.latency_ms}ms` : res.error || "LLM 失败";
    llmTestResult.value = { ok: res.ok, message };
    ui.showMessage(message, res.ok ? "success" : "error");
  } catch (e) {
    llmTestResult.value = { ok: false, message: errMsg(e) };
    ui.showMessage(errMsg(e), "error");
  } finally {
    testing.value = false;
  }
}

function selectPrompt(name: string) {
  selectedPrompt.value = name;
  promptContent.value = promptTemplates.value.find((p) => p.name === name)?.content || "";
}

async function savePrompt() {
  if (!selectedPrompt.value) return;
  saving.value = true;
  try {
    await patchPromptTemplate(selectedPrompt.value, promptContent.value);
    ui.showMessage("Prompt 模板已保存", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    saving.value = false;
  }
}

async function resetPrompt() {
  if (!selectedPrompt.value) return;
  saving.value = true;
  try {
    const res = await resetPromptTemplate(selectedPrompt.value);
    promptContent.value = res.content;
    ui.showMessage("已恢复默认模板", "success");
  } catch (e) {
    ui.showMessage(errMsg(e), "error");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <PageHeader title="设置" description="LLM 与 MCP 平台配置">
    <template #actions>
      <router-link class="btn btn--secondary" to="/settings/account">账户</router-link>
    </template>
  </PageHeader>

  <div v-if="loading" class="panel"><SkeletonLoader :rows="4" /></div>

  <template v-else-if="settings">
    <div class="settings-tabs" role="tablist">
      <button
        type="button"
        class="filter-tab"
        :class="{ active: activeTab === 'llm' }"
        @click="activeTab = 'llm'"
      >
        LLM 配置
      </button>
      <button
        type="button"
        class="filter-tab"
        :class="{ active: activeTab === 'prompts' }"
        @click="activeTab = 'prompts'"
      >
        构建模板
      </button>
      <button
        type="button"
        class="filter-tab"
        :class="{ active: activeTab === 'keys' }"
        @click="activeTab = 'keys'"
      >
        MCP / Admin 密钥
      </button>
    </div>

    <div v-show="activeTab === 'llm'" class="panel">
      <div class="panel__header"><h2 class="panel__title">LLM 配置</h2></div>
      <div class="panel__body">
        <div
          v-if="llmTestResult"
          class="page-banner"
          :class="llmTestResult.ok ? 'page-banner--info' : 'page-banner--warn'"
          role="status"
        >
          {{ llmTestResult.message }}
        </div>
        <div class="form-grid">
          <label class="form-field">
            <span class="form-field__label">Base URL</span>
            <input v-model="llm.base_url" type="url" placeholder="https://api.openai.com/v1" />
          </label>
          <label class="form-field">
            <span class="form-field__label">Model</span>
            <input v-model="llm.model" type="text" placeholder="gpt-4o-mini" />
          </label>
          <label class="form-field form-field--full">
            <span class="form-field__label">API Key {{ settings.llm_api_key_set ? "(已设置)" : "" }}</span>
            <input v-model="llm.api_key" type="password" placeholder="留空不修改" autocomplete="new-password" />
          </label>
          <label class="form-field form-field--checkbox">
            <input v-model="llm.build_enabled" type="checkbox" />
            启用 LLM 构建（关闭则全部使用规则降级）
          </label>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn--primary" :disabled="saving" @click="saveLlm">保存</button>
          <button type="button" class="btn btn--secondary" :disabled="testing" @click="testLlm">
            {{ testing ? "测试中…" : "测试连接" }}
          </button>
        </div>
      </div>
    </div>

    <div v-show="activeTab === 'prompts'" class="panel panel--spaced">
      <div class="panel__header"><h2 class="panel__title">构建 Prompt 模板</h2></div>
      <div class="panel__body">
        <label class="form-field">
          <span class="form-field__label">模板</span>
          <select :value="selectedPrompt" @change="selectPrompt(($event.target as HTMLSelectElement).value)">
            <option v-for="p in promptTemplates" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
        </label>
        <label class="form-field">
          <span class="form-field__label">内容（Jinja2）</span>
          <textarea v-model="promptContent" rows="12" class="input-w-full" />
        </label>
        <div class="page-actions">
          <button type="button" class="btn btn--primary" :disabled="saving" @click="savePrompt">保存模板</button>
          <button type="button" class="btn btn--ghost" :disabled="saving" @click="resetPrompt">恢复默认</button>
        </div>
      </div>
    </div>

    <div v-show="activeTab === 'keys'" class="panel panel--spaced">
      <div class="panel__header"><h2 class="panel__title">MCP / Admin 密钥</h2></div>
      <div class="panel__body">
        <div class="form-grid">
          <label class="form-field">
            <span class="form-field__label">MCP_API_KEY {{ settings.mcp_api_key_set ? "✓" : "" }}</span>
            <input v-model="keys.mcp_api_key" type="password" placeholder="留空不修改" autocomplete="new-password" />
          </label>
          <label class="form-field">
            <span class="form-field__label">ADMIN_API_TOKEN {{ settings.admin_api_token_set ? "✓" : "" }}</span>
            <input v-model="keys.admin_api_token" type="password" placeholder="留空不修改" autocomplete="new-password" />
          </label>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn--ghost btn--sm" @click="keys.mcp_api_key = randomToken()">
            生成 MCP Key
          </button>
          <button type="button" class="btn btn--primary" :disabled="saving" @click="saveKeys">保存密钥</button>
        </div>
        <p class="settings-hint">
          Serve 默认监听 {{ settings.mcp_http_host }}:{{ settings.mcp_http_port }}
        </p>
      </div>
    </div>
  </template>
</template>

<style scoped>
.settings-tabs {
  display: flex;
  gap: var(--space-xs);
  margin-bottom: var(--space-md);
}

.form-field--full {
  grid-column: 1 / -1;
}

.form-field--checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-md);
}

.panel--spaced {
  margin-top: var(--space-md);
}

.settings-hint {
  margin-top: var(--space-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}
</style>
