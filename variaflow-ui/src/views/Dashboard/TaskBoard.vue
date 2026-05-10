<template>
  <section class="flex flex-col">
    <article v-if="!batchStore.currentBatchId" class="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
      <el-empty description="上传 ZIP 批次后，这里会展示任务列表、生成状态和变体缩略图。" />
    </article>

    <article v-else class="rounded-xl border border-gray-100 bg-white shadow-sm">
      <FilterBar
        v-model="activeFilter"
        v-model:compact="compactView"
        v-model:search-keyword="searchKeyword"
        :total="batchStore.taskList.length"
        :visible-total="filteredTasks.length"
      />

      <div
        v-if="batchStore.loadingTasks && !filteredTasks.length"
        class="grid grid-cols-1 gap-4 px-[18px] pb-[18px] lg:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="index in 9"
          :key="index"
          class="rounded-xl border border-gray-100 bg-white p-3.5 shadow-[0_2px_8px_-4px_rgba(0,0,0,0.05)]"
        >
          <el-skeleton animated>
            <template #template>
              <el-skeleton-item variant="p" style="width: 48%;" />
              <div class="mt-3 grid grid-cols-4 gap-2">
                <el-skeleton-item
                  v-for="slot in 4"
                  :key="slot"
                  variant="image"
                  style="width: 100%; height: 60px; border-radius: 8px;"
                />
              </div>
            </template>
          </el-skeleton>
        </div>
      </div>

      <el-empty
        v-else-if="!filteredTasks.length"
        description="当前筛选条件下暂无任务"
      />

      <div
        v-else
        v-bind="containerProps"
        class="task-board-scroll px-[18px] pb-[18px]"
      >
        <div v-bind="wrapperProps">
          <div
            v-for="row in virtualRows"
            :key="row.index"
            class="grid grid-cols-1 pb-4 lg:grid-cols-2 xl:grid-cols-3"
            :class="compactView ? 'gap-3' : 'gap-4'"
          >
            <TaskCard
              v-for="task in row.data"
              :key="task.id"
              :task="task"
              :compact="compactView"
              @retry-slot="handleRetrySlot"
            />
          </div>
        </div>
      </div>

      <footer
        v-if="filteredTasks.length"
        class="flex flex-col gap-4 border-t border-gray-200 px-[18px] py-4 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="text-[12px] text-gray-500">
          <span v-if="batchStore.silentRefreshing" class="text-blue-500">后台静默同步中</span>
          <span v-else>虚拟列表已启用，当前共渲染 {{ virtualRows.length }} 行可视区域</span>
        </div>
        <div class="text-[12px] text-gray-400">
          当前过滤结果 {{ filteredTasks.length }} 条，按 3 列网格分组虚拟渲染。
        </div>
      </footer>
    </article>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useVirtualList } from "@vueuse/core";
import { ElMessage } from "element-plus";

import { retryGenerationTask } from "@/api/task";
import { useBatchStore } from "@/stores/batch";
import FilterBar from "@/views/Dashboard/components/FilterBar.vue";
import TaskCard from "@/views/Dashboard/components/TaskCard.vue";

const GRID_COLUMNS = 3;
const ROW_HEIGHT = 112;
const ACTIVE_SLOT_STATUSES = new Set(["pending", "processing", "retrying"]);
const SUCCESS_SLOT_STATUSES = new Set(["success", "fallback_success"]);

const batchStore = useBatchStore();
const activeFilter = ref("all");
const searchKeyword = ref("");
const compactView = ref(true);

const filteredTasks = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();

  return batchStore.taskList.filter((task) => {
    const statusMatched = activeFilter.value === "all" || matchesFilter(task, activeFilter.value);
    if (!statusMatched) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const sourceName = String(task.source_name || "").toLowerCase();
    return sourceName.includes(keyword);
  });
});

const taskRows = computed(() => {
  const rows = [];
  for (let index = 0; index < filteredTasks.value.length; index += GRID_COLUMNS) {
    rows.push(filteredTasks.value.slice(index, index + GRID_COLUMNS));
  }
  return rows;
});

const { list: virtualRows, containerProps, wrapperProps } = useVirtualList(taskRows, {
  itemHeight: ROW_HEIGHT,
  overscan: 6,
});

function matchesFilter(task, filter) {
  const slots = task.generation_tasks || [];
  const hasActiveSlot = slots.some((slot) => ACTIVE_SLOT_STATUSES.has(slot.status));
  const allSuccess = slots.length > 0 && slots.every((slot) => SUCCESS_SLOT_STATUSES.has(slot.status));
  const hasFailedSlot = slots.some((slot) => slot.status === "failed");

  if (filter === "processing") {
    return hasActiveSlot;
  }
  if (filter === "success") {
    return allSuccess;
  }
  if (filter === "failed") {
    return hasFailedSlot && !hasActiveSlot;
  }
  return true;
}

async function handleRetrySlot(slot) {
  const previousState = {
    status: slot.status,
    last_error_code: slot.last_error_code,
    last_error_message: slot.last_error_message,
    qc_status: slot.qc_status,
  };

  batchStore.patchGenerationTask(slot.id, {
    status: "processing",
    last_error_code: null,
    last_error_message: null,
    qc_status: "pending",
  });

  try {
    await retryGenerationTask(slot.id);
    ElMessage.success(`变体槽位 #${slot.variant_index} 已提交重试`);
    await batchStore.refreshAll(batchStore.currentBatchId, { silent: true });
  } catch (error) {
    batchStore.patchGenerationTask(slot.id, previousState);
    throw error;
  }
}

watch([activeFilter, searchKeyword], () => {
  const containerElement = containerProps.ref?.value;
  if (containerElement) {
    containerElement.scrollTop = 0;
  }
});
</script>

<style scoped>
.task-board-scroll {
  height: 640px;
  overflow-y: auto;
}
</style>
