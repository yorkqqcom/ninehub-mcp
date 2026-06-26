<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  createConnection,
  deleteConnection,
  getConnection,
  listConnections,
  updateConnection,
  verifyConnection,
} from "@/api/connections";
import type { ConnectionDetail, ConnectionSummary } from "@/api/types";
import ConnectionFormPanel from "@/components/ConnectionFormPanel.vue";
import ConnectionWorkflowSteps from "@/components/ConnectionWorkflowSteps.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import SkeletonLoader from "@/components/SkeletonLoader.vue";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
const router = useRouter();
const formPanel = ref<InstanceType<typeof ConnectionFormPanel> | null>(null);

const loading = ref(true);
const detailLoading = ref(false);
const saving = ref(false);
const verifying = ref(false);
const items = ref<ConnectionSummary[]>([]);
const search = ref("");
const selectedId = ref<string | null>(null);
const showCreate = ref(false);
const mobilePane = ref<"list" | "detail">("list");
const verifyStatus = ref<Record<string, "ok" | "err" | "pending">>({});
const verifyResult = ref<{ ok: boolean; message: string } | null>(null);
const detail = ref<ConnectionDetail | null>(null);

const formName = ref("");
const formProfile = ref("all");
const formSchemas = ref("public");

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return items.value;
  return items.value.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.database_host.toLowerCase().includes(q) ||
      c.profile.toLowerCase().includes(q),
  );
});

const isEditing = computed(() => editingId.value !== null || showCreate.value);
const editingId = computed(() => (showCreate.value ? null : selectedId.value));

const detailTitle = computed(() => {
  if (showCreate.value) return "新建数据源";
  if (detail.value) return detail.value.name;
  return "连接详情";
});

const verifiedCount = computed(
  () => Object.values(verifyStatus.value).filter((s) => s === "ok").length,
);

onMounted(() => void load());

watch(isEditing, (active) => {
  if (active) mobilePane.value = "detail";
});

async function load() {
  loading.value = true;
  try {
    const data = await listConnections();
    items.value = data.items;
    for (const row of data.items) {
      syncVerifyStatus(row);
    }
    if (items.value.length && !selectedId.value && !showCreate.value) {
      await selectConnection(items.value[0], { quiet: true });
    }
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  } finally {
    loading.value = false;
  }
}

function syncVerifyStatus(row: Pick<ConnectionSummary, "id" | "last_verify_ok">) {
  if (row.last_verify_ok === true) {
    verifyStatus.value[row.id] = "ok";
  } else if (row.last_verify_ok === false) {
    verifyStatus.value[row.id] = "err";
  }
}

async function loadDetail(id: string) {
  detailLoading.value = true;
  try {
    detail.value = await getConnection(id);
    syncVerifyStatus(detail.value);
    formName.value = detail.value.name;
    formProfile.value = detail.value.profile;
    formSchemas.value = detail.value.include_schemas.join(", ") || "public";
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
    detail.value = null;
  } finally {
    detailLoading.value = false;
  }
}

function errorMessage(e: unknown): string {
  return e && typeof e === "object" && "message" in e
    ? String((e as { message: string }).message)
    : "操作失败";
}

function resetForm() {
  formName.value = "";
  formProfile.value = "all";
  formSchemas.value = "public";
  detail.value = null;
  selectedId.value = null;
  showCreate.value = false;
  verifyResult.value = null;
  mobilePane.value = items.value.length ? "list" : "detail";
}

function startCreate() {
  resetForm();
  showCreate.value = true;
  mobilePane.value = "detail";
}

async function selectConnection(row: ConnectionSummary, opts: { quiet?: boolean } = {}) {
  showCreate.value = false;
  selectedId.value = row.id;
  mobilePane.value = "detail";
  verifyResult.value = null;
  await loadDetail(row.id);
  if (!opts.quiet && row.last_verify_ok == null && verifyStatus.value[row.id] === undefined) {
    void verify(row.id, { silentFail: true });
  }
}

