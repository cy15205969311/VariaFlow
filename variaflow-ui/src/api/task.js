import request from "@/utils/request";

export function getTasks(params = {}) {
  const query = {
    batch_id: params.batch_id,
    status: params.status,
    page: params.page || 1,
    page_size: params.size || params.page_size || 50,
  };

  return request({
    url: "/tasks",
    method: "get",
    params: query,
  });
}

export function retryGenerationTask(taskId) {
  return request({
    url: `/tasks/${taskId}/retry`,
    method: "post",
  });
}
