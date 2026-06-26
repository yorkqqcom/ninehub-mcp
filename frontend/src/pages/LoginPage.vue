<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getApiBase, setApiBase } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();

const apiUrl = ref(getApiBase() || (import.meta.env.DEV ? "" : window.location.origin));
const username = ref("admin");
const password = ref("");
const busy = ref(false);
const error = ref("");
const isDev = import.meta.env.DEV;

const apiHint = isDev
  ? "开发环境留空即可（Vite 代理）；直连后端填 http://127.0.0.1:8899"
  : "生产模式留空即可（与 Admin 同源）；跨域部署时再填 API 地址";

onMounted(() => {
  ui.applyTheme();
  const reason = route.query.reason as string | undefined;
  if (reason === "credentials_changed") {
    ui.showMessage("凭据已更新，请重新登录", "warn");
  }
});

async function submit() {
  const base = apiUrl.value.trim() || window.location.origin;
  busy.value = true;
  error.value = "";
  try {
    setApiBase(base);
    await auth.login(base, username.value.trim(), password.value);
    ui.showMessage("登录成功", "success");
    const redirect = (route.query.redirect as string) || "/";
    router.push(redirect);
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "登录失败";
    error.value = msg;
    ui.showMessage(msg, "error");
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-page__toolbar">
      <button type="button" class="btn btn--secondary" aria-label="切换主题" @click="ui.toggleTheme()">
        {{ ui.theme === "dark" ? "浅色" : "暗色" }}
      </button>
    </div>

    <div class="login-shell">
      <div class="login-card">
        <header class="login-brand">
          <div class="login-logo" aria-hidden="true">MCP</div>
          <h1>ninehub-mcp Admin</h1>
          <p class="login-tagline">PostgreSQL MCP 配置与管理</p>
        </header>

        <form class="login-form" @submit.prevent="submit">
          <label class="login-field">
            <span class="login-label">Admin API 地址</span>
            <input v-model="apiUrl" type="text" class="input-w-full" placeholder="留空走 Vite 代理（推荐）" />
            <span class="login-hint">{{ apiHint }}</span>
          </label>

          <label class="login-field">
            <span class="login-label">用户名</span>
            <input v-model="username" type="text" autocomplete="username" />
          </label>

          <label class="login-field" :class="{ 'form-field--error': error }">
            <span class="login-label">密码</span>
            <input v-model="password" type="password" autocomplete="current-password" />
            <span v-if="error" class="form-field__error" role="alert">{{ error }}</span>
          </label>

          <button type="submit" class="btn btn--primary login-submit" :disabled="busy">
            {{ busy ? "登录中…" : "登录" }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-submit {
  width: 100%;
  height: 36px;
  margin-top: var(--space-xs);
}
</style>
