# VariaFlow UI

## 初始化命令

```bash
npm create vite@latest variaflow-ui -- --template vue
cd variaflow-ui
npm install
```

## 当前依赖

- `vue`
- `vite`
- `vue-router`
- `pinia`
- `axios`
- `element-plus`
- `@element-plus/icons-vue`

## 本地启动

```bash
npm install
npm run dev
```

默认会将 `/api` 代理到 `http://127.0.0.1:8000`，便于直接联调 FastAPI。
