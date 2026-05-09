<template>
  <article class="rounded-xl border border-gray-100 bg-white p-3.5 shadow-[0_2px_8px_-4px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-md">
    <div class="mb-3 flex items-center justify-between">
      <span class="truncate text-[13px] font-semibold text-gray-900">{{ displayTitle }}</span>
      <div class="ml-2 flex shrink-0 items-center gap-1.5">
        <div class="h-1.5 w-1.5 rounded-full" :class="statusDotClass"></div>
        <span class="text-[11px] font-medium" :class="statusTextClass">{{ statusText }}</span>
      </div>
    </div>

    <div class="flex gap-2">
      <div class="h-[60px] w-[60px] shrink-0 overflow-hidden rounded border border-gray-100 bg-[#F3F4F6] shadow-inner">
        <el-image
          v-if="sourcePreviewUrl"
          :src="sourcePreviewUrl"
          fit="cover"
          class="h-full w-full"
        >
          <template #error>
            <div class="flex h-full w-full items-center justify-center text-gray-300">
              <el-icon><Picture /></el-icon>
            </div>
          </template>
        </el-image>
        <div v-else class="flex h-full w-full items-center justify-center text-gray-300">
          <el-icon><Picture /></el-icon>
        </div>
      </div>

      <div class="flex flex-1 gap-2">
        <div
          v-for="slot in paddedGenerationTasks"
          :key="slot.key"
          class="relative h-[60px] w-[60px] shrink-0 overflow-hidden rounded border"
          :class="slotClassName(slot)"
        >
          <template v-if="slot.isEmpty">
            <div class="flex h-full w-full items-center justify-center bg-[#FAFAFA] text-gray-300">
              <span class="text-sm">...</span>
            </div>
          </template>

          <template v-else-if="isSuccessSlot(slot)">
            <el-image
              v-if="resolvePreviewUrl(slot.output_path)"
              :src="resolvePreviewUrl(slot.output_path)"
              fit="cover"
              class="h-full w-full"
            >
              <template #error>
                <div class="flex h-full w-full items-center justify-center bg-[#FAFAFA] text-green-500">
                  <el-icon><CircleCheckFilled /></el-icon>
                </div>
              </template>
            </el-image>
            <div v-else class="flex h-full w-full items-center justify-center bg-[#FAFAFA] text-green-500">
              <el-icon><CircleCheckFilled /></el-icon>
            </div>
            <div class="absolute bottom-0 right-0 translate-x-[20%] translate-y-[20%] rounded-full bg-white p-[1px]">
              <div class="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-green-500"></div>
            </div>
          </template>

          <template v-else-if="isProcessingSlot(slot)">
            <div class="flex h-full w-full items-center justify-center bg-blue-50/30 text-blue-500">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
          </template>

          <template v-else-if="slot.status === 'failed'">
            <button
              type="button"
              class="flex h-full w-full flex-col items-center justify-center gap-0.5 bg-red-50/50 text-red-500 transition-colors hover:bg-red-50"
              @click="$emit('retry-slot', slot)"
            >
              <el-icon><WarningFilled /></el-icon>
              <span class="text-[10px] font-medium leading-none">重试</span>
            </button>
          </template>

          <template v-else>
            <div class="flex h-full w-full items-center justify-center bg-[#FAFAFA] text-gray-300">
              <span class="text-sm">...</span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";
import {
  CircleCheckFilled,
  Loading,
  Picture,
  WarningFilled,
} from "@element-plus/icons-vue";

const props = defineProps({
  task: {
    type: Object,
    required: true,
  },
});

defineEmits(["retry-slot"]);

const sourcePreviewUrl = computed(() => resolvePreviewUrl(props.task.normalized_path || props.task.source_path));
const sourceIndexLabel = computed(() => String(props.task.source_index || 0).padStart(3, "0"));
const displayTitle = computed(() => props.task.source_name || `SKU_${sourceIndexLabel.value}.jpg`);

const statusText = computed(() => {
  if (props.task.status === "completed") {
    return "已完成";
  }
  if (props.task.status === "partial_success") {
    return "生成中";
  }
  if (props.task.status === "failed") {
    return "异常失败";
  }
  return "处理中";
});

const statusTextClass = computed(() => {
  if (props.task.status === "completed") {
    return "text-green-600";
  }
  if (props.task.status === "failed") {
    return "text-red-500";
  }
  return "text-blue-500";
});

const statusDotClass = computed(() => {
  if (props.task.status === "completed") {
    return "bg-green-500";
  }
  if (props.task.status === "failed") {
    return "bg-red-500";
  }
  return "bg-blue-500";
});

const paddedGenerationTasks = computed(() => {
  const slots = (props.task.generation_tasks || []).map((slot) => ({
    ...slot,
    key: slot.id,
    isEmpty: false,
  }));

  while (slots.length < 3) {
    slots.push({
      key: `empty-${props.task.id}-${slots.length + 1}`,
      isEmpty: true,
    });
  }

  return slots.slice(0, 3);
});

function resolvePreviewUrl(path) {
  if (!path || typeof path !== "string") {
    return "";
  }
  if (
    path.startsWith("http://") ||
    path.startsWith("https://") ||
    path.startsWith("/") ||
    path.startsWith("data:image/")
  ) {
    return path.replaceAll("\\", "/");
  }
  return "";
}

function isSuccessSlot(slot) {
  return slot.status === "success" || slot.status === "fallback_success";
}

function isProcessingSlot(slot) {
  return slot.status === "processing" || slot.status === "retrying";
}

function slotClassName(slot) {
  if (slot.isEmpty) {
    return "border-dashed border-gray-300 bg-[#FAFAFA]";
  }
  if (isSuccessSlot(slot)) {
    return "border-gray-100 bg-[#FAFAFA]";
  }
  if (isProcessingSlot(slot)) {
    return "border border-dashed border-blue-400";
  }
  if (slot.status === "failed") {
    return "border border-red-200";
  }
  return "border border-dashed border-gray-300 bg-[#FAFAFA]";
}
</script>
