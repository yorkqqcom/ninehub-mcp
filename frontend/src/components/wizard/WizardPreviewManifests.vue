<script setup lang="ts">

import { computed, ref, watch } from "vue";

import WizardStepShell from "@/components/wizard/WizardStepShell.vue";

import WizardStatStrip from "@/components/wizard/WizardStatStrip.vue";

import WizardConfirmDialog from "@/components/wizard/WizardConfirmDialog.vue";

import ManifestQualityBadge from "@/components/wizard/ManifestQualityBadge.vue";

import CatalogJsonPanel from "@/components/wizard/CatalogJsonPanel.vue";

import { useWizardStore } from "@/stores/wizardStore";

import { computeQualityScore } from "@/utils/mcpQualityRules";

import type { ToolManifest } from "@/api/mcp";

import { retryBuildTable } from "@/api/mcp";

import { useUiStore } from "@/stores/ui";



const emit = defineEmits<{

  back: [];

  next: [];

}>();



const store = useWizardStore();

const ui = useUiStore();



const showAgentView = ref(false);

const showBackConfirm = ref(false);

const filterTab = ref<"all" | "llm" | "rule" | "low">("all");

const search = ref("");

const selectedName = ref("");



const agentExample = {

  question: "查看平安银行历史行情和股票基本信息",

  steps: [

    "list_tools → 选 browse_public_daily（关键词含 ts_code/行情）",

    "read catalog://public.daily → join_hints 指向 stock_basic",

    "browse_public_daily filters={ts_code:'000001.SZ'} + 读 catalog://public.stock_basic",

  ],

};



const filteredTools = computed(() => {

  let list = store.tools;

  const q = search.value.trim().toLowerCase();

  if (q) {

    list = list.filter(

      (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q),

    );

  }

  if (filterTab.value === "llm") list = list.filter((t) => t.enhanced);

  if (filterTab.value === "rule") list = list.filter((t) => !t.enhanced);

  if (filterTab.value === "low") list = list.filter((t) => computeQualityScore(t) < 50);

  return list;

});



const selectedTool = computed(() => store.tools.find((t) => t.name === selectedName.value) ?? null);



const avgQuality = computed(() => {

  if (!store.tools.length) return 0;

  const sum = store.tools.reduce((a, t) => a + computeQualityScore(t), 0);

  return Math.round(sum / store.tools.length);

});



const statItems = computed(() => [

  { label: "Tools", value: store.tools.length },

  { label: "LLM 增强", value: store.job?.enhanced_count ?? store.tools.filter((t) => t.enhanced).length },

  { label: "规则降级", value: store.job?.fallback_count ?? store.tools.filter((t) => !t.enhanced).length },

  { label: "平均质量分", value: avgQuality.value },

]);



function selectTool(t: ToolManifest) {

  selectedName.value = t.name;

}



watch(
  () => store.tools,
  (tools) => {
    if (tools.length && !tools.some((t) => t.name === selectedName.value)) {
      selectedName.value = tools[0].name;
    }
  },
  { immediate: true },
);

async function retryRow(t: ToolManifest) {

  if (!store.jobId) return;

  try {

    await retryBuildTable(store.jobId, t.schema, t.table);

    await store.loadTools();

    ui.showMessage(`已重试 ${t.schema}.${t.table}`, "warn");

  } catch (e) {

    ui.showMessage(errMsg(e), "error");

  }

}



function confirmBack() {

  showBackConfirm.value = false;

  emit("back");

}



function errMsg(e: unknown) {

  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";

}

</script>



