<template>
  <section class="agent-page">
    <header class="view-heading">
      <div>
        <h1>任务分析</h1>
        <p>比较登记或核验关联，查看分析结果和支持证据。</p>
      </div>
      <div class="view-actions">
        <button v-if="activeRun || activeThreadId" class="ui-button primary" type="button" :disabled="starting || resuming" @click="newTask">
          <UiIcon name="plus" /> 新建任务
        </button>
        <router-link to="/ask" class="ui-button">只问一个问题 <UiIcon name="arrow" /></router-link>
      </div>
    </header>

    <div class="agent-grid">
      <div class="task-column" role="region" aria-label="任务工作区">
        <div v-if="runLoading" class="task-loading" role="status">
          <span aria-hidden="true" class="ui-skeleton"></span> 正在恢复任务…
        </div>

        <div v-if="runError" class="ui-error run-error" role="alert">
          <p>{{ runError }}</p>
          <button v-if="activeRun" class="ui-button" type="button" @click="refreshRun(activeRun.threadId, activeRun.id)">刷新任务状态</button>
          <button v-else-if="activeThreadId" class="ui-button" type="button" @click="openThread({ id: activeThreadId })">重新打开任务</button>
        </div>

        <section v-if="activeRun" class="run-card" aria-labelledby="active-task-title">
          <div ref="runHeading" class="run-heading" tabindex="-1">
            <h2 id="active-task-title">{{ activeRun.question }}</h2>
            <span class="run-status" :class="statusTone(activeRun.status)" role="status">
              <i aria-hidden="true"></i>{{ runStatus(activeRun.status) }}
            </span>
          </div>

          <section v-if="pendingKind" class="decision-card" aria-labelledby="decision-title">
            <UiIcon name="alert" />
            <div>

              <h3 id="decision-title">{{ decisionTitle }}</h3>
              <p v-if="activeRun.interrupt && activeRun.interrupt.message" class="decision-message">{{ activeRun.interrupt.message }}</p>
              <p v-if="pendingKind === 'approval' && lastClarification" class="clarification-summary">
                <strong>已补充</strong> {{ lastClarification.detail }}
              </p>
              <div v-if="pendingKind === 'approval'" class="decision-actions">
                <button class="ui-button primary" type="button" :disabled="resuming" @click="resume({ decision: 'approve' })">批准并生成报告</button>
                <button class="ui-button" type="button" :disabled="resuming" @click="resume({ decision: 'reject' })">拒绝并保留证据</button>
              </div>
              <form v-else-if="pendingKind === 'clarification'" class="clarification-form" @submit.prevent="submitClarification">
                <label for="clarification-input">补充信息</label>
                <input id="clarification-input" ref="clarification" class="ui-input" v-model.trim="clarification"
                  required minlength="2" maxlength="160" :disabled="resuming"
                   :aria-describedby="formError ? 'clarification-help clarification-error' : 'clarification-help'">
                <small id="clarification-help">请输入缺少的实体名称或登记号，至少 2 个字。</small>
                <button class="ui-button primary" type="submit" :disabled="resuming">继续分析</button>
              </form>
              <button v-else class="ui-button primary" type="button" :disabled="resuming" @click="resume(null)">恢复任务</button>
              <p v-if="resuming" class="action-status" role="status">正在提交，任务状态即将更新…</p>
              <p v-if="formError" id="clarification-error" class="ui-error decision-error" role="alert">{{ formError }}</p>
            </div>
          </section>

          <p v-else-if="activeRun.status === 'failed'" class="ui-error" role="alert">分析未能完成。已保留任务进度，可以重新发起。</p>

          <article v-if="activeRun.report" class="report" aria-labelledby="report-title">
            <h3 id="report-title">分析结果</h3>
            <div class="report-body">
              <component v-for="(block, index) in reportBlocks" :is="block.list ? 'ul' : 'div'" :key="index">
                <component v-for="(row, rowIndex) in block.rows" :is="row.tag" :key="rowIndex">
                  <template v-for="(part, partIndex) in row.parts">
                    <button v-if="part.fact" :key="'cite-' + partIndex" class="report-citation" type="button"
                      :aria-label="'查看第 ' + part.fact.index + ' 条证据'" @click="focusEvidence(part.fact)">
                      [{{ part.fact.index }}]
                    </button>
                    <span v-else :key="'text-' + partIndex">{{ part.text }}</span>
                  </template>
                </component>
              </component>
            </div>
          </article>

          <details v-if="events.length" class="timeline">
            <summary><strong>执行记录</strong><span>{{ events.length }} 条</span></summary>
            <ol>
              <li v-for="item in events" :key="item.seq || item.kind + '-' + item.title">
                <span class="timeline-icon" :class="eventTone(item.kind)" aria-hidden="true">
                  <UiIcon :name="eventIcon(item.kind)" />
                </span>
                <div><strong>{{ item.title }}</strong><p>{{ item.detail }}</p><small>{{ formatTime(item.createdAt) }}</small></div>
              </li>
            </ol>
          </details>
        </section>

        <p v-if="activeRun && isRunning" class="task-loading current-run" role="status">
          <span class="ui-skeleton" aria-hidden="true"></span> 正在分析，进度会自动更新。
        </p>
        <form v-else-if="!pendingKind && !runLoading && !runError" class="task-composer" @submit.prevent="startAnalysis">
          <h2 v-if="!activeRun">你希望核验什么？</h2>
          <label for="agent-question">{{ activeRun ? '继续分析当前任务' : '描述要分析的任务' }}</label>
          <textarea id="agent-question" ref="question" class="ui-input" v-model.trim="question" rows="3"
            required minlength="2" maxlength="500" :disabled="starting"
            :aria-describedby="formError ? 'agent-question-help agent-start-error' : 'agent-question-help'"
            placeholder="例如，比较两项登记的有效成分和关联作物。"></textarea>
          <div class="composer-row">
            <small id="agent-question-help">至少输入 2 个字。分析过程会保存在任务记录里。</small>
            <button class="ui-button primary" type="submit" :disabled="starting">
              {{ starting ? '正在启动…' : '开始分析' }} <UiIcon name="arrow" />
            </button>
          </div>
          <p v-if="formError" id="agent-start-error" class="ui-error" role="alert">{{ formError }}</p>
        </form>

        <section v-if="!activeRun && !runLoading && !runError" class="task-starter" aria-labelledby="agent-examples-title">
          <h3 id="agent-examples-title">从一个示例开始</h3>
          <ul>
            <li v-for="item in starters" :key="item.title">
              <button type="button" :disabled="starting" @click="useExample(item.question)">
                <UiIcon :name="item.icon" />
                <div><strong>{{ item.title }}</strong><span>{{ item.description }}</span></div>
                <UiIcon name="arrow" />
              </button>
            </li>
          </ul>
        </section>
      </div>

      <aside class="evidence-rail" aria-labelledby="agent-evidence-title">
        <div class="rail-heading">
          <div class="evidence-heading"><h2 id="agent-evidence-title">来源与差异</h2><span v-if="evidence.length">{{ evidence.length }} 条证据</span></div>
          <button v-if="evidence.length" class="ui-button evidence-rail-toggle" type="button"
            aria-controls="agent-evidence-content" :aria-expanded="String(evidenceRailOpen)"
            @click="evidenceRailOpen = !evidenceRailOpen">
            {{ evidenceRailOpen ? '收起' : '查看证据' }} <UiIcon name="chevron" />
          </button>
        </div>
        <div id="agent-evidence-content" v-if="evidence.length" class="evidence-content" :class="{ expanded: evidenceRailOpen }">
          <div v-if="conflicts.length" class="conflict-summary">
            <UiIcon name="alert" />
            <p>有 {{ conflicts.length }} 组差异待核对。查看报告中的具体说明。</p>
          </div>
          <div class="evidence-list">
            <ol id="agent-evidence-list">
              <li v-for="(item, index) in visibleEvidence" :key="item.index + '-' + item.source + '-' + item.title"
                :id="'agent-evidence-' + index" tabindex="-1" :class="{ highlighted: selectedEvidence === item }">
                <div class="evidence-meta"><b>[{{ item.index }}]</b><span>{{ item.source }}</span><span v-if="item.jurisdiction">{{ item.jurisdiction }}</span></div>
                <h3>{{ item.title }}</h3>
                <p v-if="item.summary !== 'name=' + item.title">{{ item.summary }}</p>
                <a v-if="isSourceLink(item.url)" class="ui-link" :href="item.url" target="_blank" rel="noopener noreferrer">
                  查看来源 <UiIcon name="external" />
                </a>
              </li>
            </ol>
            <button v-if="evidence.length > 8" class="ui-button evidence-disclosure" type="button"
              :aria-expanded="String(evidenceExpanded)" aria-controls="agent-evidence-list"
              @click="evidenceExpanded = !evidenceExpanded">
              {{ evidenceExpanded ? '收起其余证据' : '查看全部 ' + evidence.length + ' 条证据' }}
            </button>
          </div>
        </div>
        <p v-else class="rail-state">{{ isRunning ? '正在检索证据，汇总后将在这里显示。' : '检索结束后，可在这里逐条查看图谱依据和外部来源。' }}</p>
      </aside>

      <aside class="thread-rail" aria-labelledby="agent-history-title">
        <div class="rail-heading">
          <h2 id="agent-history-title">最近任务</h2>
          <button class="ui-button history-toggle" type="button" aria-controls="agent-thread-history"
            :aria-expanded="String(historyExpanded)" @click="historyExpanded = !historyExpanded">
            {{ historyExpanded ? '收起' : '查看记录' }} <UiIcon name="chevron" />
          </button>
        </div>
        <div id="agent-thread-history" class="thread-history" :class="{ expanded: historyExpanded }">
          <p v-if="threadsLoading" class="rail-state" role="status">正在载入任务…</p>
          <div v-if="threadsError" class="rail-state">
            <p role="alert">{{ threadsError }}</p>
            <button type="button" class="ui-button" @click="loadThreads">刷新任务列表</button>
          </div>
          <ul v-if="threads.length" class="thread-list">
            <li v-for="thread in threads" :key="thread.id">
              <button type="button" class="thread-item" :class="{ active: thread.id === activeThreadId }"
                :disabled="starting || resuming" :aria-current="thread.id === activeThreadId ? 'true' : undefined"
                @click="openThread(thread)">
                <strong>{{ thread.title }}</strong>
                <small><span :class="statusTone(thread.latestStatus)">{{ runStatus(thread.latestStatus) }}</span> · {{ formatTime(thread.updatedAt) }}</small>
              </button>
            </li>
          </ul>
          <p v-else-if="!threadsLoading && !threadsError" class="rail-state">开始分析后，可以在这里找回任务。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script>
