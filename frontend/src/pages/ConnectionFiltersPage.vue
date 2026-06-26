<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  getConnection,
  linesToPatterns,
  patternsToLines,
  previewExposure,
  updateConnection,
} from "@/api/connections";
import type { ConnectionDetail, PreviewExposureResult } from "@/api/types";
import ConnectionSubpageLayout from "@/components/ConnectionSubpageLayout.vue";
import PageHeader from "@/components/PageHeader.vue";
import SkeletonLoader from "@/components/SkeletonLoader.vue";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();

const connectionId = route.params.id as string;
const loading = ref(true);
const saving = ref(false);
const previewing = ref(false);
const detail = ref<ConnectionDetail | null>(null);
const includeText = ref("");
const excludeText = ref("");
const preview = ref<PreviewExposureResult | null>(null);

const breadcrumbs = computed(() => [
  { label: "数据源", to: "/connections" },
  { label: detail.value?.name || "…" },
  { label: "通配符" },
]);

const hasPatterns = computed(() => {
  if (!detail.value) return false;
  return (
    detail.value.include_table_patterns.length + detail.value.exclude_table_patterns.length > 0
  );
});

onMounted(() => void load());

async function load() {
  loading.value = true;
  try {
    detail.value = await getConnection(connectionId);
    includeText.value = patternsToLines(detail.value.include_table_patterns);
    excludeText.value = patternsToLines(detail.value.exclude_table_patterns);
    await runPreview();
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
    router.push("/connections");
  } finally {
    loading.value = false;
  }
}

function errorMessage(e: unknown): string {
  return e && typeof e === "object" && "message" in e
    ? String((e as { message: string }).message)
    : "操作失败";
}

async function runPreview() {
  previewing.value = true;
  try {
    preview.value = await previewExposure(connectionId, {
      include_table_patterns: linesToPatterns(includeText.value),
      exclude_table_patterns: linesToPatterns(excludeText.value),
    });
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  } finally {
    previewing.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    detail.value = await updateConnection(connectionId, {
      include_table_patterns: linesToPatterns(includeText.value),
      exclude_table_patterns: linesToPatterns(excludeText.value),
    });
    ui.showMessage("通配符已保存", "success");
    await runPreview();
  } catch (e) {
    ui.showMessage(errorMessage(e), "error");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <PageHeader
    :title="detail ? `通配符 · ${detail.name}` : '通配符'"
    description="控制哪些表暴露为 MCP browse_* tools"
  >
    <template #actions>
      <button type="button" class="btn btn--secondary" @click="router.push('/connections')">
        返回连接列表
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
      :has-context-pack="detail.has_context_pack"
      :has-config="detail.has_config"
    >
      <div
        v-if="preview?.warning_level === 'warn' || preview?.warning_level === 'strong'"
        class="page-banner page-banner--warn"
        role="status"
      >
        {{ preview.exposure_warning }}
      </div>

      <div v-if="!hasPatterns" class="page-banner page-banner--info" role="status">
        尚未配置通配符时，扫描将暴露全部匹配 Schema 的表。建议先填写 Include / Exclude 规则并预览。
      </div>

      <div class="panel">
        <div class="panel__header">
          <h2 class="panel__title">表暴露规则</h2>
          <span v-if="detail.last_verify_ok === false" class="badge badge--err">连接未验证</span>
        </div>
        <div class="panel__body">
          <div class="form-grid">
            <label class="form-field form-field--full">
              <span class="form-field__label">Include 表模式（每行一条 fnmatch）</span>
              <span class="form-field__hint form-field__hint--above">
                留空表示不限制 include；可写表名（tushare_*）或 schema 限定（public.tushare_*）
              </span>
              <textarea v-model="includeText" rows="6" placeholder="tushare_*&#10;public.fact_*" />
            </label>
            <label class="form-field form-field--full">
              <span class="form-field__label">Exclude 表模式</span>
              <span class="form-field__hint form-field__hint--above">优先级高于 include</span>
              <textarea v-model="excludeText" rows="4" placeholder="*_backup" />
            </label>
          </div>

          <div v-if="preview" class="stat-strip stat-strip--compact">
            <div class="stat-card">
              <div class="stat-card__label">将暴露</div>
              <div class="stat-card__value numeric">{{ preview.exposed_count }} 张表</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__label">库内总表数</div>
              <div class="stat-card__value numeric">{{ preview.total_tables }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-card__label">暴露比例</div>
              <div class="stat-card__value numeric">
                {{
                  preview.total_tables
                    ? `${Math.round((preview.exposed_count / preview.total_tables) * 100)}%`
                    : "—"
                }}
              </div>
            </div>
          </div>

          <div class="page-actions">
            <button type="button" class="btn btn--secondary" :disabled="previewing" @click="runPreview">
              {{ previewing ? "预览中…" : "预览暴露" }}
            </button>
            <button type="button" class="btn btn--primary" :disabled="saving" @click="save">
              {{ saving ? "保存中…" : "保存" }}
            </button>
            <button
              type="button"
              class="btn btn--ghost"
              @click="router.push(`/connections/${connectionId}/scan`)"
            >
              下一步：扫描
            </button>
          </div>
        </div>
      </div>

      <p class="form-field__hint panel-section-spaced">
        连接 URL（脱敏）：{{ detail.database_url_masked }}
      </p>
    </ConnectionSubpageLayout>
  </template>
</template>

<style scoped>
.form-field--full {
  grid-column: 1 / -1;
}
</style>
