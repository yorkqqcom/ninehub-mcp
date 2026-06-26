<script setup lang="ts">
import { computed, ref, watch } from "vue";
import CopyButton from "@/components/CopyButton.vue";
import type { ConnectionDetail } from "@/api/types";
import {
  DEFAULT_DB_FIELDS,
  buildPostgresUrl,
  fieldsFromDetail,
  maskPostgresUrl,
  parsePostgresUrl,
  resolveDatabaseUrl,
  validateConnectionFields,
  type DbConnectionFields,
  type FieldValidation,
} from "@/utils/databaseUrl";

const props = defineProps<{
  mode: "create" | "edit";
  name: string;
  profile: string;
  includeSchemas: string;
  detail?: ConnectionDetail | null;
  saving?: boolean;
  verifying?: boolean;
  verifyResult?: { ok: boolean; message: string } | null;
}>();

const emit = defineEmits<{
  "update:name": [value: string];
  "update:profile": [value: string];
  "update:includeSchemas": [value: string];
  save: [];
  cancel: [];
  verify: [];
}>();

type FormTab = "basic" | "connection" | "advanced";
type InputMode = "fields" | "url";

const activeTab = ref<FormTab>("basic");
const inputMode = ref<InputMode>("fields");
const fields = ref<DbConnectionFields>({ ...DEFAULT_DB_FIELDS });
const rawUrl = ref("");
const showPassword = ref(false);
const touched = ref(false);
const autoLinked = ref(false);

const profileHint = computed(() => {
  if (props.profile === "catalog") return "仅暴露 schema / 表结构 browse 类工具";
  if (props.profile === "query") return "仅暴露 query 类工具";
  return "browse + query 全量 profile";
});

const hasCredentialInput = computed(() => {
  if (inputMode.value === "url") {
    return rawUrl.value.trim().length > 0;
  }
  return fields.value.password.trim().length > 0;
});

const fieldErrors = computed((): FieldValidation => {
  if (!touched.value && props.mode === "edit") {
    return {};
  }
  return validateConnectionFields(inputMode.value, fields.value, rawUrl.value, {
    requirePassword: props.mode === "create" && inputMode.value === "fields",
  });
});

const nameError = computed(() => {
  if (!touched.value) return "";
  return props.name.trim() ? "" : "请填写连接名称";
});

const schemaError = computed(() => {
  if (!touched.value) return "";
  const parts = props.includeSchemas
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.length ? "" : "至少填写一个 Schema";
});

const previewUrl = computed(() => {
  if (props.mode === "edit" && !hasCredentialInput.value) {
    const built = buildPostgresUrl({ ...fields.value, password: "****" });
    if (built) {
      return maskPostgresUrl(built);
    }
    return props.detail?.database_url_masked || "—";
  }
  const built = resolveDatabaseUrl(inputMode.value, fields.value, rawUrl.value);
  return built ? maskPostgresUrl(built) : "—";
});

const canSave = computed(() => {
  if (!props.name.trim()) return false;
  if (schemaError.value) return false;
  const errs = validateConnectionFields(inputMode.value, fields.value, rawUrl.value, {
    requirePassword: props.mode === "create" && inputMode.value === "fields",
  });
  if (Object.keys(errs).length) return false;
  if (props.mode === "create") {
    return resolveDatabaseUrl(inputMode.value, fields.value, rawUrl.value).length > 0;
  }
  return true;
});

const canVerify = computed(() => props.mode === "edit" && !!props.detail?.id);

const saveHint = computed(() => {
  if (canSave.value) return "";
  if (nameError.value) return nameError.value;
  if (schemaError.value) return schemaError.value;
  const errs = validateConnectionFields(inputMode.value, fields.value, rawUrl.value, {
    requirePassword: props.mode === "create" && inputMode.value === "fields",
  });
  return Object.values(errs)[0] || "";
});

function resetFields() {
  fields.value = { ...DEFAULT_DB_FIELDS };
  rawUrl.value = "";
  inputMode.value = "fields";
  showPassword.value = false;
  touched.value = false;
  autoLinked.value = false;
  activeTab.value = "basic";
}

function applyDetail(detail: ConnectionDetail | null | undefined) {
  resetFields();
  if (!detail) return;
  fields.value = fieldsFromDetail(detail);
}