<template>

  <WizardStepShell title="质量预览" subtitle="检查 Rich Manifest 与 catalog:// v1 交付内容">

    <WizardStatStrip :items="statItems" />



    <div class="preview-toolbar">

      <div class="filter-tabs">

        <button

          type="button"

          class="filter-tab"

          :class="{ 'filter-tab--active': filterTab === 'all' }"

          @click="filterTab = 'all'"

        >

          全部

        </button>

        <button

          type="button"

          class="filter-tab"

          :class="{ 'filter-tab--active': filterTab === 'llm' }"

          @click="filterTab = 'llm'"

        >

          LLM

        </button>

        <button

          type="button"

          class="filter-tab"

          :class="{ 'filter-tab--active': filterTab === 'rule' }"

          @click="filterTab = 'rule'"

        >

          规则

        </button>

        <button

          type="button"

          class="filter-tab"

          :class="{ 'filter-tab--active': filterTab === 'low' }"

          @click="filterTab = 'low'"

        >

          低质量(&lt;50)

        </button>

      </div>

      <input v-model="search" type="search" class="input input--sm" placeholder="搜索 tool" />

      <button type="button" class="btn btn--ghost btn--sm" @click="showAgentView = !showAgentView">

        {{ showAgentView ? "隐藏" : "显示" }} Agent 视角

      </button>

    </div>



    <div v-if="showAgentView" class="agent-panel">

      <p><strong>用户问：</strong>{{ agentExample.question }}</p>

      <ol>

        <li v-for="(s, i) in agentExample.steps" :key="i">{{ s }}</li>

      </ol>

    </div>



    <div class="page-split preview-split">

      <div class="panel preview-list">

        <div class="list-scroll">

          <button

            v-for="t in filteredTools"

            :key="t.name"

            type="button"

            class="list-item btn btn--ghost"

            :class="{ 'list-item--active': selectedName === t.name }"

            @click="selectTool(t)"

          >

            <code class="list-item__name">{{ t.name }}</code>

            <ManifestQualityBadge :tool="t" />

          </button>

          <p v-if="!filteredTools.length" class="wizard-shell__hint">无匹配 tool</p>

        </div>

      </div>



      <div class="panel preview-detail">

        <div v-if="selectedTool" class="panel__body">

          <h3 class="preview-detail__title">

            <code>{{ selectedTool.name }}</code>

            <span class="badge" :class="selectedTool.enhanced ? 'badge--ok' : 'badge--warn'">

              {{ selectedTool.enhanced ? "LLM" : "规则" }}

            </span>

          </h3>

          <p class="preview-detail__desc">{{ selectedTool.description }}</p>



          <div v-if="selectedTool.keywords?.length" class="preview-field">

            <strong>Keywords</strong>

            <p>{{ selectedTool.keywords.join(", ") }}</p>

          </div>



          <div v-if="selectedTool.agent_notes" class="preview-field">

            <strong>Agent notes</strong>

            <pre class="preview-pre">{{ selectedTool.agent_notes }}</pre>

          </div>



          <div v-if="selectedTool.join_hints?.length" class="preview-field">

            <strong>Join hints ({{ selectedTool.join_hints.length }})</strong>

            <ul class="preview-list-ul">

              <li v-for="(j, i) in selectedTool.join_hints" :key="i">

                {{ j.target_schema }}.{{ j.target_table }} via {{ j.via_column }}

              </li>

            </ul>

          </div>



          <div v-if="selectedTool.filter_hints?.length" class="preview-field">

            <strong>Filter hints ({{ selectedTool.filter_hints.length }})</strong>

            <ul class="preview-list-ul">

              <li v-for="(f, i) in selectedTool.filter_hints" :key="i">

                {{ f.column }} · {{ f.kind }} — {{ f.description }}

              </li>

            </ul>

          </div>



          <div v-if="selectedTool.usage_examples?.length" class="preview-field">

            <strong>Usage examples</strong>

            <ul class="preview-list-ul">

              <li v-for="(ex, i) in selectedTool.usage_examples" :key="i">{{ ex }}</li>

            </ul>

          </div>



          <CatalogJsonPanel :tool="selectedTool" />



          <button

            v-if="store.jobId"

            type="button"

            class="btn btn--ghost btn--sm"

            @click="retryRow(selectedTool)"

          >

            重试此表

          </button>

        </div>

        <div v-else class="panel__body wizard-shell__hint">选择左侧 tool 查看详情</div>

      </div>

    </div>



    <p v-if="store.job?.pass1_status" class="wizard-shell__hint">Pass1: {{ store.job.pass1_status }}</p>



    <WizardConfirmDialog

      :open="showBackConfirm"

      title="返回策略？"

      confirm-label="返回策略"

      @cancel="showBackConfirm = false"

      @confirm="confirmBack"

    >

      返回策略将丢弃本次构建结果，重新构建会覆盖已有 manifest（locked tools 除外）。也可使用「重试此表」微调单表。

    </WizardConfirmDialog>



    <template #actions>

      <button type="button" class="btn btn--ghost" @click="showBackConfirm = true">上一步</button>

      <button type="button" class="btn btn--primary" @click="emit('next')">下一步：完成</button>

    </template>

  </WizardStepShell>

</template>



<style scoped>

.preview-toolbar {

  display: flex;

  flex-wrap: wrap;

  gap: var(--space-sm);

  align-items: center;

}



.preview-split {

  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);

}



.list-scroll {

  max-height: 480px;

  overflow: auto;

  padding: var(--space-sm);

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

  font-size: var(--font-size-sm);

}



.list-item--active {

  border-color: var(--color-primary);

  background: var(--color-primary-muted);

}



.preview-detail__title {

  display: flex;

  flex-wrap: wrap;

  align-items: center;

  gap: var(--space-sm);

  margin: 0 0 var(--space-sm);

  font-size: var(--font-size-md);

}



.preview-detail__desc {

  margin: 0 0 var(--space-md);

  color: var(--color-text-secondary);

  line-height: 1.5;

}



.preview-field {

  margin-bottom: var(--space-md);

  font-size: var(--font-size-sm);

}



.preview-field p {

  margin: var(--space-xs) 0 0;

}



.preview-pre {

  margin: var(--space-xs) 0 0;

  white-space: pre-wrap;

  font-size: var(--font-size-sm);

}



.preview-list-ul {

  margin: var(--space-xs) 0 0;

  padding-left: var(--space-lg);

}



.agent-panel {

  padding: var(--space-md);

  background: var(--color-surface-muted);

  border-radius: var(--radius-sm);

  font-size: var(--font-size-sm);

}



.wizard-shell__hint {

  margin: 0;

  color: var(--color-text-muted);

  font-size: var(--font-size-sm);

}

</style>

