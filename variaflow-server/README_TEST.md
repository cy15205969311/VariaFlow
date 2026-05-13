# VariaFlow 测试说明

## 1. 本地创建测试库与测试账号

```sql
CREATE DATABASE variaflow_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'test_user'@'localhost' IDENTIFIED BY 'test_pass';
GRANT ALL PRIVILEGES ON variaflow_test.* TO 'test_user'@'localhost';
FLUSH PRIVILEGES;
```

## 2. 环境变量配置

复制 `.env.example` 为 `.env` 后，至少补齐：

```env
VARIAFLOW_APP_ENV=development
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
```

说明：

- 正常启动服务时仍使用 `VARIAFLOW_DATABASE_URL`
- 运行 `pytest` 时，测试夹具会强制校验当前连接是否指向 `VARIAFLOW_TEST_DATABASE_URL`
- 如果测试库 URL 缺失，或与主库 URL 相同，测试会拒绝启动，避免污染开发库

## 3. 重要注意事项

- 不要同时并行启动多组 `pytest` 命令指向同一个 `variaflow_test`
- 当前测试夹具会在 session 级别执行 `drop_all / create_all`
- 如果你在两个终端同时跑不同测试集合，可能出现“表不存在”或清理互相打断的问题

推荐做法：

- 一次只跑一条完整的 `pytest` 命令
- 如需拆分回归，请串行执行，不要并发执行

## 4. 推荐回归命令

### 快速回归

```powershell
pytest -q tests/test_batches_endpoint.py tests/test_scheduler.py tests/test_recovery.py tests/test_executor.py::test_happy_path tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_image_processor.py
```

### 全量回归

```powershell
pytest
```

## 5. 当前重点覆盖项

- 上传接口异常日志与错误返回
- 调度器优先消费最新运行中批次
- 恢复循环识别 MySQL `1213 deadlock`
- 恢复循环识别 MySQL `1205 lock wait timeout`
- 视觉路由输出 `dynamic_props`、`camera_perspective`、`apparel_leaning`
- Prompt Builder 注入知识图谱约束、视角锁与真人负向锁
- 场景重绘预处理支持 `apparel_leaning` 锚定
- 真人模特场景重绘自动生成背景编辑遮罩
- OpenAI `images/edits` 上传 `mask` 文件
- `test_happy_path` 使用确定性假图，避免 mock provider 随机失败

## 6. 测试数据清理

- 测试启动时自动执行 `Base.metadata.create_all`
- 测试结束后删除测试表数据
- 同时递归清理 `data/test_batch_*` 目录

## 7. 常见问题

### 1. 报错 `当前不是测试环境`

说明你没有正确加载 `.env`，或测试环境变量没有指向 `VARIAFLOW_TEST_DATABASE_URL`。

### 2. 报错某张表不存在

通常是两组 `pytest` 并发执行，或中途有一组测试先做了 `drop_all`。请停止并发测试，串行重跑。

### 3. `test_happy_path` 偶发失败

本轮已经把该测试改为确定性图片输出。如果仍失败，优先检查：

- 测试库连接是否正常
- 本地数据目录是否可写
- 是否有并发测试在清理表结构

## 最新补充

### 本轮新增回归覆盖

- `vision_router`：`material_type` 归一化与软服饰 `leaning` 纠偏
- `prompt_builder`：材质光影规则注入、软服饰互斥锁 warning 兜底
- `executor`：`material_type` 透传到 payload、snapshot 与任务接口响应
- Dashboard 预览改动已通过 `npm run build` 构建校验