function linkFromName() {
  if (props.mode !== "create" || autoLinked.value) return;
  const n = props.name.trim();
  if (!n) return;
  if (!fields.value.database.trim()) {
    fields.value.database = n;
  }
  if (!fields.value.username.trim()) {
    fields.value.username = n;
  }
  autoLinked.value = true;
}

watch(
  () => props.detail,
  (detail) => applyDetail(detail),
  { immediate: true },
);

watch(
  () => props.name,
  () => linkFromName(),
);

watch(inputMode, (mode) => {
  if (mode === "url") {
    const built = buildPostgresUrl(fields.value);
    if (built) rawUrl.value = built;
    return;
  }
  const parsed = parsePostgresUrl(rawUrl.value);
  if (parsed) {
    fields.value = {
      host: parsed.host || DEFAULT_DB_FIELDS.host,
      port: parsed.port || DEFAULT_DB_FIELDS.port,
      database: (parsed.database || "").replace(/^\/+/, ""),
      username: parsed.username || "",
      password: parsed.password || "",
    };
  }
});

function onSave() {
  touched.value = true;
  if (!canSave.value) return;
  emit("save");
}

function getDatabaseUrlPayload(mode: "create" | "edit"): string | null {
  const url = resolveDatabaseUrl(inputMode.value, fields.value, rawUrl.value);
  if (mode === "create") {
    return url || null;
  }
  return hasCredentialInput.value ? url || null : null;
}

defineExpose({ getDatabaseUrlPayload, touchValidation: () => { touched.value = true; } });
</script>

