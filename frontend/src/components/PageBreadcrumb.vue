<script setup lang="ts">
import { RouterLink } from "vue-router";

export type BreadcrumbItem = {
  label: string;
  to?: string;
};

defineProps<{
  items: BreadcrumbItem[];
}>();
</script>

<template>
  <nav class="page-breadcrumb" aria-label="面包屑">
    <template v-for="(item, index) in items" :key="`${item.label}-${index}`">
      <span v-if="index > 0" class="page-breadcrumb__sep" aria-hidden="true">/</span>
      <RouterLink v-if="item.to" :to="item.to" class="page-breadcrumb__link">
        {{ item.label }}
      </RouterLink>
      <span v-else class="page-breadcrumb__current">{{ item.label }}</span>
    </template>
  </nav>
</template>
