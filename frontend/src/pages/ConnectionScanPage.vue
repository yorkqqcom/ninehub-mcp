<script setup lang="ts">
import { computed, onActivated, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getConnection, getContextPack, getScanJob, resampleTable, startScan, verifyConnection } from "@/api/connections";
import type { ConnectionDetail, ContextPack, ScanJob } from "@/api/types";
import ConnectionSubpageLayout from "@/components/ConnectionSubpageLayout.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import SkeletonLoader from "@/components/SkeletonLoader.vue";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();

const connectionId = route.params.id as string;
const detail = ref<ConnectionDetail | null>(null);
const pack = ref<ContextPack | null>(null);
const job = ref<ScanJob | null>(null);
const loading = ref(true);
const scanning = ref(false);
const verifying = ref(false);
const expandedTable = ref<string | null>(null);
const resamplingKey = ref<string | null>(null);
let pollTimer: number | null = null;

const hintDismissKey = `ninehub_mcp.verify_hint_dismiss.${connectionId}`;
const hintDismissed = ref(sessionStorage.getItem(hintDismissKey) === "1");

const showVerifyBanner = computed(() => {
  if (!detail.value) return false;
  if (detail.value.last_verify_ok === true) return false;
  if (detail.value.last_verify_ok === false) return true;
  return !hintDismissed.value;
});

const isActiveJob = computed(
  () => job.value !== null && (job.value.status === "pending" || job.value.status === "running"),
);

const breadcrumbs = computed(() => [
  { label: "数据源", to: "/connections" },
  { label: detail.value?.name || "…" },
  { label: "扫描" },
]);

const hasPatterns = computed(() => {
  if (!detail.value) return false;
  return (
    detail.value.include_table_patterns.length + detail.value.exclude_table_patterns.length > 0
  );
});

onMounted(() => void bootstrap());

onActivated(() => {
  void refreshDetail();
});

onUnmounted(() => stopPoll());

async function refreshDetail() {
  detail.value = await getConnection(connectionId);
}

async function bootstrap() {
  loading.value = true;
  try {
    await refreshDetail();
    try {
      pack.value = await getContextPack(connectionId);
    } catch {
      pack.value = null;
    }
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
    router.push("/connections");
  } finally {
    loading.value = false;
  }
}

async function testConnection() {
  verifying.value = true;
  try {
    const res = await verifyConnection(connectionId);
    await refreshDetail();
    if (res.ok) {
      hintDismissed.value = false;
      sessionStorage.removeItem(hintDismissKey);
      ui.showMessage("连接验证成功，可以开始扫描", "success");
    } else {
      ui.showMessage(res.error || "连接验证失败", "error");
    }
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  } finally {
    verifying.value = false;
  }
}

function dismissVerifyHint() {
  hintDismissed.value = true;
  sessionStorage.setItem(hintDismissKey, "1");
}

function errorMessage(e: unknown): string {
  return e && typeof e === "object" && "message" in e
    ? String((e as { message: string }).message)
    : "操作失败";
}

function tableKey(t: { schema: string; name: string }) {
  return `${t.schema}.${t.name}`;
}

async function runScan() {
  scanning.value = true;
  try {
    const res = await startScan(connectionId);
    job.value = await getScanJob(res.job_id);
    startPoll(res.job_id);
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
    scanning.value = false;
  }
}

function startPoll(jobId: string) {
  stopPoll();
  pollTimer = window.setInterval(() => void pollJob(jobId), 800);
  void pollJob(jobId);
}

function stopPoll() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollJob(jobId: string) {
  try {
    job.value = await getScanJob(jobId);
    if (job.value.status === "completed") {
      stopPoll();
      scanning.value = false;
      pack.value = await getContextPack(connectionId);
      if (detail.value) {
        detail.value = { ...detail.value, has_context_pack: true };
      }
      ui.showMessage("扫描完成", "success");
    } else if (job.value.status === "failed") {
      stopPoll();
      scanning.value = false;
      ui.showMessage(job.value.error || "扫描失败", "error");
    }
  } catch (e) {
    stopPoll();
    scanning.value = false;
    ui.showMessage(errorMessage(e), "error");
  }
}

function toggleExpand(key: string) {
  expandedTable.value = expandedTable.value === key ? null : key;
}

async function resampleOne(t: { schema: string; name: string }) {
  const key = tableKey(t);
  resamplingKey.value = key;
  try {
    const updated = await resampleTable(connectionId, t.schema, t.name);
    if (pack.value) {
      pack.value = {
        ...pack.value,
        tables: pack.value.tables.map((row) =>
          row.schema === t.schema && row.name === t.name
            ? { ...row, sample_rows_build: updated.sample_rows_build, sample_rows_resource: updated.sample_rows_resource }
            : row,
        ),
      };
    }
    ui.showMessage(`已重采样 ${key}（10+3 条）`, "success");
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  } finally {
    resamplingKey.value = null;
  }
}
</script>

