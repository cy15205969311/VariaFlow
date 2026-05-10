<template>
  <div class="flex min-h-screen bg-[#f4f5f7] font-sans text-zinc-900">
    <aside class="hidden w-[230px] shrink-0 border-r border-[#E5E7EB] bg-white lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:h-screen lg:flex-col lg:overflow-y-auto lg:pb-4">
      <div class="flex h-[68px] shrink-0 items-center px-6">
        <div class="mr-2.5 flex h-5 w-5 items-center justify-center rounded-md border border-zinc-200 bg-white shadow-sm">
          <span class="text-[9px] font-bold tracking-[0.2em] text-black">VF</span>
        </div>
        <span class="text-[17px] font-semibold tracking-tight text-gray-900">VariaFlow</span>
      </div>

      <div class="flex-1 space-y-1 px-3 py-2">
        <component
          :is="item.path ? RouterLink : 'button'"
          v-for="item in sidebarItems"
          :key="item.label"
          v-bind="item.path ? { to: item.path } : { type: 'button' }"
          class="flex w-full cursor-pointer items-center rounded-lg px-3 py-2.5 text-left text-[14px] transition-colors"
          :class="item.path && route.path === item.path
            ? 'bg-[#F4F4F5] font-semibold text-gray-900'
            : 'font-medium text-gray-600 hover:bg-[#F9FAFB]'"
        >
          <component :is="item.icon" class="mr-3 h-[18px] w-[18px]" :stroke-width="2" />
          <span>{{ item.label }}</span>
        </component>
      </div>

      <div class="relative mt-auto flex flex-col gap-6 px-6">
        <div class="flex flex-col gap-2">
          <div class="text-[12px] font-medium text-gray-500">API 调用总量</div>
          <div class="mb-1 text-[11px] text-gray-400">今日剩余额度</div>
          <div class="relative border-b border-gray-200 pb-3 text-[16px] font-semibold text-gray-900">
            98,720
            <span class="ml-1 text-[12px] font-normal text-gray-400">/ 100,000</span>
            <div class="absolute bottom-[-1px] left-0 h-[2px] w-[60%] rounded-r bg-blue-600"></div>
          </div>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100">
              <span class="text-xs font-semibold text-blue-600">VT</span>
            </div>
            <div class="flex flex-col">
              <span class="text-[13px] font-semibold text-gray-900">VariaFlow Team</span>
              <span class="text-[11px] text-gray-500">企业版</span>
            </div>
          </div>
          <el-icon class="text-gray-400"><ArrowDown /></el-icon>
        </div>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col lg:ml-[230px]">
      <header class="flex h-[68px] shrink-0 items-center justify-between border-b border-[#E5E7EB] bg-white px-4 md:px-6">
        <div class="flex items-center gap-2 text-sm">
          <span class="text-[14px] text-gray-500">控制台</span>
          <span class="text-gray-300">/</span>
          <span class="text-[14px] font-bold tracking-wide text-gray-900">{{ currentTitle }}</span>
        </div>

        <div class="flex items-center gap-4 md:gap-5">
          <div class="hidden items-center gap-2 text-[13px] font-medium text-gray-600 md:flex">
            <span>API 连通状态</span>
            <div class="ml-1 h-2 w-2 rounded-full bg-green-500 shadow-[0_0_0_3px_rgba(34,197,94,0.15)]"></div>
            <span class="text-green-500">正常</span>
          </div>

          <div class="relative cursor-pointer">
            <el-icon class="text-[18px] text-gray-500"><Bell /></el-icon>
            <div class="absolute right-[1px] top-[1px] h-1.5 w-1.5 rounded-full border border-white bg-red-500"></div>
          </div>

          <div class="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100">
            <span class="text-[11px] font-semibold text-blue-600">A</span>
          </div>
        </div>
      </header>

      <main class="flex-1 overflow-auto p-4 md:p-6">
        <div class="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";
import {
  ArrowDown,
  Bell,
  DataBoard,
  Files,
  MagicStick,
  Picture,
  Setting,
} from "@element-plus/icons-vue";

const route = useRoute();

const sidebarItems = [
  { path: "/dashboard", label: "控制台", icon: DataBoard },
  { label: "批量任务", icon: Files },
  { label: "资源管理", icon: Picture },
  { label: "模板管理", icon: Files },
  { label: "质检中心", icon: Files },
  { path: "/prompt-presets", label: "预设设计", icon: MagicStick },
  { label: "API 实况", icon: Files },
  { label: "系统设置", icon: Setting },
];

const titleMap = {
  "/dashboard": "批量任务大盘",
  "/prompt-presets": "预设设计",
};

const currentTitle = computed(() => titleMap[route.path] || "VariaFlow");
</script>
