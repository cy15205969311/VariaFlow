# VariaFlow 测试数据库说明

## 1. 本地创建测试库与测试账号

```sql
CREATE DATABASE variaflow_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'test_user'@'localhost' IDENTIFIED BY 'test_pass';
GRANT ALL PRIVILEGES ON variaflow_test.* TO 'test_user'@'localhost';
```

## 2. 环境变量配置

复制 `.env.example` 为 `.env`，并至少补齐下面两项：

```env
VARIAFLOW_APP_ENV=development
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
```

说明：

- 正常启动服务时仍使用 `VARIAFLOW_DATABASE_URL`。
- 运行 `pytest` 时，系统会自动切换到 `VARIAFLOW_TEST_DATABASE_URL`。
- 如果测试库 URL 缺失，或与主库 URL 相同，测试会在启动前直接失败，避免污染开发数据。

## 3. 运行测试

```bash
pytest -q tests/test_executor.py
```

测试启动时会自动执行 `Base.metadata.create_all` 初始化表结构，测试结束后会删除测试表数据，并递归清理 `data/test_batch_*` 目录。
