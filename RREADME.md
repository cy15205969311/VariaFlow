# VariaFlow 开发文档

## 项目概览
VariaFlow 是一个面向电商商品图与 IP 变体图的批量 AIGC 生产平台，当前采用前后端分离架构：

- `variaflow-server`：FastAPI + SQLAlchemy Async + MySQL
- `variaflow-ui`：Vue 3 + Vite + Pinia + Element Plus

当前主链路已经升级为“智能视觉路由 + 双轨生图”架构：

- `SCENE_EDIT`：商品场景重绘，走 OpenAI `gpt-image-2` 的 `/v1/images/edits`
- `POSE_VARIATION`：IP/人物动作变体，走 OpenAI `gpt-image-2` 的 `/v1/images/generations`
- 视觉识别由可切换的多模态模型负责，当前默认使用 `mimo-v2-omni`

## 目录结构
```text
VariaFlow/
|-- variaflow-server/
|   |-- app/
|   |-- scripts/
|   |-- sql/
|   |-- tests/
|   |-- .env.example
|   `-- README.md
|-- variaflow-ui/
|   |-- src/
|   `-- vite.config.js
|-- .gitignore
`-- RREADME.md
```

## 当前核心能力
### 1. 智能视觉路由
后端在执行生图前会先调用视觉模型，输出以下结构化字段：

- `intent`：`SCENE_EDIT` 或 `POSE_VARIATION`
- `reason`：意图识别原因
- `sku_category`：商品物理摆放类别
- `suggested_scene`：推荐场景配方 key
- `subject_features`：主体稳定身份特征
- `style_features`：稳定画风特征
- `background_features`：背景与氛围特征

其中：

- `SCENE_EDIT` 主要使用 `sku_category` + `suggested_scene`
- `POSE_VARIATION` 主要使用 `subject_features` + `style_features` + `background_features`

### 2. 双轨生图执行
- `SCENE_EDIT`：使用透明底图进行局部重绘，只换背景、不改主体
- `POSE_VARIATION`：使用纯文本高保真重构 Prompt，最大限度保留 IP 气质与风格

### 3. 商品物理落地与爆品场景配方
后端 Prompt Builder 已内置：

- `SPATIAL_GROUNDING_PROMPTS`：平铺、悬挂、站立等物理锚点
- `SCENE_RECIPES`：老钱复古、极简冷感、冬日氛围等爆品场景配方
- `NEGATIVE_SPACE_COMPOSITION_RULE`：保留营销留白，便于后续排版

### 4. 本地静默抠图
当用户上传的是 JPG 或不含透明通道的商品图，`SCENE_EDIT` 分支会自动调用本地 `rembg`：

- 自动检测透明通道
- 自动抠出主体
- 将透明 PNG 喂给 OpenAI edits
- 任务完成后自动清理临时预处理文件

这部分逻辑位于：

- [variaflow-server/app/utils/image_processor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/utils/image_processor.py)
- [variaflow-server/app/services/executor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/executor.py)

## 环境要求
- Python 3.10+
- Node.js 18+
- npm 9+
- MySQL 8.0+

## 快速启动
### 后端
在 `variaflow-server` 目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

### 前端
在 `variaflow-ui` 目录执行：

```bash
npm install
npm run dev
```

默认联调地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

## 环境变量说明
### 基础配置
```env
VARIAFLOW_APP_ENV=development
VARIAFLOW_DEBUG=false
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
VARIAFLOW_DATA_ROOT=./data
VARIAFLOW_WORKER_LEASE_SECONDS=120
VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT=1
```

### OpenAI 生图链路
```env
VARIAFLOW_IMAGE_PROVIDER=openai
VARIAFLOW_OPENAI_IMAGE_EDIT_URL=https://api.openai.com/v1/images/edits
VARIAFLOW_OPENAI_IMAGE_GENERATION_URL=https://api.openai.com/v1/images/generations
VARIAFLOW_OPENAI_IMAGE_MODEL=gpt-image-2
VARIAFLOW_OPENAI_IMAGE_API_KEY=
```

### 视觉识别模型切换
```env
VARIAFLOW_VISION_ROUTER_ENABLED=true
VARIAFLOW_VISION_PROVIDER=mimo
VARIAFLOW_VISION_REQUEST_TIMEOUT_SECONDS=45
VARIAFLOW_VISION_DEFAULT_INTENT=SCENE_EDIT
```

#### Mimo
```env
VARIAFLOW_MIMO_VISION_API_URL=https://token-plan-cn.xiaomimimo.com/v1
VARIAFLOW_MIMO_VISION_MODEL=mimo-v2-omni
VARIAFLOW_MIMO_VISION_API_KEY=
```

#### DeepSeek
```env
VARIAFLOW_DEEPSEEK_VISION_API_URL=https://api.deepseek.com/v1
VARIAFLOW_DEEPSEEK_VISION_MODEL=deepseek-v4-flash
# 可选：
# VARIAFLOW_DEEPSEEK_VISION_MODEL=deepseek-v4-pro
VARIAFLOW_DEEPSEEK_VISION_API_KEY=
```

### 调试与容错
```env
VARIAFLOW_PROVIDER_DEBUG_LOG=true
VARIAFLOW_PROVIDER_REQUEST_TIMEOUT_SECONDS=180
VARIAFLOW_PROVIDER_ENABLE_FALLBACK=false
```

### 质量检查
```env
VARIAFLOW_QC_MIN_FILE_SIZE_BYTES=51200
VARIAFLOW_QC_MIN_WIDTH=768
VARIAFLOW_QC_MIN_HEIGHT=752
VARIAFLOW_QC_MIN_TOTAL_PIXELS=577536
```

## 输出目录
所有批次文件按批次号隔离落盘：

```text
variaflow-server/data/batch_<batch_code>/
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

