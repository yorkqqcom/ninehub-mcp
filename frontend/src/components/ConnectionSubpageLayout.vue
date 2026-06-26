<script setup lang="ts">
import ConnectionWorkflowSteps from "@/components/ConnectionWorkflowSteps.vue";
import PageBreadcrumb from "@/components/PageBreadcrumb.vue";
import type { BreadcrumbItem } from "@/components/PageBreadcrumb.vue";

defineProps<{
  connectionId: string;
  breadcrumbs: BreadcrumbItem[];
  verified?: boolean;
  hasPatterns?: boolean;
  hasContextPack?: boolean;
  hasConfig?: boolean;
}>();
</script>

<template>
  <PageBreadcrumb :items="breadcrumbs" />
  <ConnectionWorkflowSteps
    class="conn-subpage__workflow"
    :connection-id="connectionId"
    :verified="verified ?? false"
    :has-patterns="hasPatterns ?? false"
    :has-context-pack="hasContextPack ?? false"
    :has-config="hasConfig ?? false"
  />
  <slot />
</template>

<style scoped>
.conn-subpage__workflow {
  margin-bottom: var(--space-md);
}
</style>
