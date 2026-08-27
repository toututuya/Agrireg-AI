<template>
  <div class="app-shell" :class="{ 'graph-shell': $route.name === 'graph' }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="topbar">
      <router-link to="/graph" class="brand" aria-label="AgriReg AI 全球农药知识图谱">
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
  }
};
</script>

<style scoped>
.app-shell { min-height: 100vh; background: #f3f1ec; color: #171827; }
.skip-link { position: fixed; z-index: 100; top: 8px; left: 12px; padding: 10px 14px; transform: translateY(-160%); border-radius: 8px; background: #203264; color: #fff; font-size: 13px; font-weight: 700; }
.skip-link:focus { transform: translateY(0); }
.topbar {
  position: sticky; z-index: 30; top: 0; display: flex; min-height: 70px; align-items: center;
  padding: 9px clamp(16px, 3vw, 44px); border-bottom: 1px solid rgba(63,59,91,.1);
  background: rgba(250,249,246,.9); backdrop-filter: blur(20px) saturate(1.1);
}
.brand { display: flex; align-items: center; gap: 11px; color: inherit; text-decoration: none; }
.brand-mark { position: relative; display: block; width: 40px; height: 40px; border-radius: 13px; background: linear-gradient(145deg,#2a2858,#171832); box-shadow: 0 9px 24px rgba(46,39,105,.24); }
.brand-mark i { position: absolute; width: 7px; height: 7px; border-radius: 50%; background: #bcb4ff; }
.brand-mark i:nth-child(1) { top: 9px; left: 9px; }
.brand-mark i:nth-child(2) { top: 17px; right: 8px; }
.brand-mark i:nth-child(3) { bottom: 8px; left: 12px; }
.brand-mark::before, .brand-mark::after { position: absolute; height: 1px; background: rgba(255,255,255,.7); content: ''; transform-origin: left; }
.brand-mark::before { top: 13px; left: 15px; width: 15px; transform: rotate(27deg); }
.brand-mark::after { top: 20px; left: 16px; width: 14px; transform: rotate(-43deg); }
.brand-copy strong, .brand-copy small { display: block; }
.brand-copy strong { font-size: 15px; letter-spacing: .02em; }
.brand-copy small { margin-top: 2px; color: #85838f; font-size: 11px; }
nav { display: flex; align-self: stretch; align-items: center; gap: 8px; margin-left: clamp(28px, 6vw, 86px); }
nav a { display: flex; align-items: center; gap: 7px; padding: 10px 13px; border-radius: 11px; color: #6f6e7b; font-size: 13px; font-weight: 650; text-decoration: none; }
nav a:hover { background: #eeece8; color: #20212e; }
nav a.router-link-active { background: #e9e6ff; color: #5d50cf; }
nav svg { width: 17px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.main-panel { min-width: 0; padding: clamp(14px, 2.4vw, 34px); }
button:focus-visible, a:focus-visible { outline: 2px solid #7468e8; outline-offset: 3px; }
.graph-shell {
  background: #f3f1ec;
  color: #171827;
}
.graph-shell .topbar {
  min-height: 64px;
  border-bottom-color: rgba(63,59,91,.1);
  background: rgba(250,249,246,.9);
  box-shadow: none;
}
.graph-shell .brand-mark {
  background: linear-gradient(145deg,#2a2858,#171832);
  box-shadow: 0 9px 24px rgba(46,39,105,.24);
}
.graph-shell .brand-copy small { color: #85838f; }
.graph-shell nav a { color: #6f6e7b; }
.graph-shell nav a:hover { background: #eeece8; color: #20212e; }
.graph-shell nav a.router-link-active { background: #e9e6ff; color: #5d50cf; }
.graph-shell .main-panel { padding: 18px clamp(12px, 1.8vw, 30px) 26px; }
@media (max-width: 620px) {
  .topbar { min-height: 62px; padding-inline: 12px; }
  .brand-mark { width: 36px; height: 36px; }
  .brand-copy small { display: none; }
  nav { gap: 2px; margin-left: auto; }
  nav a { min-width: 44px; min-height: 44px; justify-content: center; padding: 9px; font-size: 0; }
  nav svg { width: 20px; }
  .main-panel { padding: 10px; }
  .graph-shell .main-panel { padding: 10px 8px 18px; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; } }
</style>
