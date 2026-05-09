# VariaFlow 开发文档

## 1. 项目简介

VariaFlow 是一个面向电商主图批量生产场景的 AIGC 裂变系统，目标是围绕“批量上传、任务调度、AI 生图、质检、结果回收”构建一套可持续迭代的生产工具。

当前项目采用前后端分离目录结构：

- `variaflow-server`：后端服务，基于 FastAPI、SQLAlchemy 2.0、MySQL。
- `variaflow-ui`：前端控制台，基于 Vue 3、Vite、Pinia、Element Plus、Tailwind CSS。

---

## 2. 目录结构

```text
VariaFlow/
├─ variaflow-server/          # 后端服务
│  ├─ alembic/                # 数据库迁移
│  ├─ app/                    # 应用主代码
│  ├─ scripts/                # 沙盒脚本、辅助脚本
│  ├─ sql/                    # SQL 脚本
│  ├─ tests/                  # 自动化测试
│  ├─ .env.example            # 后端环境变量样例
│  ├─ requirements.txt        # 后端依赖
│  └─ README.md               # 后端说明
├─ variaflow-ui/              # 前端控制台
│  ├─ src/                    # 前端源码
│  ├─ package.json            # 前端依赖与脚本
│  ├─ tailwind.config.js      # Tailwind 配置
│  └─ README.md               # 前端说明
├─ .gitignore                 # 仓库忽略规则
└─ RREADME.md                 # 根目录开发文档
```

---

## 3. 技术栈说明

### 3.1 后端

- Python 3.10+
- FastAPI
- SQLAlchemy 2.0 Async
- MySQL
- Alembic
- Pillow
- httpx

### 3.2 前端

- Vue 3
- Vite
- Pinia
- Vue Router
- Element Plus
- Tailwind CSS
- Axios

---

## 4. 本地开发环境要求

### 4.1 通用要求

- Git
- Node.js 18+
- npm 9+
- Python 3.10+
- MySQL 8.0+

### 4.2 推荐约定

- 前端默认端口：`5173`
- 后端默认端口：`8000`
- 前端通过 Vite Proxy 将 `/api` 转发到后端

---

## 5. 后端开发说明

### 5.1 安装依赖

在 `variaflow-server` 目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5.2 配置环境变量

复制环境变量模板：

```bash
copy .env.example .env
```

建议重点检查以下字段：

- `VARIAFLOW_DATABASE_URL`
- `VARIAFLOW_DATA_ROOT`
- `VARIAFLOW_DEBUG`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `WANX_API_KEY`
- `USE_MOCK_AI`

### 5.3 初始化数据库

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

### 5.4 启动后端服务

```bash
uvicorn app.main:app --reload
```

### 5.5 后端测试

```bash
pytest
```

如需沙盒验证，可结合 `scripts/` 中的脚本进行本地链路测试。

---

## 6. 前端开发说明

### 6.1 安装依赖

在 `variaflow-ui` 目录执行：

```bash
npm install
```

### 6.2 启动前端服务

```bash
npm run dev
```

### 6.3 前端构建

```bash
npm run build
```

### 6.4 前端样式方案

当前前端采用以下组合：

- Element Plus：负责基础业务组件能力。
- Tailwind CSS：负责主界面布局、间距、颜色和现代 SaaS 风格样式。

开发时建议遵循以下原则：

- 优先使用 Tailwind 原子类搭建布局与视觉层级。
- 仅在 Element Plus 组件需要覆盖默认外观时，使用少量局部样式补充。
- 新增中文文案统一使用简体中文。

---

## 7. 开发工作流建议

### 7.1 分支建议

推荐使用如下分支策略：

- `main`：稳定主分支
- `feat/*`：新功能开发分支
- `fix/*`：缺陷修复分支
- `refactor/*`：重构分支

### 7.2 提交信息规范

推荐使用语义化提交，并配合中文描述：

```text
feat: 新增根目录开发文档
feat: 重构上传区域界面样式
fix: 修复任务分页状态同步问题
refactor: 优化前端布局结构
docs: 更新本地启动说明
```

要求：

- 类型使用英文：`feat`、`fix`、`docs`、`refactor`、`test`、`chore`
- 描述使用中文，简洁明确
- 单次提交尽量只聚焦一个变更主题

---

## 8. 联调说明

前后端联调时建议顺序如下：

1. 先启动 MySQL
2. 启动后端服务 `uvicorn app.main:app --reload`
3. 启动前端服务 `npm run dev`
4. 浏览器访问前端地址并验证：
   - 批次上传
   - 批次状态轮询
   - 任务列表分页与筛选
   - 上传区交互与 UI 样式

---

## 9. 注意事项

### 9.1 不建议提交的内容

以下内容不应提交到仓库：

- `node_modules`
- `dist`
- `.env`
- 本地数据库连接信息
- 运行生成的数据目录

### 9.2 文档维护要求

- 新增模块后，同步更新根目录开发文档。
- 影响启动方式或依赖安装的修改，必须同步更新文档。
- 如果后续引入 Docker、CI/CD、对象存储、真实模型网关配置，建议继续扩展本开发文档。

---

## 10. 后续建议

当前项目已具备基础工程骨架，后续建议优先推进：

1. 完善根目录统一 README 与部署文档。
2. 清理前端依赖残留，统一锁定版本。
3. 补齐上传重试、任务重试等交互闭环。
4. 对接真实 AI 网关并补充生产环境配置说明。

如需继续扩展，可在本文件基础上追加：

- 部署文档
- 数据库建模文档
- API 接口文档
- 前端组件规范文档
