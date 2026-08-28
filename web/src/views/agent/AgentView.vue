<template>
  <section class="agent-page">
    <header class="agent-hero">
      <div>
        <p>AGRIREG INTELLIGENCE · ANALYSIS AGENT</p>
        <h1>把复杂问题拆成可核验的任务</h1>
        <span>沿知识图谱检索实体与关系，交叉核对外部来源，保留每一步证据后生成报告。</span>
      </div>
      <router-link to="/ask" class="quick-link">
        只问一个问题
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
      </router-link>
    </header>

    <div class="agent-grid">
      <aside class="thread-rail" aria-label="分析任务记录">
        <div class="rail-heading">
          <div><span>任务记录</span><strong>最近分析</strong></div>
          <button type="button" aria-label="新建分析任务" title="新建分析任务" @click="newTask">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
          </button>
        </div>
        <p v-if="threadsLoading" class="rail-state" role="status">正在载入任务…</p>
        <p v-else-if="threadsError" class="rail-state error" role="alert">{{ threadsError }}</p>
        <nav v-else-if="threads.length" :class="['thread-list', { expanded: historyExpanded }]" aria-label="最近分析列表">
          <button
            v-for="thread in threads"
            :key="thread.id"
            type="button"
            :class="['thread-item', { active: thread.id === activeThreadId }]"
            :aria-current="thread.id === activeThreadId ? 'page' : undefined"
            @click="openThread(thread)"
          >
            <span>{{ thread.title }}</span>
            <small>{{ threadStatus(thread.latestStatus) }} · {{ formatTime(thread.updatedAt) }}</small>
          </button>
        </nav>
        <button
          v-if="threads.length > 2"
          type="button"
          class="history-disclosure"
          :aria-expanded="historyExpanded ? 'true' : 'false'"
          @click="historyExpanded = !historyExpanded"
        >{{ historyExpanded ? '收起任务记录' : `查看全部 ${threads.length} 条任务` }}</button>
        <div v-else class="rail-empty">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/></svg>
          <strong>还没有分析任务</strong>
          <span>开始后，计划、证据和报告会保存在这里。</span>
        </div>
      </aside>

      <div class="task-column" role="region" aria-label="任务工作区">
        <section v-if="!activeRun" class="task-starter" aria-labelledby="agent-start-title">
          <span class="eyebrow">多步骤分析</span>
          <h2 id="agent-start-title">你希望核验什么？</h2>
          <p>适合成分对比、关系路径、登记与风险初筛。单一事实查询可以继续使用 AI 问答。</p>
          <div class="starter-grid">
            <button v-for="item in starters" :key="item.title" type="button" @click="question = item.question">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="item.icon"/></svg>
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
            </button>
          </div>
        </section>

        <section v-else class="run-card" aria-labelledby="active-task-title">
          <div class="run-heading">
            <div>
              <span class="eyebrow">当前任务</span>
              <h2 id="active-task-title">{{ activeRun.question }}</h2>
            </div>
            <span :class="['run-status', statusTone(activeRun.status)]">
              <i aria-hidden="true"></i>{{ runStatus(activeRun.status) }}
            </span>
          </div>

          <ol class="progress-steps" aria-label="分析进度">
            <li v-for="(stage, index) in stages" :key="stage.key" :class="stageState(stage.key)">
              <span>{{ index + 1 }}</span>
              <div><strong>{{ stage.title }}</strong><small>{{ stage.caption }}</small></div>
            </li>
          </ol>

          <section v-if="activeRun.interrupt" class="decision-card" aria-live="polite">
            <div class="decision-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M12 3 2.8 19h18.4L12 3Z"/><path d="M12 9v4m0 3h.01"/></svg>
            </div>
            <div>
              <span>{{ activeRun.interrupt.kind === 'approval' ? '等待确认' : '需要补充' }}</span>
              <h3>{{ activeRun.interrupt.title }}</h3>
              <p>{{ activeRun.interrupt.message }}</p>
              <div v-if="activeRun.interrupt.kind === 'approval'" class="decision-actions">
                <button type="button" class="approve" :disabled="resuming" @click="resume({ decision: 'approve' })">确认生成报告</button>
                <button type="button" class="reject" :disabled="resuming" @click="resume({ decision: 'reject' })">停止并保留证据</button>
              </div>
              <form v-else class="clarification-form" @submit.prevent="resume(clarification)">
                <label for="clarification-input">补充信息</label>
                <input id="clarification-input" v-model.trim="clarification" maxlength="160" :disabled="resuming" aria-describedby="clarification-help">
                <small id="clarification-help">例如补充第二个有效成分、登记产品或关系终点。</small>
                <button type="submit" :disabled="resuming || clarification.length < 2">继续分析</button>
              </form>
            </div>
          </section>

          <section class="timeline" aria-labelledby="timeline-title">
            <div class="section-heading"><div><span>执行记录</span><h3 id="timeline-title">任务时间线</h3></div><small>{{ events.length }} 条记录</small></div>
            <ol v-if="events.length">
              <li v-for="item in events" :key="item.seq || `${item.kind}-${item.title}`">
                <span :class="['timeline-icon', eventTone(item.kind)]" aria-hidden="true">
                  <svg viewBox="0 0 24 24"><path :d="eventIcon(item.kind)"/></svg>
                </span>
                <div><strong>{{ item.title }}</strong><p>{{ item.detail }}</p><small>{{ formatTime(item.createdAt) }}</small></div>
              </li>
            </ol>
            <div v-else class="timeline-empty" role="status">正在准备第一步…</div>
          </section>

          <article v-if="activeRun.report" class="report" aria-labelledby="report-title">
            <div class="section-heading"><div><span>分析产物</span><h3 id="report-title">证据化报告</h3></div></div>
            <div class="report-body">
              <template v-for="(line, index) in reportLines">
                <h4 v-if="line.type === 'heading'" :key="`h-${index}`">{{ line.text }}</h4>
                <p v-else-if="line.type === 'paragraph'" :key="`p-${index}`">{{ line.text }}</p>
                <p v-else :key="`b-${index}`" class="report-bullet"><span aria-hidden="true"></span>{{ line.text }}</p>
              </template>
            </div>
          </article>
        </section>

        <form class="task-composer" @submit.prevent="startAnalysis">
          <label for="agent-question">分析任务</label>
          <textarea
            id="agent-question"
            v-model.trim="question"
            rows="3"
            maxlength="500"
            :disabled="starting || isRunning"
            aria-describedby="agent-question-help agent-form-error"
            placeholder="例如：比较 Abamectin 与 Chlorantraniliprole 的作用机制和关联作物，并核对外部化学记录。"
          ></textarea>
          <div class="composer-row">
            <small id="agent-question-help">Agent 只调用受控图谱与来源核验工具，分析过程会保留为可恢复任务。</small>
            <button type="submit" :disabled="starting || isRunning || question.length < 2">
              <span>{{ starting ? '正在创建…' : '开始分析' }}</span>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 14-7-4 14-3-5-7-2Z"/><path d="m12 14 7-9"/></svg>
            </button>
          </div>
          <p v-if="formError" id="agent-form-error" class="form-error" role="alert">{{ formError }}</p>
        </form>
      </div>

      <aside class="evidence-rail" aria-label="当前任务的证据">
        <div class="section-heading"><div><span>证据集合</span><h2>来源与差异</h2></div><small>{{ evidence.length }} 条</small></div>
        <div v-if="conflicts.length" class="conflict-summary">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.8 19h18.4L12 3Z"/><path d="M12 9v4m0 3h.01"/></svg>
          <div><strong>存在 {{ conflicts.length }} 组待核对差异</strong><span>报告会将冲突与确认结论分开呈现。</span></div>
        </div>
        <div v-if="evidence.length" class="evidence-list">
          <article v-for="item in visibleEvidence" :key="`${item.index}-${item.source}-${item.title}`">
            <div><b>[{{ item.index }}]</b><span>{{ item.source }}</span><em v-if="item.jurisdiction">{{ item.jurisdiction }}</em></div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.summary }}</p>
            <a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">
              查看来源
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M18 13v6H5V6h6"/></svg>
            </a>
          </article>
          <button
            v-if="evidence.length > 12"
            type="button"
            class="evidence-disclosure"
            :aria-expanded="evidenceExpanded ? 'true' : 'false'"
            @click="evidenceExpanded = !evidenceExpanded"
          >{{ evidenceExpanded ? '收起证据' : `查看全部 ${evidence.length} 条证据` }}</button>
        </div>
        <div v-else class="evidence-empty">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/></svg>
          <strong>证据会显示在这里</strong>
          <span>图谱实体、关系和外部来源核验完成后，会按编号汇总。</span>
        </div>
      </aside>
    </div>
  </section>
