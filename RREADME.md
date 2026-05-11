# VariaFlow 开发文档总览

VariaFlow 是一套面向电商商拍场景的批量 AI 出图系统，当前仓库包含：

- `variaflow-server`：FastAPI 后端、任务调度、视觉路由、Prompt 组装、AI 网关、QC 与落盘
- `variaflow-ui`：Vue 3 控制台，负责批次上传、任务列表、识别结果透传与状态展示

## 当前核心能力

### 1. 智能视觉路由

后端会先使用视觉模型对源图做意图识别，并输出结构化结果：

- `intent`
- `reason`
- `sku_category`
- `suggested_scene`
- `subject_features`
- `style_features`
- `background_features`

当前默认意图分流：

- `SCENE_EDIT`：商品场景重绘，走 OpenAI `gpt-image-2` 编辑链路
- `POSE_VARIATION`：动作/造型变体
  - 普通 IP / 虚拟角色：走 OpenAI `gpt-image-2` 文生图链路
  - `real_human_model`：强制走 OpenAI `edits` 参考生成链路，保留真人身份一致性

### 2. 电商 SKU 物理分类

系统已扩展为面向电商商拍的全品类物理空间分类，包含但不限于：

- `apparel_flat`
- `apparel_hanging`
- `apparel_invisible_mannequin`
- `shoes_resting`
- `bag_standing`
- `beauty_bottle_standing`
- `jewelry_macro_display`
- `electronic_flat`
- `food_packaged_standing`
- `toy_standing`
- `plush_sitting`
- `real_human_model`

这些分类会驱动后续的：

- 物理锚点
- 画布补白
- 场景配方
- Prompt 约束

### 3. 商业场景配方引擎

后端内置了结构化视觉知识库，用于提升电商主图氛围感与转化感：

- `SPATIAL_GROUNDING_PROMPTS`：物理落地与摆放机位
- `ENVIRONMENT_TEMPLATES`：品类配套环境模板
- `SCENE_RECIPES`：爆品氛围配方
- `NEGATIVE_SPACE_COMPOSITION_RULE`：营销留白规则
- `QUALITY_TERMS` / `LIGHTING_TERMS` / `CAMERA_TERMS` / `RENDER_TERMS`：商业视觉增强词库

新增高转化场景配方包括：

- `french_street_vibe`
- `luxury_water_surface`
- `nature_forest_outdoor`

### 4. 智能画布预处理

为解决“主体太满、没有留白、悬浮断肢”等问题，`SCENE_EDIT` 在调用 OpenAI 之前会做本地预处理：

- 对无透明通道图片自动执行本地静默抠图
- 按 SKU 类型和场景配方进行动态缩放
- 根据物理重力锚点自动放置主体
  - `apparel_hanging`：吸顶
  - `real_human_model`、`shoes_resting`、`toy_standing`、`appliance_standing`：沉底
  - 其他类目：按配置居中或偏置

### 5. 真人模特专线

为避免真人模特被误抠图、断头、替换为假人，当前链路增加了专门纠偏：

- `real_human_model` 场景跳过 `rembg`
- `POSE_VARIATION + real_human_model` 强制走 `openai_image_edit`
- 下游 Prompt 会要求保留同一真人的面部、身形、光影与服装完整性

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

## 开发启动

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

视觉模型已做解耦，可在 `.env` 里切换：

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
pytest -q tests/test_image_processor.py tests/test_openai_config_and_prompt.py tests/test_vision_router.py tests/test_ai_provider_routing.py
```

说明：

- `tests/test_executor.py` 依赖本地 MySQL 测试库 `variaflow_test`
- 若未创建 `VARIAFLOW_TEST_DATABASE_URL` 指向的测试库，完整测试不会全部通过

## 最近一轮真实回归

已基于项目根目录 `image.zip` 做过真实批量验证，关键结论：

- 商品场景重绘可按 SKU 分类走智能补白与场景配方
- 真人模特 `POSE_VARIATION` 已成功改走 `openai_image_edit`
- 任务上下文中已能记录 `provider_hint`、`sku_category`、`suggested_scene` 与视觉特征字段

## 文档索引

- 后端细节见 [variaflow-server/README.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README.md)
- 测试说明见 [variaflow-server/README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
- 前端说明见 [variaflow-ui/README.md](/e:/e-commerce-project/VariaFlow/variaflow-ui/README.md)
