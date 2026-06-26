<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
}>();
</script>

<template>
  <section class="wizard-shell">
    <header v-if="title" class="wizard-shell__header">
      <h2 class="wizard-shell__title">{{ title }}</h2>
      <p v-if="subtitle" class="wizard-shell__desc">{{ subtitle }}</p>
    </header>
    <div class="wizard-shell__body">
      <slot />
    </div>
    <footer v-if="$slots.actions" class="wizard-shell__actions page-actions">
      <slot name="actions" />
    </footer>
  </section>
</template>

<style scoped>
.wizard-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.wizard-shell__header {
  margin: 0;
}

.wizard-shell__title {
  margin: 0 0 var(--space-xs);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.wizard-shell__desc {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.wizard-shell__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.wizard-shell__actions {
  margin-top: var(--space-sm);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border);
}
</style>
