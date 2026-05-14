import request from "@/utils/request";

export function uploadBatch(file, onUploadProgress) {
  const formData = new FormData();
  formData.append("file", file);

  return request({
    url: "/batches/upload",
    method: "post",
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress,
  });
}

export function getBatchInfo(id) {
  return request({
    url: `/batches/${id}`,
    method: "get",
  });
}

export function downloadBatchOutputs(id) {
  return request({
    url: `/batches/${id}/download`,
    method: "get",
    responseType: "blob",
  });
}
