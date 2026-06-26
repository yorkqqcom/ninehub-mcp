<script setup lang="ts">

import { computed } from "vue";

import type { DashboardConnection } from "@/api/dashboard";



const props = defineProps<{

  readiness: DashboardConnection | null;

  llmBuildEnabled?: boolean;

  llmApiKeySet?: boolean;

}>();



const showNoPack = computed(() => props.readiness && !props.readiness.has_context_pack);

const showPackLost = computed(

  () => props.readiness && props.readiness.has_config && !props.readiness.has_context_pack,

);

const showVerifyWarn = computed(

  () => props.readiness && props.readiness.last_verify_ok !== true,

);

const showLlmWarn = computed(

  () =>

    props.llmBuildEnabled &&

    !props.llmApiKeySet &&

    props.readiness?.has_context_pack,

);

</script>



<template>

  <div v-if="showPackLost" class="wizard-banner wizard-banner--warn" role="alert">

    已有 MCP 工具配置，但 Context Pack 已丢失，请重新 Scan 后再构建。

    <router-link

      v-if="readiness"

      class="wizard-banner__link"

      :to="`/connections/${readiness.id}/scan`"

    >

      前往扫描

    </router-link>

  </div>

  <div v-else-if="showNoPack" class="wizard-banner wizard-banner--err" role="alert">

    尚未生成 Context Pack，请先完成 Scan。

    <router-link

      v-if="readiness"

      class="wizard-banner__link"

      :to="`/connections/${readiness.id}/scan`"

    >

      前往扫描

    </router-link>

  </div>

  <div v-else-if="showVerifyWarn" class="wizard-banner wizard-banner--warn" role="status">

    连接尚未验证或上次验证失败，建议先 Verify。

  </div>

  <div v-if="showLlmWarn" class="wizard-banner wizard-banner--warn" role="status">

    LLM 构建已启用但未配置 API Key。

    <router-link class="wizard-banner__link" to="/settings">前往设置</router-link>

  </div>

</template>



<style scoped>

.wizard-banner {

  padding: var(--space-sm) var(--space-md);

  border-radius: var(--radius-sm);

  font-size: var(--font-size-md);

  border: 1px solid var(--color-border);

}



.wizard-banner--err {

  background: var(--color-err-bg, rgba(220, 53, 69, 0.12));

  color: var(--color-err-text, var(--color-text));

}



.wizard-banner--warn {

  background: var(--color-warn-bg, rgba(255, 193, 7, 0.12));

  color: var(--color-text-secondary);

}



.wizard-banner__link {

  margin-left: var(--space-sm);

  color: var(--color-primary);

  font-weight: 600;

}

</style>
