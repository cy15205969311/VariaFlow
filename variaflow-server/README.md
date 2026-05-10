# VariaFlow Server

## 服务说明
`variaflow-server` 是 VariaFlow 的后端服务，负责：

- ZIP 批次上传与拆包
- 原图标准化与任务切片
- 智能视觉识别与意图路由
- 双轨生图调度
- 规则质检与结果落盘
- 任务状态与前端透传

当前主架构：

- `SCENE_EDIT`：OpenAI `gpt-image-2` `/v1/images/edits`
- `POSE_VARIATION`：OpenAI `gpt-image-2` `/v1/images/generations`
- 视觉模型：默认 `mimo-v2-omni`，支持切换到 `deepseek-v4-flash` / `deepseek-v4-pro`

## 安装与启动
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## 关键环境变量
```env
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
VARIAFLOW_DATA_ROOT=./data
VARIAFLOW_WORKER_LEASE_SECONDS=120
VARIAFLOW_PROVIDER_DEBUG_LOG=true
VARIAFLOW_PROVIDER_REQUEST_TIMEOUT_SECONDS=180
```

### OpenAI 生图
```env
VARIAFLOW_IMAGE_PROVIDER=openai
VARIAFLOW_OPENAI_IMAGE_EDIT_URL=https://api.openai.com/v1/images/edits
VARIAFLOW_OPENAI_IMAGE_GENERATION_URL=https://api.openai.com/v1/images/generations
VARIAFLOW_OPENAI_IMAGE_MODEL=gpt-image-2
VARIAFLOW_OPENAI_IMAGE_API_KEY=
```

### 视觉模型
```env
VARIAFLOW_VISION_ROUTER_ENABLED=true
VARIAFLOW_VISION_PROVIDER=mimo
VARIAFLOW_VISION_REQUEST_TIMEOUT_SECONDS=45
VARIAFLOW_VISION_DEFAULT_INTENT=SCENE_EDIT
```

Mimo：

```env
VARIAFLOW_MIMO_VISION_API_URL=https://token-plan-cn.xiaomimimo.com/v1
VARIAFLOW_MIMO_VISION_MODEL=mimo-v2-omni
VARIAFLOW_MIMO_VISION_API_KEY=
```

DeepSeek：

```env
VARIAFLOW_DEEPSEEK_VISION_API_URL=https://api.deepseek.com/v1
VARIAFLOW_DEEPSEEK_VISION_MODEL=deepseek-v4-flash
# VARIAFLOW_DEEPSEEK_VISION_MODEL=deepseek-v4-pro
VARIAFLOW_DEEPSEEK_VISION_API_KEY=
```

### 质量检查
```env
VARIAFLOW_QC_MIN_FILE_SIZE_BYTES=51200
VARIAFLOW_QC_MIN_WIDTH=768
VARIAFLOW_QC_MIN_HEIGHT=752
VARIAFLOW_QC_MIN_TOTAL_PIXELS=577536
```

## 当前后端链路
### 1. 智能视觉识别
入口：

- [app/services/vision_router.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/vision_router.py)

视觉模型返回：

- `intent`
- `reason`
- `sku_category`
- `suggested_scene`
- `subject_features`
- `style_features`
- `background_features`

其中 JSON 解析使用正则提取 `{}` 再做 `json.loads()`，并带有 fallback，默认回退到 `SCENE_EDIT`。

### 2. Prompt 组装
入口：

- [app/services/prompt_builder.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/prompt_builder.py)
- [app/core/prompt_lexicon.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/core/prompt_lexicon.py)

能力包括：

- 商品物理锚点 `SPATIAL_GROUNDING_PROMPTS`
- 场景环境模板 `ENVIRONMENT_TEMPLATES`
- 爆品场景配方 `SCENE_RECIPES`
- 营销留白规则 `NEGATIVE_SPACE_COMPOSITION_RULE`
- IP 变体商业增强词 `QUALITY_TERMS`、`LIGHTING_TERMS`、`CAMERA_TERMS`、`RENDER_TERMS`

### 3. 执行器
入口：

- [app/services/executor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/executor.py)

当前行为：

- 先跑视觉识别
- 根据 `intent` 写入 `provider_hint`
- `SCENE_EDIT` 走 `openai_image_edit`
- `POSE_VARIATION` 走 `openai_image_generation`
- `SCENE_EDIT` 若源图无透明通道，则先调用本地静默抠图

### 4. 本地静默抠图
入口：

- [app/utils/image_processor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/utils/image_processor.py)

说明：

- 已透明 PNG 直接透传
- JPG 或不透明图使用 `rembg` 去背景
- 输出临时透明 PNG 到 `preprocessed/`
- 任务完成后自动清理临时文件

### 5. 任务接口透传
入口：

- [app/api/endpoints/tasks.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/api/endpoints/tasks.py)
- [app/schemas/tasks.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/schemas/tasks.py)

前端可直接读取：

- `intent`
- `intent_label`
- `intent_reason`
- `sku_category`
- `suggested_scene`
- `subject_features`
- `style_features`
- `background_features`

## 输出目录
```text
data/batch_<batch_code>/
|-- input_archive/
|-- input_unpacked/
|-- normalized/
|-- outputs/
|   `-- S0001/
|       `-- variant_1.png
|-- failed/
|-- preprocessed/
`-- tmp/
```

## 测试
推荐先运行：

```bash
pytest -q tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_ai_provider_routing.py tests/test_image_processor.py tests/test_qc_engine.py
```

说明：

- `tests/test_executor.py` 依赖 `VARIAFLOW_TEST_DATABASE_URL` 对应的本地 MySQL 测试库
- 若本地未创建 `variaflow_test`，该文件不能完整运行

## 相关新增能力摘要
- 新增视觉模型解耦，支持 Mimo / DeepSeek 切换
- 新增任务卡片可解释性字段透传
- 新增商品空间落地分类与场景配方
- 新增静默抠图中间件，防止 JPG 场景重绘误伤主体
- 新增前端静态输出代理 `/static`
