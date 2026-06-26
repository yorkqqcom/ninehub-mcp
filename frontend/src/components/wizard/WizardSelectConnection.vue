<script setup lang="ts">

import { computed } from "vue";

import { useRouter } from "vue-router";

import ConnectionWorkflowSteps from "@/components/ConnectionWorkflowSteps.vue";

import WizardStepShell from "@/components/wizard/WizardStepShell.vue";

import WizardStatStrip from "@/components/wizard/WizardStatStrip.vue";

import WizardReadinessBanner from "@/components/wizard/WizardReadinessBanner.vue";

import { useWizardStore } from "@/stores/wizardStore";



const emit = defineEmits<{

  quick: [];

  advanced: [];

}>();



const router = useRouter();

const store = useWizardStore();



const readiness = computed(() => store.readiness);



const statItems = computed(() => {

  const r = readiness.value;

  if (!r) return [];

  return [

    {

      label: "验证",

      value: r.last_verify_ok === true ? "已通过" : r.last_verify_ok === false ? "失败" : "未验证",

    },

    {

      label: "Context Pack",

      value: r.context_pack_version ?? "—",

    },

    { label: "已有 Tools", value: r.tools_count },

    {

      label: "通配符",

      value:

        (store.selectedConnection?.include_table_patterns.length ?? 0) +

        (store.selectedConnection?.exclude_table_patterns.length ?? 0),

    },

  ];

});



const workflowProps = computed(() => ({

  connectionId: store.connectionId,

  verified: readiness.value?.last_verify_ok === true,

  hasPatterns:

    (store.selectedConnection?.include_table_patterns.length ?? 0) +

      (store.selectedConnection?.exclude_table_patterns.length ?? 0) >

    0,

  hasContextPack: readiness.value?.has_context_pack ?? false,

  hasConfig: readiness.value?.has_config ?? false,

}));



function selectConnection(id: string) {

  store.setConnectionId(id);

}

</script>



<template>

  <WizardStepShell title="选择数据源" subtitle="确认 Scan 就绪后，选择快速重建或高级 6 步向导">

    <ConnectionWorkflowSteps v-bind="workflowProps" />



    <WizardReadinessBanner

      :readiness="readiness"

      :llm-build-enabled="store.dashboard?.platform.llm_build_enabled"

      :llm-api-key-set="store.dashboard?.platform.llm_api_key_set"

    />



    <WizardStatStrip v-if="readiness" :items="statItems" />



    <div class="conn-cards">

      <button

        v-for="c in store.connections"

        :key="c.id"

        type="button"

        class="conn-card"

        :class="{ 'conn-card--active': store.connectionId === c.id }"

        @click="selectConnection(c.id)"

      >

        <div class="conn-card__head">

          <strong>{{ c.name }}</strong>

          <span class="conn-card__badges">

            <span

              v-if="store.dashboard?.connections_list.find((x) => x.id === c.id)?.last_verify_ok === true"

              class="badge badge--ok"

            >

              已验证

            </span>

            <span

              v-else-if="store.dashboard?.connections_list.find((x) => x.id === c.id)?.last_verify_ok === false"

              class="badge badge--err"

            >

              验证失败

            </span>

            <span

              v-if="!store.dashboard?.connections_list.find((x) => x.id === c.id)?.has_context_pack"

              class="badge badge--muted"

            >

              无 Pack

            </span>

            <span v-else-if="store.dashboard?.connections_list.find((x) => x.id === c.id)?.has_config" class="badge badge--ok">

              {{ store.dashboard?.connections_list.find((x) => x.id === c.id)?.tools_count ?? 0 }} tools

            </span>

            <span v-else class="badge badge--ok">已扫描</span>

          </span>

        </div>

        <div class="conn-card__meta">{{ c.database_host }} · {{ c.profile }}</div>

      </button>

    </div>



    <div class="mode-cards">

      <div class="mode-card">

        <h3 class="mode-card__title">快速重建</h3>

        <p class="mode-card__desc">默认 LLM 增强，构建全部 exposed 表，跳过审视与策略步骤。</p>

        <button

          type="button"

          class="btn btn--primary"

          :disabled="!store.canBuild || store.busy"

          @click="emit('quick')"

        >

          快速重建全部

        </button>

      </div>

      <div class="mode-card">

        <h3 class="mode-card__title">高级向导</h3>

        <p class="mode-card__desc">6 步流程：审视 Pack → 配置策略 → 构建 → 预览 → 完成。</p>

        <button

          type="button"

          class="btn btn--secondary"

          :disabled="!store.canBuild || store.busy"

          @click="emit('advanced')"

        >

          高级向导

        </button>

      </div>

    </div>



    <p v-if="!store.canBuild && store.connectionId && !store.hasConfig" class="wizard-shell__hint">

      需要 Context Pack？

      <button type="button" class="btn btn--ghost btn--sm" @click="router.push(`/connections/${store.connectionId}/scan`)">

        前往 Scan

      </button>

    </p>

    <p v-else-if="!store.canBuild && store.connectionId && store.hasConfig" class="wizard-shell__hint wizard-shell__hint--warn">

      已有 MCP 工具配置，但 Context Pack 已丢失，需重新 Scan 后才能重建。

    </p>



    <template #actions>

      <router-link class="btn btn--ghost" to="/connections">管理连接</router-link>

    </template>

  </WizardStepShell>

</template>



<style scoped>

.conn-cards {

  display: grid;

  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));

  gap: var(--space-sm);

}



.conn-card {

  text-align: left;

  padding: var(--space-md);

  border: 1px solid var(--color-border);

  border-radius: var(--radius-sm);

  background: var(--color-surface);

  cursor: pointer;

  transition: border-color var(--transition-fast), background var(--transition-fast);

}



.conn-card:hover {

  background: var(--color-row-hover);

}



.conn-card--active {

  border-color: var(--color-primary);

  background: var(--color-primary-muted);

}



.conn-card__head {

  display: flex;

  justify-content: space-between;

  align-items: flex-start;

  gap: var(--space-sm);

  margin-bottom: var(--space-xs);

}



.conn-card__badges {

  display: flex;

  flex-wrap: wrap;

  gap: 4px;

  justify-content: flex-end;

}



.conn-card__meta {

  font-size: var(--font-size-sm);

  color: var(--color-text-muted);

}



.mode-cards {

  display: grid;

  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));

  gap: var(--space-md);

}



.mode-card {

  padding: var(--space-md);

  border: 1px solid var(--color-border);

  border-radius: var(--radius-panel);

  background: var(--color-surface-muted);

}



.mode-card__title {

  margin: 0 0 var(--space-xs);

  font-size: var(--font-size-md);

}



.mode-card__desc {

  margin: 0 0 var(--space-md);

  font-size: var(--font-size-sm);

  color: var(--color-text-muted);

  line-height: 1.45;

}



.wizard-shell__hint {

  margin: 0;

  font-size: var(--font-size-sm);

  color: var(--color-text-muted);

}



.wizard-shell__hint--warn {
  color: var(--color-warn-text, var(--color-text-secondary));
}

</style>