<template>
  <div class="conn-form">
    <div class="conn-form__preview-bar">
      <div class="conn-form__preview-bar-main">
        <span class="conn-form__preview-bar-label">连接预览</span>
        <code class="conn-form__preview-bar-value">{{ previewUrl }}</code>
      </div>
      <CopyButton :text="previewUrl === '—' ? '' : previewUrl" />
    </div>

    <div
      v-if="verifyResult && mode === 'edit'"
      class="conn-form__verify-banner"
      :class="verifyResult.ok ? 'conn-form__verify-banner--ok' : 'conn-form__verify-banner--err'"
      role="status"
    >
      {{ verifyResult.message }}
    </div>

    <div class="conn-form__tabs" role="tablist">
      <button
        type="button"
        class="conn-form__tab"
        :class="{ active: activeTab === 'basic' }"
        @click="activeTab = 'basic'"
      >
        基本信息
      </button>
      <button
        type="button"
        class="conn-form__tab"
        :class="{ active: activeTab === 'connection' }"
        @click="activeTab = 'connection'"
      >
        连接与认证
      </button>
      <button
        type="button"
        class="conn-form__tab"
        :class="{ active: activeTab === 'advanced' }"
        @click="activeTab = 'advanced'"
      >
        高级
      </button>
    </div>

    <div v-show="activeTab === 'basic'" class="conn-form__section">
      <div class="form-grid">
        <label class="form-field" :class="{ 'form-field--error': nameError }">
          <span class="form-field__label">连接名称</span>
          <input
            :value="name"
            type="text"
            placeholder="例如 ninehub"
            @input="emit('update:name', ($event.target as HTMLInputElement).value)"
            @blur="touched = true"
          />
          <span v-if="nameError" class="form-field__error">{{ nameError }}</span>
        </label>
        <label class="form-field">
          <span class="form-field__label">Profile</span>
          <span class="form-field__hint form-field__hint--above">{{ profileHint }}</span>
          <select
            :value="profile"
            @change="emit('update:profile', ($event.target as HTMLSelectElement).value)"
          >
            <option value="all">all</option>
            <option value="catalog">catalog</option>
            <option value="query">query</option>
          </select>
        </label>
        <label class="form-field" :class="{ 'form-field--error': schemaError }">
          <span class="form-field__label">Schema</span>
          <span class="form-field__hint form-field__hint--above">模式名，多个用逗号分隔</span>
          <input
            :value="includeSchemas"
            type="text"
            placeholder="public"
            @input="emit('update:includeSchemas', ($event.target as HTMLInputElement).value)"
            @blur="touched = true"
          />
          <span v-if="schemaError" class="form-field__error">{{ schemaError }}</span>
        </label>
      </div>
      <p v-if="mode === 'create'" class="conn-form__tip">
        填写连接名称后，将自动建议数据库名与用户名（可手动修改）。
      </p>
    </div>

    <div v-show="activeTab === 'connection'" class="conn-form__section">
      <div class="conn-form__section-head">
        <h3 class="conn-form__section-title">连接方式</h3>
        <div class="filter-tabs" role="tablist">
          <button
            type="button"
            class="filter-tab"
            :class="{ active: inputMode === 'fields' }"
            @click="inputMode = 'fields'"
          >
            主机
          </button>
          <button
            type="button"
            class="filter-tab"
            :class="{ active: inputMode === 'url' }"
            @click="inputMode = 'url'"
          >
            连接串
          </button>
        </div>
      </div>

      <template v-if="inputMode === 'fields'">
        <div class="form-grid form-grid--server">
          <label class="form-field" :class="{ 'form-field--error': fieldErrors.host }">
            <span class="form-field__label">主机</span>
            <input v-model="fields.host" type="text" placeholder="localhost" @blur="touched = true" />
            <span v-if="fieldErrors.host" class="form-field__error">{{ fieldErrors.host }}</span>
          </label>
          <label class="form-field form-field--port" :class="{ 'form-field--error': fieldErrors.port }">
            <span class="form-field__label">端口</span>
            <input v-model="fields.port" type="text" placeholder="5432" @blur="touched = true" />
            <span v-if="fieldErrors.port" class="form-field__error">{{ fieldErrors.port }}</span>
          </label>
          <label class="form-field" :class="{ 'form-field--error': fieldErrors.database }">
            <span class="form-field__label">数据库</span>
            <span class="form-field__hint form-field__hint--above">PostgreSQL 库名</span>
            <input v-model="fields.database" type="text" placeholder="ninehub" @blur="touched = true" />
            <span v-if="fieldErrors.database" class="form-field__error">{{ fieldErrors.database }}</span>
          </label>
        </div>

        <h3 class="conn-form__section-title conn-form__section-title--sub">认证</h3>
        <div class="form-grid form-grid--pair">
          <label class="form-field" :class="{ 'form-field--error': fieldErrors.username }">
            <span class="form-field__label">用户名</span>
            <input
              v-model="fields.username"
              type="text"
              autocomplete="username"
              placeholder="ninehub"
              @blur="touched = true"
            />
            <span v-if="fieldErrors.username" class="form-field__error">{{ fieldErrors.username }}</span>
          </label>
          <label class="form-field" :class="{ 'form-field--error': fieldErrors.password }">
            <span class="form-field__label">
              <span>密码</span>
              <span v-if="mode === 'edit'" class="form-field__label-hint">留空不修改</span>
            </span>
            <div class="conn-form__password">
              <input
                v-model="fields.password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="••••••••"
                @blur="touched = true"
              />
              <button type="button" class="btn btn--sm btn--ghost" @click="showPassword = !showPassword">
                {{ showPassword ? "隐藏" : "显示" }}
              </button>
            </div>
            <span v-if="fieldErrors.password" class="form-field__error">{{ fieldErrors.password }}</span>
          </label>
        </div>
      </template>

      <template v-else>
        <label class="form-field" :class="{ 'form-field--error': fieldErrors.url }">
          <span class="form-field__label">
            Database URL
            <span v-if="mode === 'edit'" class="form-field__hint">（留空不修改连接串）</span>
          </span>
          <input
            v-model="rawUrl"
            type="password"
            autocomplete="off"
            placeholder="postgresql://user:pass@localhost:5432/ninehub"
            @blur="touched = true"
          />
          <span v-if="fieldErrors.url" class="form-field__error">{{ fieldErrors.url }}</span>
        </label>
        <p class="form-field__hint">可直接粘贴 JDBC 工具导出的连接串（需改为 postgresql:// 前缀）</p>
      </template>
    </div>

    <div v-show="activeTab === 'advanced'" class="conn-form__section">
      <p class="conn-form__tip">
        Profile 控制 MCP 暴露的工具类型；Schema 限定扫描范围。保存后可在「通配符」页进一步过滤表。
      </p>
      <div v-if="mode === 'edit' && detail" class="conn-form__meta">
        <span v-if="detail.created_at">创建 {{ detail.created_at.slice(0, 10) }}</span>
        <span v-if="detail.updated_at">更新 {{ detail.updated_at.slice(0, 10) }}</span>
        <span v-if="detail.last_verified_at">
          上次验证 {{ detail.last_verified_at.slice(0, 16).replace("T", " ") }}
        </span>
        <span v-if="detail.last_verify_ok === true" class="badge badge--ok">连接可用</span>
        <span v-else-if="detail.last_verify_ok === false" class="badge badge--err">验证失败</span>
        <span v-if="detail.has_config" class="badge badge--ok">已有 MCP 配置</span>
        <span v-else class="badge badge--muted">尚未扫描生成 MCP</span>
      </div>
    </div>

    <div class="conn-form__actions">
      <button type="button" class="btn btn--primary" :disabled="saving || !canSave" @click="onSave">
        {{ saving ? "保存中…" : "保存" }}
      </button>
      <button
        type="button"
        class="btn btn--secondary"
        :disabled="!canVerify || verifying"
        @click="emit('verify')"
      >
        {{ verifying ? "测试中…" : "测试连接" }}
      </button>
      <button type="button" class="btn btn--ghost" @click="emit('cancel')">取消</button>
      <router-link
        v-if="mode === 'edit' && detail"
        class="btn btn--ghost"
        :to="`/connections/${detail.id}/filters`"
      >
        通配符
      </router-link>
      <router-link
        v-if="mode === 'edit' && detail"
        class="btn btn--ghost"
        :to="`/connections/${detail.id}/scan`"
      >
        扫描
      </router-link>
      <span v-if="saveHint && touched" class="conn-form__save-hint">{{ saveHint }}</span>
    </div>
  </div>
