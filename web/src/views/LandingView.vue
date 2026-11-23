<template>
  <div class="landing">
    <section class="hero frame" aria-labelledby="landing-title">
      <div class="hero-copy">
        <h1 id="landing-title">农药登记，<br><span>有据可查。</span></h1>
        <p class="hero-description">查找登记产品、有效成分与防治对象，沿图谱核对结论的依据。</p>

        <form class="registry-search" role="search" aria-label="登记实体检索" @submit.prevent="openSearch">
          <label class="sr-only" for="registry-keyword">登记号、有效成分或作物</label>
          <UiIcon name="search" class="search-icon" />
          <input id="registry-keyword" v-model.trim="keyword" type="search" name="keyword"
            maxlength="80" required placeholder="登记号、有效成分或作物">
          <button class="ui-button primary" type="submit">检索实体</button>
        </form>
        <div class="sample-links">
          <span>试试</span>
          <router-link v-for="sample in samples" :key="sample" :to="graphLocation(sample)">{{ sample }}</router-link>
        </div>
      </div>

      <img class="field-image" src="@/assets/rice-fields.webp" width="1024" height="768"
        alt="从空中俯瞰由田埂分隔的稻田" fetchpriority="high">
    </section>

    <section class="snapshot frame" aria-label="清洗后数据快照">
      <p>登记数据概览<small>清洗后数据快照</small></p>
      <dl>
        <div><dt>登记记录</dt><dd>16,216</dd></div>
        <div><dt>图谱实体</dt><dd>21,712</dd></div>
        <div><dt>关联关系</dt><dd>120,776</dd></div>
      </dl>
    </section>

    <section id="capabilities" class="workspaces frame" aria-labelledby="workspace-title">
      <h2 id="workspace-title">按任务进入工作台</h2>
      <ul>
        <li v-for="item in workspaces" :key="item.path">
          <router-link :to="item.path">
            <UiIcon :name="item.icon" class="workspace-icon" />
            <div><h3>{{ item.title }}</h3><p>{{ item.description }}</p></div>
            <UiIcon name="arrow" class="workspace-arrow" />
          </router-link>
        </li>
      </ul>
    </section>

    <section id="workflow" class="workflow frame" aria-labelledby="workflow-title">
      <h2 id="workflow-title">每个结论从哪里来？</h2>
      <ol>
        <li><strong>定位实体</strong><p>用登记号或名称找到起点。</p></li>
        <li><strong>检索关系</strong><p>查看作物、病虫害与登记产品的关联。</p></li>
        <li><strong>核对依据</strong><p>从回答引用回到图谱，或查阅任务报告中的来源。</p></li>
      </ol>
    </section>

    <footer class="landing-footer">
      <div class="frame"><strong>AgriReg AI</strong><span>全球农药登记知识库</span></div>
    </footer>
  </div>
</template>

<script>
import UiIcon from '@/components/UiIcon.vue';

export default {
  name: 'LandingView',
  components: { UiIcon },
  data() {
    return {
      keyword: '',
      samples: ['PD20150720', 'Chlorantraniliprole'],
      workspaces: [
        { path: '/graph', icon: 'graph', title: '知识图谱', description: '展开实体关联，查证登记字段，比较两个产品。' },
        { path: '/ask', icon: 'chat', title: 'AI 问答', description: '用自然语言提问，点击引用查看图谱依据。' },
        { path: '/agent', icon: 'task', title: '任务分析', description: '追踪多步骤任务，核对外部来源与差异。' }
      ]
    };
  },
  created() {
    document.title = 'AgriReg AI · 全球农药登记知识库';
  },
  methods: {
    graphLocation(keyword) {
      return { name: 'graph', query: { q: keyword } };
    },
    openSearch() {
      if (this.keyword) this.$router.push(this.graphLocation(this.keyword));
    }
  }
};
</script>

