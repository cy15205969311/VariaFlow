<template>
  <div class="placeholder-view">
    <p class="card-eyebrow">Prompt Presets</p>
    <h2>Prompt 预设中心</h2>
    <p>
      这里预留给后续的动作库、穿搭库、场景库和变量抽屉配置。
      当前版本优先完成任务大盘与 ZIP 上传工作流。
    </p>
  </div>
</template>

<style scoped>
.placeholder-view {
  padding: 28px;
  border: 1px solid rgba(228, 228, 231, 0.94);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: var(--vf-shadow);
}

.card-eyebrow,
h2,
p {
  margin: 0;
}

.card-eyebrow {
  color: var(--vf-subtle);
  font-size: 12px;
  font-weight: 600;
}

h2 {
  margin-top: 8px;
  color: var(--vf-text);
  font-size: 20px;
  font-weight: 700;
}

p {
  margin-top: 12px;
  max-width: 720px;
  color: var(--vf-muted);
  font-size: 14px;
  line-height: 1.7;
}
</style>
