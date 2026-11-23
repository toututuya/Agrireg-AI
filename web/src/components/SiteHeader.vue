<template>
  <header class="site-header">
    <a class="skip-link" href="#main-content" @click.prevent="skipToContent">跳到主要内容</a>
    <div class="site-header-inner frame">
      <router-link to="/" class="site-brand" aria-label="AgriReg AI 首页">
        <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
        <strong>AgriReg AI</strong>
      </router-link>
      <nav class="site-nav" aria-label="主导航">
        <router-link exact-path to="/">首页</router-link>
        <router-link exact-path to="/graph">知识图谱</router-link>
        <router-link exact-path to="/ask">AI 问答</router-link>
        <router-link exact-path to="/agent">任务分析</router-link>
      </nav>
      <router-link v-if="$route.name !== 'landing'" to="/" class="header-index">
        <UiIcon name="search" /> 登记检索
      </router-link>
      <span v-else class="header-index index-label">全球农药登记知识库</span>
    </div>
  </header>
</template>

<script>
import UiIcon from './UiIcon.vue';

export default {
  name: 'SiteHeader',
  components: { UiIcon },
  methods: {
    skipToContent() {
      const main = document.getElementById('main-content');
      if (main) {
        main.focus({ preventScroll: true });
        main.scrollIntoView({ block: 'start' });
      }
    }
  }
};
</script>

<style scoped>
.site-header {
  position: sticky;
  z-index: 10;
  top: 0;
  background: var(--paper);
  border-bottom: 1px solid var(--line);
}
.site-header-inner {
  display: grid;
  min-height: 69px;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 24px;
}
.site-brand { display: inline-flex; width: fit-content; align-items: center; gap: 10px; }
.site-brand strong { font-size: 20px; letter-spacing: -.035em; white-space: nowrap; }
.brand-mark { position: relative; width: 34px; height: 34px; border-radius: 8px; background: var(--accent); }
.brand-mark i { position: absolute; z-index: 1; width: 5px; height: 5px; border-radius: 50%; background: #ecf1d5; }
.brand-mark i:nth-child(1) { top: 9px; left: 8px; }
.brand-mark i:nth-child(2) { top: 14px; left: 21px; }
.brand-mark i:nth-child(3) { top: 22px; left: 11px; }
.brand-mark::before, .brand-mark::after {
  position: absolute;
  height: 1px;
  background: #ecf1d5;
  content: '';
  transform-origin: left;
}
.brand-mark::before { top: 11px; left: 11px; width: 14px; transform: rotate(22deg); }
.brand-mark::after { top: 24px; left: 14px; width: 13px; transform: rotate(-41deg); }
.site-nav { display: flex; align-self: stretch; align-items: stretch; gap: 9px; }
.site-nav a {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
}
@media (hover: hover) { .site-nav a:hover { color: var(--accent); background: var(--wash); } }
.site-nav .router-link-exact-active { color: var(--accent); font-weight: 750; }
.site-nav .router-link-exact-active::after {
  position: absolute;
  inset: auto 10px 0;
  height: 2px;
  background: var(--accent);
  content: '';
}
.header-index { display: inline-flex; justify-self: end; align-items: center; gap: 7px; min-height: 42px; color: var(--accent); font-size: 13px; font-weight: 700; }
.header-index:not(.index-label):hover { text-decoration: underline; }
.index-label { color: var(--muted); font-weight: 500; }
@media (max-width: 720px) {
  .site-header { position: static; }
  .site-header-inner { grid-template-columns: 1fr auto; gap: 0 12px; padding-top: 8px; }
  .site-brand { min-height: 46px; }
  .site-brand strong { font-size: 18px; }
  .brand-mark { width: 34px; flex: 0 0 34px; }
  .site-nav { grid-row: 2; grid-column: 1 / -1; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; }
  .site-nav a { min-height: 44px; justify-content: center; padding: 0 4px; font-size: 13px; }
  .header-index { grid-row: 1; grid-column: 2; }
}
</style>
