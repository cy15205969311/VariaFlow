# VariaFlow 开发文档
## 项目概览
VariaFlow 是一个面向电商商品图裂变的批量生图系统，当前采用前后端分离结构：

- `variaflow-server`：FastAPI + SQLAlchemy Async + MySQL 的后端服务
- `variaflow-ui`：Vue 3 + Vite + Pinia 的前端控制台

当前主链路已经切换到阿里云万相，默认优先使用 `wanx2.1-imageedit` 进行商品图背景融合测试。

## 目录结构
```text
VariaFlow/
|-- variaflow-server/
|   |-- alembic/
|   |-- app/
|   |-- data/
|   |-- scripts/
|   |-- sql/
|   |-- tests/
|   |-- .env.example
|   |-- README.md
|   `-- README_TEST.md
|-- variaflow-ui/
|   |-- src/
|   `-- README.md
|-- .gitignore
`-- RREADME.md
```

## 当前后端链路
- 图片提供方通过 `VARIAFLOW_IMAGE_PROVIDER` 控制，当前推荐值为 `aliyun`
- 阿里万相图像编辑模型使用 `VARIAFLOW_ALIYUN_WANX_MODEL=wanx2.1-imageedit`
- `wanx2.1-imageedit` 通过 DashScope SDK 调用，本地源图直接走 `source_image_path`
- 默认关闭 OpenAI 容灾：`VARIAFLOW_PROVIDER_ENABLE_FALLBACK=false`
- 默认单图测试：`VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT=1`
- 默认电商 Prompt 已改为“主体不变，只生成背景/光影/环境”

## 开发环境要求
- Python 3.10+
- Node.js 18+
- npm 9+
- MySQL 8.0+

## 后端开发
### 安装依赖
在 `variaflow-server` 目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 配置环境变量
复制模板：

```bash
copy .env.example .env
```

联调阿里万相时重点检查这些字段：

```env
VARIAFLOW_DATABASE_URL=mysql+aiomysql://root:password@127.0.0.1:3306/variaflow
VARIAFLOW_DATA_ROOT=./data
VARIAFLOW_IMAGE_PROVIDER=aliyun
VARIAFLOW_USE_MOCK_AI=false
VARIAFLOW_PROVIDER_ENABLE_FALLBACK=false
VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT=1
VARIAFLOW_ALIYUN_WANX_MODEL=wanx2.1-imageedit
VARIAFLOW_ALIYUN_WANX_API_KEY=你的阿里云密钥
VARIAFLOW_ALIYUN_WANX_IMAGEEDIT_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis
VARIAFLOW_ALIYUN_IMAGEEDIT_FUNCTION=description_edit
VARIAFLOW_ALIYUN_IMAGEEDIT_STRENGTH=0.35
VARIAFLOW_QC_MIN_WIDTH=768
VARIAFLOW_QC_MIN_HEIGHT=752
VARIAFLOW_QC_MIN_TOTAL_PIXELS=577536
```

### 初始化数据库
```bash
alembic upgrade head
```

### 启动服务
```bash
uvicorn app.main:app --reload
```

### 后端测试
```bash
pytest
```

如果只想验证这次调整过的配置与 QC 逻辑，可以先跑：

```bash
pytest -q tests/test_openai_config_and_prompt.py tests/test_qc_engine.py
```

## 前端开发
在 `variaflow-ui` 目录执行：

```bash
npm install
npm run dev
```

## 数据目录说明
当前输出不是统一落在 `data/outputs`，而是按批次分目录保存：

```text
variaflow-server/data/batch_<batch_code>/
|-- input_archive/
|-- input_unpacked/
|-- normalized/
|-- outputs/
|   `-- S0001/
|       `-- variant_1.png
|-- failed/
`-- tmp/
```

示例成功产物：

- `variaflow-server/data/batch_f53c4b02bfc5/outputs/S0003/variant_1.png`

如果某个任务只在 `tmp` 留下 `.part` 文件，通常表示它在最终落盘前被 QC 或上游错误拦截了。

## 当前调试建议
### 单图测试
建议先上传只包含 1 张透明 PNG 的 ZIP 包，确认以下链路：

1. 批次创建成功
2. 任务进入 `running`
3. 阿里万相返回结果
4. QC 通过
5. 图片落到对应批次的 `outputs/S000x/variant_1.png`

### wanx2.1-imageedit 注意事项
- 更适合透明底商品主体 + 背景重绘场景
- 当前项目使用电商场景融合 Prompt，不再强调人物动作变体
- 阿里返回分辨率可能小于名义值，所以系统使用可配置 QC 阈值而不是硬卡 `1024x1024`

## 提交规范
推荐使用语义化提交，并保持“类型英文 + 描述中文”的格式：

```text
feat: 切换阿里万相图像编辑链路
feat: 更新开发文档与测试说明
fix: 修复图像质检对.part文件的识别
docs: 补充批次输出目录说明
```

常用类型：

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`
