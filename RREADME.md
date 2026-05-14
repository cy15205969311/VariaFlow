# VariaFlow 开发总览

VariaFlow 是一套面向电商商拍场景的批量 AI 出图系统，当前仓库包含两个核心子项目：

- `variaflow-server`：FastAPI 后端，负责上传、任务切片、视觉路由、Prompt 组装、图像生成调度、质检与结果落盘。
- `variaflow-ui`：Vue 3 控制台，负责批次上传、进度轮询、任务查看、结果预览与批量下载。

## 本轮架构升级

### 1. 从同步上传升级到异步队列

系统已接入：

- `Celery`
- `Redis`
- 批次级进度聚合
- 批次 ZIP 一键下载

新的处理流程：

1. 上传 ZIP。
2. 后端完成解压、标准化与任务入库。
3. 接口立即返回 `202 Accepted`。
4. 每个生成任务异步进入 Celery 队列。
5. Worker 独立消费并写回任务状态。
6. 前端按批次展示总进度并在完成后开放下载。

补充说明：

- Worker 侧数据库访问已采用 `NullPool` 隔离，避免 Windows + Celery + `asyncio.run()` 下的跨事件循环连接复用问题。
- 批次 ZIP 下载只会收录成功落盘的大图，失败任务或缺失文件不会混入导出结果。

### 2. 前端批次体验增强

Dashboard 已新增：

- 批次总进度条
- `已完成 / 总数` 处理态展示
- 一键打包下载按钮
- 上传成功后的异步处理提示
- 下载时自动读取服务端返回文件名
- 下载失败时支持解析 blob 错误响应并弹出明确提示

### 3. 保留双模式运行

环境变量：

```env
VARIAFLOW_ASYNC_EXECUTION_MODE=celery
```

可切换：

- `celery`
- `inline`

这样可以兼顾生产异步吞吐与本地回退调试。

## 仓库结构

```text
VariaFlow/
|-- RREADME.md
|-- variaflow-server/
|   |-- app/
|   |   |-- api/
|   |   |-- core/
|   |   |-- gateways/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- services/
|   |   `-- utils/
|   |-- tests/
|   |-- worker.py
|   `-- README.md
`-- variaflow-ui/
    |-- src/
    `-- README.md
```

## 本地启动

### Redis

```powershell
docker run -d --name variaflow-redis -p 6379:6379 redis:7-alpine
```

### 后端 API

```powershell
cd variaflow-server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

### Celery Worker

```powershell
cd variaflow-server
celery -A worker.celery_app worker --loglevel=info
```

### 前端

```powershell
cd variaflow-ui
npm install
npm run dev
```

默认本地地址：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`

## 推荐验证

### 后端

```powershell
cd variaflow-server
pytest -q tests/test_batches_endpoint.py tests/test_recovery.py tests/test_scheduler.py tests/test_executor.py tests/test_openai_config_and_prompt.py -o asyncio_default_test_loop_scope=session
```

### 前端

```powershell
cd variaflow-ui
npm run build
```

## 文档索引

- 后端开发说明：[variaflow-server/README.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README.md)
- 测试说明：[variaflow-server/README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
- 前端说明：[variaflow-ui/README.md](/e:/e-commerce-project/VariaFlow/variaflow-ui/README.md)
