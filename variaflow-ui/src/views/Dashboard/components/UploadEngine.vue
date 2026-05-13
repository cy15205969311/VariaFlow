<template>
  <div class="rounded-2xl border border-gray-100 bg-white p-3 shadow-sm md:p-4">
    <div
      class="relative overflow-hidden rounded-[18px] border border-dashed border-[#D7DCE4] bg-white"
    >
      <div
        class="absolute left-1/2 top-5 z-10 flex h-11 w-11 -translate-x-1/2 items-center justify-center rounded-2xl border border-gray-200 bg-[#F4F5F7] shadow-sm"
      >
        <el-icon class="text-[20px] text-[#111827]"><UploadFilled /></el-icon>
      </div>

      <el-upload
        ref="uploadRef"
        drag
        :show-file-list="false"
        :auto-upload="false"
        :accept="'.zip'"
        :http-request="handleCustomUpload"
        :before-upload="validateZip"
        :on-change="handleFileChange"
        class="w-full"
      >
        <div
          class="flex min-h-[188px] w-full flex-col items-center justify-center px-6 pb-10 pt-16 text-center md:min-h-[194px]"
        >
          <div class="mb-3 flex items-center justify-center gap-3">
            <h3 class="m-0 text-[16px] font-bold tracking-[0.01em] text-gray-900">
              ZIP 文件拖拽至此，自动启动解析与调度
            </h3>
          </div>

          <p class="mb-6 text-[12px] text-gray-500">
            单次最多支持 500 张图片，支持 ZIP 格式
          </p>

          <el-button
            class="!h-10 !rounded-xl !border-0 !bg-[#18181B] !px-6 !text-[13px] !font-medium !text-white hover:!bg-black"
            :loading="uploading"
            @click.stop="handlePrimaryAction"
          >
            {{ selectedFile ? "开始上传" : "选择本地文件" }}
          </el-button>

          <p v-if="selectedFile" class="mt-4 text-[12px] text-gray-400">
            {{ selectedFile.name }}
          </p>
        </div>
      </el-upload>
    </div>

    <div v-if="uploading" class="mt-4 px-1">
      <div class="mb-2 flex items-center justify-between text-[12px] text-gray-600">
        <span>上传进度</span>
        <strong class="text-gray-900">{{ uploadProgress }}%</strong>
      </div>
      <el-progress :percentage="uploadProgress" :stroke-width="6" :show-text="false" />
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";

import { uploadBatch } from "@/api/batch";

const emit = defineEmits(["upload-success"]);

const uploadRef = ref();
const selectedFile = ref(null);
const uploadProgress = ref(0);
const uploading = ref(false);

function validateZip(rawFile) {
  const isZip = rawFile.name.toLowerCase().endsWith(".zip");
  if (!isZip) {
    ElMessage.warning("只能上传 ZIP 文件");
    return false;
  }
  return true;
}

function handleFileChange(uploadFile) {
  const rawFile = uploadFile.raw;
  if (!rawFile) {
    return;
  }
  if (!rawFile.name.toLowerCase().endsWith(".zip")) {
    selectedFile.value = null;
    return;
  }
  selectedFile.value = rawFile;
}

function triggerSelect() {
  uploadRef.value?.$el?.querySelector("input")?.click();
}

function handlePrimaryAction() {
  if (uploading.value) {
    return;
  }

  if (!selectedFile.value) {
    triggerSelect();
    return;
  }

  submitUpload();
}

async function submitUpload() {
  if (!selectedFile.value || uploading.value) {
    return;
  }

  try {
    await handleCustomUpload({ file: selectedFile.value });
  } catch (error) {
    console.error(error);
    uploadProgress.value = 0;
    uploading.value = false;
  }
}

async function handleCustomUpload(options) {
  const file = options.file || selectedFile.value;
  if (!file) {
    ElMessage.warning("请先选择 ZIP 文件");
    return;
  }

  uploading.value = true;
  uploadProgress.value = 0;

  try {
    const batch = await uploadBatch(file, (progressEvent) => {
      if (!progressEvent.total) {
        return;
      }
      uploadProgress.value = Math.min(
        100,
        Math.round((progressEvent.loaded / progressEvent.total) * 100)
      );
    });

    if (!batch || !Number.isInteger(Number(batch.id))) {
      throw new Error("上传接口返回的数据结构不完整，缺少 batch.id");
    }

    ElMessage.success(`上传成功，批次 #${batch.id} 已创建`);
    selectedFile.value = null;
    uploadProgress.value = 100;
    uploadRef.value?.clearFiles?.();
    emit("upload-success", batch.id);
    options.onSuccess?.(batch);
  } catch (error) {
    uploadProgress.value = 0;
    options.onError?.(error);
    throw error;
  } finally {
    uploading.value = false;
  }
}
</script>

<style scoped>
:deep(.el-upload) {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 0;
}

:deep(.el-progress-bar__outer) {
  background: #f4f4f5;
}
</style>
