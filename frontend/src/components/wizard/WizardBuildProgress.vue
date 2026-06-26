<script setup lang="ts">

import { computed } from "vue";

import WizardStepShell from "@/components/wizard/WizardStepShell.vue";

import WizardStatStrip from "@/components/wizard/WizardStatStrip.vue";

import { useWizardStore } from "@/stores/wizardStore";

import { mapBuildProgressRows } from "@/utils/buildProgressRows";



const emit = defineEmits<{

  "back-to-strategy": [];

}>();



const store = useWizardStore();



const rows = computed(() => mapBuildProgressRows(store.job));



const statItems = computed(() => {

  const j = store.job;

  if (!j) return [{ label: "进度", value: "0%" }];

  const perTable = j.per_table_results ?? [];

  const enhancedLive =

    perTable.length > 0 ? perTable.filter((r) => r.enhanced).length : j.enhanced_count;

  const fallbackLive =

    perTable.length > 0 ? perTable.filter((r) => !r.enhanced).length : j.fallback_count;

  return [

    { label: "总进度", value: `${j.progress}%` },

    { label: "LLM 增强", value: enhancedLive },

    { label: "规则降级", value: fallbackLive },

    { label: "Pass1", value: j.pass1_status ?? "—" },

  ];

});



const pass1Label = computed(() => {

  const s = store.job?.pass1_status;

  if (!s) return "等待中";

  if (s === "completed") return "SchemaGraph 完成";

  if (s === "fallback") return "已降级为规则图";

  return s;

});



const isFailed = computed(() => store.job?.status === "failed");

const isRunning = computed(

  () => store.job?.status === "pending" || store.job?.status === "running",

);

</script>



<template>

  <WizardStepShell

    title="构建进度"

    :subtitle="isRunning ? 'Pass1 + Pass2 构建中，请勿离开此页' : isFailed ? '构建失败' : '构建完成'"

  >

    <WizardStatStrip :items="statItems" />



    <div

      class="progress-bar"

      role="progressbar"

      :aria-valuenow="store.job?.progress ?? 0"

      aria-valuemin="0"

      aria-valuemax="100"

    >

      <div class="progress-bar__fill" :style="{ width: `${store.job?.progress ?? 0}%` }" />

    </div>



    <div class="phase-grid">

      <div class="panel phase-card">

        <div class="panel__header">Pass1 · SchemaGraph</div>

        <div class="panel__body">

          <span

            class="badge"

            :class="

              store.job?.pass1_status === 'completed'

                ? 'badge--ok'

                : store.job?.pass1_status === 'fallback'

                  ? 'badge--warn'

                  : isRunning

                    ? 'badge--muted'

                    : 'badge--muted'

            "

          >

            {{ pass1Label }}

          </span>

        </div>

      </div>



      <div class="panel phase-card phase-card--wide">

        <div class="panel__header">

          Pass2 · 逐表 Rich Manifest

          <span v-if="store.job?.current_table" class="phase-card__current">

            当前：{{ store.job.current_table }}

          </span>

        </div>

        <div class="panel__body">

          <div class="table-scroll table-scroll--progress">

            <table class="data-table">

              <thead>

                <tr>

                  <th>表</th>

                  <th>来源</th>

                  <th>关键词</th>

                  <th>Join</th>

                  <th>状态</th>

                </tr>

              </thead>

              <tbody>

                <tr

                  v-for="row in rows"

                  :key="row.key"

                  class="progress-row"

                  :class="{ 'progress-row--running': row.status === 'running' }"

                >

                  <td><code>{{ row.key }}</code></td>

                  <td>

                    <span v-if="row.status === 'done'" class="badge" :class="row.enhanced ? 'badge--ok' : 'badge--warn'">

                      {{ row.enhanced ? "LLM" : "规则" }}

                    </span>

                    <span v-else class="badge badge--muted">…</span>

                  </td>

                  <td>{{ row.status === "done" ? row.keywordsCount : "—" }}</td>

                  <td>{{ row.status === "done" ? row.joinHintsCount : "—" }}</td>

                  <td>{{ row.status === "done" ? "✓" : row.status === "running" ? "构建中" : "—" }}</td>

                </tr>

                <tr v-if="!rows.length && isRunning">

                  <td colspan="5" class="wizard-shell__hint">等待 Pass2 开始…</td>

                </tr>

              </tbody>

            </table>

          </div>

        </div>

      </div>

    </div>



    <p v-if="store.jobError" class="form-field__error" role="alert">{{ store.jobError }}</p>



    <template v-if="isFailed" #actions>

      <button type="button" class="btn btn--ghost" @click="emit('back-to-strategy')">返回策略</button>

    </template>

  </WizardStepShell>

</template>



<style scoped>

.phase-grid {

  display: grid;

  grid-template-columns: minmax(200px, 280px) minmax(0, 1fr);

  gap: var(--space-md);

}



@media (max-width: 768px) {

  .phase-grid {

    grid-template-columns: 1fr;

  }

}



.phase-card__current {

  font-size: var(--font-size-sm);

  font-weight: normal;

  color: var(--color-primary);

  margin-left: var(--space-sm);

}



.table-scroll--progress {

  max-height: 360px;

}



.progress-row {

  transition: background var(--transition-fast);

}



.progress-row--running {

  background: var(--color-primary-muted);

}



.wizard-shell__hint {

  color: var(--color-text-muted);

  font-size: var(--font-size-sm);

}

</style>

