import { defineStore } from "pinia";
import {
  apiFetch,
  clearSession,
  getToken,
  getUsername,
  setApiBase,
  setSession,
} from "@/api/client";

type LoginResponse = {
  token: string;
  expires_at: string;
  username: string;
};

export const useAuthStore = defineStore("auth", {
  state: () => ({
    username: getUsername(),
    ready: false,
  }),
  getters: {
    isLoggedIn: () => getToken() !== null,
  },
  actions: {
    hydrate() {
      this.username = getUsername();
      this.ready = true;
    },
    async login(apiBase: string, username: string, password: string) {
      setApiBase(apiBase);
      const data = await apiFetch<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setSession(data.token, data.expires_at, data.username);
      this.username = data.username;
    },
    async logout() {
      try {
        await apiFetch("/api/v1/auth/logout", { method: "POST" });
      } catch {
        /* session may already be invalid */
      }
      clearSession();
      this.username = "";
    },
  },
});
