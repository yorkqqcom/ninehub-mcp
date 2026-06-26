<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  text: string;
  disabled?: boolean;
}>();

const copied = ref(false);

async function copy() {
  if (!props.text || props.disabled) return;
  try {
    await navigator.clipboard.writeText(props.text);
    copied.value = true;
    window.setTimeout(() => {
      copied.value = false;
    }, 1500);
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <button type="button" class="btn btn--sm btn--ghost" :disabled="disabled || !text" @click="copy">
    {{ copied ? "已复制" : "复制" }}
  </button>
</template>