</template>

<style scoped>
.conn-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.conn-form__preview-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  background: var(--color-surface-elevated, var(--color-surface-muted));
}

.conn-form__preview-bar-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.conn-form__preview-bar-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.conn-form__preview-bar-value {
  font-family: var(--font-mono, monospace);
  font-size: var(--font-size-sm);
  color: var(--color-text);
  word-break: break-all;
}

.conn-form__verify-banner {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-panel);
  font-size: var(--font-size-sm);
}

.conn-form__verify-banner--ok {
  background: var(--color-ok-bg, rgba(34, 197, 94, 0.12));
  color: var(--color-ok-text, #22c55e);
  border: 1px solid var(--color-ok-text, #22c55e);
}

.conn-form__verify-banner--err {
  background: var(--color-err-bg, rgba(239, 68, 68, 0.12));
  color: var(--color-err-text, #ef4444);
  border: 1px solid var(--color-err-text, #ef4444);
}

.conn-form__tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  border-radius: var(--radius-panel);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
}

.conn-form__tab {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: calc(var(--radius-panel) - 2px);
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.conn-form__tab.active {
  background: var(--color-surface);
  color: var(--color-text);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.conn-form__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-panel);
  background: var(--color-surface-muted);
}

.conn-form__section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.conn-form__section-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.conn-form__section-title--sub {
  margin-top: var(--space-xs);
}

.conn-form__password {
  display: flex;
  gap: var(--space-xs);
  align-items: stretch;
}

.conn-form__password input {
  flex: 1;
  min-height: 32px;
}

.conn-form__password .btn {
  flex-shrink: 0;
  align-self: stretch;
}

.conn-form__tip {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  line-height: 1.5;
}

.form-field__hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  font-weight: normal;
}

.form-field__hint--above {
  margin-bottom: 2px;
  line-height: 1.4;
}

.form-field__error {
  font-size: var(--font-size-sm);
  color: var(--color-danger, #ef4444);
  margin-top: 2px;
}

.form-field--error input,
.form-field--error select {
  border-color: var(--color-danger, #ef4444);
}

.conn-form__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.conn-form__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
}

.conn-form__actions .btn {
  flex-shrink: 0;
}

.conn-form__save-hint {
  font-size: var(--font-size-sm);
  color: var(--color-danger, #ef4444);
  margin-left: var(--space-xs);
}

.form-grid--server {
  grid-template-columns: minmax(0, 1.4fr) 96px minmax(0, 1fr);
  align-items: start;
}

.form-field--port input {
  max-width: 100%;
}

@media (max-width: 640px) {
  .form-grid--server {
    grid-template-columns: 1fr 1fr;
  }

  .form-grid--server .form-field:last-child {
    grid-column: 1 / -1;
  }

  .conn-form__tabs {
    flex-direction: column;
  }
}
</style>
