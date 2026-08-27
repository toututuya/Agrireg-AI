<template>
    <div id="agrireg-ai-app">
      <router-view></router-view>
    </div>
</template>

<script>
export default { name: 'App' };
</script>

<style>
  html { color-scheme: light; }
  html, body, #app, #agrireg-ai-app { min-width: 320px; min-height: 100%; margin: 0; background: #f3f7f1; }
  body { font-family: Inter, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; color: #16352b; }
  * { box-sizing: border-box; }
a { color: inherit; text-decoration: none; }
</style>
