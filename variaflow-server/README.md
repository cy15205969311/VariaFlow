# VariaFlow 服务端
## 本地启动
### 1. 安装依赖
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量
在 `variaflow-server/` 目录下复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

当前推荐的阿里万相单图测试配置：

```env
VARIAFLOW_APP_ENV=development
VARIAFLOW_DEBUG=true
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_DATA_ROOT=./data
VARIAFLOW_IMAGE_PROVIDER=aliyun
VARIAFLOW_USE_MOCK_AI=false
VARIAFLOW_PROVIDER_ENABLE_FALLBACK=false
VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT=1
VARIAFLOW_ALIYUN_WANX_MODEL=wanx2.1-imageedit
VARIAFLOW_ALIYUN_WANX_IMAGEEDIT_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis
VARIAFLOW_ALIYUN_IMAGEEDIT_FUNCTION=description_edit
VARIAFLOW_ALIYUN_IMAGEEDIT_STRENGTH=0.35
VARIAFLOW_ALIYUN_WANX_API_KEY=
VARIAFLOW_QC_MIN_WIDTH=768
VARIAFLOW_QC_MIN_HEIGHT=752
VARIAFLOW_QC_MIN_TOTAL_PIXELS=577536
```

如果需要排查提供方请求和 QC 流程，可以额外打开：

```env
VARIAFLOW_PROVIDER_DEBUG_LOG=true
```

### 3. 初始化数据库
```bash
alembic upgrade head
```

### 4. 启动 API
```bash
uvicorn app.main:app --reload
```

### 5. 验证服务
```bash
curl http://127.0.0.1:8000/health
```

## 输出目录
系统按批次保存文件，不是统一写进 `data/outputs`。

典型结构如下：

```text
data/batch_<batch_code>/
|-- input_archive/
|-- input_unpacked/
|-- normalized/
|-- outputs/
|   `-- S0001/
|       `-- variant_1.png
|-- failed/
`-- tmp/
```

其中：

- `normalized/` 保存去重后的标准化源图
- `outputs/` 保存最终通过 QC 的正式产物
- `tmp/` 保存写入中的临时文件或尚未完成收尾的 `.part`
- `failed/` 预留给失败归档

## 当前图像生成逻辑
- 主提供方由 `VARIAFLOW_IMAGE_PROVIDER` 控制
- 当值为 `aliyun` 时，主链路走阿里万相
- `wanx2.1-imageedit` 通过 DashScope SDK 调用，直接使用本地 `source_image_path`
- 默认关闭 OpenAI fallback，避免测试阶段混入其他提供方结果
- Prompt 已调整为电商背景融合模式：主体保持不变，仅生成背景、环境与自然阴影

## 智能双轨与特征注入
- 视觉识别链路与生图链路已经解耦：
  - 视觉识别使用 `VARIAFLOW_VISION_API_URL` + `VARIAFLOW_VISION_MODEL`
  - 默认示例配置为 `mimo-v2-omni`，也可以切换到其他兼容 `/v1/chat/completions` 的视觉模型
  - 生图仍使用 `VARIAFLOW_OPENAI_IMAGE_MODEL=gpt-image-2`
- 视觉路由会输出五个核心字段：
  - `intent`: `SCENE_EDIT` 或 `POSE_VARIATION`
  - `reason`: 路由原因
  - `subject_features`: 仅在 `POSE_VARIATION` 时返回，描述角色稳定身份特征的英文短语
  - `style_features`: 仅在 `POSE_VARIATION` 时返回，描述渲染风格、材质、光影语义
  - `background_features`: 仅在 `POSE_VARIATION` 时返回，描述原图背景环境与色调
- 这三类特征会被写入任务 `prompt_snapshot_json`，并透传到任务列表 API
- 当任务命中 `POSE_VARIATION` 时，Prompt Builder 会同时把 `subject_features`、`style_features`、`background_features` 强注入到最终提示词中，用于尽量锁定 IP 主体一致性、画风和原始场景氛围
- 当前双轨执行策略：
  - `SCENE_EDIT` -> `/v1/images/edits`
  - `POSE_VARIATION` -> `/v1/images/generations`

## 说明
- 上传接口 `POST /api/v1/batches/upload` 当前仅接收 ZIP 压缩包
- 上传后的文件会落在 `VARIAFLOW_DATA_ROOT/batch_<batch_code>/...`
- 默认单图测试张数由 `VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT=1` 控制
- 调度器只会消费父批次 `batch_job.status=running` 的 `generation_task`
- 阿里 `wanx2.1-imageedit` 的返回分辨率可能略低于请求值，因此 QC 改为可配置阈值校验
