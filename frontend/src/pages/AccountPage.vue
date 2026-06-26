<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import PageHeader from "@/components/PageHeader.vue";
import { changeCredentials, getPlatformSettings } from "@/api/platform";
import { clearSession } from "@/api/client";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
const router = useRouter();

const form = ref({
  current_password: "",
  new_username: "",
  new_password: "",
  confirm: "",
});
const adminUsername = ref("");
const touched = ref(false);

const passwordMismatch = computed(
  () => touched.value && form.value.new_password && form.value.new_password !== form.value.confirm,
);

onMounted(async () => {
  try {
    const s = await getPlatformSettings();
    adminUsername.value = s.admin_username;
    form.value.new_username = s.admin_username;
  } catch {
    /* ignore */
  }
});

async function submit() {
  touched.value = true;
  if (passwordMismatch.value) {
    ui.showMessage("两次密码不一致", "error");
    return;
  }
  try {
    await changeCredentials({
      current_password: form.value.current_password,
      new_username: form.value.new_username || undefined,
      new_password: form.value.new_password || undefined,
    });
    clearSession();
    ui.showMessage("凭据已更新，请重新登录", "warn");
    router.push({ name: "login", query: { reason: "credentials_changed" } });
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String((e as { message: string }).message) : "失败";
    ui.showMessage(msg, "error");
  }
}
</script>

<template>
  <PageHeader title="账户" description="Admin 登录凭据">
    <template #actions>
      <router-link class="btn btn--secondary" to="/settings">返回设置</router-link>
    </template>
  </PageHeader>

  <div class="panel">
    <div class="panel__body">
      <p class="account-hint">当前用户：<strong>{{ adminUsername || "admin" }}</strong></p>
      <div class="form-grid">
        <label class="form-field form-field--full">
          <span class="form-field__label">当前密码</span>
          <input v-model="form.current_password" type="password" autocomplete="current-password" />
        </label>
        <label class="form-field">
          <span class="form-field__label">新用户名</span>
          <input v-model="form.new_username" type="text" :placeholder="adminUsername" autocomplete="username" />
        </label>
        <label class="form-field">
          <span class="form-field__label">新密码</span>
          <input v-model="form.new_password" type="password" autocomplete="new-password" />
        </label>
        <label class="form-field" :class="{ 'form-field--error': passwordMismatch }">
          <span class="form-field__label">确认密码</span>
          <input
            v-model="form.confirm"
            type="password"
            autocomplete="new-password"
            @blur="touched = true"
          />
          <span v-if="passwordMismatch" class="form-field__error">两次密码不一致</span>
        </label>
      </div>
      <div class="page-actions">
        <button type="button" class="btn btn--primary" @click="submit">保存</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-field--full {
  grid-column: 1 / -1;
}

.account-hint {
  margin: 0 0 var(--space-md);
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}
</style>
