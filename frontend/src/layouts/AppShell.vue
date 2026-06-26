<script setup lang="ts">
import { onMounted } from "vue";
import { RouterView } from "vue-router";
import TopBar from "@/components/TopBar.vue";
import SidebarNav from "@/layouts/SidebarNav.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
onMounted(() => auth.hydrate());
</script>

<template>
  <a href="#main-content" class="skip-link">跳到主内容</a>
  <div class="app-shell">
    <TopBar />
    <div class="app-body">
      <SidebarNav />
      <main id="main-content" class="app-main" tabindex="-1">
        <RouterView />
      </main>
    </div>
  </div>
</template>
