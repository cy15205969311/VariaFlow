import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { getBatchInfo } from "@/api/batch";
import { getTasks } from "@/api/task";

const POLLING_INTERVAL = 3000;
const FETCH_PAGE_SIZE = 200;
const TERMINAL_BATCH_STATUSES = new Set(["completed", "failed", "partial_success"]);

function mergeGenerationTasks(previousSlots = [], nextSlots = []) {
  const previousMap = new Map(previousSlots.map((slot) => [slot.id, slot]));

  return nextSlots.map((slot) => {
    const existing = previousMap.get(slot.id);
    if (!existing) {
      return { ...slot };
    }

    Object.assign(existing, slot);
    return existing;
  });
}

function mergeTaskListById(previousTasks = [], nextTasks = []) {
  const previousMap = new Map(previousTasks.map((task) => [task.id, task]));

  return nextTasks.map((task) => {
    const existing = previousMap.get(task.id);
    if (!existing) {
      return {
        ...task,
        generation_tasks: (task.generation_tasks || []).map((slot) => ({ ...slot })),
      };
    }

    const mergedSlots = mergeGenerationTasks(existing.generation_tasks, task.generation_tasks);
    Object.assign(existing, task, { generation_tasks: mergedSlots });
    return existing;
  });
}

export const useBatchStore = defineStore("batch", () => {
  const currentBatchId = ref(null);
  const batchInfo = ref(null);
  const taskList = ref([]);
  const loadingBatch = ref(false);
  const loadingTasks = ref(false);
  const silentRefreshing = ref(false);
  const pollingTimer = ref(null);
  const requestToken = ref(0);

  const hasActiveBatch = computed(() => Number.isInteger(currentBatchId.value) && currentBatchId.value > 0);

  function setCurrentBatchId(batchId) {
    currentBatchId.value = Number.isFinite(Number(batchId)) ? Number(batchId) : null;
  }

  function resetBatchState() {
    batchInfo.value = null;
    taskList.value = [];
    silentRefreshing.value = false;
    loadingBatch.value = false;
    loadingTasks.value = false;
    requestToken.value += 1;
  }

  async function fetchBatchStatus(batchId = currentBatchId.value, { silent = false } = {}) {
    if (!batchId) {
      batchInfo.value = null;
      return null;
    }

    if (!silent) {
      loadingBatch.value = true;
    }

    try {
      const data = await getBatchInfo(batchId);
      batchInfo.value = data;

      if (TERMINAL_BATCH_STATUSES.has(data?.status)) {
        stopPolling();
      }

      return data;
    } finally {
      if (!silent) {
        loadingBatch.value = false;
      }
    }
  }

  async function fetchTasks(batchId = currentBatchId.value, { silent = false, status } = {}) {
    if (!batchId) {
      taskList.value = [];
      return [];
    }

    if (loadingTasks.value || silentRefreshing.value) {
      return taskList.value;
    }

    const token = ++requestToken.value;
    if (silent) {
      silentRefreshing.value = true;
    } else {
      loadingTasks.value = true;
    }

    try {
      const firstPage = await getTasks({
        batch_id: batchId,
        status,
        page: 1,
        size: FETCH_PAGE_SIZE,
      });

      const total = firstPage?.total || 0;
      const totalPages = Math.max(1, Math.ceil(total / FETCH_PAGE_SIZE));
      const pages = [firstPage];

      if (totalPages > 1) {
        const restPages = await Promise.all(
          Array.from({ length: totalPages - 1 }, (_, index) =>
            getTasks({
              batch_id: batchId,
              status,
              page: index + 2,
              size: FETCH_PAGE_SIZE,
            })
          )
        );
        pages.push(...restPages);
      }

      if (token !== requestToken.value) {
        return taskList.value;
      }

      const mergedItems = pages
        .flatMap((page) => page?.items || [])
        .sort((left, right) => (left.source_index || 0) - (right.source_index || 0));

      taskList.value = mergeTaskListById(taskList.value, mergedItems);
      return taskList.value;
    } finally {
      if (token === requestToken.value) {
        silentRefreshing.value = false;
        loadingTasks.value = false;
      }
    }
  }

  async function refreshAll(batchId = currentBatchId.value, { silent = false } = {}) {
    if (!batchId) {
      return;
    }

    try {
      await Promise.all([
        fetchBatchStatus(batchId, { silent }),
        fetchTasks(batchId, { silent }),
      ]);
    } catch (error) {
      console.error("刷新批次状态或任务列表失败", {
        batchId,
        silent,
        error,
      });
      throw error;
    }
  }

  function stopPolling() {
    if (pollingTimer.value) {
      window.clearInterval(pollingTimer.value);
      pollingTimer.value = null;
    }
  }

  function startPolling(batchId = currentBatchId.value) {
    stopPolling();

    if (!batchId) {
      return;
    }

    pollingTimer.value = window.setInterval(async () => {
      await refreshAll(batchId, { silent: true });
    }, POLLING_INTERVAL);
  }

  function patchGenerationTask(taskId, patch) {
    for (const task of taskList.value) {
      const targetSlot = (task.generation_tasks || []).find((slot) => slot.id === taskId);
      if (targetSlot) {
        Object.assign(targetSlot, patch);
        return targetSlot;
      }
    }
    return null;
  }

  return {
    currentBatchId,
    batchInfo,
    taskList,
    loadingBatch,
    loadingTasks,
    silentRefreshing,
    pollingTimer,
    hasActiveBatch,
    setCurrentBatchId,
    resetBatchState,
    fetchBatchStatus,
    fetchTasks,
    refreshAll,
    startPolling,
    stopPolling,
    patchGenerationTask,
  };
});