<template>
  <PageHeader
    :title="detail ? `扫描 · ${detail.name}` : '扫描'"
    description="Inspect → Sample → Manifest，生成 Context Pack"
  >
    <template #actions>
      <button type="button" class="btn btn--secondary" @click="router.push('/connections')">
        返回
      </button>
      <button
        type="button"
        class="btn btn--secondary"
        :disabled="verifying"
        @click="testConnection"
      >
        {{ verifying ? "测试中…" : "测试连接" }}
      </button>
      <button
        type="button"
        class="btn btn--primary"
        :disabled="scanning || isActiveJob"
        @click="runScan"
      >
        {{ scanning || isActiveJob ? "扫描中…" : "开始扫描" }}
      </button>
    </template>
  </PageHeader>

  <div v-if="loading" class="panel">
    <SkeletonLoader :rows="4" />
  </div>

  <template v-else-if="detail">
    <ConnectionSubpageLayout
      :connection-id="connectionId"
      :breadcrumbs="breadcrumbs"
      :verified="detail.last_verify_ok === true"
      :has-patterns="hasPatterns"
      :has-context-pack="!!pack"
      :has-config="detail.has_config"
    >
      <div
        v-if="showVerifyBanner"
        class="page-banner"
        :class="detail.last_verify_ok === false ? 'page-banner--warn' : 'page-banner--info'"
        role="status"
      >
        <span v-if="detail.last_verify_ok === false">
          连接验证失败：{{ detail.last_verify_error || "请检查数据源配置" }}
        </span>
        <span v-else>尚未验证连接，建议扫描前先测试数据库连通性。</span>
        <button type="button" class="btn btn--sm btn--secondary" :disabled="verifying" @click="testConnection">
          {{ verifying ? "测试中…" : "测试连接" }}
        </button>
        <button
          v-if="detail.last_verify_ok == null"
          type="button"
          class="btn btn--sm btn--ghost"
          @click="dismissVerifyHint"
        >
          知道了
        </button>
      </div>

      <div v-if="job && (isActiveJob || job.status === 'failed')" class="panel">
        <div class="panel__header">
          <h2 class="panel__title">扫描进度</h2>
          <span class="badge" :class="job.status === 'failed' ? 'badge--err' : 'badge--warn'">
            {{ job.status }}
          </span>
        </div>
        <div class="panel__body">
          <div
            class="progress-bar"
            role="progressbar"
            :aria-valuenow="job.progress"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div class="progress-bar__fill" :style="{ width: `${job.progress}%` }" />
          </div>
          <p class="scan-phase">
            {{ job.phase_label || job.phase }}
            <span class="numeric">{{ job.progress }}%</span>
          </p>
          <p v-if="job.status === 'failed'" class="form-field__error" role="alert">{{ job.error }}</p>
        </div>
      </div>

      <div v-if="pack?.exposure_warning" class="page-banner page-banner--warn" role="status">
        {{ pack.exposure_warning }}
      </div>

      <div v-if="pack" class="panel">
        <div class="panel__header">
          <h2 class="panel__title">Context Pack</h2>
          <span class="badge badge--muted">v {{ pack.version }}</span>
        </div>
        <div class="panel__body">
          <div class="stat-strip stat-strip--compact">
            <div class="stat-card">
              <div class="stat-card__label">总表数</div>
              <div class="stat-card__value numeric">{{ pack.tables.length }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__label">暴露</div>
              <div class="stat-card__value numeric">{{ pack.exposed_count }}</div>
            </div>
          </div>

          <div class="table-scroll panel-section-spaced">
            <table class="data-table">
              <thead>
                <tr>
                  <th>表</th>
                  <th>暴露</th>
                  <th>列数</th>
                  <th>样例</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="t in pack.tables" :key="tableKey(t)">
                  <tr>
                    <td><code class="table-name">{{ t.schema }}.{{ t.name }}</code></td>
                    <td>
                      <span class="badge" :class="t.exposed ? 'badge--exposed' : 'badge--hidden'">
                        {{ t.exposed ? "是" : "否" }}
                      </span>
                    </td>
                    <td class="numeric">{{ t.columns.length }}</td>
                    <td>
                      <button
                        type="button"
                        class="btn btn--sm btn--ghost"
                        @click="toggleExpand(tableKey(t))"
                      >
                        {{ expandedTable === tableKey(t) ? "收起" : "预览" }}
                      </button>
                    </td>
                    <td>
                      <button
                        v-if="t.exposed"
                        type="button"
                        class="btn btn--sm btn--ghost"
                        :disabled="resamplingKey === tableKey(t)"
                        @click="resampleOne(t)"
                      >
                        {{ resamplingKey === tableKey(t) ? "采样中…" : "重采样" }}
                      </button>
                    </td>
                  </tr>
                  <tr v-if="expandedTable === tableKey(t)">
                    <td colspan="5">
                      <pre class="sample-preview">{{ JSON.stringify(t.sample_rows_build.slice(0, 3), null, 2) }}</pre>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>

          <div class="page-actions">
            <button type="button" class="btn btn--primary" @click="router.push('/mcp/build')">
              下一步：MCP 生成
            </button>
            <button
              type="button"
              class="btn btn--ghost"
              @click="router.push(`/connections/${connectionId}/filters`)"
            >
              调整通配符
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="!isActiveJob && !scanning" class="panel">
        <EmptyState
          title="尚未扫描"
          description="点击顶栏「开始扫描」采集表结构、样例数据并生成 Context Pack。"
        >
          <button type="button" class="btn btn--primary" @click="runScan">开始扫描</button>
        </EmptyState>
      </div>
    </ConnectionSubpageLayout>
  </template>
</template>

<style scoped>
.scan-phase {
  margin-top: var(--space-md);
  font-size: var(--font-size-md);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  color: var(--color-text-secondary);
}

.table-name {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.sample-preview {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  background: var(--color-surface-muted);
  padding: var(--space-md);
  border-radius: var(--radius-input);
  overflow-x: auto;
  max-height: 200px;
}

.page-banner--warn,
.page-banner--info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
}
</style>
