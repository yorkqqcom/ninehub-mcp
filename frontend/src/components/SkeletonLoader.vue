<script setup lang="ts">
defineProps<{
  rows?: number;
  variant?: "stat" | "row";
}>();
</script>

<template>
  <div>
    <div
      v-for="i in rows ?? 3"
      :key="i"
      class="skeleton"
      :class="variant === 'stat' ? 'skeleton-stat' : 'skeleton-row'"
    />
  </div>
</template>
