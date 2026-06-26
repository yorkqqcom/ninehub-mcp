<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getDashboardSummary, type DashboardSummary } from "@/api/dashboard";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import SkeletonLoader from "@/components/SkeletonLoader.vue";
import { useUiStore } from "@/stores/ui";

type RouteTarget = string | { path: string; query?: Record<string, string> };

type WorkflowStep = {
  id: string;
  label: string;
  done: boolean;
  to: RouteTarget;
  hint: string;
};

const ui = useUiStore();
const router = useRouter();
const loading = ref(true);
const refreshing = ref(false);
const summary = ref<DashboardSummary | null>(null);
const lastRefreshAt = ref<string>("");

let pollTimer: ReturnType<typeof setInterval> | null = null;

const primaryId = computed(() => summary.value?.primary_connection_id ?? null);

const verifiedCount = computed(
  () => summary.value?.connections_list.filter((c) => c.last_verify_ok === true).length ?? 0,
);

const workflowSteps = computed<WorkflowStep[]>(() => {
  if (!summary.value) return [];
  const s = summary.value;
  const cid = primaryId.value;
  const anyVerified = s.connections_list.some((c) => c.last_verify_ok === true);
  return [
    {
      id: "conn",
      label: "配置连接",
      done: s.connections > 0,
      to: "/connections",
      hint: "添加 PostgreSQL 数据源",
    },
    {
      id: "verify",
      label: "验证连接",
      done: anyVerified,
      to: "/connections",
      hint: "测试数据库连通性",
    },
    {
      id: "scan",
      label: "扫描结构",
      done: !!s.last_scan_at,
      to: cid ? `/connections/${cid}/scan` : "/connections",
      hint: "生成 Context Pack",
    },
    {
      id: "build",
      label: "生成 MCP",
      done: s.tools_count > 0,
      to: cid ? { path: "/mcp/build", query: { connection_id: cid } } : "/mcp/build",
      hint: "LLM 构建 tool manifest",
    },
    {
      id: "serve",
      label: "启动 Serve",
      done: s.serve.status === "running",
      to: "/mcp/serve",
      hint: "对外提供 MCP 接口",
    },
  ];
});

const workflowProgress = computed(() => {
  const steps = workflowSteps.value;
  if (!steps.length) return 0;
  return Math.round((steps.filter((x) => x.done).length / steps.length) * 100);
});

const nextStep = computed(() => workflowSteps.value.find((s) => !s.done) ?? null);

const workflowComplete = computed(
  () => !!summary.value?.connections && workflowProgress.value === 100,
);

const llmReady = computed(() => {
  if (!summary.value) return true;
  const p = summary.value.platform;
  return !p.llm_build_enabled || p.llm_api_key_set;
});

const showVerifyWarn = computed(
  () => !!summary.value?.connections && verifiedCount.value === 0,
);

const showLlmWarn = computed(
  () => !!summary.value?.last_scan_at && !summary.value.tools_count && !llmReady.value,
);

const serveFailed = computed(() => summary.value?.serve.status === "failed");
const serveError = computed(() => summary.value?.serve.error);

const lastRefreshLabel = computed(() => lastRefreshAt.value || "—");

const serveRunning = computed(() => summary.value?.serve.status === "running");
const serveEndpoint = computed(() => {
  if (!summary.value) return "—";
  const { host, port } = summary.value.serve;
  return `${host}:${port}`;
});

