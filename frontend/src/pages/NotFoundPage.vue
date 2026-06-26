<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

const links = [
  { label: "概览", to: "/" },
  { label: "数据源", to: "/connections" },
  { label: "MCP 生成", to: "/mcp/build" },
];
</script>

<template>
  <div class="not-found">
    <p class="not-found__code" aria-hidden="true">404</p>
    <h1 class="not-found__title">页面不存在</h1>
    <p class="not-found__desc">链接可能已失效，或地址输入有误。</p>
    <div class="page-actions not-found__actions">
      <button type="button" class="btn btn--primary" @click="router.push('/')">返回概览</button>
      <button
        v-for="link in links"
        :key="link.to"
        type="button"
        class="btn btn--ghost"
        @click="router.push(link.to)"
      >
        {{ link.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  text-align: center;
  padding: var(--space-xl);
}

.not-found__code {
  margin: 0;
  font-size: 64px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-primary);
  opacity: 0.35;
  font-family: var(--font-mono, monospace);
}

.not-found__title {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--color-text);
}

.not-found__desc {
  margin: 0;
  color: var(--color-text-muted);
  max-width: 360px;
}

.not-found__actions {
  justify-content: center;
  margin-top: var(--space-sm);
}
</style>
