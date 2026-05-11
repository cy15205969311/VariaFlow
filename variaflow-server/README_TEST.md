# VariaFlow 测试数据库说明
## 1. 本地创建测试库与测试账号
```sql
CREATE DATABASE variaflow_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'test_user'@'localhost' IDENTIFIED BY 'test_pass';
GRANT ALL PRIVILEGES ON variaflow_test.* TO 'test_user'@'localhost';
FLUSH PRIVILEGES;
```

## 2. 环境变量配置
复制 `.env.example` 为 `.env` 后，至少补齐以下字段：

```env
VARIAFLOW_APP_ENV=development
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
```

说明：

- 正常启动服务时仍使用 `VARIAFLOW_DATABASE_URL`
- 运行 `pytest` 时，系统会自动切换到 `VARIAFLOW_TEST_DATABASE_URL`
- 如果测试库 URL 缺失，或者与主库 URL 相同，服务会直接拒绝启动测试，避免污染开发库

## 3. 运行测试
```bash
pytest
```

如果只想验证本轮改动，建议先跑：

```bash
pytest -q tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_image_processor.py tests/test_ai_provider_routing.py tests/test_recovery.py
```

## 4. 当前测试重点
- OpenAI 图片编辑 URL 规范化逻辑
- Prompt Builder 是否保留原始源图扩展名
- QC 是否能正确识别 `.part` 临时文件里的真实 PNG 内容
- QC 是否支持通过总像素阈值接收阿里返回的近 1K 图
- 视觉路由是否输出新字段 `dynamic_spatial_prompt` / `dynamic_lighting_prompt`
- 场景重绘是否为真人模特自动生成背景遮罩
- OpenAI `images/edits` 适配器是否会携带 `mask` 文件
- 恢复逻辑是否能识别 MySQL `1213 deadlock` 与 `1205 lock wait timeout`

## 5. 测试数据清理
- 测试启动时会自动执行 `Base.metadata.create_all` 初始化表结构
- 测试结束后会删除测试表数据
- 同时会递归清理 `data/test_batch_*` 目录
