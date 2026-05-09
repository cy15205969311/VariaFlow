import { computed, ref } from "vue";
import { defineStore } from "pinia";

export const useAppStore = defineStore("app", () => {
  const theme = ref("light");
  const currentBatchId = ref(null);

  const isDark = computed(() => theme.value === "dark");

  function toggleTheme(nextTheme) {
    theme.value = nextTheme || (theme.value === "light" ? "dark" : "light");
    document.documentElement.classList.toggle("dark", theme.value === "dark");
  }

  function setCurrentBatchId(batchId) {
    currentBatchId.value = batchId;
  }

  return {
    theme,
    isDark,
    currentBatchId,
    toggleTheme,
    setCurrentBatchId,
  };
});
