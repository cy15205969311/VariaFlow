<template>
  <section class="flex flex-col">
    <article v-if="!batchId" class="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
      <el-empty description="上传 ZIP 批次后，这里会展示任务列表、生成状态和变体缩略图。" />
    </article>

    <article v-else class="rounded-xl border border-gray-100 bg-white shadow-sm">
      <FilterBar
        v-model="activeFilter"
        :auto-refresh="autoRefresh"
        :loading="loading"
        :total="taskList.length"
        :visible-total="paginatedTasks.length"
        @update:auto-refresh="handleAutoRefreshChange"
        @refresh="refreshNow"
      />

      <div v-if="loading" class="grid grid-cols-1 gap-4 px-[18px] pb-[18px] lg:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="index in pageSize"
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

      <div v-else class="grid grid-cols-1 gap-4 px-[18px] pb-[18px] lg:grid-cols-2 xl:grid-cols-3">
        <TaskCard
          v-for="task in paginatedTasks"
          :key="task.id"
          :task="task"
          @retry-slot="handleRetrySlot"
        />
      </div>

      <footer v-if="filteredTasks.length" class="flex flex-col gap-4 border-t border-gray-200 px-[18px] py-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="text-[12px] text-gray-500">
          <span v-if="silentRefreshing" class="text-blue-500">后台同步中</span>
          <span v-else>当前展示 {{ pageStart }} - {{ pageEnd }}</span>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            layout="prev, pager, next"
            :total="filteredTasks.length"
            background
          />

          <el-select v-model="pageSize" class="w-[100px]">
            <el-option
              v-for="option in pageSizeOptions"
              :key="option"
              :label="`${option} / 页`"
              :value="option"
            />
          </el-select>
        </div>
      </footer>
    </article>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { getTasks } from "@/api/task";
import FilterBar from "@/views/Dashboard/components/FilterBar.vue";
import TaskCard from "@/views/Dashboard/components/TaskCard.vue";

const props = defineProps({
  batchId: {
    type: Number,
    default: null,
  },
});

const PAGE_SIZE_FETCH = 200;
const POLL_INTERVAL = 4000;
const ACTIVE_SLOT_STATUSES = new Set(["pending", "processing", "retrying"]);
const SUCCESS_SLOT_STATUSES = new Set(["success", "fallback_success"]);

const activeFilter = ref("all");
const autoRefresh = ref(true);
const loading = ref(false);
const silentRefreshing = ref(false);
const taskList = ref([]);
const currentPage = ref(1);
const pageSize = ref(12);
const pageSizeOptions = [12, 20, 28, 36];

let pollingTimer = null;
let requestToken = 0;

const filteredTasks = computed(() => {
  if (activeFilter.value === "all") {
    return taskList.value;
  }
  return taskList.value.filter((task) => matchesFilter(task, activeFilter.value));
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / pageSize.value)));

const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return filteredTasks.value.slice(start, end);
});

const pageStart = computed(() => {
  if (!filteredTasks.value.length) {
    return 0;
  }
  return (currentPage.value - 1) * pageSize.value + 1;
});

const pageEnd = computed(() => {
  if (!filteredTasks.value.length) {
    return 0;
  }
  return Math.min(currentPage.value * pageSize.value, filteredTasks.value.length);
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

function mergeGenerationTasks(previousSlots = [], nextSlots = []) {
  const slotMap = new Map(previousSlots.map((slot) => [slot.id, slot]));
  return nextSlots.map((slot) => {
    const existing = slotMap.get(slot.id);
    if (!existing) {
      return slot;
    }
    Object.assign(existing, slot);
    return existing;
  });
}

function mergeTaskList(previousTasks = [], nextTasks = []) {
  const taskMap = new Map(previousTasks.map((task) => [task.id, task]));
  return nextTasks.map((task) => {
    const existing = taskMap.get(task.id);
    if (!existing) {
      return task;
    }
    const mergedSlots = mergeGenerationTasks(existing.generation_tasks, task.generation_tasks);
    Object.assign(existing, task, { generation_tasks: mergedSlots });
    return existing;
  });
}

async function fetchAllTaskPages(batchId) {
  const firstPage = await getTasks({
    batch_id: batchId,
    page: 1,
    size: PAGE_SIZE_FETCH,
  });
  const total = firstPage.total || 0;
  const totalPagesCount = Math.max(1, Math.ceil(total / PAGE_SIZE_FETCH));
  const pages = [firstPage];

  if (totalPagesCount > 1) {
    const otherPages = await Promise.all(
      Array.from({ length: totalPagesCount - 1 }, (_, index) =>
        getTasks({
          batch_id: batchId,
          page: index + 2,
          size: PAGE_SIZE_FETCH,
        })
      )
    );
    pages.push(...otherPages);
  }

  return pages
    .flatMap((page) => page.items || [])
    .sort((left, right) => (left.source_index || 0) - (right.source_index || 0));
}

async function loadTasks({ silent = false } = {}) {
  if (!props.batchId) {
    taskList.value = [];
    return;
  }

  if (silentRefreshing.value || loading.value) {
    return;
  }

  const token = ++requestToken;
  if (silent) {
    silentRefreshing.value = true;
  } else {
    loading.value = true;
  }

  try {
    const items = await fetchAllTaskPages(props.batchId);
    if (token !== requestToken) {
      return;
    }
    taskList.value = mergeTaskList(taskList.value, items);
  } finally {
    if (token === requestToken) {
      silentRefreshing.value = false;
      loading.value = false;
    }
  }
}

function stopPolling() {
  if (pollingTimer) {
    window.clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

function startPolling() {
  stopPolling();
  if (!props.batchId || !autoRefresh.value) {
    return;
  }
  pollingTimer = window.setInterval(() => {
    loadTasks({ silent: true });
  }, POLL_INTERVAL);
}

async function refreshNow() {
  await loadTasks();
}

function handleAutoRefreshChange(value) {
  autoRefresh.value = value;
  startPolling();
}

function handleRetrySlot(slot) {
  ElMessage.info(`变体槽位 #${slot.variant_index} 的重试接口待接入`);
}

watch(
  () => props.batchId,
  async (batchId) => {
    stopPolling();
    taskList.value = [];
    requestToken += 1;
    currentPage.value = 1;
    if (!batchId) {
      return;
    }
    await loadTasks();
    startPolling();
  },
  { immediate: true }
);

watch(activeFilter, () => {
  currentPage.value = 1;
});

watch(pageSize, () => {
  currentPage.value = 1;
});

watch(filteredTasks, () => {
  if (currentPage.value > totalPages.value) {
    currentPage.value = totalPages.value;
  }
});

watch(autoRefresh, () => {
  startPolling();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>
