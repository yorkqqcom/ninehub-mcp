import { createRouter, createWebHistory } from "vue-router";
import AppShell from "@/layouts/AppShell.vue";
import { getToken } from "@/api/client";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", name: "dashboard", component: () => import("@/pages/DashboardPage.vue") },
        { path: "connections", name: "connections", component: () => import("@/pages/ConnectionsPage.vue") },
        {
          path: "connections/:id/filters",
          name: "connection-filters",
          component: () => import("@/pages/ConnectionFiltersPage.vue"),
        },
        {
          path: "connections/:id/scan",
          name: "connection-scan",
          component: () => import("@/pages/ConnectionScanPage.vue"),
        },
        { path: "mcp/build", name: "mcp-build", component: () => import("@/pages/McpBuildPage.vue") },
        {
          path: "mcp/build/:jobId/step/:step",
          name: "mcp-build-step",
          component: () => import("@/pages/McpBuildPage.vue"),
        },
        { path: "mcp/tools", name: "mcp-tools", component: () => import("@/pages/McpToolsPage.vue") },
        { path: "mcp/test", name: "mcp-test", component: () => import("@/pages/McpTestPage.vue") },
        { path: "mcp/serve", name: "mcp-serve", component: () => import("@/pages/McpServePage.vue") },
        { path: "mcp/logs", name: "mcp-logs", component: () => import("@/pages/McpLogsPage.vue") },
        { path: "settings", name: "settings", component: () => import("@/pages/SettingsPage.vue") },
        { path: "settings/account", name: "settings-account", component: () => import("@/pages/AccountPage.vue") },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/pages/NotFoundPage.vue"),
      meta: { public: true },
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.public) {
    return true;
  }
  if (!getToken()) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  return true;
});

export default router;
