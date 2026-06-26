<script setup lang="ts">
defineProps<{
  title?: string;
  description?: string;
}>();
</script>

<template>
  <div class="empty-state">
    <p v-if="title" class="empty-state__title">{{ title }}</p>
    <p v-if="description" class="empty-state__desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state__title {
  font-weight: 600;
  margin-bottom: var(--space-xs);
}
.empty-state__desc {
  color: var(--color-text-muted);
  margin-bottom: var(--space-md);
}
.empty-state__actions {
  margin-top: var(--space-sm);
}
</style>
