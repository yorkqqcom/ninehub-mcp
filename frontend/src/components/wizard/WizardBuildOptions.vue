<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import WizardStepShell from "@/components/wizard/WizardStepShell.vue";
import PromptTemplatePreview from "@/components/wizard/PromptTemplatePreview.vue";
import { listPromptTemplates, type PromptTemplate } from "@/api/mcp";
import { useWizardStore } from "@/stores/wizardStore";

const emit = defineEmits<{
  back: [];
  next: [];
}>();

const store = useWizardStore();
const promptTemplates = ref<PromptTemplate[]>([]);

const tableScopeLabel = computed(() => {
  if (store.tableFilter.length) return `${store.tableFilter.length} 张表`;
  return `全部 exposed（${store.packSummary?.exposed_count ?? "—"}）`;
});

const llmReady = computed(() => {
  const p = store.dashboard?.platform;
  if (!p?.llm_build_enabled) return true;
  return p.llm_api_key_set;
});

onMounted(async () => {
  try {
    const res = await listPromptTemplates();
    promptTemplates.value = res.items;
  } catch {
    promptTemplates.value = [];
  }
});

function updateLlmEnabled(v: boolean) {
  store.setBuildOption("llm_enabled", v);
}

function updateSkipPass1(v: boolean) {
  store.setBuildOption("skip_pass1", v);
}

function updateDomainHint(v: string) {
  store.setBuildOption("domain_hint", v);
}

function updateCustomSuffix(v: string) {
  store.setBuildOption("custom_prompt_suffix", v);
}
</script>

<template>
  <WizardStepShell title="构建策略" subtitle="配置两阶段 LLM 构建与 Prompt 上下文">
    <div v-if="!llmReady" class="strategy-banner strategy-banner--warn">
      LLM 构建已启用但未配置 API Key。
      <router-link to="/settings">前往设置</router-link>
    </div>

    <div class="strategy-grid">
      <div class="panel strategy-form">
        <div class="panel__body">
          <label class="form-field form-field--inline">
            <input
              type="checkbox"
              :checked="store.buildOptions.llm_enabled"
              @change="updateLlmEnabled(($event.target as HTMLInputElement).checked)"
            />
            启用 LLM 增强（关闭则全部使用规则 rich_rule）
          </label>
          <label class="form-field form-field--inline">
            <input
              type="checkbox"
              :checked="store.buildOptions.skip_pass1"
              @change="updateSkipPass1(($event.target as HTMLInputElement).checked)"
            />
            跳过 Pass1 图谱（仅用 FK/推断 join 规则图）
          </label>
          <label class="form-field">
            <span class="form-field__label">业务域说明（domain_hint）</span>
            <input
              :value="store.buildOptions.domain_hint ?? ''"
              placeholder="例：A股量化行情与基本面"
              @input="updateDomainHint(($event.target as HTMLInputElement).value)"
            />
          </label>
          <label class="form-field">
            <span class="form-field__label">追加 Prompt 指令</span>
            <textarea
              :value="store.buildOptions.custom_prompt_suffix ?? ''"
              rows="3"
              placeholder="可选：追加到 LLM prompt 末尾"
              @input="updateCustomSuffix(($event.target as HTMLTextAreaElement).value)"
            />
          </label>
        </div>
      </div>

      <div class="panel strategy-summary">
        <div class="panel__header">策略摘要</div>
        <div class="panel__body strategy-summary__body">
          <dl class="summary-dl">
            <dt>模式</dt>
            <dd>高级向导</dd>
            <dt>表范围</dt>
            <dd>{{ tableScopeLabel }}</dd>
            <dt>流程</dt>
            <dd>Pass1 SchemaGraph → Pass2 逐表 Rich Manifest</dd>
            <dt>降级</dt>
            <dd>fallback_to_rule ✓</dd>
            <dt>LLM</dt>
            <dd>
              {{ store.buildOptions.llm_enabled ? "启用" : "关闭（全规则）" }}
              · {{ store.dashboard?.platform.llm_model ?? "—" }}
            </dd>
          </dl>
        </div>
      </div>
    </div>

    <PromptTemplatePreview :templates="promptTemplates" edit-href="/settings" />

    <template #actions>
      <button type="button" class="btn btn--ghost" @click="emit('back')">上一步</button>
      <button type="button" class="btn btn--primary" @click="emit('next')">开始构建</button>
    </template>
  </WizardStepShell>
</template>

<style scoped>
.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-md);
}

.strategy-banner--warn {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  background: var(--color-warn-bg, rgba(255, 193, 7, 0.12));
  font-size: var(--font-size-md);
}

.strategy-banner--warn a {
  margin-left: var(--space-sm);
  color: var(--color-primary);
  font-weight: 600;
}

.summary-dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-xs) var(--space-md);
  margin: 0;
  font-size: var(--font-size-md);
}

.summary-dl dt {
  color: var(--color-text-muted);
}

.summary-dl dd {
  margin: 0;
}

.form-field--inline {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
</style>
