import { defineStore } from "pinia";

type ToastKind = "info" | "success" | "error" | "warn";

export const useUiStore = defineStore("ui", {
  state: () => ({
    theme: (localStorage.getItem("ninehub_mcp.theme") || "dark") as "light" | "dark",
    message: null as { text: string; kind: ToastKind } | null,
    healthOk: false,
  }),
  actions: {
    applyTheme() {
      document.documentElement.setAttribute("data-theme", this.theme);
      localStorage.setItem("ninehub_mcp.theme", this.theme);
    },
    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      this.applyTheme();
    },
    showMessage(text: string, kind: ToastKind = "info") {
      this.message = { text, kind };
      window.setTimeout(() => {
        if (this.message?.text === text) {
          this.message = null;
        }
      }, 4000);
    },
    setHealth(ok: boolean) {
      this.healthOk = ok;
    },
  },
});
