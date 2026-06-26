<script setup lang="ts">

import { computed, onActivated, onMounted, onUnmounted, watch } from "vue";

import { useRoute, useRouter } from "vue-router";

import PageHeader from "@/components/PageHeader.vue";

import EmptyState from "@/components/EmptyState.vue";

import SkeletonLoader from "@/components/SkeletonLoader.vue";

import WizardSelectConnection from "@/components/wizard/WizardSelectConnection.vue";

import WizardReviewPack from "@/components/wizard/WizardReviewPack.vue";

import WizardBuildOptions from "@/components/wizard/WizardBuildOptions.vue";

import WizardBuildProgress from "@/components/wizard/WizardBuildProgress.vue";

import WizardPreviewManifests from "@/components/wizard/WizardPreviewManifests.vue";

import WizardComplete from "@/components/wizard/WizardComplete.vue";

import { canGoToStep, stepperItems } from "@/composables/useWizardState";

import { useWizardStore } from "@/stores/wizardStore";

import { useUiStore } from "@/stores/ui";



const route = useRoute();

const router = useRouter();

const store = useWizardStore();

const ui = useUiStore();



let pollTimer: number | null = null;



const steps = computed(() => stepperItems(store.mode));



const displayStep = computed(() => store.currentStep);



function stopPoll() {

  if (pollTimer) window.clearInterval(pollTimer);

  pollTimer = null;

}



async function startPoll() {

  stopPoll();

  pollTimer = window.setInterval(() => void pollJob(), 800);

  await pollJob();

}



async function pollJob() {

  if (!store.jobId) return;

  await store.refreshJob();

  if (store.job?.status === "completed") {

    stopPoll();

    store.onJobCompleted();

    syncRoute();

  } else if (store.job?.status === "failed") {

    stopPoll();

    if (store.jobError) ui.showMessage(store.jobError, "error");

  }

}



function syncRoute() {

  if (store.jobId) {

    router.replace({

      name: "mcp-build-step",

      params: { jobId: store.jobId, step: String(store.currentStep) },

    });

  } else if (route.name === "mcp-build-step") {

    router.replace({ name: "mcp-build", query: route.query });

  }

}



watch(

  () => store.currentStep,

  () => syncRoute(),

);



onMounted(async () => {

  const routeJob = route.params.jobId as string | undefined;

  const routeStep = Number(route.params.step) || undefined;

  const qid = route.query.connection_id as string | undefined;

  try {

    await store.bootstrap(qid, routeJob, routeStep);

    if (store.jobId && store.job && (store.job.status === "pending" || store.job.status === "running")) {

      store.busy = true;

      await startPoll();

    }

  } catch (e) {

    ui.showMessage(errMsg(e), "error");

  }

});



onActivated(async () => {

  if (!store.initialized) return;

  try {

    await store.refreshDashboard();

    await store.refreshPackStatus();

  } catch (e) {

    ui.showMessage(errMsg(e), "error");

  }

});



onUnmounted(() => stopPoll());



async function onQuick() {

  store.mode = "quick";

  store.buildOptions.mode = "quick";

  store.persistPreferences();

  await runBuild();

}



async function onAdvanced() {
  store.goAdvanced();
  try {
    await store.ensurePackForAdvanced();
  } catch (e) {
    store.setStep(1);
    ui.showMessage(errMsg(e), "error");
  }
}



async function runBuild() {

  try {

    store.busy = true;

    await store.startBuild();

    syncRoute();

    await startPoll();

  } catch (e) {

    store.busy = false;

    ui.showMessage(errMsg(e), "error");

  }

}



function onStepClick(target: number) {

  const ok = canGoToStep(target, {

    mode: store.mode,

    currentStep: store.currentStep,

    jobId: store.jobId,

    jobStatus: store.job?.status,

  });

  if (!ok) return;

  store.setStep(target);

}



function onBackFromReview() {

  store.setStep(1);

}



function onNextFromReview() {

  store.setStep(3);

}



function onBackFromStrategy() {

  store.setStep(2);

}



function onBackFromPreview() {

  store.confirmBackToStrategy();

  syncRoute();

}



function onNextFromPreview() {

  store.setStep(6);

}



function onBackToStrategyFromProgress() {

  store.confirmBackToStrategy();

  syncRoute();

}