</template>

<script>
import agentService, { eventStreamUrl } from '@/utils/agent';

export default {
  name: 'AgentView',
  data() {
    return {
      threads: [],
      threadsLoading: false,
      threadsError: '',
      activeThreadId: '',
      activeRun: null,
      events: [],
      question: '',
      clarification: '',
      formError: '',
      starting: false,
      resuming: false,
      stream: null,
      historyExpanded: false,
      evidenceExpanded: false,
      starters: [
        { title: '成分对比', description: '比较作用机制、关联对象与外部化学记录', question: "比较 'Abamectin' 与 'Chlorantraniliprole' 的作用机制和关联作物", icon: 'M4 7h6v6H4zM14 11h6v6h-6zM10 10l4 4' },
        { title: '关系路径', description: '解释两个实体之间的多跳关联链', question: "查找 'Prothioconazole' 到 'Spring barley' 的关系路径", icon: 'M5 6h4v4H5zM15 14h4v4h-4zM9 8c5 0 1 8 6 8' },
        { title: '登记初筛', description: '汇总图谱依据、外部来源和待确认差异', question: "核验 'Abamectin' 的登记与使用风险，并生成证据化初筛报告", icon: 'M12 3 4 7v5c0 4.5 3 7.4 8 9 5-1.6 8-4.5 8-9V7l-8-4Zm-3 9 2 2 4-4' }
      ],
      stages: [
        { key: 'plan', title: '规划任务', caption: '识别目标与约束' },
        { key: 'tools', title: '检索核验', caption: '调用受控工具' },
        { key: 'verify', title: '检查差异', caption: '汇总编号证据' },
        { key: 'report', title: '生成报告', caption: '保留结论边界' }
      ]
    };
  },
  computed: {
    isRunning() {
      return this.activeRun && this.activeRun.status === 'running';
    },
    evidenceEvent() {
      return [...this.events].reverse().find(item => item.kind === 'evidence_verified');
    },
    evidence() {
      return this.evidenceEvent && this.evidenceEvent.payload && Array.isArray(this.evidenceEvent.payload.evidence)
        ? this.evidenceEvent.payload.evidence
        : [];
    },
    conflicts() {
      return this.evidenceEvent && this.evidenceEvent.payload && Array.isArray(this.evidenceEvent.payload.conflicts)
        ? this.evidenceEvent.payload.conflicts
        : [];
    },
    visibleEvidence() {
      return this.evidenceExpanded ? this.evidence : this.evidence.slice(0, 12);
    },
    reportLines() {
      return String((this.activeRun && this.activeRun.report) || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(value => {
        if (/^#{1,4}\s/.test(value)) return { type: 'heading', text: value.replace(/^#{1,4}\s+/, '') };
        if (/^-\s/.test(value)) return { type: 'bullet', text: value.replace(/^-\s+/, '') };
        return { type: 'paragraph', text: value };
      });
    }
  },
  async mounted() {
    await this.loadThreads();
  },
  beforeDestroy() {
    this.closeStream();
  },
  methods: {
    async loadThreads() {
      this.threadsLoading = true;
      this.threadsError = '';
      try {
        const response = await agentService.get('/api/agent/threads');
        this.threads = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        this.threadsError = '最近任务暂时无法载入。启动任务分析服务后可以继续。';
      } finally {
        this.threadsLoading = false;
      }
    },
    newTask() {
      this.closeStream();
      this.activeThreadId = '';
      this.activeRun = null;
      this.events = [];
      this.question = '';
      this.formError = '';
      this.evidenceExpanded = false;
      this.$nextTick(() => document.getElementById('agent-question')?.focus());
    },
    async openThread(thread) {
      if (!thread || !thread.id) return;
      this.closeStream();
      this.activeThreadId = thread.id;
      this.evidenceExpanded = false;
      try {
        const response = await agentService.get(`/api/agent/threads/${encodeURIComponent(thread.id)}`);
        const runs = response.data && Array.isArray(response.data.runs) ? response.data.runs : [];
        if (!runs.length) {
          this.activeRun = null;
          this.events = [];
          return;
        }
        await this.loadRun(thread.id, runs[0].id);
      } catch (error) {
        this.formError = '这条任务记录暂时无法打开。';
      }
    },
    async loadRun(threadId, runId) {
      const response = await agentService.get(`/api/agent/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}`);
      this.activeRun = response.data;
      this.events = response.data.events || [];
      if (response.data.status === 'running') this.connectStream(threadId, runId);
    },
    async startAnalysis() {
      if (this.starting || this.isRunning || this.question.length < 2) return;
      this.starting = true;
      this.formError = '';
      try {
        let threadId = this.activeThreadId;
        if (!threadId) {
          const threadResponse = await agentService.post('/api/agent/threads', { title: '新分析任务' });
          threadId = threadResponse.data.id;
          this.activeThreadId = threadId;
        }
        const response = await agentService.post(`/api/agent/threads/${encodeURIComponent(threadId)}/runs`, { question: this.question });
        this.activeRun = response.data;
        this.events = response.data.events || [];
        this.question = '';
        await this.loadThreads();
        this.connectStream(threadId, response.data.id);
      } catch (error) {
        this.formError = '任务没有启动成功。请确认任务分析服务已启动，然后重试。';
      } finally {
        this.starting = false;
      }
    },
    connectStream(threadId, runId) {
      this.closeStream();
      const last = this.events.length ? Number(this.events[this.events.length - 1].seq || 0) : 0;
      this.stream = new EventSource(eventStreamUrl(threadId, runId, last));
      this.stream.addEventListener('agent_event', event => {
        const item = JSON.parse(event.data);
        if (!this.events.some(existing => Number(existing.seq) === Number(item.seq))) this.events.push(item);
      });
      this.stream.addEventListener('run_snapshot', event => {
        this.activeRun = JSON.parse(event.data);
        this.closeStream();
        this.loadThreads();
      });
      this.stream.onerror = () => {
        this.closeStream();
        window.setTimeout(() => this.refreshRun(threadId, runId), 800);
      };
    },
    async refreshRun(threadId, runId) {
      try {
        await this.loadRun(threadId, runId);
      } catch (error) {
        this.formError = '任务进度暂时无法刷新，可以稍后重新打开这条任务。';
      }
    },
    closeStream() {
      if (this.stream) this.stream.close();
      this.stream = null;
    },
    async resume(value) {
      if (!this.activeRun || this.resuming) return;
      this.resuming = true;
      this.formError = '';
      try {
        const threadId = this.activeRun.threadId;
        const runId = this.activeRun.id;
        const response = await agentService.post(`/api/agent/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/resume`, { value });
        this.activeRun = response.data;
        this.clarification = '';
        this.connectStream(threadId, runId);
      } catch (error) {
        this.formError = '这次确认没有提交成功，请重试。';
      } finally {
        this.resuming = false;
      }
    },
    stageState(key) {
      const completed = {
        plan: this.events.some(item => item.kind === 'plan_ready'),
        tools: this.events.some(item => ['tool_completed', 'tool_failed'].includes(item.kind)),
        verify: this.events.some(item => item.kind === 'evidence_verified'),
        report: Boolean(this.activeRun && this.activeRun.report)
      };
      if (completed[key]) return 'done';
      const order = ['plan', 'tools', 'verify', 'report'];
      const firstPending = order.find(item => !completed[item]);
      return firstPending === key && this.activeRun && this.activeRun.status === 'running' ? 'current' : '';
    },
    runStatus(status) {
      return ({ running: '分析中', waiting_clarification: '等待补充', waiting_approval: '等待确认', completed: '已完成', rejected: '已停止', failed: '未完成', paused: '可继续' })[status] || '准备中';
    },
    threadStatus(status) {
      return this.runStatus(status || '');
    },
    statusTone(status) {
      if (status === 'completed') return 'success';
      if (status === 'failed' || status === 'rejected') return 'danger';
      if (String(status).startsWith('waiting_')) return 'warning';
      return 'working';
    },
    eventTone(kind) {
      if (kind === 'tool_failed' || kind === 'run_failed') return 'danger';
      if (kind === 'evidence_verified' || kind === 'report_ready') return 'success';
      if (kind === 'input_required') return 'warning';
      return 'primary';
    },
    eventIcon(kind) {
      if (kind === 'plan_ready') return 'M5 6h14M5 12h9M5 18h11';
      if (kind === 'evidence_verified') return 'm5 12 4 4L19 6';
      if (kind === 'report_ready') return 'M5 3h10l4 4v14H5zM14 3v5h5M8 13h8M8 17h6';
      if (kind === 'input_required') return 'M12 3 2.8 19h18.4L12 3ZM12 9v4m0 3h.01';
      if (kind === 'tool_failed' || kind === 'run_failed') return 'M6 6l12 12M18 6 6 18';
      return 'M4 12h5l2-4 3 8 2-4h4';
    },
    formatTime(value) {
      if (!value) return '刚刚';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return '';
      return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date);
    }
  }
};
</script>

<style scoped>
.agent-page {
  --primary: #2563eb; --primary-dark: #1d4ed8; --accent: #c2410c; --ink: #1e293b;
  --muted-ink: #475569; --surface: #fff; --soft: #f8fafc; --muted: #e9eff8;
  --border: #dbe4f0; --danger: #b42318; --warning: #9a3412; --success: #166534;
  min-height: calc(100vh - 118px); color: var(--ink); font-family: "Work Sans", Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.agent-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; max-width: 1480px; margin: 0 auto 18px; padding: 8px 2px 0; }
.agent-hero p, .eyebrow, .section-heading span, .rail-heading span { margin: 0 0 6px; color: var(--primary); font-size: 11px; font-weight: 800; letter-spacing: .12em; }
.agent-hero h1 { margin: 0; font-family: Outfit, "PingFang SC", sans-serif; font-size: clamp(26px, 3vw, 40px); line-height: 1.15; letter-spacing: -.025em; }
.agent-hero > div > span { display: block; max-width: 720px; margin-top: 10px; color: var(--muted-ink); font-size: 14px; line-height: 1.65; }
.quick-link { display: inline-flex; min-height: 44px; flex: 0 0 auto; align-items: center; gap: 6px; padding: 0 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--primary-dark); font-size: 13px; font-weight: 750; box-shadow: 0 1px 2px rgba(15,23,42,.05); transition: border-color 180ms ease, background 180ms ease; }
.quick-link:hover { border-color: #93b4ed; background: #f7faff; }
.quick-link svg, button svg, a svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.agent-grid { display: grid; grid-template-columns: minmax(190px, .72fr) minmax(520px, 2.2fr) minmax(250px, 1fr); gap: 14px; max-width: 1480px; margin: 0 auto; align-items: start; }
.thread-rail, .task-column, .evidence-rail { min-width: 0; border: 1px solid var(--border); border-radius: 15px; background: var(--surface); box-shadow: 0 4px 16px rgba(30,41,59,.055); }
.thread-rail, .evidence-rail { position: sticky; top: 86px; max-height: calc(100vh - 110px); overflow: auto; padding: 14px; }
.rail-heading, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.rail-heading strong, .section-heading h2, .section-heading h3 { display: block; margin: 0; font-size: 17px; line-height: 1.25; }
.rail-heading button { display: grid; width: 44px; height: 44px; flex: 0 0 auto; place-items: center; border: 1px solid var(--border); border-radius: 10px; background: var(--soft); color: var(--primary); cursor: pointer; transition: background 180ms ease, border-color 180ms ease; }
.rail-heading button:hover { border-color: #93b4ed; background: #eef5ff; }
.thread-list { display: grid; min-width: 0; gap: 6px; margin-top: 14px; }
.history-disclosure { display: none; width: 100%; min-height: 44px; margin-top: 6px; border: 1px solid var(--border); border-radius: 9px; background: var(--soft); color: var(--primary-dark); font-size: 12px; font-weight: 750; cursor: pointer; }
.thread-item { width: 100%; min-width: 0; min-height: 62px; padding: 10px 11px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: var(--ink); text-align: left; cursor: pointer; transition: background 180ms ease, border-color 180ms ease; }
.thread-item:hover { background: var(--soft); }
.thread-item.active { border-color: #b8cef2; background: #eef5ff; }
.thread-item span, .thread-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thread-item span { font-size: 13px; font-weight: 700; }
.thread-item small { margin-top: 5px; color: var(--muted-ink); font-size: 11px; }
.rail-state, .rail-empty, .evidence-empty { color: var(--muted-ink); font-size: 12px; line-height: 1.55; }
.rail-state { margin: 18px 2px; }
.rail-state.error, .form-error { color: var(--danger); }
.rail-empty, .evidence-empty { display: grid; justify-items: start; gap: 7px; padding: 28px 5px; }
.rail-empty svg, .evidence-empty svg { width: 28px; fill: none; stroke: #7890af; stroke-width: 1.5; }
.rail-empty strong, .evidence-empty strong { color: var(--ink); font-size: 13px; }
.task-column { padding: clamp(16px, 2vw, 26px); }
.task-starter { padding: clamp(10px, 2vw, 28px) 4px clamp(20px, 3vw, 42px); }
.task-starter h2 { margin: 0; font-family: Outfit, "PingFang SC", sans-serif; font-size: clamp(24px, 3vw, 34px); }
.task-starter > p { max-width: 660px; margin: 10px 0 22px; color: var(--muted-ink); font-size: 14px; line-height: 1.65; }
.starter-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.starter-grid button { min-height: 142px; padding: 16px; border: 1px solid var(--border); border-radius: 12px; background: var(--soft); color: var(--ink); text-align: left; cursor: pointer; transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease; }
.starter-grid button:hover { border-color: #93b4ed; background: #f7faff; box-shadow: 0 5px 14px rgba(37,99,235,.08); }
.starter-grid svg { color: var(--primary); }
.starter-grid strong, .starter-grid span { display: block; }
.starter-grid strong { margin-top: 17px; font-size: 14px; }
.starter-grid span { margin-top: 7px; color: var(--muted-ink); font-size: 12px; line-height: 1.5; }
.run-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.run-heading h2 { max-width: 760px; margin: 0; font-size: clamp(19px, 2.2vw, 27px); line-height: 1.35; overflow-wrap: anywhere; }
.run-status { display: inline-flex; min-height: 32px; flex: 0 0 auto; align-items: center; gap: 7px; padding: 0 10px; border-radius: 999px; font-size: 12px; font-weight: 750; }
.run-status i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.run-status.working { background: #eaf2ff; color: #1d4ed8; }
.run-status.success { background: #e9f8ee; color: var(--success); }
.run-status.warning { background: #fff1e8; color: var(--warning); }
.run-status.danger { background: #fff0ef; color: var(--danger); }
.progress-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 22px 0; padding: 0; list-style: none; }
.progress-steps li { display: flex; min-width: 0; align-items: center; gap: 9px; padding: 10px; border: 1px solid var(--border); border-radius: 11px; background: var(--soft); }
.progress-steps li > span { display: grid; width: 26px; height: 26px; flex: 0 0 auto; place-items: center; border: 1px solid #b7c5d8; border-radius: 50%; color: #64748b; font-size: 11px; font-weight: 800; }
.progress-steps strong, .progress-steps small { display: block; }
.progress-steps strong { font-size: 12px; }
.progress-steps small { margin-top: 3px; color: var(--muted-ink); font-size: 10px; }
.progress-steps li.done { border-color: #b6d9c0; background: #f1faf4; }
.progress-steps li.done > span { border-color: var(--success); background: var(--success); color: #fff; }
.progress-steps li.current { border-color: #91b4ee; background: #eef5ff; box-shadow: inset 0 0 0 1px #d3e2fa; }
.progress-steps li.current > span { border-color: var(--primary); color: var(--primary); }
.decision-card { display: grid; grid-template-columns: 42px 1fr; gap: 13px; margin: 18px 0; padding: 16px; border: 1px solid #f3c7a8; border-radius: 12px; background: #fff9f5; }
.decision-icon { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 10px; background: #ffeadb; color: var(--warning); }
.decision-card > div > span { color: var(--warning); font-size: 11px; font-weight: 800; letter-spacing: .08em; }
.decision-card h3 { margin: 3px 0 5px; font-size: 16px; }
.decision-card p { margin: 0; color: var(--muted-ink); font-size: 13px; line-height: 1.6; }
.decision-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 13px; }
.decision-actions button, .clarification-form button { min-height: 44px; padding: 0 15px; border-radius: 9px; font-size: 13px; font-weight: 750; cursor: pointer; }
.decision-actions .approve, .clarification-form button { border: 1px solid var(--primary); background: var(--primary); color: #fff; }
.decision-actions .reject { border: 1px solid #e2aaa5; background: #fff; color: var(--danger); }
.decision-actions button:disabled, .clarification-form button:disabled { cursor: not-allowed; opacity: .48; }
.clarification-form { display: grid; grid-template-columns: 1fr auto; gap: 7px 9px; margin-top: 13px; }
.clarification-form label { grid-column: 1 / -1; font-size: 12px; font-weight: 750; }
.clarification-form input { min-width: 0; min-height: 44px; padding: 0 12px; border: 1px solid #c8d4e3; border-radius: 9px; background: #fff; color: var(--ink); font-size: 16px; }
.clarification-form small { grid-column: 1 / -1; color: var(--muted-ink); font-size: 11px; }
.timeline { margin-top: 22px; }
.section-heading small { color: var(--muted-ink); font-size: 11px; }
.timeline ol { display: grid; gap: 0; margin: 13px 0 0; padding: 0; list-style: none; }
.timeline li { position: relative; display: grid; grid-template-columns: 34px 1fr; gap: 10px; padding-bottom: 15px; }
.timeline li:not(:last-child)::after { position: absolute; top: 30px; bottom: 0; left: 16px; width: 1px; background: var(--border); content: ''; }
.timeline-icon { z-index: 1; display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid #c6d5e8; border-radius: 10px; background: #f2f6fb; color: var(--primary); }
.timeline-icon svg { width: 17px; }
.timeline-icon.success { border-color: #b6d9c0; background: #effaf2; color: var(--success); }
.timeline-icon.warning { border-color: #f3c7a8; background: #fff4eb; color: var(--warning); }
.timeline-icon.danger { border-color: #e6b5b0; background: #fff2f1; color: var(--danger); }
.timeline li strong { display: block; font-size: 13px; }
.timeline li p { max-width: 72ch; margin: 4px 0; color: var(--muted-ink); font-size: 12px; line-height: 1.55; }
.timeline li small { color: #718096; font-size: 10px; }
.timeline-empty { margin-top: 12px; padding: 14px; border-radius: 10px; background: var(--soft); color: var(--muted-ink); font-size: 12px; }
.report { margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border); }
.report-body { max-width: 74ch; margin-top: 14px; }
.report-body h4 { margin: 19px 0 7px; font-size: 16px; }
.report-body h4:first-child { margin-top: 0; font-size: 20px; }
.report-body p { margin: 6px 0; color: #334155; font-size: 13px; line-height: 1.75; overflow-wrap: anywhere; }
.report-bullet { position: relative; padding-left: 16px; }
.report-bullet > span { position: absolute; top: .78em; left: 2px; width: 5px; height: 5px; border-radius: 50%; background: var(--primary); }
.task-composer { margin-top: 22px; padding-top: 19px; border-top: 1px solid var(--border); }
.task-composer > label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 780; }
.task-composer textarea { display: block; width: 100%; min-height: 92px; resize: vertical; padding: 12px 13px; border: 1px solid #c8d4e3; border-radius: 11px; background: #fbfdff; color: var(--ink); font-family: inherit; font-size: 16px; line-height: 1.55; transition: border-color 180ms ease, box-shadow 180ms ease; }
.task-composer textarea:focus, .clarification-form input:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(37,99,235,.15); }
.task-composer textarea:disabled { cursor: not-allowed; opacity: .58; }
.composer-row { display: flex; align-items: center; justify-content: space-between; gap: 15px; margin-top: 9px; }
.composer-row small { max-width: 620px; color: var(--muted-ink); font-size: 11px; line-height: 1.5; }
.composer-row button { display: inline-flex; min-width: 120px; min-height: 44px; align-items: center; justify-content: center; gap: 7px; padding: 0 15px; border: 1px solid var(--accent); border-radius: 9px; background: var(--accent); color: #fff; font-size: 13px; font-weight: 780; cursor: pointer; transition: background 180ms ease, border-color 180ms ease; }
.composer-row button:hover:not(:disabled) { border-color: #9a3412; background: #9a3412; }
.composer-row button:disabled { cursor: not-allowed; opacity: .46; }
.form-error { margin: 8px 0 0; font-size: 12px; }
.evidence-rail .section-heading { padding-bottom: 11px; border-bottom: 1px solid var(--border); }
.conflict-summary { display: grid; grid-template-columns: 28px 1fr; gap: 8px; margin: 12px 0; padding: 10px; border: 1px solid #f3c7a8; border-radius: 10px; background: #fff7f0; color: var(--warning); }
.conflict-summary svg { width: 23px; fill: none; stroke: currentColor; stroke-width: 1.8; }
.conflict-summary strong, .conflict-summary span { display: block; }
.conflict-summary strong { font-size: 12px; }
.conflict-summary span { margin-top: 3px; color: #7c4a31; font-size: 10px; line-height: 1.45; }
.evidence-list { display: grid; gap: 9px; margin-top: 12px; }
.evidence-list article { padding: 11px; border: 1px solid var(--border); border-radius: 10px; background: var(--soft); }
.evidence-list article > div { display: flex; min-width: 0; align-items: center; gap: 6px; }
.evidence-list b { color: var(--primary); font-size: 11px; }
.evidence-list div span, .evidence-list em { overflow: hidden; color: var(--muted-ink); font-size: 10px; font-style: normal; text-overflow: ellipsis; white-space: nowrap; }
.evidence-list em { margin-left: auto; padding: 2px 5px; border-radius: 999px; background: var(--muted); }
.evidence-list article > strong { display: block; margin-top: 7px; font-size: 12px; overflow-wrap: anywhere; }
.evidence-list p { display: -webkit-box; overflow: hidden; margin: 5px 0 0; color: var(--muted-ink); font-size: 11px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.evidence-list a { display: inline-flex; min-height: 32px; align-items: center; gap: 4px; margin-top: 6px; color: var(--primary-dark); font-size: 11px; font-weight: 750; }
.evidence-list a svg { width: 14px; }
.evidence-disclosure { min-height: 44px; border: 1px solid #b8cef2; border-radius: 9px; background: #eef5ff; color: var(--primary-dark); font-size: 12px; font-weight: 750; cursor: pointer; }
button:focus-visible, a:focus-visible, textarea:focus-visible, input:focus-visible { outline: 3px solid rgba(37,99,235,.32); outline-offset: 2px; }

/* Match the landing, graph and GraphRAG workspaces. */
.agent-page {
  --primary: #a4ffcb; --primary-dark: #a4ffcb; --accent: #ffd36c; --ink: #edf7f1;
  --muted-ink: #91a79c; --surface: #0c1914; --soft: #10231b; --muted: #152a21;
  --border: rgba(181,231,203,.14); --danger: #ff9b8d; --warning: #ffb27b; --success: #75dda0;
}
.agent-hero p,
.eyebrow,
.section-heading span,
.rail-heading span { color: #a4ffcb; }
.agent-hero h1 { color: #edf7f1; }
.agent-hero > div > span { color: #91a79c; }
.quick-link { border-color: var(--border); background: #10231b; color: #a4ffcb; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
.quick-link:hover { border-color: rgba(164,255,203,.3); background: rgba(164,255,203,.08); }
.thread-rail,
.task-column,
.evidence-rail { border-color: var(--border); background: #0c1914; box-shadow: 0 18px 50px rgba(0,0,0,.18); }
.rail-heading button { border-color: var(--border); background: #10231b; color: #a4ffcb; }
.rail-heading button:hover { border-color: rgba(164,255,203,.3); background: rgba(164,255,203,.08); }
.thread-item.active { border-color: rgba(164,255,203,.28); background: rgba(164,255,203,.09); }
.starter-grid button { border-color: var(--border); background: #10231b; }
.starter-grid button:hover { border-color: rgba(164,255,203,.3); background: rgba(164,255,203,.07); box-shadow: 0 8px 24px rgba(0,0,0,.12); }
.progress-steps li { border-color: var(--border); background: #10231b; }
.progress-steps li > span { border-color: #537364; color: #91a79c; }
.progress-steps li.done { border-color: rgba(117,221,160,.28); background: rgba(117,221,160,.08); }
.progress-steps li.current { border-color: rgba(164,255,203,.34); background: rgba(164,255,203,.09); box-shadow: inset 0 0 0 1px rgba(164,255,203,.07); }
.run-status.working { background: rgba(123,229,255,.1); color: #7be5ff; }
.run-status.success { background: rgba(117,221,160,.1); }
.run-status.warning { background: rgba(255,178,123,.1); }
.run-status.danger { background: rgba(255,155,141,.1); }
.decision-card,
.conflict-summary { border-color: rgba(255,178,123,.24); background: rgba(255,178,123,.075); }
.decision-icon { background: rgba(255,178,123,.12); }
.decision-actions .approve,
.clarification-form button { border-color: #a4ffcb; background: #a4ffcb; color: #07110e; }
.decision-actions .reject { border-color: rgba(255,155,141,.28); background: transparent; color: #ff9b8d; }
.clarification-form input,
.task-composer textarea { border-color: var(--border); background: #10231b; color: #edf7f1; }
.task-composer textarea::placeholder,
.clarification-form input::placeholder { color: #61776c; }
.task-composer textarea:focus,
.clarification-form input:focus { border-color: #a4ffcb; box-shadow: 0 0 0 3px rgba(164,255,203,.1); }
.timeline-icon { border-color: var(--border); background: #10231b; color: #a4ffcb; }
.timeline-icon.success { border-color: rgba(117,221,160,.28); background: rgba(117,221,160,.08); }
.timeline-icon.warning { border-color: rgba(255,178,123,.24); background: rgba(255,178,123,.08); }
.timeline-icon.danger { border-color: rgba(255,155,141,.24); background: rgba(255,155,141,.08); }
.report-body p { color: #c2d3c9; }
.composer-row button { border-color: #a4ffcb; background: #a4ffcb; color: #07110e; }
.composer-row button:hover:not(:disabled) { border-color: #d3ffe5; background: #d3ffe5; }
.conflict-summary span { color: #d9b596; }
.evidence-list article { border-color: var(--border); background: #10231b; }
.evidence-disclosure { border-color: rgba(164,255,203,.22); background: rgba(164,255,203,.08); color: #a4ffcb; }
button:focus-visible,
a:focus-visible,
textarea:focus-visible,
input:focus-visible { outline-color: rgba(164,255,203,.5); }
@media (max-width: 1179px) { .agent-grid { grid-template-columns: 210px minmax(0, 1fr); } .evidence-rail { position: static; grid-column: 1 / -1; max-height: none; } .evidence-list { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 899px) { .agent-hero { align-items: flex-start; } .agent-grid { grid-template-columns: 1fr; } .thread-rail, .evidence-rail { position: static; max-height: none; } .thread-list { grid-template-columns: repeat(2, minmax(0, 1fr)); } .starter-grid, .evidence-list { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 620px) {
  .agent-page { min-height: calc(100dvh - 82px); }
  .agent-hero { display: block; padding: 4px 4px 0; }
  .agent-hero h1 { font-size: 27px; }
  .quick-link { margin-top: 13px; }
  .agent-grid { gap: 10px; }
  .thread-rail, .task-column, .evidence-rail { border-radius: 12px; }
  .thread-list, .starter-grid, .evidence-list { grid-template-columns: 1fr; }
  .thread-list:not(.expanded) .thread-item:nth-child(n + 3) { display: none; }
  .history-disclosure { display: block; }
  .progress-steps { grid-template-columns: repeat(2, 1fr); }
  .run-heading { display: block; }
  .run-status { margin-top: 10px; }
  .composer-row { align-items: stretch; flex-direction: column; }
  .composer-row button { width: 100%; }
  .clarification-form { grid-template-columns: 1fr; }
  .clarification-form label, .clarification-form small { grid-column: auto; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; } }
</style>