async function save() {
  formPanel.value?.touchValidation?.();
  if (!formName.value.trim()) {
    ui.showMessage("请填写连接名称", "error");
    return;
  }

  const mode = showCreate.value ? "create" : "edit";
  const databaseUrl = formPanel.value?.getDatabaseUrlPayload(mode) ?? null;

  if (showCreate.value && !databaseUrl) {
    ui.showMessage("请填写主机、数据库、用户名及密码", "error");
    return;
  }

  saving.value = true;
  try {
    const schemas = formSchemas.value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    if (showCreate.value) {
      const created = await createConnection({
        name: formName.value.trim(),
        database_url: databaseUrl!,
        profile: formProfile.value,
        include_schemas: schemas,
      });
      ui.showMessage("连接已创建", "success");
      showCreate.value = false;
      selectedId.value = created.id;
      await load();
      await loadDetail(created.id);
      await verify(created.id, { silentFail: false });
      return;
    }

    if (!selectedId.value) return;

    const payload: Record<string, unknown> = {
      name: formName.value.trim(),
      profile: formProfile.value,
      include_schemas: schemas,
    };
    if (databaseUrl) {
      payload.database_url = databaseUrl;
    }
    detail.value = await updateConnection(selectedId.value, payload);
    syncVerifyStatus(detail.value);
    ui.showMessage("连接已更新", "success");
    await load();
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  } finally {
    saving.value = false;
  }
}

async function verify(id: string, opts: { silentFail?: boolean } = {}) {
  verifyStatus.value[id] = "pending";
  verifying.value = true;
  try {
    const res = await verifyConnection(id);
    verifyStatus.value[id] = res.ok ? "ok" : "err";
    const msg = res.ok ? "连接验证成功，可继续配置通配符并扫描" : res.error || "连接失败";
    if (selectedId.value === id) {
      verifyResult.value = { ok: res.ok, message: msg };
      if (detail.value?.id === id) {
        detail.value = {
          ...detail.value,
          last_verify_ok: res.ok,
          last_verified_at: res.last_verified_at ?? new Date().toISOString(),
          last_verify_error: res.ok ? null : res.error || "连接失败",
        };
      }
    }
    if (!opts.silentFail || res.ok) {
      ui.showMessage(msg, res.ok ? "success" : "error");
    }
  } catch (e) {
    verifyStatus.value[id] = "err";
    const msg = errorMessage(e);
    if (selectedId.value === id) {
      verifyResult.value = { ok: false, message: msg };
    }
    if (!opts.silentFail) {
      ui.showMessage(msg, "error");
    }
  } finally {
    verifying.value = false;
  }
}

const hasPatterns = computed(() => {
  if (!detail.value) return false;
  const inc = detail.value.include_table_patterns?.length ?? 0;
  const exc = detail.value.exclude_table_patterns?.length ?? 0;
  return inc + exc > 0;
});

const isVerified = computed(() => {
  if (!selectedId.value) return false;
  return verifyStatus.value[selectedId.value] === "ok";
});

async function testSelected() {
  if (!selectedId.value) return;
  await verify(selectedId.value);
}

async function quickVerify(id: string, event: Event) {
  event.stopPropagation();
  await verify(id);
}

function goScan(id: string, event: Event) {
  event.stopPropagation();
  router.push(`/connections/${id}/scan`);
}

async function remove(id: string, name: string) {
  if (!window.confirm(`确定删除连接「${name}」？此操作不可撤销。`)) {
    return;
  }
  try {
    await deleteConnection(id);
    ui.showMessage("连接已删除", "success");
    if (selectedId.value === id) {
      resetForm();
    }
    await load();
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  }
}

function verifyBadge(id: string): string {
  const s = verifyStatus.value[id];
  if (s === "ok") return "badge--ok";
  if (s === "err") return "badge--err";
  if (s === "pending") return "badge--warn";
  return "badge--muted";
}

function verifyLabel(id: string): string {
  const s = verifyStatus.value[id];
  if (s === "ok") return "已验证";
  if (s === "err") return "失败";
  if (s === "pending") return "验证中";
  return "未验证";
}

function statusDotClass(id: string): string {
  const s = verifyStatus.value[id];
  if (s === "ok") return "conn-card__dot--ok";
  if (s === "err") return "conn-card__dot--err";
  if (s === "pending") return "conn-card__dot--pending";
  return "conn-card__dot--idle";
}

function profileBadge(profile: string): string {
  if (profile === "catalog") return "badge--catalog";
  if (profile === "query") return "badge--query";
  return "badge--muted";
}

function patternSummary(row: ConnectionSummary): string {
  const inc = row.include_table_patterns.length;
  const exc = row.exclude_table_patterns.length;
  if (!inc && !exc) return "通配符未配置";
  return `include ${inc} · exclude ${exc}`;
}
</script>

