# VariaFlow Server

`variaflow-server` 是 VariaFlow 的后端服务，负责：

- ZIP 批次上传与解压
- 原图标准化与任务切片
- 多模态视觉路由
- Prompt 组装与知识图谱约束注入
- 图像生成调度、重试、QC 与结果落盘
- 向前端透传任务识别结果、状态与输出地址

## 当前核心链路

### 1. 上传入库

入口：

- `app/api/endpoints/batches.py`
- `app/services/upload.py`

职责：

- 接收 ZIP 上传
- 归档输入文件、解压图片、生成标准化源图
- 创建 `batch_job / source_task / generation_task`
- 对上传异常补齐 `logger.exception(...)`

本轮新增：

- ZIP 解析或写库失败时明确返回错误，不再静默吞异常
- 上传成功后由前端立即刷新对应批次

### 2. 视觉路由

核心文件：

- `app/services/vision_router.py`

当前会输出：

- `intent`
- `reason`
- `subject_type`
- `sku_category`
- `material_type`
- `primary_sku_description`
- `secondary_props`
- `dynamic_props`
- `suggested_scene`
- `suggested_scene_recipe`
- `dynamic_spatial_prompt`
- `dynamic_lighting_prompt`
- `camera_perspective`
- `subject_features`
- `style_features`
- `background_features`

本轮新增的物理互斥与材质认知：

- `material_type` 统一收敛到 `fabric_soft / fabric_stiff / reflective_glass / leather_or_pu / matte_solid`
- 软性服饰命中 `fabric_soft` 时，禁止走 `apparel_leaning`
- `prompt_builder` 会在最终 Prompt 阶段再次兜底，防止前端或模型误传错误姿态

关键规则：

- `SCENE_EDIT`：优先走场景重绘
- `POSE_VARIATION`：优先走变体生成
- 只要有真人身体部位，`sku_category` 必须为 `real_human_model`
- 新增 `apparel_leaning` 类目，用于墙面斜靠陈列

### 3. 知识图谱与 Prompt 编译

核心文件：

- `app/core/knowledge_engine.py`
- `app/core/knowledge_graph.py`
- `app/core/prompt_lexicon.py`
- `app/services/prompt_builder.py`

当前 Prompt 组装逻辑为：

1. 读取视觉模型输出的动态物理与光影字段
2. 根据 `sku_category` 注入领域约束
3. 根据 `material_type` 注入材质专属光影规则
4. 根据 `camera_perspective` 注入视角对齐语句
5. 若触发“软服饰 + leaning”互斥锁，则强制降级为 `apparel_flat` 并写入 warning 日志
6. 根据 `primary_sku_description` / `dynamic_props` 过滤不合理 props
7. 对真人模特追加严格负向锁

已经落地的典型约束：

- `real_human_model`：禁止新增饰品、包、帽子、手表
- `shoes_resting`：锁死原始透视与地面接触关系
- `apparel_leaning`：只允许硬挺结构类商品使用
- `fabric_soft`：强制改写为平铺/悬挂安全路径，避免软衣物靠墙
- `reflective_glass`：自动注入焦散反射、镜面反射与透明材质高光
- `leather_or_pu`：自动注入皮纹高光和高级材质边缘光
- `food_plated`：强制暖色食欲光影

### 4. 本地图像预处理

核心文件：

- `app/utils/image_processor.py`

当前支持：

- 不透明图片本地透明底处理
- 1024 透明画布缩放补白
- 按类目执行顶部/底部/居中锚定
- 真人模特生成反向背景遮罩
- 非 PNG 真人源图自动转成可配合 `mask` 上传的 PNG

关键策略：

- `real_human_model`：保留原图主体像素，只让 OpenAI 修改背景
- `apparel_leaning`：底部锚定，给墙角构图留空间
- 站立类商品：底部锚定，避免“踩空”

### 5. 执行器与 Provider 调度

核心文件：

- `app/services/executor.py`
- `app/gateways/ai_provider.py`

职责：

- 调用视觉路由
- 组装 provider payload
- 场景重绘前执行图像预处理
- 调 OpenAI / 其他图像 provider
- 执行 QC
- 结果落盘并回写数据库

本轮新增：

- `prompt_snapshot_json` 中会记录：
  - `dynamic_props`
  - `camera_perspective`
  - `source_image_mask_generated`
  - `source_image_mask_name`
  - 预处理后的画布信息

### 6. 调度器与恢复循环

核心文件：

- `app/services/scheduler.py`
- `app/services/recovery.py`

当前行为：

- 优先拉取最新上传且仍在 `running` 的批次
- 从 `pending / retrying` 中锁定下一个任务
- 恢复循环会回收租约超时任务
- 测试中已覆盖 MySQL `1213 deadlock` 与 `1205 lock wait timeout`

## 前端关心的任务透传字段

`/api/v1/tasks` 现在会额外返回这些信息，供控制台展示或调试：

- `dynamic_props`
- `camera_perspective`
- `material_type`
- `dynamic_spatial_anchor`
- `dynamic_lighting_needs`
- `primary_sku_description`
- `secondary_props`
- `output_path`

接口相关文件：

- `app/api/endpoints/tasks.py`
- `app/schemas/tasks.py`

另外已新增手动重试接口：

- `POST /api/v1/tasks/{generation_task_id}/retry`

## 常用环境变量

### 基础配置

```env
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_TEST_DATABASE_URL=mysql+aiomysql://test_user:test_pass@127.0.0.1:3306/variaflow_test
VARIAFLOW_DATA_ROOT=./data
VARIAFLOW_PROVIDER_DEBUG_LOG=true
VARIAFLOW_PROVIDER_REQUEST_TIMEOUT_SECONDS=180
```

### 视觉路由

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

### OpenAI 生图

```env
VARIAFLOW_IMAGE_PROVIDER=openai
VARIAFLOW_OPENAI_IMAGE_EDIT_URL=https://api.openai.com/v1/images/edits
VARIAFLOW_OPENAI_IMAGE_GENERATION_URL=https://api.openai.com/v1/images/generations
VARIAFLOW_OPENAI_IMAGE_MODEL=gpt-image-2
VARIAFLOW_OPENAI_IMAGE_API_KEY=
```

## 本地启动

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
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

## 推荐回归

```powershell
pytest -q tests/test_batches_endpoint.py tests/test_scheduler.py tests/test_recovery.py tests/test_executor.py::test_happy_path tests/test_vision_router.py tests/test_openai_config_and_prompt.py tests/test_image_processor.py
```

## 相关文档

- 项目总览：[../RREADME.md](/e:/e-commerce-project/VariaFlow/RREADME.md)
- 测试说明：[README_TEST.md](/e:/e-commerce-project/VariaFlow/variaflow-server/README_TEST.md)