onMounted(() => {
  void refreshAll();
  pollTimer = setInterval(() => {
    if (document.hidden) return;
    void refreshAll(true);
  }, 30_000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});

async function refreshAll(silent = false) {
  await load(silent);
}

async function load(silent = false) {
  if (!silent) loading.value = true;
  else refreshing.value = true;
  try {
    summary.value = await getDashboardSummary();
    lastRefreshAt.value = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "加载失败";
    if (!silent) ui.showMessage(msg, "error");
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

function serveLabel(status: string): string {
  if (status === "running") return "运行中";
  if (status === "stopped") return "已停止";
  if (status === "failed") return "异常";
  return "未知";
}

function serveBadgeClass(status: string): string {
  if (status === "running") return "badge--ok";
  if (status === "failed") return "badge--err";
  return "badge--muted";
}

function formatUptime(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function go(to: RouteTarget) {
  router.push(to);
}

function scanRoute(): RouteTarget {
  const cid = primaryId.value;
  return cid ? `/connections/${cid}/scan` : "/connections";
}

function toolsRoute(): RouteTarget {
  const cid = primaryId.value;
  return cid ? { path: "/mcp/tools", query: { connection_id: cid } } : "/mcp/tools";
}

function connToolsRoute(id: string) {
  return { path: "/mcp/tools", query: { connection_id: id } };
}

function testRoute(): RouteTarget {
  const cid = primaryId.value;
  return cid ? { path: "/mcp/test", query: { connection_id: cid } } : "/mcp/test";
}

function primaryName(): string {
  if (!summary.value || !primaryId.value) return "";
  return summary.value.connections_list.find((c) => c.id === primaryId.value)?.name ?? "";
}

function verifyBadge(ok: boolean | null): string {
  if (ok === true) return "badge--ok";
  if (ok === false) return "badge--err";
  return "badge--muted";
}

function verifyLabel(ok: boolean | null): string {
  if (ok === true) return "已验证";
  if (ok === false) return "失败";
  return "未验证";
}
</script>

<template>
  <PageHeader title="概览" description="平台状态与推荐流程">
    <template #actions>
      <span class="dash-refresh-meta">更新于 {{ lastRefreshLabel }}</span>
      <button type="button" class="btn btn--secondary" :disabled="refreshing" @click="refreshAll(true)">
        {{ refreshing ? "刷新中…" : "刷新" }}
      </button>
    </template>
  </PageHeader>

  <div v-if="loading" class="stat-strip">
    <SkeletonLoader :rows="4" variant="stat" />
  </div>

  <template v-else-if="summary">
    <!-- 迭代1：可点击 KPI + Serve 详情 -->
    <div class="stat-strip">
      <button type="button" class="stat-card stat-card--link" @click="go('/connections')">
        <div class="stat-card__label">数据源连接</div>
        <div class="stat-card__value numeric">{{ summary.connections }}</div>
        <div class="stat-card__foot">
          {{ verifiedCount }} 已验证 · 管理连接
        </div>
      </button>
      <button type="button" class="stat-card stat-card--link" @click="go(toolsRoute())">
        <div class="stat-card__label">暴露 Tools</div>
        <div class="stat-card__value numeric">{{ summary.tools_count }}</div>
        <div class="stat-card__foot">接口清单</div>
      </button>
      <button type="button" class="stat-card stat-card--link" @click="go(scanRoute())">
        <div class="stat-card__label">Context Pack</div>
        <div class="stat-card__value">{{ summary.last_scan_at || "未扫描" }}</div>
        <div class="stat-card__foot">最近 scan 版本</div>
      </button>
      <button type="button" class="stat-card stat-card--link" @click="go('/mcp/serve')">
        <div class="stat-card__label">MCP Serve</div>
        <div class="stat-card__value stat-card__value--row">
          <span class="badge" :class="serveBadgeClass(summary.serve.status)">
            {{ serveLabel(summary.serve.status) }}
          </span>
        </div>
        <div class="stat-card__foot">{{ serveEndpoint }}</div>
      </button>
    </div>

    <div v-if="showVerifyWarn" class="dash-alert dash-alert--warn">
      <span>已有 {{ summary.connections }} 个连接尚未通过验证，建议先测试连接再扫描。</span>
      <button type="button" class="btn btn--sm btn--secondary" @click="go('/connections')">去验证</button>
    </div>

    <div v-if="showLlmWarn" class="dash-alert dash-alert--warn">
      <span>LLM API Key 未配置，MCP 生成将使用规则降级。</span>
      <button type="button" class="btn btn--sm btn--secondary" @click="go('/settings')">去设置</button>
    </div>

    <div v-if="serveFailed && serveError" class="dash-alert dash-alert--err">
      <span>Serve 异常：{{ serveError }}</span>
      <button type="button" class="btn btn--sm btn--secondary" @click="go('/mcp/serve')">查看管控</button>
    </div>

    <div v-else-if="nextStep?.id === 'serve' && !workflowComplete" class="dash-alert dash-alert--info">
      <span>
        主连接「{{ primaryName() }}」已就绪，前往服务管控启动 MCP Serve（{{ serveEndpoint }}）。
      </span>
      <button type="button" class="btn btn--sm btn--primary" @click="go('/mcp/serve')">去启动</button>
    </div>

    <div v-if="workflowComplete" class="dash-complete">
      <div class="dash-complete__body">
        <span class="badge badge--ok">闭环就绪</span>
        <span class="dash-complete__text">连接、扫描、MCP 与 Serve 均已就绪，可对外提供接口。</span>
      </div>
      <div class="dash-complete__actions">
        <button type="button" class="btn btn--primary btn--sm" @click="go(testRoute())">接口测试</button>
        <button type="button" class="btn btn--secondary btn--sm" @click="go('/mcp/logs')">监控日志</button>
      </div>
    </div>

    <!-- 迭代2：闭环流程条 -->
    <div class="panel dash-workflow">
      <div class="panel__header dash-workflow__header">
        <div>
          <h2 class="panel__title">推荐流程</h2>
          <p class="dash-workflow__sub">完成度 {{ workflowProgress }}%</p>
        </div>
        <button v-if="nextStep" type="button" class="btn btn--primary btn--sm" @click="go(nextStep.to)">
          下一步：{{ nextStep.label }}
        </button>
        <span v-else-if="workflowComplete" class="badge badge--ok">全部完成</span>
      </div>
      <div class="panel__body">
        <div class="progress-bar" role="progressbar" :aria-valuenow="workflowProgress" aria-valuemin="0" aria-valuemax="100">
          <div class="progress-bar__fill" :style="{ width: `${workflowProgress}%` }" />
        </div>
        <div class="dash-pipeline">
          <button
            v-for="(step, idx) in workflowSteps"
            :key="step.id"
            type="button"
            class="dash-pipeline__step"
            :class="{ 'dash-pipeline__step--done': step.done, 'dash-pipeline__step--next': nextStep?.id === step.id }"
            @click="go(step.to)"
          >
            <span class="dash-pipeline__idx">{{ idx + 1 }}</span>
            <span class="dash-pipeline__label">{{ step.label }}</span>
            <span class="dash-pipeline__hint">{{ step.hint }}</span>
            <span class="dash-pipeline__state">{{ step.done ? "已完成" : "待完成" }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 迭代2+3：Serve 状态面板 -->
    <div class="panel dash-serve" :class="{ 'dash-serve--running': serveRunning, 'dash-serve--failed': serveFailed }">
      <div class="panel__body dash-serve__body">
        <div class="dash-serve__info">
          <span
            class="dash-serve__dot"
            :class="{
              'dash-serve__dot--ok': serveRunning,
              'dash-serve__dot--err': serveFailed,
              'dash-serve__dot--idle': !serveRunning && !serveFailed,
            }"
          />
          <div>
            <div class="dash-serve__title">
              MCP Serve
              <span class="badge" :class="serveBadgeClass(summary.serve.status)">
                {{ serveLabel(summary.serve.status) }}
              </span>
            </div>
            <div class="dash-serve__meta">
              <span>端点 {{ serveEndpoint }}</span>
              <span v-if="summary.serve.profile">profile {{ summary.serve.profile }}</span>
              <span v-if="serveRunning && summary.serve.pid">PID {{ summary.serve.pid }}</span>
              <span v-if="serveRunning">运行 {{ formatUptime(summary.serve.uptime) }}</span>
            </div>
            <p v-if="serveError && !serveRunning" class="dash-serve__error">{{ serveError }}</p>
          </div>
        </div>
        <div class="dash-serve__actions">
          <button type="button" class="btn btn--secondary btn--sm" @click="go('/mcp/serve')">
            {{ serveRunning ? "管控" : "去启动" }}
          </button>
          <button type="button" class="btn btn--ghost btn--sm" @click="go('/mcp/logs')">查看日志</button>
        </div>
      </div>
    </div>

    <!-- 连接概览 -->
    <div v-if="summary.connections_list.length" class="dash-bottom page-split page-split--chart">
      <div class="panel dash-conns">
        <div class="panel__header">
          <h2 class="panel__title">数据源概览</h2>
          <button type="button" class="btn btn--sm btn--ghost" @click="go('/connections')">全部管理</button>
        </div>
        <div class="panel__body table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>主机</th>
                <th>验证</th>
                <th>Profile</th>
                <th>Context Pack</th>
                <th>Tools</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in summary.connections_list"
                :key="row.id"
                :class="{ 'dash-conns__row--primary': row.id === primaryId }"
              >
                <td>
                  {{ row.name }}
                  <span v-if="row.id === primaryId" class="badge badge--sm badge--catalog">主连接</span>
                </td>
                <td class="numeric">{{ row.database_host }}</td>
                <td>
                  <span class="badge badge--sm" :class="verifyBadge(row.last_verify_ok)">
                    {{ verifyLabel(row.last_verify_ok) }}
                  </span>
                  <span v-if="row.last_verified_at && row.last_verify_ok" class="dash-conns__verified-at">
                    {{ row.last_verified_at.slice(0, 10) }}
                  </span>
                </td>
                <td><span class="badge badge--catalog">{{ row.profile }}</span></td>
                <td>{{ row.context_pack_version || "—" }}</td>
                <td class="numeric">{{ row.tools_count }}</td>
                <td class="dash-conns__actions">
                  <button type="button" class="btn btn--sm btn--ghost" @click="go('/connections')">
                    配置
                  </button>
                  <button type="button" class="btn btn--sm btn--ghost" @click="go(`/connections/${row.id}/scan`)">
                    扫描
                  </button>
                  <button
                    v-if="row.has_config"
                    type="button"
                    class="btn btn--sm btn--ghost"
                    @click="go(connToolsRoute(row.id))"
                  >
                    工具
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="dash-bottom__side">
        <div class="panel dash-platform">
          <div class="panel__header">
            <h2 class="panel__title">平台配置</h2>
            <button type="button" class="btn btn--sm btn--ghost" @click="go('/settings')">设置</button>
          </div>
          <div class="panel__body dash-platform__body">
            <div class="kv-list">
              <div class="kv-list__row">
                <span class="kv-list__key">LLM 模型</span>
                <span class="kv-list__val">{{ summary.platform.llm_model }}</span>
              </div>
              <div class="kv-list__row">
                <span class="kv-list__key">LLM 构建</span>
                <span class="kv-list__val">
                  <span class="badge" :class="summary.platform.llm_build_enabled ? 'badge--ok' : 'badge--muted'">
                    {{ summary.platform.llm_build_enabled ? "已启用" : "已关闭" }}
                  </span>
                </span>
              </div>
              <div class="kv-list__row">
                <span class="kv-list__key">API Key</span>
                <span class="kv-list__val">
                  <span class="badge" :class="summary.platform.llm_api_key_set ? 'badge--ok' : 'badge--warn'">
                    {{ summary.platform.llm_api_key_set ? "已配置" : "未配置" }}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="summary.connections === 0" class="panel">
      <EmptyState title="尚无数据源连接" description="添加 PostgreSQL 连接后开始 scan 与 MCP 生成。">
        <button type="button" class="btn btn--primary" @click="go('/connections')">新建连接</button>
      </EmptyState>
    </div>
  </template>
</template>

<style scoped>
.stat-card--link {
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.stat-card--link:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-elevated);
}

.stat-card__foot {
  margin-top: var(--space-xs);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.stat-card__value--row {
  display: flex;
  align-items: center;
  min-height: 24px;
}

.dash-workflow {
  margin-top: var(--space-lg);
}

.dash-workflow .progress-bar {
  margin-bottom: var(--space-md);
}

.dash-conns {
  margin-top: 0;
}

.dash-bottom {
  margin-top: var(--space-lg);
  align-items: start;
}

.dash-bottom__side {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.dash-refresh-meta {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.dash-alert {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  margin-top: var(--space-lg);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-panel);
  font-size: var(--font-size-md);
}

.dash-alert--info {
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
}

.dash-alert--warn {
  border: 1px solid var(--color-warning);
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
}

.dash-alert--err {
  border: 1px solid var(--color-danger);
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
}

.dash-conns__row--primary {
  background: var(--color-primary-muted);
}

.dash-serve--failed {
  border-color: var(--color-danger);
}

.dash-serve__dot--err {
  background: var(--color-danger);
}

.dash-serve__error {
  margin: var(--space-xs) 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-danger);
}

.dash-platform__body {
  padding-top: 0;
}

.kv-list__row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-xs) 0;
  font-size: var(--font-size-sm);
}

.kv-list__key {
  color: var(--color-text-muted);
}

.kv-list__val {
  color: var(--color-text-secondary);
}

.dash-complete {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  margin-top: var(--space-lg);
  padding: var(--space-md) var(--space-lg);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-panel);
  background: var(--color-primary-muted);
}

.dash-complete__body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
}

