# VariaFlow UI

`variaflow-ui` 是 VariaFlow 的前端控制台，基于 Vue 3 + Vite，负责：

- ZIP 批次上传
- 批次状态轮询
- 原图任务与生成槽位展示
- 输出图预览
- 手动重试与异常定位辅助

## 技术栈

- `vue`
- `vite`
- `vue-router`
- `pinia`
- `axios`
- `element-plus`
- `@element-plus/icons-vue`

## 本地启动

```bash
npm install
npm run dev
```

默认会将 `/api` 代理到 `http://127.0.0.1:8000`。

## 当前 Dashboard 链路

### 1. 上传

核心文件：

- `src/views/Dashboard/components/UploadEngine.vue`

本轮已加固：

- 上传成功后必须校验返回结构中存在 `batch.id`
- 上传失败时重置 `uploadProgress` 与 `uploading`
- 避免“进度条 100% 但界面没有继续流转”

### 2. 批次刷新与轮询

核心文件：

- `src/views/Dashboard/index.vue`
- `src/stores/batch.js`

本轮已加固：

- `handleUploadSuccess(batchId)` 会立即 `refreshAll(batchId)`
- 拉取失败时前端会弹出错误提示，而不是静默卡住
- `refreshAll()` 内部已补充控制台错误日志
- `watch(currentBatchId)` 使用 `flush: "post"`，减少页面切换阶段的竞态

### 3. 任务展示

任务接口来自：

- `GET /api/v1/tasks?batch_id=...`

当前生成槽位除了基础状态外，还能拿到这些后端透传字段：

- `intent`
- `subject_type`
- `sku_category`
- `suggested_scene_recipe`
- `dynamic_spatial_anchor`
- `dynamic_lighting_needs`
- `primary_sku_description`
- `secondary_props`
- `dynamic_props`
- `camera_perspective`
- `output_path`

这使得前端可以继续扩展更强的调试视图和任务解释面板。

## 构建校验

```bash
npm run build
```

## 联调建议

- 上传成功但结果不更新时，先看浏览器 `Console`
- 如果批次已经创建但任务长时间不动，优先检查后端调度器是否在消费最新批次
- 如果接口返回成功但页面没有切换，先确认上传返回结构里是否包含 `batch.id`
