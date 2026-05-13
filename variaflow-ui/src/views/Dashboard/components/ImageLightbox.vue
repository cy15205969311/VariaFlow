<template>
  <Teleport to="body">
    <transition name="lightbox-fade">
      <div
        v-if="open && imageUrl"
        class="glass-overlay"
        @click="$emit('close')"
      >
        <div class="preview-wrapper" @click.stop>
          <img
            :src="imageUrl"
            :alt="alt || '高清预览'"
            class="max-preview-img"
          />

          <button
            type="button"
            class="close-btn"
            aria-label="关闭预览"
            @click="$emit('close')"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from "vue";

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  imageUrl: {
    type: String,
    default: "",
  },
  alt: {
    type: String,
    default: "高清预览",
  },
});

const emit = defineEmits(["close"]);

function handleKeydown(event) {
  if (event.key === "Escape" && props.open) {
    emit("close");
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", handleKeydown);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", handleKeydown);
  }
});
</script>

<style scoped>
.glass-overlay {
  position: fixed;
  inset: 0;
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.preview-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80vmin;
  height: 80vmin;
}

.max-preview-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 16px;
  background-color: #ffffff;
  box-shadow: 0 30px 70px -24px rgba(15, 23, 42, 0.9);
  user-select: none;
}

.close-btn {
  position: absolute;
  top: 0;
  right: 0;
  transform: translate(50%, -50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #0f172a;
  cursor: pointer;
  box-shadow: 0 14px 32px -18px rgba(15, 23, 42, 0.8);
  transition:
    transform 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.96);
  transform: translate(50%, -50%) scale(1.06);
  box-shadow: 0 18px 36px -18px rgba(15, 23, 42, 0.85);
}

.close-btn:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.95);
  outline-offset: 2px;
}

.lightbox-fade-enter-active,
.lightbox-fade-leave-active {
  transition: opacity 0.3s ease;
}

.lightbox-fade-enter-active .preview-wrapper,
.lightbox-fade-leave-active .preview-wrapper {
  transition:
    transform 0.3s ease,
    opacity 0.3s ease;
}

.lightbox-fade-enter-from,
.lightbox-fade-leave-to {
  opacity: 0;
}

.lightbox-fade-enter-from .preview-wrapper,
.lightbox-fade-leave-to .preview-wrapper {
  transform: translateY(10px) scale(0.97);
  opacity: 0;
}

@media (max-width: 640px) {
  .glass-overlay {
    padding: 14px;
  }

  .preview-wrapper {
    width: 80vmin;
    height: 80vmin;
  }

  .max-preview-img {
    border-radius: 14px;
  }

  .close-btn {
    width: 38px;
    height: 38px;
  }
}
</style>
