<template>
  <article class="relative flex h-[116px] flex-col rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
    <div class="mb-2 flex items-start justify-between">
      <div class="text-[14px] font-medium text-gray-600">{{ title }}</div>
      <div
        class="flex h-10 w-10 items-center justify-center rounded-full border"
        :class="badgeClass"
      >
        <div class="h-4 w-4 rounded-full" :class="coreClass"></div>
      </div>
    </div>

    <div class="absolute bottom-5 left-5 right-5 flex flex-col">
      <div class="mb-1.5 text-[28px] font-bold leading-none tracking-tight" :class="valueClass">
        {{ value }}
      </div>
      <div class="text-[12px] text-gray-500">{{ hint }}</div>
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number],
    required: true,
  },
  hint: {
    type: String,
    default: "",
  },
  tone: {
    type: String,
    default: "neutral",
  },
});

const badgeClass = computed(() => {
  if (props.tone === "info") {
    return "border-blue-100 bg-blue-50";
  }
  if (props.tone === "success") {
    return "border-green-100 bg-green-50";
  }
  if (props.tone === "danger") {
    return "border-red-100 bg-red-50";
  }
  return "border-gray-200 bg-gray-100";
});

const coreClass = computed(() => {
  if (props.tone === "info") {
    return "bg-blue-500 shadow-[0_0_0_6px_rgba(59,130,246,0.12)]";
  }
  if (props.tone === "success") {
    return "bg-green-500 shadow-[0_0_0_6px_rgba(16,185,129,0.12)]";
  }
  if (props.tone === "danger") {
    return "bg-red-500 shadow-[0_0_0_6px_rgba(239,68,68,0.12)]";
  }
  return "bg-gray-700 shadow-[0_0_0_6px_rgba(55,65,81,0.08)]";
});

const valueClass = computed(() => {
  if (props.tone === "info") {
    return "text-blue-600";
  }
  if (props.tone === "success") {
    return "text-green-600";
  }
  if (props.tone === "danger") {
    return "text-red-600";
  }
  return "text-gray-900";
});
</script>
