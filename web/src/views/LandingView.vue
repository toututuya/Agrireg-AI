<template>
  <div class="landing-page">
    <header class="landing-nav">
      <router-link class="landing-brand" to="/" aria-label="AgriReg AI 首页">
        <span class="brand-glyph" aria-hidden="true">
          <i></i><i></i><i></i><i></i>
        </span>
        <span><strong>AgriReg AI</strong><small>AGRICULTURAL EVIDENCE ENGINE</small></span>
      </router-link>
      <nav aria-label="首页导航">
        <a href="#capabilities">能力</a>
        <a href="#workflow">工作流</a>
        <router-link to="/graph">知识图谱</router-link>
      </nav>
      <router-link class="nav-cta" to="/agent">开始分析 <span>↗</span></router-link>
    </header>

    <main>
      <section class="hero">
        <div class="hero-grid" aria-hidden="true"></div>
        <div class="hero-glow glow-one" aria-hidden="true"></div>
        <div class="hero-glow glow-two" aria-hidden="true"></div>

        <div class="hero-copy">
          <p class="eyebrow"><span></span> EVIDENCE-GROUNDED AGRICULTURAL INTELLIGENCE</p>
          <h1>把分散的登记数据<br>连接成<span>可追溯的决策证据</span></h1>
          <p class="hero-description">
            从跨地区农药登记信息到实体关系、检索证据与任务结论，
            用一张可探索的知识网络回答“是什么、为什么、依据在哪里”。
          </p>
          <div class="hero-actions">
            <router-link class="primary-button" to="/graph">探索知识图谱 <span>→</span></router-link>
            <router-link class="secondary-button" to="/agent">
              <span class="pulse-dot"></span> 启动证据分析
            </router-link>
          </div>
          <div class="hero-stats" aria-label="知识图谱规模">
            <div><strong>22,328</strong><span>实体节点</span></div>
            <div><strong>145,579</strong><span>关联关系</span></div>
            <div><strong>8 × 6</strong><span>实体 / 关系类型</span></div>
          </div>
        </div>

        <div class="knowledge-stage" aria-label="农药知识网络示意图">
          <div class="stage-caption"><span>LIVE KNOWLEDGE MAP</span><i></i></div>
          <svg class="network-lines" viewBox="0 0 620 590" role="img" aria-label="有效成分、作物、病害和登记信息之间的关系">
            <defs>
              <linearGradient id="lineGlow" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#a4ffcb" stop-opacity=".18"/>
                <stop offset=".5" stop-color="#a4ffcb" stop-opacity=".9"/>
                <stop offset="1" stop-color="#7be5ff" stop-opacity=".2"/>
              </linearGradient>
            </defs>
            <g class="base-lines">
              <path d="M307 292 126 160M307 292 480 136M307 292 516 338M307 292 382 495M307 292 108 405"/>
              <path d="M126 160 480 136M480 136 516 338M516 338 382 495M382 495 108 405M108 405 126 160"/>
            </g>
            <g class="flow-lines">
              <path d="M307 292 126 160"/>
              <path d="M307 292 480 136"/>
              <path d="M307 292 516 338"/>
              <path d="M307 292 382 495"/>
              <path d="M307 292 108 405"/>
            </g>
          </svg>

          <div class="node node-center">
            <span class="node-icon">AI</span>
            <strong>证据推理</strong><small>EVIDENCE CORE</small>
          </div>
          <div class="node node-a"><i></i><strong>有效成分</strong><small>ACTIVE SUBSTANCE</small></div>
          <div class="node node-b"><i></i><strong>登记信息</strong><small>REGISTRATION</small></div>
          <div class="node node-c"><i></i><strong>靶标病害</strong><small>PEST &amp; DISEASE</small></div>
          <div class="node node-d"><i></i><strong>适用作物</strong><small>CROP</small></div>
          <div class="node node-e"><i></i><strong>作用机制</strong><small>MODE OF ACTION</small></div>

          <div class="evidence-card">
            <div><span>Evidence path</span><strong>03 hops</strong></div>
            <p>有效成分 <b>→</b> 登记产品 <b>→</b> 适用作物 <b>→</b> 靶标病害</p>
          </div>
        </div>
      </section>

      <section id="capabilities" class="capabilities section-wrap">
        <div class="section-heading">
          <p>ONE GRAPH, THREE WAYS TO USE IT</p>
          <h2>不止是“查得到”，还要<span>看得懂、问得清、追得回</span></h2>
        </div>
        <div class="capability-grid">
          <router-link to="/graph" class="capability-card graph-card">
            <span class="card-index">01 / EXPLORE</span>
            <div class="mini-graph" aria-hidden="true">
              <i></i><i></i><i></i><i></i><i></i>
              <svg viewBox="0 0 260 120"><path d="M30 55 108 28l48 55 76-48M30 55l75 45 51-17 76 20M108 28l124 75"/></svg>
            </div>
            <h3>Knowledge Graph</h3>
            <p>拖拽探索实体与关系，从一个登记产品逐层展开到成分、作物和防治对象。</p>
            <strong>进入关系网络 <span>↗</span></strong>
          </router-link>
          <router-link to="/ask" class="capability-card rag-card">
            <span class="card-index">02 / ASK</span>
            <div class="evidence-stack" aria-hidden="true">
              <div><span>01</span> MATCH (product)-[:CONTROLS]-&gt;(disease)</div>
              <div><span>02</span> Evidence retrieved from graph</div>
              <div><span>03</span> Answer grounded in source nodes</div>
            </div>
            <h3>GraphRAG</h3>
            <p>先规划检索词，再用参数化 Cypher 召回图谱证据，让回答带着依据生成。</p>
            <strong>开始证据问答 <span>↗</span></strong>
          </router-link>
          <router-link to="/agent" class="capability-card agent-card">
            <span class="card-index">03 / ANALYZE</span>
            <div class="agent-orbit" aria-hidden="true">
              <span>PLAN</span><span>SEARCH</span><span>VERIFY</span><i>AI</i>
            </div>
            <h3>Stateful Agent</h3>
            <p>把多步分析拆成规划、检索、核验和输出，并保留每一步的证据链路。</p>
            <strong>打开任务分析 <span>↗</span></strong>
          </router-link>
        </div>
      </section>

      <section id="workflow" class="workflow section-wrap">
        <div class="workflow-copy">
          <p class="eyebrow"><span></span> FROM QUESTION TO TRACEABLE ANSWER</p>
          <h2>一条可以被检查的<br>农业知识工作流</h2>
          <p>每个结论都对应检索路径、图谱节点与关系证据，减少通用模型脱离数据库作答的风险。</p>
          <router-link to="/agent">查看完整分析流程 <span>→</span></router-link>
        </div>
        <ol class="workflow-rail">
          <li><span>01</span><div><strong>理解问题</strong><small>抽取作物、病害、成分和地区约束</small></div><i></i></li>
          <li><span>02</span><div><strong>规划检索</strong><small>生成受限的一跳 / 两跳图谱查询</small></div><i></i></li>
          <li><span>03</span><div><strong>召回证据</strong><small>返回带编号的实体与关系路径</small></div><i></i></li>
          <li><span>04</span><div><strong>核验冲突</strong><small>检查证据缺口与相互矛盾的信息</small></div><i></i></li>
          <li><span>05</span><div><strong>生成结论</strong><small>只根据已召回证据组织回答</small></div></li>
        </ol>
      </section>

      <section class="final-cta">
        <p>EXPLORE THE EVIDENCE, NOT JUST THE ANSWER.</p>
        <h2>从一个实体开始，打开整张农业知识网络。</h2>
        <div>
          <router-link class="primary-button" to="/graph">进入知识图谱 <span>→</span></router-link>
          <router-link class="text-link" to="/ask">或者直接提问 <span>↗</span></router-link>
        </div>
      </section>
    </main>

    <footer>
      <span>AgriReg AI</span>
      <p>Global pesticide knowledge graph &amp; evidence-grounded reasoning.</p>
      <span>2026</span>
    </footer>
  </div>
