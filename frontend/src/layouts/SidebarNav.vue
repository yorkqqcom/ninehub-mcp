<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";
import { NAV_GROUPS } from "@/config/navigation";

const route = useRoute();

function isActive(to: string): boolean {
  if (to === "/") return route.path === "/";
  return route.path === to || route.path.startsWith(`${to}/`);
}
</script>

<template>
  <nav class="app-sidebar" aria-label="主导航">
    <div v-for="group in NAV_GROUPS" :key="group.section" class="app-sidebar__group">
      <div class="app-sidebar__section">{{ group.section }}</div>
      <RouterLink
        v-for="item in group.items"
        :key="item.to"
        :to="item.to"
        class="app-sidebar__link"
        :class="{ active: isActive(item.to) }"
        :title="item.hint"
      >
        <span class="app-sidebar__label">{{ item.label }}</span>
        <span v-if="item.hint" class="app-sidebar__hint">{{ item.hint }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.app-sidebar__link {
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding-top: 8px;
  padding-bottom: 8px;
}

.app-sidebar__hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  font-weight: normal;
  line-height: 1.3;
}

.app-sidebar__link.active .app-sidebar__hint {
  color: var(--color-nav-active-text);
  opacity: 0.85;
}

@media (max-width: 768px) {
  .app-sidebar__hint {
    display: none;
  }

  .app-sidebar__link {
    flex-direction: row;
    align-items: center;
  }
}
</style>
