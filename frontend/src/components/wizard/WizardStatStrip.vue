<script setup lang="ts">
defineProps<{
  items: { label: string; value: string | number; hint?: string }[];
}>();
</script>

<template>
  <div class="stat-strip wizard-stat-strip">
    <div v-for="item in items" :key="item.label" class="stat-card">
      <div class="stat-card__label">{{ item.label }}</div>
      <div class="stat-card__value">{{ item.value }}</div>
      <div v-if="item.hint" class="stat-card__hint">{{ item.hint }}</div>
    </div>
  </div>
</template>

<style scoped>
.wizard-stat-strip {
  margin-bottom: 0;
}
</style>