目录说明：

- `normalized/`：标准化后的源图
- `outputs/`：最终通过 QC 的正式产物
- `preprocessed/`：静默抠图的透明 PNG 中间产物
- `tmp/`：临时写入文件与 `.part`
- `failed/`：预留失败归档

## 前端状态透出
任务列表已支持展示智能识别结果：

- `intent_label`
- `intent_reason`
- `sku_category`
- `suggested_scene`
- `subject_features`
- `style_features`
- `background_features`

当前前端还完成了以下优化：

- 任务列表工具栏改为单行 SaaS 布局
- 支持紧凑视图切换
- 支持前端搜索与状态筛选
- 任务卡片支持 Tooltip 查看识别原因与主体特征

## 推荐测试命令
### 后端单测
在 `variaflow-server` 目录执行：

```bash
pytest -q tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_ai_provider_routing.py tests/test_image_processor.py tests/test_qc_engine.py
```

### 说明
- `tests/test_executor.py` 依赖本地测试库 `variaflow_test`
- 若未创建 `VARIAFLOW_TEST_DATABASE_URL` 对应库，则不建议直接跑该文件

### 前端构建
在 `variaflow-ui` 目录执行：

```bash
npm run build
```

## 关键代码入口
- 智能视觉路由：[variaflow-server/app/services/vision_router.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/vision_router.py)
- Prompt 组装：[variaflow-server/app/services/prompt_builder.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/prompt_builder.py)
- 爆品词库与场景配方：[variaflow-server/app/core/prompt_lexicon.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/core/prompt_lexicon.py)
- 执行器：[variaflow-server/app/services/executor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/executor.py)
- 任务接口：[variaflow-server/app/api/endpoints/tasks.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/api/endpoints/tasks.py)
- 任务卡片 UI：[variaflow-ui/src/views/Dashboard/components/TaskCard.vue](/e:/e-commerce-project/VariaFlow/variaflow-ui/src/views/Dashboard/components/TaskCard.vue)
- 列表工具栏 UI：[variaflow-ui/src/views/Dashboard/components/FilterBar.vue](/e:/e-commerce-project/VariaFlow/variaflow-ui/src/views/Dashboard/components/FilterBar.vue)

## 提交规范
建议统一使用“类型英文 + 描述中文”的格式：

```text
feat: 引入智能视觉路由与双轨生图链路
feat: 新增爆品场景配方与静默抠图能力
fix: 修复任务卡片状态透出异常
docs: 更新开发文档与环境变量说明
test: 补充视觉路由与图片预处理测试
```