.dash-complete__text {
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}

.dash-complete__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

.badge--sm {
  white-space: nowrap;
  font-size: var(--font-size-sm);
  padding: 1px 6px;
}

.dash-conns__actions {
  white-space: nowrap;
}

.dash-conns__actions .btn {
  margin-right: 4px;
}

.dash-conns__verified-at {
  display: block;
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  font-family: var(--font-mono, monospace);
}

.dash-workflow__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.dash-workflow__sub {
  margin: 2px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.dash-pipeline {
  display: grid;
  gap: var(--space-sm);
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.dash-pipeline__step {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-md);
  text-align: left;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  background: var(--color-surface-muted);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.dash-pipeline__step:hover {
  border-color: var(--color-border-strong);
  background: var(--color-row-hover);
}

.dash-pipeline__step--done {
  border-color: var(--color-primary);
  background: var(--color-primary-muted);
}

.dash-pipeline__step--next {
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.dash-pipeline__idx {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-primary);
}

.dash-pipeline__label {
  font-weight: 600;
  color: var(--color-text);
}

.dash-pipeline__hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  line-height: 1.35;
}

.dash-pipeline__state {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.dash-serve {
  margin-top: var(--space-lg);
}

.dash-serve--running {
  border-color: var(--color-primary);
}

.dash-serve__body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.dash-serve__info {
  display: flex;
  gap: var(--space-md);
  align-items: flex-start;
}

.dash-serve__dot {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dash-serve__dot--ok {
  background: var(--color-success, var(--color-primary));
  box-shadow: 0 0 0 3px var(--color-primary-muted);
}

.dash-serve__dot--idle {
  background: var(--color-text-muted);
}

.dash-serve__title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
  font-weight: 600;
  color: var(--color-text);
}

.dash-serve__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
  margin-top: 4px;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  font-family: var(--font-mono, monospace);
}

.dash-serve__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

@media (min-width: 1100px) {
  .dash-bottom.page-split--chart {
    grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
  }
}

@media (max-width: 900px) {
  .dash-pipeline {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .dash-pipeline {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .dash-pipeline {
    grid-template-columns: 1fr;
  }
}
</style>
