<script setup lang="ts">

import { computed, onMounted, ref, watch } from "vue";

import { useRouter } from "vue-router";

import WizardStepShell from "@/components/wizard/WizardStepShell.vue";

import WizardStatStrip from "@/components/wizard/WizardStatStrip.vue";

import SkeletonLoader from "@/components/SkeletonLoader.vue";

import { useTableDetail, TABLE_DETAIL_WARN_THRESHOLD } from "@/composables/useTableDetail";

import { useWizardStore } from "@/stores/wizardStore";

import {

  clearTableSelection,

  filterPackTables,

  selectAllTables,

  toggleTableFilter,

  type TableFilterTab,

} from "@/utils/wizardReviewPack";



const emit = defineEmits<{

  back: [];

  next: [];

}>();



const router = useRouter();

const store = useWizardStore();



const tab = ref<TableFilterTab>("all");

const search = ref("");



const exposedCount = computed(() => store.packSummary?.exposed_count ?? 0);



const tableDetail = useTableDetail(
  () => store.connectionId,
  () => exposedCount.value,
);

const { loading: detailLoading, error: detailError, detail: detailData } = tableDetail;



const filteredTables = computed(() => {

  if (!store.packSummary) return [];

  return filterPackTables(store.packSummary.tables, tab.value, search.value);

});



const statItems = computed(() => {

  const s = store.packSummary;

  if (!s) return [];

  return [

    { label: "Exposed 表", value: s.exposed_count },

    { label: "物理 FK", value: s.physical_fk_count },

    { label: "推断 Join", value: s.inferred_join_count },

    { label: "Pack 版本", value: s.version },

  ];

});



const selectedKey = computed({

  get: () => store.selectedTableKey,

  set: (v) => {

    store.selectedTableKey = v;

  },

});



onMounted(() => {

  void tableDetail.preloadIfSmall();

});



watch(selectedKey, (key) => {

  if (key) void tableDetail.loadTable(key);

});



function onSelectTable(qn: string) {

  selectedKey.value = qn;

}



function onToggle(qn: string) {

  store.tableFilter = toggleTableFilter(store.tableFilter, qn);

  store.persistPreferences();

}



function onSelectAll() {

  store.tableFilter = selectAllTables(filteredTables.value);

  store.persistPreferences();

}



function onClearSelection() {

  store.tableFilter = clearTableSelection();

  store.persistPreferences();

}

</script>



