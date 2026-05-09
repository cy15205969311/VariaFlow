import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "@/layout/MainLayout.vue";
import DashboardView from "@/views/Dashboard/index.vue";
import PromptPresetsView from "@/views/PromptPresets/index.vue";

const routes = [
  {
    path: "/",
    component: MainLayout,
    redirect: "/dashboard",
    children: [
      {
        path: "dashboard",
        name: "dashboard",
        component: DashboardView,
      },
      {
        path: "prompt-presets",
        name: "prompt-presets",
        component: PromptPresetsView,
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
