<template>
  <div class="flex flex-col gap-6">
    <section>
      <p class="m-0 text-[12px] font-medium text-gray-500">今日任务</p>
    </section>

    <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="总任务数"
        :value="formatStat(totalGenerationCount)"
        hint="当前批次累计变体任务"
        tone="neutral"
      />
      <StatCard
        title="正在生成"
        :value="formatStat(processingGenerationCount)"
        hint="包含排队、处理中与重试中"
        tone="info"
      />
      <StatCard
        title="成功落盘"
        :value="formatStat(successGenerationCount)"
        hint="已通过规则质检并写入输出目录"
        tone="success"
      />
      <StatCard
        title="异常失败"
        :value="formatStat(failedGenerationCount)"
        hint="可在下方任务卡片中查看并手动重试"
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
        <el-tag :type="statusTagType" effect="plain">{{ batchInfo.status || "idle" }}</el-tag>
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
          :disabled="!batchStore.currentBatchId || batchStore.loadingBatch"
          @click="refreshBatch"
        >
          刷新状态
        </el-button>
      </div>
    </section>

    <TaskBoard />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, watch } from "vue";
import { ElMessage } from "element-plus";

import StatCard from "@/views/Dashboard/components/StatCard.vue";
import TaskBoard from "@/views/Dashboard/TaskBoard.vue";
import UploadEngine from "@/views/Dashboard/components/UploadEngine.vue";
import { useBatchStore } from "@/stores/batch";

const batchStore = useBatchStore();

const batchInfo = computed(() => batchStore.batchInfo);

const activeBatchLabel = computed(() => {
  if (!batchStore.currentBatchId) {
    return "未开始";
  }
  return `#${batchStore.currentBatchId}`;
});

const totalGenerationCount = computed(() => batchInfo.value?.total_generation_count || 0);
const successGenerationCount = computed(() => batchInfo.value?.success_generation_count || 0);
const failedGenerationCount = computed(() => batchInfo.value?.failed_generation_count || 0);
const processingGenerationCount = computed(() =>
  Math.max(
    totalGenerationCount.value - successGenerationCount.value - failedGenerationCount.value,
    0
  )
);

const remainingLabel = computed(() => {
  if (batchInfo.value?.estimated_remaining_seconds === 0) {
    return "0s";
  }

  if (!batchInfo.value?.estimated_remaining_seconds) {
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

async function handleUploadSuccess(batchId) {
  batchStore.setCurrentBatchId(batchId);
  try {
    await batchStore.refreshAll(batchId);
    batchStore.startPolling(batchId);
  } catch (error) {
    console.error("批次上传成功，但拉取批次详情或任务列表失败", error);
    ElMessage.error("上传已完成，但批次详情加载失败，请点击刷新状态或查看控制台日志");
    throw error;
  }
}

async function refreshBatch() {
  if (!batchStore.currentBatchId) {
    return;
  }
  await batchStore.refreshAll(batchStore.currentBatchId);
}

watch(
  () => batchStore.currentBatchId,
  async (batchId) => {
    batchStore.stopPolling();
    if (!batchId) {
      return;
    }

    await batchStore.refreshAll(batchId);
    batchStore.startPolling(batchId);
  },
  { immediate: true, flush: "post" }
);

onBeforeUnmount(() => {
  batchStore.stopPolling();
});
</script>
