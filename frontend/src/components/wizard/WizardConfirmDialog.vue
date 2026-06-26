<script setup lang="ts">
defineProps<{
  open: boolean;
  title?: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();
</script>

<template>
  <div v-if="open" class="wizard-dialog-backdrop" role="presentation" @click.self="emit('cancel')">
    <div class="wizard-dialog" role="dialog" aria-modal="true" :aria-labelledby="'wizard-dialog-title'">
      <h3 id="wizard-dialog-title" class="wizard-dialog__title">{{ title ?? "确认操作" }}</h3>
      <p class="wizard-dialog__message">
        <slot>{{ message }}</slot>
      </p>
      <div class="wizard-dialog__actions page-actions">
        <button type="button" class="btn btn--ghost" @click="emit('cancel')">
          {{ cancelLabel ?? "取消" }}
        </button>
        <button type="button" class="btn btn--primary" @click="emit('confirm')">
          {{ confirmLabel ?? "确认" }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  padding: var(--space-md);
}

.wizard-dialog {
  width: min(480px, 100%);
  padding: var(--space-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  box-shadow: var(--shadow-panel, 0 8px 32px rgba(0, 0, 0, 0.2));
}

.wizard-dialog__title {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-lg);
}

.wizard-dialog__message {
  margin: 0 0 var(--space-lg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  line-height: 1.5;
}

.wizard-dialog__actions {
  margin: 0;
  padding: 0;
  border: none;
  justify-content: flex-end;
}
</style>
