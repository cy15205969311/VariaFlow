<template>
  <section class="filter-bar">
    <div class="filter-bar__summary">
      <h3 class="filter-bar__title">任务列表</h3>
      <span class="filter-bar__meta">共 {{ total }} 个任务</span>
    </div>

    <div class="filter-bar__actions">
      <button
        type="button"
        class="filter-bar__button"
        :class="{ 'filter-bar__button--active': compact }"
        @click="emit('update:compact', !compact)"
      >
        <el-icon><Grid /></el-icon>
        <span>紧凑视图</span>
      </button>

      <el-select
        :model-value="modelValue"
        class="filter-bar__select"
        placeholder="全部状态"
        @update:model-value="(value) => emit('update:modelValue', value)"
      >
        <el-option
          v-for="option in options"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>

      <el-input
        :model-value="searchKeyword"
        class="filter-bar__search"
        clearable
        placeholder="搜索文件名"
        @update:model-value="(value) => emit('update:searchKeyword', value || '')"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
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
  compact: {
    type: Boolean,
    default: false,
  },
  searchKeyword: {
    type: String,
    default: "",
  },
  total: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(["update:modelValue", "update:compact", "update:searchKeyword"]);

const options = [
  { label: "全部状态", value: "all" },
  { label: "处理中", value: "processing" },
  { label: "成功", value: "success" },
  { label: "异常失败", value: "failed" },
];
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 18px 14px;
}

.filter-bar__summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.filter-bar__title {
  margin: 0;
  color: #111827;
  font-size: 15px;
  font-weight: 700;
  white-space: nowrap;
}

.filter-bar__meta {
  color: #9ca3af;
  font-size: 13px;
  white-space: nowrap;
}

.filter-bar__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-bar__button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #ffffff;
  padding: 0 14px;
  color: #4b5563;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: all 0.18s ease;
}

.filter-bar__button:hover {
  background: #f9fafb;
}

.filter-bar__button--active {
  border-color: #bfdbfe;
  background: rgba(239, 246, 255, 0.9);
  color: #2563eb;
}

.filter-bar__select {
  width: 120px;
}

.filter-bar__search {
  width: 200px;
}

.filter-bar__select :deep(.el-input__wrapper),
.filter-bar__search :deep(.el-input__wrapper) {
  min-height: 36px;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.filter-bar__search :deep(.el-input__prefix) {
  color: #9ca3af;
}

@media (max-width: 960px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-bar__summary {
    justify-content: space-between;
  }

  .filter-bar__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .filter-bar {
    padding: 14px 14px 12px;
  }

  .filter-bar__summary {
    flex-wrap: wrap;
    gap: 8px;
  }

  .filter-bar__actions {
    gap: 12px;
  }

  .filter-bar__select,
  .filter-bar__search {
    width: 100%;
  }
}
</style>
