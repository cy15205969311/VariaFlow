# VariaFlow 服务端

## 本地启动

1. 安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. 配置本地环境。在 `variaflow-server/` 目录下创建 `.env` 文件，内容可参考：

```env
VARIAFLOW_APP_ENV=development
VARIAFLOW_DEBUG=true
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_DATA_ROOT=./data
VARIAFLOW_DB_POOL_SIZE=10
VARIAFLOW_DB_MAX_OVERFLOW=20
VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT=3
```

3. 生成并执行初始迁移：

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

4. 本地启动 API：

```bash
uvicorn app.main:app --reload
```

5. 验证服务：

```bash
curl http://127.0.0.1:8000/health
```

## 说明

- 上传接口 `POST /api/v1/batches/upload` 仅接收 ZIP 压缩包。
- 上传后的文件会落在 `VARIAFLOW_DATA_ROOT` 指定目录下。
- 调度器只会消费父批次 `batch_job.status` 为 `running` 的 `generation_task` 记录。
