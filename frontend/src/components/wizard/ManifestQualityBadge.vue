<script setup lang="ts">
import type { ToolManifest } from "@/api/mcp";
import { computeQualityScore, qualityTier, qualityTierLabel } from "@/utils/mcpQualityRules";

const props = defineProps<{
  tool: ToolManifest;
}>();

const score = computeQualityScore(props.tool);
const tier = qualityTier(score);
</script>

<template>
  <span class="badge" :class="`badge--${tier === 'ok' ? 'ok' : tier === 'warn' ? 'warn' : 'err'}`">
    {{ score }} · {{ qualityTierLabel(tier) }}
  </span>
</template>