function onNewBuild() {

  store.resetWizard();

  router.replace({ name: "mcp-build", query: { connection_id: store.connectionId } });

}



function errMsg(e: unknown) {

  return e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";

}

</script>



<template>

  <PageHeader title="MCP 生成向导" description="两阶段 LLM 构建 Rich Manifest · catalog:// v1">

    <template #actions>

      <button

        v-if="store.connectionId"

        type="button"

        class="btn btn--ghost"

        @click="router.push(`/connections/${store.connectionId}/scan`)"

      >

        查看 Scan

      </button>

    </template>

  </PageHeader>



  <div v-if="store.pageLoading" class="panel"><SkeletonLoader :rows="3" /></div>



  <div v-else-if="!store.connections.length" class="panel">

    <EmptyState title="无可用连接" description="请先添加数据源并完成扫描。">

      <button type="button" class="btn btn--primary" @click="router.push('/connections')">新建连接</button>

    </EmptyState>

  </div>



  <div v-else class="panel">

    <div class="panel__body">

      <div class="wizard-stepper" role="list">

        <button

          v-for="s in steps"

          :key="s.n"

          type="button"

          class="wizard-stepper__item"

          :class="{

            active: displayStep >= s.n,

            current: displayStep === s.n,

            clickable: canGoToStep(s.n, {

              mode: store.mode,

              currentStep: store.currentStep,

              jobId: store.jobId,

              jobStatus: store.job?.status,

            }),

          }"

          :disabled="

            !canGoToStep(s.n, {

              mode: store.mode,

              currentStep: store.currentStep,

              jobId: store.jobId,

              jobStatus: store.job?.status,

            })

          "

          role="listitem"

          @click="onStepClick(s.n)"

        >

          <span class="wizard-stepper__num">{{ s.n }}</span>

          {{ s.label }}

        </button>

      </div>



      <WizardSelectConnection

        v-if="store.currentStep === 1"

        @quick="onQuick"

        @advanced="onAdvanced"

      />



      <WizardReviewPack

        v-else-if="store.currentStep === 2"

        @back="onBackFromReview"

        @next="onNextFromReview"

      />



      <WizardBuildOptions

        v-else-if="store.currentStep === 3"

        @back="onBackFromStrategy"

        @next="runBuild"

      />



      <WizardBuildProgress

        v-else-if="store.currentStep === 4"

        @back-to-strategy="onBackToStrategyFromProgress"

      />



      <WizardPreviewManifests

        v-else-if="store.currentStep === 5"

        @back="onBackFromPreview"

        @next="onNextFromPreview"

      />



      <WizardComplete

        v-else-if="store.currentStep === 6"

        :is-quick-mode="store.isQuickMode"

        @new-build="onNewBuild"

      />

    </div>

  </div>

</template>



<style scoped>

.wizard-stepper {

  display: flex;

  flex-wrap: wrap;

  gap: var(--space-sm);

  margin-bottom: var(--space-lg);

  padding-bottom: var(--space-md);

  border-bottom: 1px solid var(--color-border);

}



.wizard-stepper__item {

  display: inline-flex;

  align-items: center;

  gap: 8px;

  padding: 6px 12px;

  border-radius: var(--radius-sm);

  font-size: var(--font-size-md);

  color: var(--color-text-muted);

  border: none;

  background: transparent;

  cursor: default;

}



.wizard-stepper__item.clickable:not(:disabled) {

  cursor: pointer;

}



.wizard-stepper__item.clickable:not(:disabled):hover {

  background: var(--color-row-hover);

}



.wizard-stepper__item:disabled {

  opacity: 0.55;

}



.wizard-stepper__item.active {

  color: var(--color-text-secondary);

}



.wizard-stepper__item.current {

  background: var(--color-primary-muted);

  color: var(--color-primary);

  font-weight: 600;

}



.wizard-stepper__num {

  display: inline-flex;

  align-items: center;

  justify-content: center;

  width: 20px;

  height: 20px;

  border-radius: 50%;

  font-size: 11px;

  font-weight: 700;

  background: var(--color-surface-muted);

  border: 1px solid var(--color-border);

}



.wizard-stepper__item.current .wizard-stepper__num {

  background: var(--color-primary);

  border-color: transparent;

  color: #fff;

}

</style>

