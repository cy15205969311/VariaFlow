# VariaFlow Server

`variaflow-server` 是 VariaFlow 的后端服务，负责 ZIP 批次上传、任务切片、视觉路由、Prompt 组装、图像生成调度、质检与结果落盘。

## 本轮重点更新

### 1. 异步任务架构升级

- 新增 `Celery + Redis` 异步执行链路。
- 上传接口 `POST /api/v1/batches/upload` 现在在批次和任务入库后立即返回 `202 Accepted`。
- 每个 `generation_task` 会在上传完成后异步投递到队列，不再阻塞上传请求。
- 保留 `inline` 兼容模式，方便本地无队列回退调试。

核心文件：

- `app/core/celery_app.py`
- `app/services/async_tasks.py`
- `app/services/scheduler.py`
- `worker.py`

### 2. 批次聚合状态增强

`GET /api/v1/batches/{batch_id}` 现在会返回：

- `processing_generation_count`
- `terminal_generation_count`
- `progress_percent`
- `download_ready`
- `export_status`

这些字段用于前端展示批次总进度、处理中数量以及下载按钮可用状态。

### 3. 批次打包下载

新增接口：

- `GET /api/v1/batches/{batch_id}/download`

行为：

- 仅打包当前批次已成功落盘的输出图片。
- 仅收录 `generation_task.status` 为 `success` 或 `fallback_success` 且文件实际存在的输出，自动跳过失败任务和缺失文件。
- 服务端临时生成 ZIP 后通过 `FileResponse` 返回。
- 下载完成后自动清理临时 ZIP 和临时目录，避免磁盘堆积。

实现细节：

- 归档来源不是简单扫描 `output_root_path`，而是以数据库中的 `GenerationTask.output_path` 为准，避免把失败残留文件或无关临时文件打进压缩包。
- 归档过程使用 `zipfile` 直接写文件路径，不会先把所有图片载入内存，适合大批量高清图下载。

### 4. 手动重试与恢复循环联动

- `POST /api/v1/tasks/{generation_task_id}/retry` 在 Celery 模式下会立即重新入队。
- 恢复循环会回收租约过期任务，并在 Celery 模式下重新投递，避免任务卡死在 `processing`。

## 执行模式

通过环境变量控制：

```env
VARIAFLOW_ASYNC_EXECUTION_MODE=celery
```

可选值：

- `celery`：推荐，生产或大批量处理使用
- `inline`：兼容旧模式，本地排障可用

## Redis 与 Celery 配置

```env
VARIAFLOW_REDIS_URL=redis://127.0.0.1:6379/0
VARIAFLOW_CELERY_BROKER_URL=redis://127.0.0.1:6379/0
VARIAFLOW_CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
VARIAFLOW_CELERY_TASK_TIME_LIMIT_SECONDS=900
VARIAFLOW_CELERY_TASK_SOFT_TIME_LIMIT_SECONDS=840
VARIAFLOW_EXPORT_TEMP_ROOT=./data/_exports
```

## Docker 启动 Redis

如果本机已安装 Docker Desktop，可直接启动 Redis：

```powershell
docker run -d --name variaflow-redis -p 6379:6379 redis:7-alpine
```

健康检查：

```powershell
docker exec variaflow-redis redis-cli ping
```

预期返回：

```text
PONG
```

## 本地启动

### 1. 安装依赖

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. 启动 API

```powershell
uvicorn app.main:app --reload
```

### 3. 启动 Celery Worker

```powershell
celery -A worker.celery_app worker --loglevel=info
```

### 3.1 Celery 数据库隔离

当前 Worker 侧已采用 `NullPool` + 任务级会话工厂，专门规避 Windows + `asyncio.run()` + `aiomysql` 场景下的跨事件循环连接污染问题。

如果看到类似以下错误，说明没有使用隔离会话：

```text
AttributeError: 'NoneType' object has no attribute 'send'
```

当前修复策略：

- Celery 任务使用独立 `worker_session_factory`
- Worker 侧异步引擎使用 `NullPool`
- 任务结束后补充 `dispose()` 清理

### 4. 健康检查

```powershell
curl http://127.0.0.1:8000/health
```

## 当前批次链路

1. 上传 ZIP。
2. 解压、归档、标准化原图。
3. 创建 `batch_job / source_task / generation_task`。
4. 接口立即返回 `202` 和批次信息。
5. 后端将每个生成任务投递到 Celery。
6. Worker 认领任务并执行视觉路由、Prompt 构建、图像生成、QC、落盘。
7. 前端按批次轮询进度并在完成后开放 ZIP 下载。

## 关键接口

### 上传批次

```http
POST /api/v1/batches/upload
```

返回：

- `202 Accepted`
- `BatchResponse`

### 查询批次

```http
GET /api/v1/batches/{batch_id}
```

### 下载批次结果

```http
GET /api/v1/batches/{batch_id}/download
```

### 手动重试单个生成任务

```http
POST /api/v1/tasks/{generation_task_id}/retry
```

## 推荐回归

```powershell
pytest -q tests/test_batches_endpoint.py tests/test_recovery.py tests/test_scheduler.py tests/test_executor.py tests/test_openai_config_and_prompt.py -o asyncio_default_test_loop_scope=session
```

## 相关文档

- 项目总览：[../RREADME.md](/e:/e-commerce-project/VariaFlow/RREADME.md)
- 测试说明：[README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
