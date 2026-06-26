<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  connectionId?: string | null;
  verified: boolean;
  hasPatterns: boolean;
  hasContextPack: boolean;
  hasConfig: boolean;
}>();

type StepState = "done" | "current" | "todo";

const steps = computed(() => {
  const id = props.connectionId;
  const configured = !!id;
  const patternsDone = props.hasPatterns;
  const scanDone = props.hasContextPack;
  const mcpDone = props.hasConfig;

  function state(index: number): StepState {
    const doneFlags = [configured, patternsDone, scanDone, mcpDone];
    if (doneFlags[index]) return "done";
    const firstTodo = doneFlags.findIndex((d) => !d);
    if (firstTodo === index) return "current";
    return "todo";
  }

  return [
    {
      key: "config",
      label: "配置",
      state: state(0),
      to: id ? undefined : undefined,
    },
    {
      key: "filters",
      label: "通配符",
      state: state(1),
      to: id ? `/connections/${id}/filters` : undefined,
    },
    {
      key: "scan",
      label: "扫描",
      state: state(2),
      to: id ? `/connections/${id}/scan` : undefined,
    },
    {
      key: "mcp",
      label: "MCP",
      state: state(3),
      to: "/build",
    },
  ];
});
</script>

<template>
  <nav class="conn-workflow" aria-label="推荐配置流程">
    <template v-for="(step, index) in steps" :key="step.key">
      <span v-if="index > 0" class="conn-workflow__sep" aria-hidden="true">→</span>
      <router-link
        v-if="step.to"
        :to="step.to"
        class="conn-workflow__step"
        :class="`conn-workflow__step--${step.state}`"
      >
        <span class="conn-workflow__index">{{ index + 1 }}</span>
        {{ step.label }}
      </router-link>
      <span
        v-else
        class="conn-workflow__step"
        :class="`conn-workflow__step--${step.state}`"
      >
        <span class="conn-workflow__index">{{ index + 1 }}</span>
        {{ step.label }}
      </span>
    </template>
    <span v-if="verified" class="conn-workflow__verified badge badge--ok">已验证</span>
  </nav>
</template>

<style scoped>
.conn-workflow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  background: var(--color-surface);
  font-size: var(--font-size-sm);
}

.conn-workflow__sep {
  color: var(--color-text-muted);
  user-select: none;
}

.conn-workflow__step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: var(--color-text-muted);
  transition: background var(--transition-fast);
}

.conn-workflow__step--done {
  color: var(--color-text-secondary);
}

.conn-workflow__step--current {
  color: var(--color-primary);
  background: var(--color-primary-muted);
  font-weight: 600;
}

.conn-workflow__step--todo {
  opacity: 0.75;
}

a.conn-workflow__step:hover {
  background: var(--color-row-hover);
}

.conn-workflow__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
}

.conn-workflow__step--done .conn-workflow__index {
  background: var(--color-ok-bg, var(--color-primary-muted));
  border-color: transparent;
  color: var(--color-ok-text, var(--color-primary));
}

.conn-workflow__step--current .conn-workflow__index {
  background: var(--color-primary);
  border-color: transparent;
  color: #fff;
}

.conn-workflow__verified {
  margin-left: auto;
}
</style>