<template>
  <PageHeader title="数据源连接" description="管理 PostgreSQL 连接，配置后扫描并生成 MCP 工具">
    <template #actions>
      <button type="button" class="btn btn--primary" @click="startCreate">+ 新建连接</button>
    </template>
  </PageHeader>

  <div v-if="loading" class="panel">
    <SkeletonLoader :rows="5" />
  </div>

  <div v-else-if="items.length === 0 && !isEditing" class="panel">
    <EmptyState title="尚无数据源" description="添加 PostgreSQL 连接后即可扫描表结构并生成 MCP 接口。">
      <button type="button" class="btn btn--primary" @click="startCreate">新建连接</button>
    </EmptyState>
  </div>

  <template v-else>
    <div class="stat-strip">
      <div class="stat-card">
        <div class="stat-card__label">连接数</div>
        <div class="stat-card__value numeric">{{ items.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">已验证</div>
        <div class="stat-card__value numeric">{{ verifiedCount }}</div>
      </div>
      <div class="stat-card stat-card--hint">
        <div class="stat-card__label">推荐流程</div>
        <div class="stat-card__value stat-card__value--sm">配置 → 通配符 → 扫描 → MCP</div>
      </div>
    </div>

    <div class="connections-mobile-tabs">
      <button
        type="button"
        class="filter-tab"
        :class="{ active: mobilePane === 'list' }"
        @click="mobilePane = 'list'"
      >
        连接列表
      </button>
      <button
        type="button"
        class="filter-tab"
        :class="{ active: mobilePane === 'detail' }"
        @click="mobilePane = 'detail'"
      >
        {{ showCreate ? "新建" : detail?.name || "详情" }}
      </button>
    </div>

    <div class="connections-layout">
      <aside class="panel connections-list" :class="{ 'connections-list--hidden': mobilePane !== 'list' }">
        <div class="panel__header connections-list__header">
          <h2 class="panel__title">连接列表</h2>
          <span class="connections-list__count">{{ filtered.length }}</span>
        </div>
        <div class="connections-list__search">
          <input v-model="search" type="search" class="input input--sm input-w-full" placeholder="搜索名称 / 主机" />
        </div>
        <div class="panel__body connections-list__body">
          <button
            v-for="row in filtered"
            :key="row.id"
            type="button"
            class="conn-card"
            :class="{ 'conn-card--active': selectedId === row.id && !showCreate }"
            @click="selectConnection(row)"
          >
            <span class="conn-card__dot" :class="statusDotClass(row.id)" aria-hidden="true" />
            <span class="conn-card__body">
              <span class="conn-card__row">
                <span class="conn-card__name">{{ row.name }}</span>
                <span class="badge" :class="profileBadge(row.profile)">{{ row.profile }}</span>
              </span>
              <span class="conn-card__host">{{ row.database_host }}</span>
              <span class="conn-card__meta">
                <span class="badge badge--sm" :class="verifyBadge(row.id)">{{ verifyLabel(row.id) }}</span>
                <span v-if="row.last_verified_at && verifyStatus[row.id] === 'ok'" class="conn-card__verified-at">
                  {{ row.last_verified_at.slice(0, 10) }}
                </span>
                <span class="conn-card__patterns">{{ patternSummary(row) }}</span>
              </span>
            </span>
            <span class="conn-card__actions">
              <button
                type="button"
                class="btn btn--sm btn--ghost"
                title="测试连接"
                :disabled="verifyStatus[row.id] === 'pending'"
                @click="quickVerify(row.id, $event)"
              >
                测试
              </button>
              <button type="button" class="btn btn--sm btn--ghost" title="扫描" @click="goScan(row.id, $event)">
                扫描
              </button>
            </span>
          </button>
          <p v-if="filtered.length === 0" class="empty-hint">无匹配连接</p>
        </div>
      </aside>

      <section class="panel connections-detail" :class="{ 'connections-detail--hidden': mobilePane !== 'detail' }">
        <div class="panel__header connections-detail__header">
          <div class="connections-detail__title-wrap">
            <button
              v-if="mobilePane === 'detail'"
              type="button"
              class="btn btn--sm btn--ghost connections-detail__back"
              @click="mobilePane = 'list'"
            >
              ← 列表
            </button>
            <h2 class="panel__title">{{ detailTitle }}</h2>
          </div>
          <div v-if="!showCreate && selectedId && detail" class="connections-detail__chips">
            <span class="badge" :class="profileBadge(detail.profile)">{{ detail.profile }}</span>
            <span class="badge" :class="verifyBadge(selectedId)">{{ verifyLabel(selectedId) }}</span>
            <span class="conn-chip">{{ detail.database_host }}</span>
          </div>
          <button
            v-if="!showCreate && selectedId"
            type="button"
            class="btn btn--sm btn--ghost"
            @click="remove(selectedId!, detail?.name || '')"
          >
            删除
          </button>
        </div>

        <div v-if="detailLoading" class="panel__body">
          <SkeletonLoader :rows="6" />
        </div>

        <div v-else-if="isEditing" class="panel__body connections-detail__body">
          <ConnectionWorkflowSteps
            v-if="!showCreate && selectedId"
            class="connections-detail__workflow"
            :connection-id="selectedId"
            :verified="isVerified"
            :has-patterns="hasPatterns"
            :has-context-pack="detail?.has_context_pack ?? false"
            :has-config="detail?.has_config ?? false"
          />
          <ConnectionFormPanel
            ref="formPanel"
            :mode="showCreate ? 'create' : 'edit'"
            :name="formName"
            :profile="formProfile"
            :include-schemas="formSchemas"
            :detail="showCreate ? null : detail"
            :saving="saving"
            :verifying="verifying"
            :verify-result="verifyResult"
            @update:name="formName = $event"
            @update:profile="formProfile = $event"
            @update:include-schemas="formSchemas = $event"
            @save="save"
            @cancel="resetForm"
            @verify="testSelected"
          />
        </div>

        <div v-else class="panel__body connections-detail__empty">
          <p class="connections-detail__empty-title">选择左侧连接以查看配置</p>
          <p class="connections-detail__empty-desc">或新建 PostgreSQL 数据源，完成后可测试连接并扫描表结构。</p>
          <button type="button" class="btn btn--primary" @click="startCreate">新建连接</button>
        </div>
      </section>
    </div>
  </template>
</template>

<style scoped>
.stat-card--hint {
  grid-column: span 2;
}

.stat-card__value--sm {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.connections-mobile-tabs {
  display: none;
  gap: var(--space-xs);
  margin-bottom: var(--space-md);
}

.connections-layout {
  display: grid;
  grid-template-columns: minmax(300px, 340px) minmax(0, 1fr);
  gap: var(--space-lg);
  align-items: start;
}

.connections-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.connections-list__count {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  padding: 0 8px;
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
}

.connections-list__search {
  padding: 0 var(--space-lg) var(--space-md);
  border-bottom: 1px solid var(--color-border);
}

.connections-list__body {
  max-height: calc(100vh - 280px);
  overflow: auto;
  padding: var(--space-sm);
}

.conn-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: var(--space-sm);
  align-items: start;
  width: 100%;
  padding: var(--space-md);
  margin-bottom: var(--space-xs);
  text-align: left;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  background: var(--color-surface-muted);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.conn-card:hover {
  border-color: var(--color-border-strong);
  background: var(--color-row-hover);
}

.conn-card--active {
  border-color: var(--color-primary);
  background: var(--color-primary-muted);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.conn-card__dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.conn-card__dot--idle {
  background: var(--color-text-muted);
}

.conn-card__dot--ok {
  background: var(--color-success, var(--color-primary));
}

.conn-card__dot--err {
  background: var(--color-danger);
}

.conn-card__dot--pending {
  background: var(--color-warning);
  animation: conn-pulse 1s ease-in-out infinite;
}

@keyframes conn-pulse {
  50% {
    opacity: 0.4;
  }
}

.conn-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.conn-card__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.conn-card__name {
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conn-card__host {
  font-size: var(--font-size-sm);
  font-family: var(--font-mono, monospace);
  color: var(--color-text-secondary);
}

.conn-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-xs);
}

.conn-card__patterns {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.conn-card__verified-at {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  font-family: var(--font-mono, monospace);
}

.conn-card__actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.conn-card:hover .conn-card__actions,
.conn-card--active .conn-card__actions {
  opacity: 1;
}

.badge--sm {
  font-size: var(--font-size-sm);
  padding: 1px 6px;
}

.connections-detail__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.connections-detail__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.connections-detail__back {
  display: none;
}

.connections-detail__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  align-items: center;
}

.conn-chip {
  font-size: var(--font-size-sm);
  font-family: var(--font-mono, monospace);
  color: var(--color-text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
}

.connections-detail__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.connections-detail__workflow {
  margin-bottom: var(--space-xs);
}

.connections-detail__empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-xl);
}

.connections-detail__empty-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.connections-detail__empty-desc {
  margin: 0;
  color: var(--color-text-muted);
  max-width: 420px;
  line-height: 1.5;
}

.empty-hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  padding: var(--space-md);
}

@media (max-width: 900px) {
  .connections-layout {
    grid-template-columns: 1fr;
  }

  .connections-mobile-tabs {
    display: flex;
  }

  .connections-detail__back {
    display: inline-flex;
  }

  .connections-list--hidden,
  .connections-detail--hidden {
    display: none;
  }

  .connections-list__body {
    max-height: none;
  }

  .conn-card__actions {
    opacity: 1;
  }
}
</style>