<template>

  <WizardStepShell

    title="审视 Context Pack"

    subtitle="确认 exposed 表、FK/join 与样例；可选勾选部分表重建"

  >

    <div v-if="store.packLoading" class="panel"><SkeletonLoader :rows="4" /></div>



    <template v-else-if="store.packSummary">

      <WizardStatStrip :items="statItems" />



      <p v-if="store.packSummary.exposure_warning" class="wizard-banner wizard-banner--warn">

        {{ store.packSummary.exposure_warning }}

      </p>

      <p v-if="exposedCount > TABLE_DETAIL_WARN_THRESHOLD" class="wizard-shell__hint">

        表数较多（{{ exposedCount }}），详情按需加载。

      </p>



      <div class="review-toolbar">

        <div class="filter-tabs">

          <button

            type="button"

            class="filter-tab"

            :class="{ 'filter-tab--active': tab === 'all' }"

            @click="tab = 'all'"

          >

            全部

          </button>

          <button

            type="button"

            class="filter-tab"

            :class="{ 'filter-tab--active': tab === 'fk' }"

            @click="tab = 'fk'"

          >

            有 FK

          </button>

          <button

            type="button"

            class="filter-tab"

            :class="{ 'filter-tab--active': tab === 'inferred' }"

            @click="tab = 'inferred'"

          >

            有推断 Join

          </button>

        </div>

        <input v-model="search" type="search" class="input input--sm" placeholder="搜索表名" />

        <button type="button" class="btn btn--ghost btn--sm" @click="onSelectAll">全选当前列表</button>

        <button type="button" class="btn btn--ghost btn--sm" @click="onClearSelection">清空选择</button>

      </div>



      <p class="wizard-shell__hint">留空勾选 = 构建全部 exposed 表（当前 {{ store.tableFilter.length || "全部" }}）</p>



      <div class="page-split review-split">

        <div class="panel review-list">

          <div class="table-scroll">

            <table class="data-table">

              <thead>

                <tr>

                  <th></th>

                  <th>表</th>

                  <th>列</th>

                  <th>FK</th>

                  <th>推断</th>

                </tr>

              </thead>

              <tbody>

                <tr

                  v-for="t in filteredTables"

                  :key="t.qualified_name"

                  :class="{ 'row--active': selectedKey === t.qualified_name }"

                  @click="onSelectTable(t.qualified_name)"

                >

                  <td @click.stop>

                    <input

                      type="checkbox"

                      :checked="store.tableFilter.includes(t.qualified_name)"

                      @change="onToggle(t.qualified_name)"

                    />

                  </td>

                  <td><code>{{ t.qualified_name }}</code></td>

                  <td>{{ t.column_count }}</td>

                  <td>{{ t.physical_fk_count }}</td>

                  <td>{{ t.inferred_join_count }}</td>

                </tr>

              </tbody>

            </table>

          </div>

        </div>



        <div class="panel review-detail">

          <div v-if="!selectedKey" class="review-detail__empty">选择左侧表查看 FK、推断 join 与样例</div>

          <div v-else-if="detailLoading" class="review-detail__empty">加载表详情…</div>
          <div v-else-if="detailError" class="review-detail__empty">{{ detailError }}</div>
          <div v-else-if="detailData" class="review-detail__body">

            <h3 class="review-detail__title">{{ selectedKey }}</h3>

            <p class="wizard-shell__hint">

              列 {{ detailData.columnCount }} · PK
              {{ detailData.primaryKeys.join(", ") || "—" }} · 行数估计
              {{ detailData.rowCountEstimate ?? "—" }}

            </p>



            <h4 class="review-detail__section">物理 FK</h4>

            <ul v-if="detailData.foreignKeys.length" class="review-detail__list">
              <li v-for="(fk, i) in detailData.foreignKeys" :key="i">

                <code>{{ fk.column }}</code> → {{ fk.ref_schema }}.{{ fk.ref_table }}.{{ fk.ref_column }}

              </li>

            </ul>

            <p v-else class="wizard-shell__hint">无</p>



            <h4 class="review-detail__section">推断 Join</h4>

            <ul v-if="detailData.inferredJoins.length" class="review-detail__list">
              <li v-for="(j, i) in detailData.inferredJoins" :key="i">

                <code>{{ j.column }}</code> → {{ j.ref_schema }}.{{ j.ref_table }}

                <span class="badge badge--muted">{{ j.source ?? "inferred" }}</span>

              </li>

            </ul>

            <p v-else class="wizard-shell__hint">无</p>



            <h4 class="review-detail__section">样例（最多 3 行）</h4>

            <div v-if="detailData.samples.length" class="table-scroll table-scroll--compact">
              <table class="data-table data-table--compact">
                <thead>
                  <tr>
                    <th v-for="col in Object.keys(detailData.samples[0] || {})" :key="col">

                      {{ col }}

                    </th>

                  </tr>

                </thead>

                <tbody>

                  <tr v-for="(row, ri) in detailData.samples" :key="ri">
                    <td v-for="col in Object.keys(detailData.samples[0] || {})" :key="col">

                      {{ row[col] }}

                    </td>

                  </tr>

                </tbody>

              </table>

            </div>

            <p v-else class="wizard-shell__hint">无样例</p>



            <button

              type="button"

              class="btn btn--ghost btn--sm"

              @click="router.push(`/connections/${store.connectionId}/scan`)"

            >

              在 Scan 页查看完整样例

            </button>

          </div>

        </div>

      </div>

    </template>



    <template #actions>

      <button type="button" class="btn btn--ghost" @click="emit('back')">上一步</button>

      <button type="button" class="btn btn--primary" :disabled="!store.packSummary" @click="emit('next')">

        下一步

      </button>

    </template>

  </WizardStepShell>

</template>



<style scoped>

.review-toolbar {

  display: flex;

  flex-wrap: wrap;

  gap: var(--space-sm);

  align-items: center;

}



.review-split {

  grid-template-columns: minmax(0, 42%) minmax(0, 1fr);

  gap: var(--space-md);

}



@media (max-width: 900px) {

  .review-split {

    grid-template-columns: 1fr;

  }

}



.review-list .table-scroll {

  max-height: 420px;

}



.row--active {

  background: var(--color-primary-muted);

}



.review-detail {

  min-height: 280px;

}



.review-detail__empty {

  padding: var(--space-lg);

  color: var(--color-text-muted);

  font-size: var(--font-size-md);

}



.review-detail__title {

  margin: 0 0 var(--space-xs);

  font-size: var(--font-size-md);

}



.review-detail__section {

  margin: var(--space-md) 0 var(--space-xs);

  font-size: var(--font-size-sm);

  color: var(--color-text-secondary);

}



.review-detail__list {

  margin: 0;

  padding-left: var(--space-lg);

  font-size: var(--font-size-sm);

}



.table-scroll--compact {

  max-height: 160px;

}



.wizard-banner--warn {

  padding: var(--space-sm) var(--space-md);

  border-radius: var(--radius-sm);

  background: var(--color-warn-bg, rgba(255, 193, 7, 0.12));

  margin: 0;

}



.wizard-shell__hint {

  margin: 0;

  font-size: var(--font-size-sm);

  color: var(--color-text-muted);

}

</style>