</template>

<script>
export default {
  name: 'LandingView',
  created() {
    document.title = 'AgriReg AI · 让农业知识可连接、可追溯';
  }
};
</script>

<style scoped>
.landing-page {
  --ink: #edf7f1;
  --muted: #91a79c;
  --line: rgba(181, 231, 203, .14);
  --green: #a4ffcb;
  --cyan: #7be5ff;
  min-height: 100vh;
  overflow: hidden;
  background: #07110e;
  color: var(--ink);
}
.landing-nav {
  position: absolute;
  z-index: 20;
  top: 0;
  left: 0;
  display: flex;
  width: 100%;
  min-height: 82px;
  align-items: center;
  padding: 14px clamp(18px, 4.8vw, 78px);
  border-bottom: 1px solid rgba(255,255,255,.07);
  background: linear-gradient(180deg, rgba(7,17,14,.86), rgba(7,17,14,0));
}
.landing-brand { display: flex; align-items: center; gap: 12px; }
.landing-brand strong, .landing-brand small { display: block; }
.landing-brand strong { font-size: 15px; letter-spacing: -.01em; }
.landing-brand small { margin-top: 4px; color: #6f8c7f; font: 600 8px/1 ui-monospace, Consolas, monospace; letter-spacing: .14em; }
.brand-glyph { position: relative; width: 38px; height: 38px; border: 1px solid rgba(164,255,203,.28); border-radius: 50%; }
.brand-glyph i { position: absolute; width: 5px; height: 5px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px rgba(164,255,203,.8); }
.brand-glyph i:nth-child(1) { top: 8px; left: 10px; }
.brand-glyph i:nth-child(2) { top: 13px; right: 7px; }
.brand-glyph i:nth-child(3) { bottom: 7px; left: 15px; }
.brand-glyph i:nth-child(4) { top: 17px; left: 16px; width: 7px; height: 7px; background: #fff; }
.landing-nav nav { display: flex; gap: 30px; margin-left: auto; }
.landing-nav nav a { color: #9bb0a5; font-size: 12px; }
.landing-nav nav a:hover { color: #fff; }
.nav-cta { display: inline-flex; align-items: center; gap: 18px; margin-left: clamp(22px, 4vw, 56px); padding: 11px 15px; border: 1px solid rgba(164,255,203,.28); border-radius: 999px; color: var(--green); font-size: 12px; }
.nav-cta:hover { border-color: var(--green); background: rgba(164,255,203,.08); }
.hero { position: relative; display: grid; min-height: 860px; grid-template-columns: minmax(420px, .9fr) minmax(560px, 1.1fr); align-items: center; gap: clamp(20px, 3vw, 58px); padding: 130px clamp(22px, 5.6vw, 92px) 60px; }
.hero-grid { position: absolute; inset: 0; opacity: .22; background-image: linear-gradient(rgba(169,220,192,.11) 1px, transparent 1px), linear-gradient(90deg, rgba(169,220,192,.11) 1px, transparent 1px); background-size: 64px 64px; mask-image: linear-gradient(to bottom, #000 10%, transparent 92%); }
.hero::after { position: absolute; right: -12%; bottom: -28%; width: 75%; height: 68%; border: 1px solid rgba(164,255,203,.09); border-radius: 50%; content: ''; transform: rotate(-12deg); }
.hero-glow { position: absolute; border-radius: 50%; filter: blur(90px); pointer-events: none; }
.glow-one { top: 24%; right: 12%; width: 300px; height: 300px; background: rgba(40,191,123,.14); }
.glow-two { bottom: 8%; left: 18%; width: 240px; height: 240px; background: rgba(63,178,207,.08); }
.hero-copy { position: relative; z-index: 2; max-width: 730px; }
.eyebrow { display: flex; align-items: center; gap: 10px; color: var(--green); font: 700 10px/1.4 ui-monospace, Consolas, monospace; letter-spacing: .15em; }
.eyebrow span { width: 32px; height: 1px; background: currentColor; }
h1 { margin: 24px 0 25px; font-size: clamp(52px, 6.3vw, 98px); font-weight: 650; line-height: .98; letter-spacing: -.07em; }
h1 span { display: inline-block; color: transparent; -webkit-text-stroke: 1px rgba(213,255,229,.58); }
.hero-description { max-width: 630px; color: var(--muted); font-size: clamp(14px, 1.2vw, 17px); line-height: 1.85; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 34px; }
.primary-button, .secondary-button { display: inline-flex; min-height: 50px; align-items: center; justify-content: center; gap: 25px; padding: 0 20px; border-radius: 999px; font-size: 13px; font-weight: 750; }
.primary-button { background: var(--green); color: #07110e; }
.primary-button:hover { background: #d3ffe5; transform: translateY(-2px); }
.secondary-button { border: 1px solid var(--line); color: #dcece3; background: rgba(255,255,255,.025); }
.secondary-button:hover { border-color: rgba(164,255,203,.45); background: rgba(164,255,203,.06); }
.pulse-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 0 rgba(164,255,203,.7); animation: pulse 2s infinite; }
@keyframes pulse { 70% { box-shadow: 0 0 0 8px rgba(164,255,203,0); } 100% { box-shadow: 0 0 0 0 rgba(164,255,203,0); } }
.hero-stats { display: flex; gap: clamp(24px, 4vw, 58px); margin-top: 52px; padding-top: 22px; border-top: 1px solid var(--line); }
.hero-stats strong, .hero-stats span { display: block; }
.hero-stats strong { font: 520 clamp(22px, 2vw, 30px)/1 ui-monospace, Consolas, monospace; letter-spacing: -.05em; }
.hero-stats span { margin-top: 8px; color: #71877c; font-size: 10px; }
.knowledge-stage { position: relative; z-index: 2; width: min(100%, 670px); aspect-ratio: 1.02; margin-left: auto; border: 1px solid rgba(164,255,203,.12); border-radius: 42% 58% 45% 55% / 55% 46% 54% 45%; background: radial-gradient(circle at center, rgba(35,126,83,.16), rgba(8,22,17,.1) 40%, transparent 68%); box-shadow: inset 0 0 110px rgba(73,226,147,.035); }
.knowledge-stage::before, .knowledge-stage::after { position: absolute; inset: 9%; border: 1px solid rgba(164,255,203,.08); border-radius: 50%; content: ''; animation: rotate 22s linear infinite; }
.knowledge-stage::after { inset: 20%; border-style: dashed; animation-duration: 14s; animation-direction: reverse; }
@keyframes rotate { to { transform: rotate(360deg); } }
.stage-caption { position: absolute; top: 4%; left: 8%; display: flex; align-items: center; gap: 8px; color: #6f8c7f; font: 700 9px/1 ui-monospace, Consolas, monospace; letter-spacing: .13em; }
.stage-caption i { width: 5px; height: 5px; border-radius: 50%; background: var(--green); box-shadow: 0 0 9px var(--green); }
.network-lines { position: absolute; inset: 4%; width: 92%; height: 92%; overflow: visible; }
.base-lines path, .flow-lines path { fill: none; stroke-linecap: round; }
.base-lines path { stroke: rgba(175,230,201,.16); stroke-width: 1; }
.flow-lines path { stroke: url(#lineGlow); stroke-width: 1.6; stroke-dasharray: 3 19; animation: dash 5s linear infinite; }
.flow-lines path:nth-child(2) { animation-delay: -.8s; }.flow-lines path:nth-child(3) { animation-delay: -1.6s; }.flow-lines path:nth-child(4) { animation-delay: -2.4s; }.flow-lines path:nth-child(5) { animation-delay: -3.2s; }
@keyframes dash { to { stroke-dashoffset: -88; } }
.node { position: absolute; z-index: 3; min-width: 130px; padding: 12px 14px; border: 1px solid rgba(164,255,203,.18); border-radius: 10px; background: rgba(8,22,17,.84); box-shadow: 0 12px 34px rgba(0,0,0,.22); backdrop-filter: blur(14px); animation: float 6s ease-in-out infinite; }
.node strong, .node small { display: block; }
.node strong { padding-left: 13px; font-size: 12px; }
.node small { margin-top: 5px; padding-left: 13px; color: #61776c; font: 600 7px/1 ui-monospace, Consolas, monospace; letter-spacing: .09em; }
.node > i { position: absolute; top: 16px; left: 10px; width: 5px; height: 5px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 9px rgba(123,229,255,.8); }
.node-center { top: 44%; left: 50%; display: flex; min-width: 162px; align-items: center; gap: 10px; padding: 15px; transform: translate(-50%,-50%); border-color: rgba(164,255,203,.44); background: rgba(13,39,28,.92); animation-name: centerFloat; }
.node-center strong, .node-center small { padding-left: 0; }
.node-icon { display: grid; width: 38px; height: 38px; flex: 0 0 38px; place-items: center; border-radius: 50%; background: var(--green); color: #0a1812; font: 800 10px/1 ui-monospace, Consolas, monospace; box-shadow: 0 0 28px rgba(164,255,203,.25); }
.node-a { top: 17%; left: 4%; }.node-b { top: 12%; right: 3%; animation-delay: -1s; }.node-c { top: 51%; right: -2%; animation-delay: -2s; }.node-d { right: 17%; bottom: 4%; animation-delay: -3s; }.node-e { bottom: 17%; left: 0; animation-delay: -4s; }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes centerFloat { 0%,100% { transform: translate(-50%,-50%); } 50% { transform: translate(-50%,calc(-50% - 7px)); } }
.evidence-card { position: absolute; z-index: 4; right: 0; bottom: 18%; width: min(320px, 54%); padding: 13px 15px; border: 1px solid rgba(123,229,255,.2); border-radius: 10px; background: rgba(6,19,18,.9); box-shadow: 0 18px 50px rgba(0,0,0,.35); }
.evidence-card div { display: flex; justify-content: space-between; color: #6f8c7f; font: 700 8px/1 ui-monospace, Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.evidence-card div strong { color: var(--cyan); }.evidence-card p { margin-top: 10px; color: #b9cbbf; font-size: 10px; }.evidence-card b { padding: 0 4px; color: var(--green); }
.section-wrap { padding: 115px clamp(22px, 5.6vw, 92px); }
.capabilities { border-top: 1px solid var(--line); background: #0a1511; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 40px; margin-bottom: 50px; }
.section-heading > p { color: var(--green); font: 700 9px/1.4 ui-monospace, Consolas, monospace; letter-spacing: .14em; }
.section-heading h2 { max-width: 790px; font-size: clamp(34px, 4vw, 60px); font-weight: 560; line-height: 1.06; letter-spacing: -.05em; }
.section-heading h2 span { color: #83988d; }
.capability-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.capability-card { position: relative; min-height: 440px; overflow: hidden; padding: 24px; border: 1px solid var(--line); border-radius: 18px; background: #0c1914; transition: border-color .25s ease, transform .25s ease, background .25s ease; }
.capability-card:hover { border-color: rgba(164,255,203,.34); background: #0f1e18; transform: translateY(-5px); }
.card-index { display: block; color: #6d8176; font: 700 9px/1 ui-monospace, Consolas, monospace; letter-spacing: .12em; }
.capability-card h3 { margin-top: 30px; font-size: clamp(23px, 2.5vw, 34px); font-weight: 550; letter-spacing: -.04em; }
.capability-card > p { min-height: 74px; margin-top: 12px; color: #82968b; font-size: 13px; line-height: 1.7; }
.capability-card > strong { display: flex; align-items: center; justify-content: space-between; margin-top: 25px; padding-top: 16px; border-top: 1px solid var(--line); color: #cfe0d6; font-size: 11px; }
.mini-graph, .evidence-stack, .agent-orbit { position: relative; height: 170px; margin-top: 24px; overflow: hidden; border-radius: 12px; background: rgba(164,255,203,.025); }
.mini-graph svg { position: absolute; inset: 0; width: 100%; height: 100%; }.mini-graph path { fill: none; stroke: rgba(164,255,203,.28); stroke-width: 1; }
.mini-graph i { position: absolute; z-index: 2; width: 11px; height: 11px; border: 3px solid #12231b; border-radius: 50%; background: var(--green); box-shadow: 0 0 14px rgba(164,255,203,.35); }
.mini-graph i:nth-child(1){top:45%;left:8%}.mini-graph i:nth-child(2){top:20%;left:40%}.mini-graph i:nth-child(3){top:65%;left:59%}.mini-graph i:nth-child(4){top:26%;right:7%}.mini-graph i:nth-child(5){bottom:10%;right:5%}
.evidence-stack { display: flex; flex-direction: column; justify-content: center; gap: 8px; padding: 18px; }
.evidence-stack div { overflow: hidden; padding: 11px; border: 1px solid rgba(123,229,255,.1); border-radius: 7px; background: #0a1416; color: #778b85; font: 8px/1.3 ui-monospace, Consolas, monospace; white-space: nowrap; }
.evidence-stack div:nth-child(2) { transform: translateX(12px); }.evidence-stack div:nth-child(3) { transform: translateX(24px); color: #a9c6b6; }
.evidence-stack span { margin-right: 9px; color: var(--cyan); }
.agent-orbit { display: grid; place-items: center; }
.agent-orbit::before, .agent-orbit::after { position: absolute; width: 124px; height: 124px; border: 1px dashed rgba(164,255,203,.22); border-radius: 50%; content: ''; animation: rotate 12s linear infinite; }
.agent-orbit::after { width: 76px; height: 76px; border-style: solid; animation-direction: reverse; }
.agent-orbit i { position: relative; z-index: 2; display: grid; width: 44px; height: 44px; place-items: center; border-radius: 50%; background: var(--green); color: #07110e; font: 800 11px/1 ui-monospace, Consolas, monospace; }
.agent-orbit span { position: absolute; color: #759086; font: 700 7px/1 ui-monospace, Consolas, monospace; letter-spacing: .1em; }.agent-orbit span:nth-child(1){top:18px}.agent-orbit span:nth-child(2){right:18px;bottom:48px}.agent-orbit span:nth-child(3){bottom:18px;left:28px}
.workflow { display: grid; grid-template-columns: .8fr 1.2fr; gap: clamp(50px, 8vw, 130px); background: #07110e; }
.workflow-copy { align-self: center; }.workflow-copy h2 { margin: 22px 0; font-size: clamp(37px, 4.5vw, 64px); font-weight: 560; line-height: 1.05; letter-spacing: -.055em; }.workflow-copy > p:not(.eyebrow) { max-width: 500px; color: #81968a; font-size: 13px; line-height: 1.8; }.workflow-copy > a { display: inline-flex; gap: 25px; margin-top: 30px; padding-bottom: 7px; border-bottom: 1px solid rgba(164,255,203,.35); color: var(--green); font-size: 12px; }
.workflow-rail { margin: 0; padding: 0; list-style: none; }.workflow-rail li { position: relative; display: grid; min-height: 92px; grid-template-columns: 50px 1fr; align-items: start; padding: 21px 0; border-top: 1px solid var(--line); }.workflow-rail li:last-child { border-bottom: 1px solid var(--line); }.workflow-rail li > span { color: var(--green); font: 700 9px/1.5 ui-monospace, Consolas, monospace; }.workflow-rail strong, .workflow-rail small { display: block; }.workflow-rail strong { font-size: 15px; }.workflow-rail small { margin-top: 6px; color: #71857a; font-size: 11px; }.workflow-rail i { position: absolute; top: 42px; right: 8px; width: 6px; height: 6px; border: 1px solid var(--green); border-radius: 50%; }.workflow-rail i::after { position: absolute; top: 8px; left: 2px; width: 1px; height: 62px; background: linear-gradient(var(--green), transparent); content: ''; }
.final-cta { padding: 115px clamp(22px, 5.6vw, 92px); border-top: 1px solid var(--line); background: linear-gradient(140deg, #10241b, #07110e 62%); text-align: center; }.final-cta > p { color: var(--green); font: 700 9px/1.4 ui-monospace, Consolas, monospace; letter-spacing: .15em; }.final-cta h2 { max-width: 880px; margin: 20px auto 32px; font-size: clamp(38px, 5vw, 72px); font-weight: 560; line-height: 1.03; letter-spacing: -.06em; }.final-cta > div { display: flex; justify-content: center; gap: 28px; align-items: center; }.text-link { color: #a9bdb2; font-size: 12px; }.text-link span { margin-left: 12px; color: var(--green); }
footer { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 22px clamp(22px, 5.6vw, 92px); border-top: 1px solid var(--line); color: #65786e; font: 700 9px/1.4 ui-monospace, Consolas, monospace; letter-spacing: .06em; } footer > span:first-child { color: #b7c8be; font-size: 11px; }
a, .primary-button, .secondary-button { transition: .22s ease; }
a:focus-visible { outline: 2px solid var(--green); outline-offset: 4px; }
@media (max-width: 1080px) {
  .hero { min-height: auto; grid-template-columns: 1fr; padding-top: 150px; }
  .hero-copy { max-width: 820px; }.knowledge-stage { width: min(100%, 660px); margin: 20px auto 0; }.capability-grid { grid-template-columns: 1fr; }.capability-card { min-height: auto; }.workflow { grid-template-columns: 1fr; }.section-heading { align-items: flex-start; flex-direction: column; }.landing-nav nav { display: none; }
}
@media (max-width: 620px) {
  .landing-nav { min-height: 70px; padding-inline: 14px; }.landing-brand small { display: none; }.nav-cta { margin-left: auto; padding: 9px 12px; }.nav-cta span { display: none; }
  .hero { padding: 120px 16px 54px; }.hero-description br { display: none; }h1 { font-size: 48px; }.hero-stats { gap: 14px; justify-content: space-between; }.hero-stats strong { font-size: 19px; }.hero-stats span { font-size: 8px; }
  .knowledge-stage { width: 110%; margin-left: -5%; }.node { min-width: 108px; padding: 10px; }.node strong { font-size: 10px; }.node small { display: none; }.node-center { min-width: 138px; }.evidence-card { right: 3%; bottom: 10%; width: 65%; }
  .section-wrap { padding: 78px 16px; }.section-heading h2 { font-size: 38px; }.capability-card { padding: 19px; }.workflow { gap: 42px; }.final-cta { padding: 78px 18px; }.final-cta > div { flex-direction: column; gap: 19px; }footer { align-items: flex-start; flex-direction: column; }footer p { display: none; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important; } }
</style>