import agentService, { eventStreamUrl } from '@/utils/agent';
import UiIcon from '@/components/UiIcon.vue';
import { citationParts, isSourceLink } from '@/utils/citations';

export default {
  name: 'AgentView',
  components: { UiIcon },
  data() {
    return {
      threads: [],
      threadsLoading: false,
      threadsError: '',
      threadsVersion: 0,
      activeThreadId: '',
      activeRun: null,
      runLoading: false,
      runError: '',
      runVersion: 0,
      events: [],
      question: '',
      clarification: '',
      formError: '',
      starting: false,
      resuming: false,
      stream: null,
      refreshTimer: null,
      historyExpanded: false,
      evidenceExpanded: false,
      evidenceRailOpen: false,
      selectedEvidence: null,

      starters: [
        { title: '成分对比', description: '比较作用机制与关联作物', question: "比较 'Abamectin' 与 'Chlorantraniliprole' 的作用机制和关联作物", icon: 'task' },
        { title: '关系路径', description: '解释两个实体如何相连', question: "查找 'Prothioconazole' 到 'Spring barley' 的关系路径", icon: 'graph' },
        { title: '登记初筛', description: '核验登记依据与外部来源', question: "核验 'Abamectin' 的登记与使用风险，并生成证据化初筛报告", icon: 'document' }
      ]
    };
  },
  computed: {
    isRunning() {
      return this.activeRun?.status === 'running';
    },
    pendingKind() {
      const status = this.activeRun?.status;
      return ({ waiting_clarification: 'clarification', waiting_approval: 'approval', paused: 'paused' })[status];
    },
    decisionTitle() {
      const titles = { clarification: '还需要补充信息', approval: '确认是否生成报告', paused: '从上次进度继续' };
      return this.activeRun?.interrupt?.title || titles[this.pendingKind];
    },
    lastClarification() {
      return [...this.events].reverse().find(item => item.kind === 'clarification_received');
    },
    evidenceEvent() {
      return [...this.events].reverse().find(item => item.kind === 'evidence_verified');
    },
    evidence() {
      const items = this.evidenceEvent?.payload?.evidence;
      return Array.isArray(items) ? items : [];
    },
    conflicts() {
      const items = this.evidenceEvent?.payload?.conflicts;
      return Array.isArray(items) ? items : [];
    },
    visibleEvidence() {
      return this.evidenceExpanded ? this.evidence : this.evidence.slice(0, 8);
    },
    reportBlocks() {
      const lines = String(this.activeRun?.report || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
      return lines.reduce((blocks, line) => {
        const list = /^[-*]\s+/.test(line);
        const heading = /^#{1,6}\s+/.test(line);
        const row = {
          tag: list ? 'li' : heading ? 'h4' : 'p',
          parts: citationParts(line.replace(/^(?:[-*]|#{1,6})\s+/, ''), this.evidence)
        };
        const previous = blocks[blocks.length - 1];
        if (list && previous?.list) previous.rows.push(row);
        else blocks.push({ list, rows: [row] });
        return blocks;
      }, []);
    }
  },
  mounted() {
    document.title = '任务分析 · AgriReg AI';
    this.loadThreads();
  },
  beforeDestroy() {
    this.runVersion += 1;
    this.threadsVersion += 1;
    this.closeStream();
  },
  methods: {
    async loadThreads() {
      const version = ++this.threadsVersion;
      this.threadsLoading = true;
      this.threadsError = '';
      try {
        const response = await agentService.get('/api/agent/threads', { timeout: 8000 });
        if (version !== this.threadsVersion) return;
        this.threads = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        if (version !== this.threadsVersion) return;
        this.threadsError = '任务记录暂时无法载入。';
        this.historyExpanded = true;
      } finally {
        if (version === this.threadsVersion) this.threadsLoading = false;
      }
    },
    resetTask() {
      this.runVersion += 1;
      this.closeStream();
      this.activeThreadId = '';
      this.activeRun = null;
      this.events = [];
      this.question = '';
      this.clarification = '';
      this.formError = '';
      this.runError = '';
      this.runLoading = false;
      this.evidenceRailOpen = false;
      this.evidenceExpanded = false;
      this.selectedEvidence = null;
    },
    newTask() {
      this.resetTask();
      this.$nextTick(() => this.$refs.question?.focus());
    },
    useExample(question) {
      this.question = question;
      this.formError = '';
      this.$nextTick(() => this.$refs.question?.focus());
    },
    async openThread(thread) {
      if (!thread?.id || this.starting || this.resuming) return;
      this.resetTask();
      const version = this.runVersion;
      this.activeThreadId = thread.id;
      this.runLoading = true;
      try {
        const response = await agentService.get('/api/agent/threads/' + encodeURIComponent(thread.id));
        if (version !== this.runVersion) return;
        const recentRun = response.data?.runs?.[0];
        if (recentRun) await this.refreshRun(thread.id, recentRun.id);
        if (version !== this.runVersion) return;
        if (!this.runError) this.historyExpanded = false;
      } catch (error) {
        if (version === this.runVersion) this.runError = '这条任务记录暂时无法打开。';
      } finally {
        if (version === this.runVersion) {
          this.runLoading = false;
          if (this.activeRun) this.$nextTick(() => this.$refs.runHeading?.focus());
        }
      }
    },
    async startAnalysis() {
      if (this.starting || this.isRunning || this.pendingKind || this.question.length < 2) return;
      const version = this.runVersion;
      this.starting = true;
      this.formError = '';
      try {
        let threadId = this.activeThreadId;
        if (!threadId) {
          const response = await agentService.post('/api/agent/threads', { title: '新分析任务' });
          if (version !== this.runVersion) return;
          threadId = response.data.id;
          this.activeThreadId = threadId;
        }
        const response = await agentService.post(this.runUrl(threadId), { question: this.question });
        if (version !== this.runVersion) return;
        this.evidenceRailOpen = false;
        this.evidenceExpanded = false;
        this.selectedEvidence = null;
        this.applyRun(response.data);
        this.question = '';
        this.connectStream(threadId, response.data.id);
        this.loadThreads();
        this.$nextTick(() => this.$refs.runHeading?.focus());
      } catch (error) {
        if (version === this.runVersion) this.formError = '任务没有启动成功。请确认任务分析服务可用后重试。';
      } finally {
        if (version === this.runVersion) this.starting = false;
      }
    },
    runUrl(threadId, runId) {
      const runs = '/api/agent/threads/' + encodeURIComponent(threadId) + '/runs';
      return runId ? runs + '/' + encodeURIComponent(runId) : runs;
    },
    applyRun(run) {
      this.activeRun = run;
      if (Array.isArray(run.events)) this.events = run.events;
    },
    connectStream(threadId, runId, retry = true) {
      this.closeStream();
      const after = Number(this.events[this.events.length - 1]?.seq || 0);
      const stream = new EventSource(eventStreamUrl(threadId, runId, after));
      this.stream = stream;
      stream.addEventListener('agent_event', event => {
        if (this.stream !== stream) return;
        const item = JSON.parse(event.data);
        if (!this.events.some(existing => Number(existing.seq) === Number(item.seq))) this.events.push(item);
      });
      stream.addEventListener('run_snapshot', event => {
        if (this.stream !== stream) return;
        this.applyRun(JSON.parse(event.data));
        this.closeStream();
        this.loadThreads();
      });
      stream.onerror = () => {
        if (this.stream !== stream) return;
        this.closeStream();
        if (retry) {
          this.refreshTimer = window.setTimeout(() => this.refreshRun(threadId, runId, false), 800);
        } else {
          this.runError = '任务进度连接中断。可以手动刷新状态。';
        }
      };
    },
    async refreshRun(threadId, runId, retry = true) {
      const version = this.runVersion;
      this.closeStream();
      try {
        const response = await agentService.get(this.runUrl(threadId, runId));
        if (version !== this.runVersion) return;
        this.applyRun(response.data);
        this.runError = '';
        if (this.isRunning) this.connectStream(threadId, runId, retry);
        else this.loadThreads();
      } catch (error) {
        if (version === this.runVersion) this.runError = '任务进度暂时无法载入，请重试。';
      }
    },
    closeStream() {
      if (this.refreshTimer !== null) window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
      if (this.stream) this.stream.close();
      this.stream = null;
    },
    submitClarification() {
      if (this.clarification.length < 2) {
        this.formError = '请输入至少 2 个字。';
        return;
      }
      this.resume(this.clarification);
    },
    async resume(value) {
      if (!this.pendingKind || this.resuming) return;
      const version = this.runVersion;
      const { threadId, id } = this.activeRun;
      this.resuming = true;
      this.formError = '';
      try {
        const response = await agentService.post(this.runUrl(threadId, id) + '/resume', { value });
        if (version !== this.runVersion) return;
        this.applyRun(response.data);
        this.clarification = '';
        this.runError = '';
        if (this.isRunning) this.connectStream(threadId, id);
        else this.loadThreads();
        this.$nextTick(() => {
          if (this.pendingKind === 'clarification') this.$refs.clarification?.focus();
          else this.$refs.runHeading?.focus({ preventScroll: true });
        });
      } catch (error) {
        if (version !== this.runVersion) return;
        if (error.response?.status === 409) {
          await this.refreshRun(threadId, id);
          if (version !== this.runVersion || !this.pendingKind) return;
        }
        this.formError = '这次操作没有提交成功，请重试。';
      } finally {
        if (version === this.runVersion) this.resuming = false;
      }
    },
    focusEvidence(item) {
      const index = this.evidence.indexOf(item);
      if (index < 0) return;
      this.evidenceRailOpen = true;
      if (index >= 8) this.evidenceExpanded = true;
      this.selectedEvidence = item;
      this.$nextTick(() => document.getElementById('agent-evidence-' + index)?.focus());
    },
    isSourceLink,
    runStatus(status) {
      return ({
        running: '分析中', waiting_clarification: '等待补充', waiting_approval: '待审批',
        completed: '已完成', rejected: '已拒绝', failed: '分析失败', paused: '已暂停'
      })[status] || '待开始';
    },
    statusTone(status) {
      if (status === 'completed' || status === 'running') return 'success';
      if (status === 'failed' || status === 'rejected') return 'danger';
      if (String(status).startsWith('waiting_') || status === 'paused') return 'warning';
      return '';
    },
    eventTone(kind) {
      if (kind === 'tool_failed' || kind === 'run_failed') return 'danger';
      if (kind === 'input_required') return 'warning';
      return 'success';
    },
    eventIcon(kind) {
      if (kind === 'evidence_verified') return 'check';
      if (kind === 'input_required' || kind === 'tool_failed' || kind === 'run_failed') return 'alert';
      return 'document';
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
.view-actions { display: flex; flex-wrap: wrap; gap: 7px; }
.agent-grid { display: grid; grid-template-columns: minmax(172px, 205px) minmax(0, 1fr) minmax(238px, 288px); align-items: start; gap: 14px; }
.task-column, .thread-rail, .evidence-rail { min-width: 0; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
.task-column { grid-area: 1 / 2; }
.evidence-rail { grid-area: 1 / 3; }
.thread-rail { grid-area: 1 / 1; }
.rail-heading { display: flex; min-height: 54px; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 5px 7px; padding: 9px 13px; border-bottom: 1px solid var(--line); }
.rail-heading h2 { font-size: 16px; }
.rail-heading span { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.history-toggle, .evidence-rail-toggle { display: none; }
.evidence-heading { display: flex; flex: 1; align-items: baseline; justify-content: space-between; gap: 6px; }
.rail-state { display: grid; justify-items: start; gap: 6px; padding: 13px; color: var(--muted); font-size: 13px; }
.rail-state [role="alert"] { color: var(--danger); }
.thread-list { display: grid; grid-template-columns: minmax(0, 1fr); gap: 4px; max-height: 65vh; margin: 0; padding: 7px; list-style: none; overflow-y: auto; }
.thread-item { width: 100%; min-height: 48px; padding: 6px; border: 1px solid transparent; border-radius: 6px; background: transparent; text-align: left; }
.thread-item:not(:disabled):hover, .thread-item.active { border-color: var(--line); background: var(--wash); }
.thread-item strong, .thread-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thread-item strong { font-size: 13px; }
.thread-item small { color: var(--muted); font-size: 12px; }

.task-composer, .task-starter, .run-card { padding: 19px 21px; }
.task-composer { display: grid; gap: 7px; }
.run-card + .task-composer { border-top: 1px solid var(--line); }
.task-composer h2 { margin-bottom: 7px; font-size: 1.4rem; }
.task-composer label, .clarification-form label { width: fit-content; font-size: 14px; font-weight: 700; }
.task-composer textarea { min-height: 101px; }
.composer-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px 12px; }
.composer-row .ui-button { margin-left: auto; }
.composer-row small, .clarification-form small { color: var(--muted); font-size: 12px; }
.task-starter { padding-top: 0; }
.task-starter h3 { padding-top: 15px; border-top: 1px solid var(--line); font-size: 15px; }
.task-starter ul, .evidence-list ol { margin: 0; padding: 0; list-style: none; }
.task-starter button {
  display: grid;
  width: 100%;
  min-height: 60px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: var(--accent);
  text-align: left;
}
.task-starter li:last-child button { border-bottom: 0; }
.task-starter button:hover:not(:disabled) { background: var(--wash); }
.task-starter button strong, .task-starter button span { display: block; }
.task-starter button strong { color: var(--ink); font-size: 14px; }
.task-starter button span { color: var(--muted); font-size: 13px; }
.task-loading { display: grid; gap: 8px; padding: 18px 21px; color: var(--muted); font-size: 14px; }
.current-run { border-top: 1px solid var(--line); }
.run-error { margin: 13px; }
.run-error .ui-button { margin-top: 7px; }

.run-heading { display: flex; align-items: start; justify-content: space-between; flex-wrap: wrap; gap: 7px 10px; margin-bottom: 16px; }
.run-heading h2 { min-width: 0; flex: 1 1 280px; font-size: 1.25rem; line-height: 1.5; overflow-wrap: anywhere; }
.run-status { display: inline-flex; min-height: 30px; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 5px; background: var(--wash); font-size: 13px; font-weight: 750; }
.run-status i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.success { color: var(--accent); }
.warning { color: var(--warn); }
.danger { color: var(--danger); }
.run-status.success { background: var(--tint); }
.run-status.warning { background: var(--warn-bg); }
.run-status.danger { background: var(--danger-bg); }

.decision-card { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: start; gap: 9px; margin-bottom: 16px; padding: 13px; border: 1px solid #e5cf9d; border-radius: var(--control-radius); background: var(--warn-bg); }
.decision-card > .ui-icon { margin-top: 1px; color: var(--warn); }
.action-status { color: var(--warn); font-size: 13px; font-weight: 700; }
.clarification-summary { margin-top: 8px; color: var(--warn); font-size: 13px; overflow-wrap: anywhere; }
.decision-card h3 { margin-top: 4px; font-size: 17px; }
.decision-message { margin-top: 5px; overflow-wrap: anywhere; }
.decision-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.decision-card > div > .ui-button { margin-top: 10px; }
.clarification-form { display: grid; gap: 6px; margin-top: 11px; }
.clarification-form button { justify-self: start; margin-top: 2px; }
.decision-error, .action-status { margin-top: 8px; }

.timeline { margin-top: 14px; border-top: 1px solid var(--line); }
.timeline summary { min-height: 44px; padding: 10px 0; color: var(--accent); }
.timeline summary span { margin-left: 10px; color: var(--muted); font-size: 12px; }
.timeline ol { margin: 0; padding: 0; list-style: none; }
.timeline li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 9px; padding-block: 9px; border-top: 1px solid var(--line); }
.timeline-icon { display: grid; width: 25px; height: 25px; place-items: center; border-radius: 5px; background: var(--wash); }
.timeline-icon.warning { background: var(--warn-bg); }
.timeline-icon.danger { background: var(--danger-bg); }
.timeline-icon .ui-icon { width: 15px; height: 15px; }
.timeline li strong { font-size: 14px; }
.timeline li p, .timeline li small { color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }

.report { padding-top: 11px; border-top: 1px solid var(--line); }
.report > h3 { margin-bottom: 12px; font-size: 1.23rem; }
.report-body { max-width: 72ch; font-size: 15px; line-height: 1.7; overflow-wrap: anywhere; }
.report-body h4 { margin-top: 14px; font-size: 15px; }
.report-body p { margin-block: 5px 8px; text-wrap: pretty; }
.report-body ul { margin: 6px 0 10px; padding-left: 1.45em; }
.report-body li { margin-block: 4px; }
.report-citation { min-height: 25px; margin-inline: 2px; padding: 0 4px; border: 0; border-radius: 4px; background: var(--tint); color: var(--accent); font: 700 12px/1.3 var(--mono); text-decoration: underline; }
.report-citation:hover { background: #d6e1c8; }

.conflict-summary { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px; margin: 9px 10px; padding: 8px; border: 1px solid #e5cf9d; border-radius: 6px; background: var(--warn-bg); color: var(--warn); font-size: 13px; }
.conflict-summary .ui-icon { width: 15px; height: 15px; margin-top: 2px; }
.evidence-list li { padding: 10px 12px; overflow-wrap: anywhere; }
.evidence-list li + li { border-top: 1px solid var(--line); }
.evidence-list li:focus-visible, .evidence-list li.highlighted { outline: 2px solid var(--focus); outline-offset: -2px; background: var(--wash); }
.evidence-meta { display: flex; align-items: baseline; flex-wrap: wrap; gap: 2px 7px; color: var(--muted); font-size: 12px; }
.evidence-meta b { color: var(--accent); font: 700 12px/1.3 var(--mono); }
.evidence-list h3 { margin-block: 4px 3px; font-size: 14px; }
.evidence-list li p, .evidence-list li a { font-size: 13px; }
.evidence-list li a { display: inline-flex; min-height: 31px; align-items: center; gap: 4px; }
.evidence-list li .ui-icon { width: 14px; height: 14px; }
.evidence-disclosure { width: calc(100% - 20px); margin: 3px 10px 9px; }
@media (max-width: 1100px) {
  .agent-grid { grid-template-columns: minmax(0, 1fr) minmax(225px, .47fr); }
  .task-column { grid-area: 1 / 1; }
  .evidence-rail { grid-area: 1 / 2; }
  .thread-rail { grid-area: 2 / 1 / auto / span 2; }
  .history-toggle { display: inline-flex; }
  .thread-history:not(.expanded) { display: none; }
  .thread-rail .rail-heading { border-bottom: 0; }
  .thread-history { border-top: 1px solid var(--line); }
}
@media (max-width: 760px) {
  .agent-grid { grid-template-columns: minmax(0, 1fr); gap: 11px; }
  .task-column, .evidence-rail, .thread-rail { grid-area: auto; }
  .task-composer, .task-starter, .run-card { padding-inline: 13px; }
  .task-composer, .run-card { padding-top: 14px; }
  .run-heading { margin-bottom: 11px; }
  .view-actions .ui-button { justify-content: start; }
  .evidence-rail-toggle { display: inline-flex; min-height: 44px; }
  .evidence-content:not(.expanded) { display: none; }
}
@media (max-width: 430px) {
  .decision-card { gap: 6px; padding-inline: 8px; }
}
</style>
