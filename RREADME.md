# VariaFlow 开发文档总览

VariaFlow 是一套面向电商商拍场景的批量 AI 出图系统，当前仓库包含：

- `variaflow-server`：FastAPI 后端、任务调度、视觉路由、Prompt 组装、AI 网关、QC 与落盘
- `variaflow-ui`：Vue 3 控制台，负责批次上传、任务列表、识别结果透传与状态展示

## 当前架构重点

### 1. 智能视觉路由

后端会先使用视觉模型对源图做结构化分析，当前会输出：

- `intent`
- `reason`
- `subject_type`
- `sku_category`
- `suggested_scene`
- `suggested_scene_recipe`
- `dynamic_spatial_prompt`
- `dynamic_lighting_prompt`
- `primary_sku_description`
- `secondary_props`
- `subject_features`
- `style_features`
- `background_features`

其中：

- `SCENE_EDIT`：商品场景重绘，主链路走 OpenAI `gpt-image-2` 编辑接口
- `POSE_VARIATION`：动作/造型变体
  - 普通 IP / 虚拟角色：走 OpenAI `gpt-image-2` 文生图链路
  - `real_human_model`：强制走 OpenAI `edits` 参考生成链路，保留真人身份一致性

### 2. 从静态规则到动态分析

系统已经从“纯 SKU 字典映射”升级为“动态物理约束生成 + 轻量兜底”的混合架构。

当前原则：

- 优先让 Mimo 直接生成商品的物理落位和打光提示
- 后端直接把这些动态分析结果拼进最终 Prompt
- 如果动态字段缺失、太短或不可执行，再回退到少量内置兜底规则

这意味着系统不再依赖庞大的 `SPATIAL_GROUNDING_PROMPTS` 词典，但仍保留可控的保护层，避免完全裸奔。

### 3. 任务卡片可解释性

前后端任务链路现在可以透传更多 AI 思考结果：

- 主售卖主体 `primary_sku_description`
- 次要配饰 `secondary_props`
- 动态空间落位 `dynamic_spatial_anchor`
- 动态打光需求 `dynamic_lighting_needs`
- 场景配方键 `suggested_scene_recipe`

这让控制台既能展示结果，也能展示 AI 为什么这样画。

### 4. 预处理与真人豁免

为解决“主体太满、悬浮、误抠图”等问题，`SCENE_EDIT` 在调用 OpenAI 之前会做本地预处理：

- 对无透明通道图片自动执行本地静默抠图
- 对商品图执行自动缩放、透明画布补白和重力锚点排版
- 对真人模特类任务不再裁主体，而是生成背景编辑遮罩

现在真人豁免不再只依赖 `real_human_model`，还可以通过：

- `subject_type == human_model`

来直接控制。当前真人链路会把原图转为 `PNG` 后与自动生成的 `mask` 一起传给 OpenAI `images/edits`，从而只换背景、不动模特与配饰主体。

## 关键目录

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
|   `-- README.md
`-- variaflow-ui/
    |-- src/
    `-- README.md
```

## 本地启动

### 后端

```powershell
cd variaflow-server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
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

## 环境变量重点

视觉模型已解耦，可在 `.env` 里切换：

```env
VARIAFLOW_VISION_PROVIDER=mimo

VARIAFLOW_MIMO_VISION_API_URL=https://token-plan-cn.xiaomimimo.com/v1
VARIAFLOW_MIMO_VISION_MODEL=mimo-v2-omni
VARIAFLOW_MIMO_VISION_API_KEY=

VARIAFLOW_DEEPSEEK_VISION_API_URL=https://api.deepseek.com/v1
VARIAFLOW_DEEPSEEK_VISION_MODEL=deepseek-v4-flash
# VARIAFLOW_DEEPSEEK_VISION_MODEL=deepseek-v4-pro
VARIAFLOW_DEEPSEEK_VISION_API_KEY=
```

图像生成主链路：

```env
VARIAFLOW_IMAGE_PROVIDER=openai
VARIAFLOW_OPENAI_IMAGE_EDIT_URL=https://api.openai.com/v1/images/edits
VARIAFLOW_OPENAI_IMAGE_GENERATION_URL=https://api.openai.com/v1/images/generations
VARIAFLOW_OPENAI_IMAGE_MODEL=gpt-image-2
VARIAFLOW_OPENAI_IMAGE_API_KEY=
```

## 测试建议

快速回归：

```powershell
cd variaflow-server
pytest -q tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_image_processor.py tests/test_ai_provider_routing.py tests/test_recovery.py
```

说明：

- 当前这一组回归已覆盖动态视觉字段、Prompt 动态 grounding、食品暖调兜底、真人遮罩链路、OpenAI `mask` 透传以及恢复逻辑中的死锁重试判定
- `tests/test_executor.py` 依赖本地 MySQL 测试库 `variaflow_test`
- 若未创建 `VARIAFLOW_TEST_DATABASE_URL` 指向的测试库，完整测试不会全部通过

## 最近一轮架构演进

本轮已完成以下升级：

- 视觉模型输出字段升级为 `dynamic_spatial_prompt` 与 `dynamic_lighting_prompt`，后端继续兼容旧字段名
- 场景重绘新增真人背景遮罩链路，自动向 OpenAI `images/edits` 追加 `mask`
- 自动补白策略收敛为三档：真人沉底、悬挂吸顶、常规商品居中
- 执行器会把预处理元信息、遮罩文件名与是否生成遮罩持久化到任务快照
- 新增死锁/锁等待超时识别测试，便于恢复循环后续接入重试策略

## 文档索引

- 后端细节见 [variaflow-server/README.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README.md)
- 测试说明见 [variaflow-server/README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
- 前端说明见 [variaflow-ui/README.md](/e:/e-commerce-project/VariaFlow/variaflow-ui/README.md)
