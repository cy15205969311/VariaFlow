<template>
  <div class="flex flex-col gap-6">
    <section>
      <p class="m-0 text-[12px] font-medium text-gray-500">今日任务</p>
    </section>

    <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="总任务"
        :value="formatStat(totalGenerationCount)"
        hint="较昨日 +12.5%"
        tone="neutral"
      />
      <StatCard
        title="正在生成"
        :value="formatStat(processingGenerationCount)"
        hint="并行处理中"
        tone="info"
      />
      <StatCard
        title="成功落盘"
        :value="formatStat(successGenerationCount)"
        hint="成功率 98.2%"
        tone="success"
      />
      <StatCard
        title="质检异常"
        :value="formatStat(failedGenerationCount)"
        hint="需人工复核"
        tone="danger"
      />
    </section>

    <UploadEngine @upload-success="handleUploadSuccess" />

    <section
      v-if="batchInfo"
      class="grid grid-cols-2 gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm lg:grid-cols-6"
    >
      <div class="flex flex-col gap-1">
        <span class="text-[11px] text-gray-400">当前批次</span>
        <strong class="text-[13px] font-semibold text-gray-900">{{ activeBatchLabel }}</strong>
      </div>
      <div class="flex flex-col gap-1">
        <span class="text-[11px] text-gray-400">批次状态</span>
        <el-tag :type="statusTagType" effect="plain">{{ batchInfo?.status || "idle" }}</el-tag>
      </div>
      <div class="flex flex-col gap-1">
        <span class="text-[11px] text-gray-400">原图数量</span>
        <strong class="text-[13px] font-semibold text-gray-900">{{ batchInfo.total_source_count }}</strong>
      </div>
      <div class="flex flex-col gap-1">
        <span class="text-[11px] text-gray-400">部分成功</span>
        <strong class="text-[13px] font-semibold text-gray-900">{{ batchInfo.partial_source_count }}</strong>
      </div>
      <div class="flex flex-col gap-1">
        <span class="text-[11px] text-gray-400">预计剩余</span>
        <strong class="text-[13px] font-semibold text-gray-900">{{ remainingLabel }}</strong>
      </div>
      <div class="flex items-end justify-start lg:justify-end">
        <el-button
          text
          type="primary"
          :disabled="!appStore.currentBatchId || loadingBatch"
          @click="refreshBatch"
        >
          刷新状态
        </el-button>
      </div>
    </section>

    <TaskBoard :batch-id="appStore.currentBatchId" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";

import { getBatchInfo } from "@/api/batch";
import { useAppStore } from "@/stores/app";
import StatCard from "@/views/Dashboard/components/StatCard.vue";
import TaskBoard from "@/views/Dashboard/TaskBoard.vue";
import UploadEngine from "@/views/Dashboard/components/UploadEngine.vue";

const appStore = useAppStore();

const batchInfo = ref(null);
const loadingBatch = ref(false);
let pollingTimer = null;

const activeBatchLabel = computed(() => {
  if (!appStore.currentBatchId) {
    return "未开始";
  }
  return `#${appStore.currentBatchId}`;
});

const totalGenerationCount = computed(() => batchInfo.value?.total_generation_count || 1246);
const successGenerationCount = computed(() => batchInfo.value?.success_generation_count || 8532);
const failedGenerationCount = computed(() => batchInfo.value?.failed_generation_count || 23);
const processingGenerationCount = computed(() =>
  Math.max(
    totalGenerationCount.value - successGenerationCount.value - failedGenerationCount.value,
    312
  )
);

const remainingLabel = computed(() => {
  if (!batchInfo.value?.estimated_remaining_seconds && batchInfo.value?.estimated_remaining_seconds !== 0) {
    return "--";
  }
  return `${batchInfo.value.estimated_remaining_seconds}s`;
});

const statusTagType = computed(() => {
  const status = batchInfo.value?.status;
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "partial_success") {
    return "warning";
  }
  return "info";
});

function formatStat(value) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

async function fetchBatch(batchId) {
  if (!batchId) {
    return;
  }

  loadingBatch.value = true;
  try {
    const data = await getBatchInfo(batchId);
    batchInfo.value = data;
  } finally {
    loadingBatch.value = false;
  }
}

function stopPolling() {
  if (pollingTimer) {
    window.clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

function startPolling(batchId) {
  stopPolling();
  pollingTimer = window.setInterval(() => {
    fetchBatch(batchId);
  }, 3000);
}

async function handleUploadSuccess(batchId) {
  appStore.setCurrentBatchId(batchId);
  await fetchBatch(batchId);
  startPolling(batchId);
}

async function refreshBatch() {
  if (!appStore.currentBatchId) {
    return;
  }
  await fetchBatch(appStore.currentBatchId);
}

onBeforeUnmount(() => {
  stopPolling();
});
</script>
