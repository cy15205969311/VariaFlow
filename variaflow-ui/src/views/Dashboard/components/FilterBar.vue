<template>
  <section class="flex flex-col gap-4 border-b border-gray-200 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-[18px] md:pb-[14px]">
    <div class="flex items-center gap-3">
      <h3 class="m-0 text-[15px] font-bold text-gray-900">任务列表</h3>
      <span class="text-[13px] text-gray-400">共 {{ total }} 个任务</span>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <button class="flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-medium text-gray-600 shadow-sm transition-colors hover:bg-gray-50">
        <el-icon class="text-gray-400"><Grid /></el-icon>
        紧凑视图
      </button>

      <el-radio-group
        :model-value="modelValue"
        class="filter-bar__radios"
        @update:model-value="handleFilterChange"
      >
        <el-radio-button
          v-for="option in options"
          :key="option.value"
          :label="option.value"
        >
          {{ option.label }}
        </el-radio-button>
      </el-radio-group>

      <div class="relative">
        <el-icon class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300"><Search /></el-icon>
        <input
          type="text"
          placeholder="搜索文件名"
          class="w-[180px] rounded-md border border-gray-200 bg-white py-1.5 pl-9 pr-4 text-[12px] text-gray-700 outline-none transition-all placeholder:text-gray-400 focus:border-gray-400 focus:ring-1 focus:ring-gray-200"
        />
      </div>

      <div class="flex items-center gap-3">
        <el-switch
          :model-value="autoRefresh"
          inline-prompt
          active-text="自动"
          inactive-text="手动"
          @change="handleAutoRefreshChange"
        />
        <el-button type="primary" plain :loading="loading" @click="$emit('refresh')">
          刷新
        </el-button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { Grid, Search } from "@element-plus/icons-vue";

defineProps({
  modelValue: {
    type: String,
    default: "all",
  },
  autoRefresh: {
    type: Boolean,
    default: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  total: {
    type: Number,
    default: 0,
  },
  visibleTotal: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(["update:modelValue", "update:autoRefresh", "refresh"]);

const options = [
  { label: "全部状态", value: "all" },
  { label: "处理中", value: "processing" },
  { label: "成功", value: "success" },
  { label: "异常失败", value: "failed" },
];

function handleFilterChange(value) {
  emit("update:modelValue", value);
}

function handleAutoRefreshChange(value) {
  emit("update:autoRefresh", value);
}
</script>

<style scoped>
.filter-bar__radios :deep(.el-radio-button__inner) {
  min-width: 84px;
  min-height: 34px;
  border-radius: 10px;
  box-shadow: none;
  font-size: 12px;
}
</style>
