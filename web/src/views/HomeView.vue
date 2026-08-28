<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="topbar">
      <router-link to="/" class="brand" aria-label="返回 AgriReg AI 首页">
        <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="brand-copy">
          <strong>AgriReg AI</strong>
          <small>全球农药知识图谱</small>
        </span>
      </router-link>

      <nav aria-label="主导航">
        <router-link to="/graph">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="m8.2 10.9 7.6-3.8M8.2 13.1l7.6 3.8"/></svg>
          知识图谱
        </router-link>
        <router-link to="/ask">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v11H9l-4 3V5Z"/><path d="M9 9h6M9 12h4"/></svg>
          AI 问答
        </router-link>
        <router-link to="/agent">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v5H5zM5 15h14v5H5zM8 9v6m8-6v6"/><circle cx="8" cy="12" r="1.5"/><circle cx="16" cy="12" r="1.5"/></svg>
          任务分析
        </router-link>
      </nav>
    </header>

    <main id="main-content" class="main-panel" tabindex="-1"><router-view /></main>
  </div>
</template>

<script>
export default {
  name: 'HomeView',
  created() {
    document.title = 'AgriReg AI · 全球农药知识图谱';
  },
  watch: {
    '$route.name'() {
      this.$nextTick(() => {
        const main = document.getElementById('main-content');
        if (main) main.focus({ preventScroll: true });
      });
    }
  }
};
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at 72% -8%, rgba(80, 214, 144, .09), transparent 32rem),
    radial-gradient(circle at 10% 34%, rgba(74, 184, 203, .055), transparent 28rem),
    #07110e;
  color: #edf7f1;
}
.skip-link { position: fixed; z-index: 100; top: 8px; left: 12px; padding: 10px 14px; transform: translateY(-160%); border-radius: 8px; background: #a4ffcb; color: #07110e; font-size: 13px; font-weight: 800; }
.skip-link:focus { transform: translateY(0); }
.topbar {
  position: sticky; z-index: 30; top: 0; display: flex; min-height: 70px; align-items: center;
  padding: 9px clamp(16px, 3vw, 44px); border-bottom: 1px solid rgba(181,231,203,.13);
  background: rgba(7,17,14,.88); box-shadow: 0 12px 34px rgba(0,0,0,.12); backdrop-filter: blur(20px) saturate(1.1);
}
.brand { display: flex; align-items: center; gap: 11px; color: inherit; text-decoration: none; }
.brand-mark { position: relative; display: block; width: 40px; height: 40px; border: 1px solid rgba(164,255,203,.28); border-radius: 50%; background: rgba(164,255,203,.035); box-shadow: 0 0 24px rgba(80,214,144,.08); }
.brand-mark i { position: absolute; width: 7px; height: 7px; border-radius: 50%; background: #a4ffcb; box-shadow: 0 0 10px rgba(164,255,203,.7); }
.brand-mark i:nth-child(1) { top: 9px; left: 9px; }
.brand-mark i:nth-child(2) { top: 17px; right: 8px; }
.brand-mark i:nth-child(3) { bottom: 8px; left: 12px; }
.brand-mark::before, .brand-mark::after { position: absolute; height: 1px; background: rgba(164,255,203,.55); content: ''; transform-origin: left; }
.brand-mark::before { top: 13px; left: 15px; width: 15px; transform: rotate(27deg); }
.brand-mark::after { top: 20px; left: 16px; width: 14px; transform: rotate(-43deg); }
.brand-copy strong, .brand-copy small { display: block; }
.brand-copy strong { color: #edf7f1; font-size: 15px; letter-spacing: .02em; }
.brand-copy small { margin-top: 2px; color: #71877c; font-size: 10px; }
nav { display: flex; align-self: stretch; align-items: center; gap: 8px; margin-left: clamp(28px, 6vw, 86px); }
nav a { display: flex; align-items: center; gap: 7px; padding: 10px 13px; border: 1px solid transparent; border-radius: 11px; color: #91a79c; font-size: 13px; font-weight: 650; text-decoration: none; }
nav a:hover { border-color: rgba(164,255,203,.12); background: rgba(164,255,203,.05); color: #d8e9df; }
nav a.router-link-active { border-color: rgba(164,255,203,.2); background: rgba(164,255,203,.1); color: #a4ffcb; }
nav svg { width: 17px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.main-panel { min-width: 0; padding: clamp(14px, 2.4vw, 34px); }
button:focus-visible, a:focus-visible { outline: 2px solid #a4ffcb; outline-offset: 3px; }
@media (max-width: 620px) {
  .topbar { min-height: 62px; padding-inline: 12px; }
  .brand-mark { width: 36px; height: 36px; }
  .brand-copy small { display: none; }
  nav { gap: 2px; margin-left: auto; }
  nav a { min-width: 44px; min-height: 44px; justify-content: center; padding: 9px; font-size: 0; }
  nav svg { width: 20px; }
  .main-panel { padding: 10px; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; } }
</style>
