import { defineStore } from "pinia";
import type { DashboardConnection, DashboardSummary } from "@/api/dashboard";
import {
  getBuildJob,
  getPackSummary,
  listMcpTools,
  loadWizardState,
  saveWizardState,
  startBuildJob,
  type BuildJob,
  type BuildJobOptions,
  type PackSummary,
  type ToolManifest,
} from "@/api/mcp";
import { getDashboardSummary } from "@/api/dashboard";
import { listConnections, getContextPackStatus } from "@/api/connections";
import type { ConnectionSummary } from "@/api/types";
import { stepFromJobStatus } from "@/composables/useWizardState";
import { clearTableDetailCache } from "@/composables/useTableDetail";

const defaultBuildOptions = (): BuildJobOptions => ({
  llm_enabled: true,
  skip_pass1: false,
  domain_hint: "",
  custom_prompt_suffix: "",
  fallback_to_rule: true,
  mode: "quick",
});

export const useWizardStore = defineStore("wizard", {
  state: () => ({
    initialized: false,
    pageLoading: true,
    busy: false,
    jobError: "",
    mode: "quick" as "quick" | "full",
    currentStep: 1,
    connections: [] as ConnectionSummary[],
    connectionId: "" as string,
    dashboard: null as DashboardSummary | null,
    packSummary: null as PackSummary | null,
    packLoading: false,
    selectedTableKey: null as string | null,
    tableFilter: [] as string[],
    buildOptions: defaultBuildOptions(),
    jobId: null as string | null,
    job: null as BuildJob | null,
    tools: [] as ToolManifest[],
    packStatus: null as { exists: boolean; version: string | null } | null,
  }),

  getters: {
    readiness(state): DashboardConnection | null {
      if (!state.dashboard || !state.connectionId) return null;
      return state.dashboard.connections_list.find((c) => c.id === state.connectionId) ?? null;
    },
    selectedConnection(state): ConnectionSummary | undefined {
      return state.connections.find((c) => c.id === state.connectionId);
    },
    hasConfig(): boolean {
      return this.readiness?.has_config ?? false;
    },
    canBuild(): boolean {
      if (this.packStatus?.exists) return true;
      return this.readiness?.has_context_pack ?? false;
    },
    buildOptionsPayload(state): BuildJobOptions {
      return {
        ...state.buildOptions,
        table_filter: state.tableFilter.length ? state.tableFilter : undefined,
        mode: state.mode,
      };
    },
    isQuickMode(state): boolean {
      return state.mode === "quick";
    },
  },

  actions: {
    persistPreferences() {
      saveWizardState({
        connectionId: this.connectionId,
        mode: this.mode,
        domainHint: this.buildOptions.domain_hint ?? "",
        tableFilter: this.tableFilter,
        skipPass1: this.buildOptions.skip_pass1 ?? false,
        llmEnabled: this.buildOptions.llm_enabled ?? true,
      });
    },

    applySavedPreferences() {
      const saved = loadWizardState();
      if (saved.mode) this.mode = saved.mode;
      if (saved.domainHint) this.buildOptions.domain_hint = saved.domainHint;
      if (saved.tableFilter) this.tableFilter = saved.tableFilter;
      if (saved.skipPass1 !== undefined) this.buildOptions.skip_pass1 = saved.skipPass1;
      if (saved.llmEnabled !== undefined) this.buildOptions.llm_enabled = saved.llmEnabled;
    },

    async bootstrap(queryConnectionId?: string, routeJobId?: string, routeStep?: number) {
      this.pageLoading = true;
      try {
        this.applySavedPreferences();
        const [connRes, dash] = await Promise.all([listConnections(), getDashboardSummary()]);
        this.connections = connRes.items;
        this.dashboard = dash;

        const qid = queryConnectionId;
        this.connectionId =
          qid && connRes.items.some((c) => c.id === qid)
            ? qid
            : savedConnectionId(connRes.items) || connRes.items[0]?.id || "";

        if (routeJobId) {
          this.jobId = routeJobId;
          await this.refreshJob();
          if (this.job) {
            this.connectionId = this.job.connection_id;
            this.currentStep = stepFromJobStatus(this.job.status, this.mode, routeStep);
            if (this.currentStep >= 5) await this.loadTools();
          }
        }
        await this.refreshPackStatus(this.connectionId);
      } finally {
        this.pageLoading = false;
        this.initialized = true;
      }
    },

    async refreshDashboard() {
      this.dashboard = await getDashboardSummary();
    },

    async refreshPackStatus(connectionId?: string) {
      const id = connectionId ?? this.connectionId;
      if (!id) return;
      try {
        const status = await getContextPackStatus(id);
        this.packStatus = { exists: status.exists, version: status.version };
        this.patchDashboardConnection(id, status);
        return;
      } catch {
        /* status endpoint missing on older Admin builds */
      }
      try {
        await getPackSummary(id);
        this.packStatus = { exists: true, version: null };
        this.patchDashboardConnection(id, { exists: true, version: null });
      } catch {
        this.packStatus = { exists: false, version: null };
        this.patchDashboardConnection(id, { exists: false, version: null });
      }
    },

    patchDashboardConnection(
      connectionId: string,
      status: { exists: boolean; version: string | null },
    ) {
      if (!this.dashboard) return;
      const row = this.dashboard.connections_list.find((c) => c.id === connectionId);
      if (!row) return;
      row.has_context_pack = status.exists;
      if (status.version) row.context_pack_version = status.version;
    },

    setConnectionId(id: string) {
      if (this.connectionId === id) return;
      this.connectionId = id;
      this.packSummary = null;
      this.packStatus = null;
      this.selectedTableKey = null;
      clearTableDetailCache(id);
      this.persistPreferences();
      void this.refreshPackStatus(id);
    },

    setStep(step: number) {
      this.currentStep = step;
    },

    goAdvanced() {
      this.mode = "full";
      this.buildOptions.mode = "full";
      this.persistPreferences();
      this.currentStep = 2;
    },

    async ensurePackForAdvanced() {
      await this.loadPackSummary();
    },

    async loadPackSummary() {
      if (!this.connectionId) return;
      this.packLoading = true;
      try {
        this.packSummary = await getPackSummary(this.connectionId);
      } catch {
        this.packSummary = null;
        throw new Error("Context Pack 不存在或已丢失，请重新 Scan");
      } finally {
        this.packLoading = false;
      }
    },

    async startBuild() {
      if (!this.connectionId) throw new Error("请选择连接");
      this.busy = true;
      this.jobError = "";
      const res = await startBuildJob(this.connectionId, this.buildOptionsPayload);
      this.jobId = res.job_id;
      this.currentStep = 4;
      return res.job_id;
    },

    async refreshJob() {
      if (!this.jobId) return;
      const j = await getBuildJob(this.jobId);
      this.job = j;
      if (j.status === "completed") {
        this.busy = false;
        await this.loadTools();
      } else if (j.status === "failed") {
        this.busy = false;
        this.jobError = j.error || "构建失败";
      }
    },

    onJobCompleted() {
      this.currentStep = 5;
    },

    async loadTools() {
      if (!this.connectionId) return;
      const data = await listMcpTools(this.connectionId);
      this.tools = data.items;
    },

    confirmBackToStrategy() {
      this.jobId = null;
      this.job = null;
      this.tools = [];
      this.jobError = "";
      this.currentStep = 3;
    },

    resetWizard() {
      this.jobId = null;
      this.job = null;
      this.tools = [];
      this.jobError = "";
      this.tableFilter = [];
      this.packSummary = null;
      this.packStatus = null;
      this.selectedTableKey = null;
      this.currentStep = 1;
      this.busy = false;
    },

    setBuildOption<K extends keyof BuildJobOptions>(key: K, value: BuildJobOptions[K]) {
      this.buildOptions[key] = value;
      this.persistPreferences();
    },
  },
});

function savedConnectionId(items: ConnectionSummary[]): string {
  const saved = loadWizardState();
  if (saved.connectionId && items.some((c) => c.id === saved.connectionId)) {
    return saved.connectionId;
  }
  return "";
}
