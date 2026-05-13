<template>
  <article
    class="rounded-xl border border-gray-100 bg-white shadow-[0_2px_8px_-4px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-md"
    :class="compact ? 'p-3' : 'p-3.5'"
  >
    <div class="flex items-start justify-between gap-3" :class="compact ? 'mb-2.5' : 'mb-3'">
      <div class="min-w-0 flex-1">
        <div class="truncate text-[13px] font-semibold text-gray-900">{{ displayTitle }}</div>
        <div v-if="intentLabel" class="mt-1">
          <el-tooltip
            effect="dark"
            placement="top"
            popper-class="task-intent-tooltip"
          >
            <template #content>
              <div class="max-w-[280px] space-y-1.5 text-[12px] leading-5">
                <div class="font-semibold text-white">{{ intentLabel }}</div>
                <div v-if="intentReason" class="whitespace-normal break-words text-slate-100">
                  {{ intentReason }}
                </div>
                <div
                  v-if="subjectFeatures"
                  class="rounded-md border border-white/10 bg-white/5 px-2 py-1.5 text-slate-100"
                >
                  <div class="mb-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-300">
                    Subject Features
                  </div>
                  <div class="whitespace-normal break-words leading-5">
                    {{ subjectFeatures }}
                  </div>
                </div>
              </div>
            </template>
            <span
              class="inline-flex items-center rounded-full px-2 py-[2px] text-[10px] font-semibold"
              :class="intentTagClass"
            >
              {{ intentLabel }}
            </span>
          </el-tooltip>
        </div>
      </div>
      <div class="ml-2 flex shrink-0 items-center gap-1.5">
        <div class="h-1.5 w-1.5 rounded-full" :class="statusDotClass"></div>
        <span class="text-[11px] font-medium" :class="statusTextClass">{{ statusText }}</span>
      </div>
    </div>

    <div class="flex gap-2" :class="compact ? 'items-start' : ''">
      <div
        class="shrink-0 overflow-hidden rounded border border-gray-100 bg-[#F3F4F6] shadow-inner"
        :class="[
          compact ? 'h-[56px] w-[56px]' : 'h-[60px] w-[60px]',
          sourcePreviewUrl ? 'cursor-zoom-in transition-opacity duration-200 hover:opacity-90' : '',
        ]"
        :role="sourcePreviewUrl ? 'button' : undefined"
        :tabindex="sourcePreviewUrl ? 0 : undefined"
        @click="emitPreview(sourcePreviewUrl, `${displayTitle} 原图预览`)"
        @keydown.enter.prevent="emitPreview(sourcePreviewUrl, `${displayTitle} 原图预览`)"
        @keydown.space.prevent="emitPreview(sourcePreviewUrl, `${displayTitle} 原图预览`)"
      >
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
          class="relative shrink-0 overflow-hidden rounded border"
          :class="[
            compact ? 'h-[56px] w-[56px]' : 'h-[60px] w-[60px]',
            slotClassName(slot),
            isPreviewableSlot(slot) ? 'cursor-zoom-in transition-opacity duration-200 hover:opacity-90' : '',
          ]"
          :role="isPreviewableSlot(slot) ? 'button' : undefined"
          :tabindex="isPreviewableSlot(slot) ? 0 : undefined"
          @click="handleSlotPreview(slot)"
          @keydown.enter.prevent="handleSlotPreview(slot)"
          @keydown.space.prevent="handleSlotPreview(slot)"
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

            <div class="absolute inset-x-1 bottom-1 flex items-center justify-between">
              <div class="h-3.5 w-3.5 rounded-full border border-white bg-green-500"></div>
              <span
                v-if="slot.status === 'fallback_success'"
                class="rounded bg-amber-500/90 px-1 py-[1px] text-[9px] font-semibold text-white"
              >
                Wanx
              </span>
            </div>
          </template>

          <template v-else-if="isProcessingSlot(slot)">
            <div class="flex h-full w-full items-center justify-center bg-blue-50/30 text-blue-500">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
          </template>

          <template v-else-if="slot.status === 'failed'">
            <el-tooltip
              effect="dark"
              placement="top"
              :content="slot.last_error_message || slot.last_error_code || '任务执行失败，请重试'"
            >
              <button
                type="button"
                class="flex h-full w-full flex-col items-center justify-center gap-0.5 bg-red-50/50 text-red-500 transition-colors hover:bg-red-50"
                @click="$emit('retry-slot', slot)"
              >
                <el-icon><WarningFilled /></el-icon>
                <span class="text-[10px] font-medium leading-none">重试</span>
              </button>
            </el-tooltip>
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
  compact: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["retry-slot", "preview-image"]);

const sourcePreviewUrl = computed(() => resolvePreviewUrl(props.task.normalized_path || props.task.source_path));
const sourceIndexLabel = computed(() => String(props.task.source_index || 0).padStart(3, "0"));
const displayTitle = computed(() => props.task.source_name || `SKU_${sourceIndexLabel.value}.jpg`);
const primarySlot = computed(() => (props.task.generation_tasks || [])[0] || null);
const intentLabel = computed(() => primarySlot.value?.intent_label || primarySlot.value?.intent || "");
const intentReason = computed(() => primarySlot.value?.intent_reason || "");
const subjectFeatures = computed(() => primarySlot.value?.subject_features || "");
const intentTagClass = computed(() => {
  const intent = primarySlot.value?.intent;
  if (intent === "POSE_VARIATION") {
    return "bg-violet-50 text-violet-700 ring-1 ring-violet-200";
  }
  if (intent === "SCENE_EDIT") {
    return "bg-sky-50 text-sky-700 ring-1 ring-sky-200";
  }
  return "bg-gray-50 text-gray-600 ring-1 ring-gray-200";
});

const statusText = computed(() => {
  if (props.task.status === "completed") {
    return "已完成";
  }
  if (props.task.status === "partial_success") {
    return "部分成功";
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
  if (props.task.status === "partial_success") {
    return "text-amber-500";
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
  if (props.task.status === "partial_success") {
    return "bg-amber-500";
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
    path.startsWith("data:image/")
  ) {
    return path.replaceAll("\\", "/");
  }

  if (path.startsWith("/static/")) {
    return path.replaceAll("\\", "/");
  }

  if (path.startsWith("/")) {
    return `http://127.0.0.1:8000${path.replaceAll("\\", "/")}`;
  }

  return "";
}

function isSuccessSlot(slot) {
  return slot.status === "success" || slot.status === "fallback_success";
}

function isPreviewableSlot(slot) {
  return isSuccessSlot(slot) && !!resolvePreviewUrl(slot.output_path);
}

function isProcessingSlot(slot) {
  return slot.status === "processing" || slot.status === "retrying";
}

function emitPreview(url, alt) {
  if (!url) {
    return;
  }

  emit("preview-image", {
    url,
    alt,
  });
}

function handleSlotPreview(slot) {
  if (!isPreviewableSlot(slot)) {
    return;
  }

  emitPreview(
    resolvePreviewUrl(slot.output_path),
    `${displayTitle.value} 生成结果预览`
  );
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
  if (slot.status === "pending") {
    return "border-dashed border-gray-300 bg-[#FAFAFA]";
  }
  return "border border-dashed border-gray-300 bg-[#FAFAFA]";
}
</script>
