# VariaFlow 开发总览

VariaFlow 是一套面向电商商拍场景的批量 AI 出图系统，当前仓库包含两个核心子项目：

- `variaflow-server`：FastAPI 后端，负责上传、任务切片、视觉路由、Prompt 组装、图像生成调度、QC 与结果落盘。
- `variaflow-ui`：Vue 3 控制台，负责批次上传、任务轮询、结果展示与人工重试入口。

## 本轮架构更新

### 1. 视觉中枢升级为“动态分析 + 轻量知识图谱”混合架构

视觉路由不再只输出简单的 `intent`，还会补充更强的结构化结果：

- `subject_type`
- `sku_category`
- `primary_sku_description`
- `secondary_props`
- `dynamic_props`
- `suggested_scene_recipe`
- `dynamic_spatial_prompt`
- `dynamic_lighting_prompt`
- `camera_perspective`

当前主原则：

- `SCENE_EDIT`：以商品不变形为核心，只重绘环境与辅陈。
- `POSE_VARIATION`：用于 IP、角色、玩偶等动作/造型变体。
- 只要原图里出现真实人体部位，`sku_category` 必须优先落到 `real_human_model`。

### 2. Prompt Builder 已接入电商知识图谱约束

后端现在会把视觉模型输出与领域知识一起编译成最终 Prompt：

- 相机视角约束：`camera_perspective`
- 类目物理约束：如鞋靴落地、服饰斜靠、真人严格锁定
- 动态 props 过滤：默认屏蔽不合理道具，如非商务场景下的 `watch`
- 负向保护锁：真人模特禁止新增首饰、包、帽子等配件

新增核心文件：

- `variaflow-server/app/core/knowledge_engine.py`
- `variaflow-server/app/core/knowledge_graph.py`

### 3. 场景重绘新增真人保护与智能排版

`SCENE_EDIT` 在调用 OpenAI 之前会先执行本地预处理：

- 普通商品：透明底处理 + 智能缩放补白 + 锚点排版
- `apparel_leaning`：新增“斜靠墙面”底部锚定策略
- 真人模特：不再破坏原图像素，改为生成背景编辑遮罩并走 `images/edits`

这样可以同时解决：

- 商品撑满画面导致无留白
- 鞋靴/站立主体悬浮
- 真人模特被误抠图或被模型“换人”

### 4. 调度器已优先处理最新批次

为了解决“旧批次长期占用队列，前端看不到新批次结果”的问题，调度器现在会优先消费最新上传的运行中批次，而不是一味按最早任务 ID 排序。

核心改动文件：

- `variaflow-server/app/services/scheduler.py`

### 5. 上传与前端联调链路已加固

上传与轮询链路补齐了防呆逻辑：

- 后端上传接口补充异常日志，ZIP 解析失败不再静默
- 前端上传成功后，立即刷新批次和任务列表
- 上传响应缺少 `batch.id` 时直接报错
- 轮询刷新失败时写入控制台，避免“进度条 100% 但界面无反馈”

相关文件：

- `variaflow-server/app/api/endpoints/batches.py`
- `variaflow-server/app/services/upload.py`
- `variaflow-ui/src/views/Dashboard/components/UploadEngine.vue`
- `variaflow-ui/src/views/Dashboard/index.vue`
- `variaflow-ui/src/stores/batch.js`

## 仓库结构

```text
VariaFlow/
|-- RREADME.md
|-- image.zip
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
|   |-- README.md
|   `-- README_TEST.md
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

## 推荐回归

### 后端关键回归

```powershell
cd variaflow-server
pytest -q tests/test_batches_endpoint.py tests/test_scheduler.py tests/test_recovery.py tests/test_executor.py::test_happy_path tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_image_processor.py
```

### 前端构建校验

```powershell
cd variaflow-ui
npm run build
```

## 文档索引

- 后端开发说明：[variaflow-server/README.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README.md)
- 测试说明：[variaflow-server/README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
- 前端说明：[variaflow-ui/README.md](/e:/e-commerce-project/VariaFlow/variaflow-ui/README.md)

## 最新补充

### 物理互斥锁与材质感知

- 视觉路由现在会额外输出 `material_type`，统一收敛为 `fabric_soft / fabric_stiff / reflective_glass / leather_or_pu / matte_solid`
- 当商品被识别为软性织物时，后端会自动拦截 `apparel_leaning`，避免卫衣、毛衣这类商品出现违背重力的靠墙姿态
- Prompt Builder 会把材质规则作为高优先级指令注入最终 Prompt，例如玻璃焦散反射、皮革高光、针织纹理柔光

### Dashboard 大图预览

- 任务卡片已支持点击原图与结果图打开毛玻璃预览层
- 预览层画框固定为 `80vmin` 正方形，统一不同图片的观感尺寸
- 支持点击遮罩关闭、Esc 关闭、透明图白底展示
