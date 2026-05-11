# VariaFlow Server

`variaflow-server` 是 VariaFlow 的后端服务，负责：

- ZIP 批次上传与解包
- 源图标准化与任务切片
- 多模态视觉意图识别
- Prompt 组装与 AI Provider 调度
- 图像质检、状态流转与结果落盘
- 前端任务列表所需的识别信息透传

## 当前架构概览

### 1. 智能双轨路由

视觉模型会先对源图做结构化分析，并输出：

- `intent`
- `reason`
- `subject_type`
- `sku_category`
- `suggested_scene`
- `suggested_scene_recipe`
- `dynamic_spatial_anchor`
- `dynamic_lighting_needs`
- `primary_sku_description`
- `secondary_props`
- `subject_features`
- `style_features`
- `background_features`

路由规则：

- `SCENE_EDIT` -> `openai_image_edit`
- `POSE_VARIATION` -> `openai_image_generation`
- `POSE_VARIATION + real_human_model` -> 强制改走 `openai_image_edit`

### 2. 动态物理约束生成

当前后端已从“纯静态类目映射”演进到“动态主路径 + 轻量兜底”：

- 对 `SCENE_EDIT`，优先使用视觉模型生成的：
  - `dynamic_spatial_anchor`
  - `dynamic_lighting_needs`
- 这些字段会直接拼进最终发给 OpenAI 的 Prompt
- 若动态字段过短、缺失或不可执行，则使用少量后端 fallback 规则兜底

这让系统不需要继续维护臃肿的全量品类静态 Prompt 字典，同时又保留足够稳定性。

### 3. 视觉模型解耦

当前支持通过 `.env` 在以下视觉模型之间切换：

- `mimo-v2-omni`
- `deepseek-v4-flash`
- `deepseek-v4-pro`

### 4. 电商商拍增强

当前已经落地以下后端能力：

- 场景配方库与商业摄影增强词库
- 动态空间落位与动态打光注入
- 智能画布补白与重力锚点
- 本地静默抠图
- `human_model` 与真人模特豁免链路
- 真人模特动作变体专线

## 关键模块

### 1. 视觉路由

文件：

- [app/services/vision_router.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/vision_router.py)

职责：

- 调用视觉模型识别 `SCENE_EDIT` / `POSE_VARIATION`
- 输出 `subject_type`
- 为 `SCENE_EDIT` 生成动态物理约束与动态打光需求
- 为 `SCENE_EDIT` 推荐 `suggested_scene_recipe`
- 为 `POSE_VARIATION` 提取主体、画风、背景三类特征
- 输出主售卖主体与次级配饰拆分结果

### 2. Prompt 词库与组装

文件：

- [app/core/prompt_lexicon.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/core/prompt_lexicon.py)
- [app/services/prompt_builder.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/prompt_builder.py)

职责：

- 注入商业场景 recipe
- 为 `POSE_VARIATION` 注入主体、风格、背景三维特征
- 对真人模特和 3D IP 使用不同 Prompt 分支
- 对 `SCENE_EDIT` 优先拼接动态 grounding / lighting
- 当动态字段不可靠时使用 fallback

当前保留的词库重点：

- `SCENE_RECIPES`
- `SCENE_RECIPE_FALLBACKS`
- `ENVIRONMENT_TEMPLATES`
- `QUALITY_TERMS`
- `LIGHTING_TERMS`
- `CAMERA_TERMS`
- `RENDER_TERMS`
- `NEGATIVE_SPACE_COMPOSITION_RULE`

新增与强化的场景配方包括：

- `french_street_vibe`
- `luxury_water_surface`
- `nature_forest_outdoor`
- `gourmet_morning_bakery`
- `luxury_dark_chocolate`

### 3. 图片预处理

文件：

- [app/utils/image_processor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/utils/image_processor.py)

职责：

- 检查透明通道
- 对非透明图片执行本地 `rembg` 静默抠图
- 按 SKU 分类与场景进行智能补白
- 通过锚点控制主体在画布中的落位

当前能力：

- `subject_type == human_model` 时跳过 `rembg`
- `real_human_model` 仍然保留专门豁免
- 输出预处理元信息到 `prompt_snapshot_json`

### 4. 执行器

文件：

- [app/services/executor.py](/e:/e-commerce-project/VariaFlow/variaflow-server/app/services/executor.py)

职责：

- 调用视觉路由
- 组装 Provider payload
- 决定最终 Provider hint
- 在 `SCENE_EDIT` 下执行智能预处理
- 在真人变体场景下保留原图直送 OpenAI edits
- 记录 attempt、QC 和最终状态

当前新增逻辑：

- 将 `subject_type`
- `dynamic_spatial_anchor`
- `dynamic_lighting_needs`
- `primary_sku_description`
- `secondary_props`

一起持久化进任务快照，并透传到接口层。

## 本地启动

### 安装

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 数据库

确保本地 MySQL 已创建：

- `variaflow`
- `variaflow_test`

迁移或初始化后再启动服务。

### 启动 API

```powershell
uvicorn app.main:app --reload
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 关键环境变量

### 基础配置

```env
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
VARIAFLOW_DATA_ROOT=./data
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
# 可切换为 deepseek-v4-pro
VARIAFLOW_DEEPSEEK_VISION_API_KEY=
```

### 阿里能力保留配置

当前主路径已回到 OpenAI，但项目仍保留阿里相关配置，便于后续实验：

```env
VARIAFLOW_ALIYUN_WANX_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation
VARIAFLOW_ALIYUN_WANX_IMAGEEDIT_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis
VARIAFLOW_ALIYUN_WANX_MODEL=wanx2.1-imageedit
VARIAFLOW_ALIYUN_WANX_API_KEY=
VARIAFLOW_ALIYUN_USE_SDK_FOR_IMAGEEDIT=true
VARIAFLOW_ALIYUN_IMAGEEDIT_FUNCTION=description_edit
VARIAFLOW_ALIYUN_IMAGEEDIT_STRENGTH=0.85
```

## 输出目录

```text
data/
`-- batch_<batch_code>/
    |-- input_archive/
    |-- input_unpacked/
    |-- normalized/
    |-- preprocessed/
    |-- outputs/
    |   `-- S0001/
    |       `-- variant_1.png
    |-- failed/
    `-- tmp/
```

## 测试

推荐快速回归：

```powershell
pytest -q tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_image_processor.py tests/test_ai_provider_routing.py
```

说明：

- 这组回归已覆盖：
  - 动态视觉字段解析
  - 动态 grounding / lighting Prompt 注入
  - 食品暖调 recipe 强制保护
  - `human_model` 抠图豁免
  - OpenAI 路由逻辑
- `tests/test_executor.py` 需要本地测试库 `variaflow_test`
- 若测试库不存在，完整测试会因数据库连接失败而中断

## 最近一轮真实演进方向

当前系统已经完成从“静态 SKU 规则映射”向“动态物理约束生成”的过渡：

- 视觉模型开始直接生成可执行的物理与光影 Prompt
- 后端只保留少量 fallback 守门逻辑
- 既缓解了规则爆炸，也避免了现阶段完全放权带来的失控

## 相关文档

- 总览文档见 [../RREADME.md](/e:/e-commerce-project/VariaFlow/RREADME.md)
- 测试说明见 [README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
