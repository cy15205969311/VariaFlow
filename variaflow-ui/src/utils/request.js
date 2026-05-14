import axios from "axios";
import { ElMessage } from "element-plus";

const request = axios.create({
  baseURL: "/api/v1",
  timeout: 60000,
});

request.interceptors.response.use(
  (response) => {
    if (response.config.responseType === "blob") {
      return response;
    }
    return response.data;
  },
  (error) => {
    if (error?.config?.responseType === "blob") {
      return Promise.reject(error);
    }
    const detail =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      "请求失败，请稍后重试";

    ElMessage.error(typeof detail === "string" ? detail : "网络异常，请检查服务连接");
    return Promise.reject(error);
  }
);

export default request;