<style scoped>
@font-face {
  font-family: "Noto Serif SC Title";
  src: url("../assets/noto-serif-sc-title.ttf") format("truetype");
  font-style: normal;
  font-weight: 800;
  font-display: swap;
  unicode-range: U+3002, U+519C, U+53EF, U+636E, U+6709, U+67E5, U+767B, U+836F, U+8BB0, U+FF0C;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, .98fr) minmax(0, 1.02fr);
  align-items: center;
  gap: clamp(32px, 5vw, 88px);
  padding-block: clamp(36px, 5.2vw, 76px) clamp(27px, 4.2vw, 62px);
}
.hero h1 {
  font: 800 clamp(3.15rem, 5.6vw, 5.5rem)/1.12 "Noto Serif SC Title", var(--song);
  letter-spacing: -.025em;
}
.hero h1 span { color: var(--accent); }
.hero-description {
  max-width: 29em;
  margin-top: 21px;
  color: var(--muted);
  font-size: clamp(1rem, 1.3vw, 1.18rem);
  text-wrap: balance;
  line-height: 1.7;
}
.registry-search {
  display: grid;
  max-width: 520px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-top: 27px;
  padding: 6px 6px 6px 15px;
  border: 1px solid var(--field-line);
  border-radius: var(--radius);
  background: var(--surface);
}
.registry-search:focus-within { outline: 2px solid var(--focus); outline-offset: 2px; }
.registry-search input { min-width: 0; width: 100%; min-height: 44px; padding: 0; border: 0; outline: 0; background: transparent; font-size: 16px; }
.search-icon { color: var(--accent); }
.registry-search .ui-button { min-width: 98px; min-height: 44px; white-space: nowrap; }
.sample-links { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 12px; margin-top: 8px; font-size: 13px; }
.sample-links > span { color: var(--muted); }
.sample-links a { display: inline-flex; align-items: center; min-height: 36px; color: var(--accent); font-weight: 650; text-decoration: underline; text-decoration-color: var(--field-line); text-underline-offset: .22em; overflow-wrap: anywhere; }
.sample-links a:hover { text-decoration-color: currentColor; }
.field-image { display: block; width: 100%; height: auto; aspect-ratio: 4 / 3; border-radius: var(--radius); object-fit: cover; }
.snapshot {
  display: grid;
  grid-template-columns: minmax(135px, .85fr) minmax(0, 2.2fr);
  align-items: center;
  gap: 18px;
  padding-block: 18px;
  border-block: 1px solid var(--line);
}
.snapshot p { font-weight: 750; }
.snapshot small { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; font-weight: 500; }
.snapshot dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.snapshot dl > div { display: flex; flex-direction: column-reverse; gap: 2px; padding-inline: clamp(10px, 2.3vw, 34px); border-inline-start: 1px solid var(--line); }
.snapshot dt { color: var(--muted); font-size: 13px; }
.snapshot dd { color: var(--accent); font-size: clamp(1.2rem, 2.2vw, 2rem); font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.15; }
.workspaces { padding-block: clamp(35px, 4vw, 61px) clamp(36px, 5.4vw, 75px); }
.landing h2 { font-size: clamp(1.45rem, 2.25vw, 2rem); font-weight: 750; letter-spacing: -.025em; }
.workspaces ul { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 19px 0 0; padding: 0; list-style: none; }
.workspaces li { min-width: 0; border-block: 1px solid var(--line); border-right: 1px solid var(--line); }
.workspaces li:first-child { border-left: 1px solid var(--line); border-radius: var(--radius) 0 0 var(--radius); }
.workspaces li:last-child { border-radius: 0 var(--radius) var(--radius) 0; }
.workspaces a {
  display: grid;
  height: 100%;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: start;
  gap: 13px;
  padding: 22px 17px;
  border-radius: inherit;
  transition: background-color 160ms;
}
.workspaces a:hover { background: var(--wash); }
.workspace-icon { box-sizing: content-box; width: 21px; height: 21px; padding: 8px; border: 1px solid var(--line); border-radius: var(--control-radius); background: var(--surface); color: var(--accent); }
.workspace-arrow { margin-top: 4px; color: var(--accent); }
.workspaces h3 { margin-block: 1px 5px; font-size: 16px; }
.workspaces p, .workflow p { color: var(--muted); font-size: 14px; line-height: 1.6; }
.workflow { display: grid; grid-template-columns: minmax(200px, .8fr) minmax(0, 2fr); gap: 22px; padding-block: 29px 54px; border-top: 1px solid var(--line); }
.workflow ol { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px 28px; margin: 0; padding-inline-start: 1.6em; }
.workflow li::marker { color: var(--accent); font-weight: 700; }
.workflow p { margin-top: 4px; }
.landing-footer { border-top: 1px solid var(--line); }
.landing-footer .frame { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; padding-block: 17px; }
.landing-footer span { color: var(--muted); font-size: 13px; }
@media (max-width: 920px) {
  .hero { gap: 25px; }
  .hero h1 { font-size: clamp(2.8rem, 6.7vw, 4rem); }
  .hero-description { margin-top: 12px; }
  .registry-search { margin-top: 17px; }
  .workspaces a { grid-template-columns: minmax(0, 1fr) auto; }
  .workspace-icon { grid-column: 1 / -1; }
}
@media (max-width: 720px) {
  .hero { grid-template-columns: 1fr; align-items: start; gap: 16px; padding-block: 30px 23px; }
  .hero h1 { font-size: clamp(2.77rem, 11vw, 4.15rem); }
  .field-image { aspect-ratio: 1.7; }
  .registry-search { max-width: none; gap: 8px; padding-left: 10px; }
  .registry-search .ui-button { min-width: 0; padding-inline: 10px; }
  .snapshot { grid-template-columns: 1fr; gap: 11px; }
  .snapshot p { display: flex; align-items: baseline; flex-wrap: wrap; gap: 5px 10px; font-size: 14px; }
  .snapshot dl > div:first-child { padding-left: 0; border-left: 0; }
  .workspaces ul, .workflow, .workflow ol { grid-template-columns: 1fr; }
  .workspaces li, .workspaces li:first-child { border: 1px solid var(--line); }
  .workspaces li:not(:first-child) { border-top: 0; }
  .workspaces li:first-child { border-radius: var(--radius) var(--radius) 0 0; }
  .workspaces li:last-child { border-radius: 0 0 var(--radius) var(--radius); }
  .workspaces a { grid-template-columns: auto minmax(0, 1fr) auto; padding: 15px 12px; }
  .workspace-icon { grid-column: auto; }
  .workflow { padding-block: 23px 32px; }
}
@media (max-width: 370px) {
  .registry-search input { font-size: 14px; }
  .registry-search .search-icon { display: none; }
  .registry-search { grid-template-columns: minmax(0, 1fr) auto; }
}
</style>
