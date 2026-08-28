<template>
  <section class="ask-page">
    <header class="ask-intro">
      <div>
        <p>AGRIREG INTELLIGENCE · ASSISTANT</p>
        <h1>用自然语言，追溯农药知识</h1>
        <span>答案来自知识图谱中的实体与关系，并附带可继续探索的依据。</span>
      </div>
      <div class="ask-intro-actions">
        <button
          type="button"
          class="history-toggle"
          aria-controls="recent-conversations"
          :aria-expanded="sidebarOpen ? 'true' : 'false'"
          @click="sidebarOpen = true"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
          最近对话
        </button>
        <router-link to="/graph" class="graph-link">
          打开知识图谱
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
        </router-link>
      </div>
    </header>

    <div :class="['chat-workspace', { 'sidebar-open': sidebarOpen }]">
      <button
        v-if="sidebarOpen"
        type="button"
        class="sidebar-backdrop"
        aria-label="关闭最近对话"
        @click="sidebarOpen = false"
      ></button>

      <aside id="recent-conversations" class="conversation-sidebar" aria-label="最近对话">
        <div class="history-heading">
          <div>
            <span>对话记录</span>
            <strong>最近对话</strong>
          </div>
          <button type="button" class="mobile-close" aria-label="关闭最近对话" @click="sidebarOpen = false">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>
          </button>
        </div>

        <button type="button" class="new-conversation" @click="newConversation">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
          新建对话
        </button>

        <p v-if="historyLoading" class="history-status" role="status">正在载入对话…</p>
        <p v-else-if="historyError" class="history-status error">{{ historyError }}</p>
        <nav v-else-if="conversations.length" class="conversation-list" aria-label="对话列表">
          <div v-for="conversation in conversations" :key="conversation.id" class="conversation-row">
            <button
              type="button"
              :class="['conversation-item', { active: conversation.id === activeConversationId }]"
              :aria-current="conversation.id === activeConversationId ? 'page' : undefined"
              @click="openConversation(conversation.id)"
            >
              <span>{{ conversation.title }}</span>
              <small>{{ formatConversationTime(conversation.updatedAt) }}</small>
            </button>
            <button
              type="button"
              class="delete-conversation"
              :aria-label="`删除对话：${conversation.title}`"
              @click.stop="deleteConversation(conversation)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5"/></svg>
            </button>
          </div>
        </nav>
        <div v-else class="history-empty">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v11H9l-4 3V5Z"/></svg>
          <p>还没有历史对话</p>
          <span>发送第一个问题后会自动保存。</span>
        </div>
        <p class="history-note">问题、回答与图谱依据会一起保存。</p>
      </aside>

      <div class="chat-shell">
        <main ref="messages" class="messages" role="log" aria-live="polite" aria-relevant="additions">
        <article
          v-for="message in messages"
          :key="message.id"
          :class="['message', message.role]"
        >
          <div class="avatar" aria-hidden="true">{{ message.role === 'user' ? '你' : 'AR' }}</div>
          <div class="message-body">
            <strong>{{ message.role === 'user' ? '你' : 'AgriReg AI' }}</strong>
            <p v-if="message.role === 'user'">{{ message.content }}</p>
            <p v-else>
              <template v-for="(part, partIndex) in answerParts(message)">
                <button
                  v-if="part.evidenceIndex"
                  :key="'citation-' + partIndex"
                  type="button"
                  class="citation-link"
                  :aria-label="`在图谱中查看第 ${part.evidenceIndex} 条依据`"
                  @click="openEvidenceByIndex(message, part.evidenceIndex)"
                >[{{ part.evidenceIndex }}]</button>
                <span v-else :key="'text-' + partIndex">{{ part.text }}</span>
              </template>
            </p>

            <div v-if="message.focusEntities && message.focusEntities.length" class="focus-row">
              <span>识别实体</span>
              <button
                v-for="entity in message.focusEntities"
                :key="entity"
                type="button"
                @click="openGraph(entity)"
              >{{ entity }}</button>
            </div>

            <section v-if="message.evidence && message.evidence.length" class="evidence-panel" aria-label="回答引用的图谱关系">
              <div class="evidence-title">
                <strong>图谱依据</strong>
                <span>{{ message.evidence.length }} 条依据</span>
              </div>
              <button
                v-for="fact in visibleEvidence(message)"
                :key="fact.index"
                type="button"
                class="evidence-item"
                @click="openEvidence(fact)"
              >
                <b>[{{ fact.index }}]</b>
                <span>{{ fact.sourceName }}</span>
                <em>{{ fact.factType === 'attribute' ? '属性' : relationName(fact.relation) }}</em>
                <span>{{ fact.factType === 'attribute' ? `${fact.property}：${fact.value}` : fact.targetName }}</span>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
              </button>
              <button
                v-if="message.evidence.length > 8"
                type="button"
                class="evidence-toggle"
                :aria-expanded="message.showAllEvidence ? 'true' : 'false'"
                @click="toggleEvidence(message)"
              >{{ message.showAllEvidence ? '收起图谱依据' : `查看全部 ${message.evidence.length} 条图谱依据` }}</button>
            </section>

            <div v-if="message.followUps && message.followUps.length" class="follow-ups">
              <button
                v-for="followUp in message.followUps"
                :key="followUp"
                type="button"
                @click="submitQuestion(followUp)"
              >{{ followUp }}</button>
            </div>
          </div>
        </article>

        <article v-if="loading" class="message assistant" role="status">
          <div class="avatar" aria-hidden="true">AR</div>
          <div class="message-body">
            <strong>AgriReg AI</strong>
            <div class="thinking"><i></i><i></i><i></i><span>正在检索图谱关系并组织答案…</span></div>
          </div>
        </article>
        </main>

        <section v-if="messages.length === 1 && !historyLoading" class="starter-panel">
        <p>可以这样问</p>
        <div>
          <button v-for="question in starters" :key="question" type="button" @click="submitQuestion(question)">
            {{ question }}<span aria-hidden="true">↗</span>
          </button>
        </div>
        </section>

        <form class="composer" @submit.prevent="submitQuestion()">
        <label class="sr-only" for="assistant-input">输入农药知识问题</label>
        <textarea
          id="assistant-input"
          name="assistant-question"
          v-model="input"
          rows="2"
          maxlength="300"
          autocomplete="off"
          aria-describedby="assistant-note"
          placeholder="询问农药、作物、病虫害、有效成分或作用机制…"
          @keydown.enter.exact="handleComposerEnter"
        ></textarea>
        <button type="submit" :disabled="loading || historyLoading || input.trim().length < 2" aria-label="发送问题">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 12 16-8-5 16-3-6-8-2Z"/><path d="m12 14 8-10"/></svg>
        </button>
        <small id="assistant-note">按 Enter 发送，Shift + Enter 换行。结论附带可点击的图谱依据。</small>
        </form>
      </div>
    </div>
  </section>
</template>

<script>
import service from '@/utils/axios';

const INTRO_MESSAGE = {
  id: 'intro',
  role: 'assistant',
  content: '告诉我你想了解的农药、作物或病虫害。我会先定位图谱实体，再沿关系检索并给出可追溯的回答。'
};

function freshMessages() {
  return [{ ...INTRO_MESSAGE }];
}

function visitorId() {
  const key = 'agrireg.visitorId';
  let value = localStorage.getItem(key);
  if (!value) {
    value = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID()
      : `visitor-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(key, value);
  }
  return value;
}

export default {
  name: 'AnswerView',
  data() {
    return {
      input: '',
      loading: false,
      historyLoading: false,
      historyError: '',
      sidebarOpen: false,
      visitorId: '',
      activeConversationId: '',
      conversations: [],
      lastQuery: '',
      messageSequence: 1,
      starters: [
        'Chlorantraniliprole 与哪些作物或病虫害有关？',
        '哪些农药登记可以防治 Leaf spot disease？',
        'Spring barley 关联了哪些病害和有效成分？'
      ],
      messages: freshMessages(),
      relationNames: {
        TREATS: '防治',
        INFECTS: '感染',
        APPLIED_TO: '适用于',
        INCLUDES: '包含',
        REL_TYPE: '属于',
        DETERMINES: '决定',
        RELATED_TO: '相关'
      }
    };
  },
  watch: {
    '$route.query.q'(question) {
      if (question && question !== this.lastQuery && !this.activeConversationId) this.submitQuestion(question);
    },
    '$route.query.conversation'(conversationId) {
      if (conversationId && conversationId !== this.activeConversationId) {
        this.openConversation(String(conversationId), false);
      }
    }
  },
  async mounted() {
    this.visitorId = visitorId();
    await this.loadConversations();
    const conversationId = String(this.$route.query.conversation || '');
    if (conversationId) {
      await this.openConversation(conversationId, false);
    } else if (this.$route.query.q) {
      this.submitQuestion(this.$route.query.q);
    }
  },
  methods: {
    async loadConversations() {
      this.historyLoading = true;
      this.historyError = '';
      try {
        const response = await service.get('/api/conversations', {
          params: { visitorId: this.visitorId }
        });
        this.conversations = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        this.historyError = '对话记录暂时无法载入。';
      } finally {
        this.historyLoading = false;
      }
    },
    async openConversation(conversationId, updateRoute = true) {
      if (!conversationId || this.loading) return;
      this.historyLoading = true;
      this.historyError = '';
      try {
        const response = await service.get(`/api/conversations/${encodeURIComponent(conversationId)}`, {
          params: { visitorId: this.visitorId }
        });
        const result = response.data || {};
        const storedMessages = Array.isArray(result.messages) ? result.messages : [];
        this.messages = freshMessages().concat(storedMessages.map(message => ({
          ...message,
          id: `db-${message.id}`,
          focusEntities: message.focusEntities || [],
          evidence: message.evidence || [],
          followUps: message.followUps || [],
          showAllEvidence: false
        })));
        this.activeConversationId = conversationId;
        this.lastQuery = '';
        this.sidebarOpen = false;
        if (updateRoute) {
          this.$router.push({ path: '/ask', query: { conversation: conversationId } }).catch(() => {});
        }
        this.scrollToBottom();
      } catch (error) {
        this.historyError = '这条对话不存在或已被删除。';
      } finally {
        this.historyLoading = false;
      }
    },
    newConversation() {
      this.activeConversationId = '';
      this.lastQuery = '';
      this.input = '';
      this.messages = freshMessages();
      this.sidebarOpen = false;
      this.$router.push({ path: '/ask' }).catch(() => {});
      this.$nextTick(() => {
        const input = document.getElementById('assistant-input');
        if (input) input.focus();
      });
    },
    async deleteConversation(conversation) {
      if (!window.confirm(`删除“${conversation.title}”？`)) return;
      try {
        await service.delete(`/api/conversations/${encodeURIComponent(conversation.id)}`, {
          params: { visitorId: this.visitorId }
        });
        this.conversations = this.conversations.filter(item => item.id !== conversation.id);
        if (this.activeConversationId === conversation.id) this.newConversation();
      } catch (error) {
        this.historyError = '这条对话没有删除成功。';
      }
    },
    async submitQuestion(preset) {
      const question = String(preset || this.input).trim();
      if (question.length < 2 || question.length > 300 || this.loading || this.historyLoading) return;
      this.lastQuery = question;
      this.messages.push({ id: `local-${this.messageSequence++}`, role: 'user', content: question });
      this.input = '';
      this.loading = true;
      this.scrollToBottom();

      try {
        const response = await service.post('/api/assistant/ask', {
          question,
          visitorId: this.visitorId,
          conversationId: this.activeConversationId || undefined
        });
        const result = response.data || {};
        this.activeConversationId = result.conversationId || this.activeConversationId;
        this.messages.push({
          id: `local-${this.messageSequence++}`,
          role: 'assistant',
          content: result.answer || '没有找到能够支持回答的图谱关系。',
          focusEntities: result.focusEntities || [],
          evidence: result.evidence || [],
          followUps: result.followUps || [],
          showAllEvidence: false
        });
        await this.loadConversations();
        if (this.activeConversationId) {
          this.$router.replace({
            path: '/ask',
            query: { conversation: this.activeConversationId }
          }).catch(() => {});
        }
      } catch (error) {
        const message = error.response && error.response.data && error.response.data.message
          ? error.response.data.message
          : '这次没有获得答案，请稍后再试。';
        this.messages.push({ id: `local-${this.messageSequence++}`, role: 'assistant', content: message });
      } finally {
        this.loading = false;
        this.scrollToBottom();
      }
    },
    relationName(relation) {
      return this.relationNames[relation] || relation || '相关';
    },
    visibleEvidence(message) {
      if (!message.evidence) return [];
      return message.showAllEvidence ? message.evidence : message.evidence.slice(0, 8);
    },
    toggleEvidence(message) {
      this.$set(message, 'showAllEvidence', !message.showAllEvidence);
    },
    handleComposerEnter(event) {
      if (event.isComposing) return;
      event.preventDefault();
      this.submitQuestion();
    },
    answerParts(message) {
      const content = String(message.content || '').replace(/\*\*/g, '');
      if (!message.evidence || !message.evidence.length) return [{ text: content }];
      return content.split(/(\[\d+\])/g).filter(Boolean).map(part => {
        const match = part.match(/^\[(\d+)\]$/);
        return match ? { evidenceIndex: Number(match[1]) } : { text: part };
      });
    },
    openEvidenceByIndex(message, index) {
      const fact = (message.evidence || []).find(item => Number(item.index) === Number(index));
      if (fact) this.openEvidence(fact);
    },
    openEvidence(fact) {
      if (fact.factType === 'attribute') {
        this.openGraph(fact.sourceName);
        return;
      }
      this.$router.push({
        path: '/graph',
        query: {
          q: fact.sourceName || fact.targetName,
          evidenceSourceId: fact.sourceId == null ? undefined : String(fact.sourceId),
          evidenceTargetId: fact.targetId == null ? undefined : String(fact.targetId),
          evidenceSource: fact.sourceName || '',
          evidenceTarget: fact.targetName || '',
          evidenceRelation: fact.relation || 'RELATED_TO',
          evidenceIndex: fact.index == null ? '1' : String(fact.index)
        }
      }).catch(() => {});
    },
    openGraph(keyword) {
      this.$router.push({ path: '/graph', query: { q: keyword } }).catch(() => {});
    },
    formatConversationTime(value) {
      const time = new Date(value);
      if (Number.isNaN(time.getTime())) return '';
      const now = new Date();
      if (time.toDateString() === now.toDateString()) {
        return time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      }
      return time.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    },
    scrollToBottom() {
      this.$nextTick(() => {
        if (this.$refs.messages) this.$refs.messages.scrollTop = this.$refs.messages.scrollHeight;
      });
    }
  }
};
</script>

<style scoped>
.ask-page { max-width: 1320px; margin: 0 auto; color: #172033; }
.ask-page button, .ask-page a { touch-action: manipulation; }
.ask-page button:focus-visible, .ask-page textarea:focus-visible, .ask-page a:focus-visible { outline: 3px solid rgba(79,110,247,.46); outline-offset: 2px; }
.ask-intro { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 5px 4px 24px; }
.ask-intro p { margin: 0 0 7px; color: #4f6ef7; font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.ask-intro h1 { margin: 0; font-size: clamp(27px, 3.3vw, 43px); line-height: 1.15; letter-spacing: -.04em; text-wrap: balance; }
.ask-intro span { display: block; margin-top: 10px; color: #667085; font-size: 14px; }
.ask-intro-actions { display: flex; align-items: center; gap: 8px; }
.graph-link, .history-toggle { display: inline-flex; min-height: 44px; align-items: center; gap: 6px; flex: 0 0 auto; padding: 10px 13px; border: 1px solid #d8deea; border-radius: 10px; background: #fff; color: #43506a; cursor: pointer; font-size: 12px; font-weight: 700; text-decoration: none; }
.graph-link:hover { border-color: #9cacfa; color: #3654d8; }
.graph-link svg, .history-toggle svg { width: 15px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.history-toggle { display: none; }
.chat-workspace { position: relative; display: grid; height: min(720px, calc(100vh - 190px)); min-height: 540px; grid-template-columns: 250px minmax(0,1fr); overflow: hidden; border: 1px solid #d8deea; border-radius: 20px; background: #fff; box-shadow: 0 20px 54px rgba(35,48,82,.1); }
.conversation-sidebar { display: flex; min-width: 0; min-height: 0; flex-direction: column; border-right: 1px solid #e0e5ef; background: #f7f8fb; }
.history-heading { display: flex; min-height: 67px; align-items: center; justify-content: space-between; padding: 13px 15px 10px; }
.history-heading span, .history-heading strong { display: block; }
.history-heading span { margin-bottom: 3px; color: #7a8497; font-size: 10px; font-weight: 800; letter-spacing: .08em; }
.history-heading strong { font-size: 15px; }
.mobile-close { display: none; width: 44px; height: 44px; place-items: center; border: 0; border-radius: 10px; background: transparent; color: #657087; cursor: pointer; }
.mobile-close svg, .new-conversation svg, .delete-conversation svg, .history-empty svg { fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.mobile-close svg { width: 18px; }
.new-conversation { display: flex; min-height: 44px; align-items: center; justify-content: center; gap: 8px; margin: 0 12px 12px; border: 1px solid #cfd7e6; border-radius: 10px; background: #fff; color: #3654d8; cursor: pointer; font-size: 12px; font-weight: 800; }
.new-conversation:hover { border-color: #9bacf7; background: #f2f4ff; }
.new-conversation svg { width: 16px; }
.conversation-list { min-height: 0; flex: 1; padding: 2px 8px 12px; overflow-y: auto; overscroll-behavior: contain; }
.conversation-row { display: grid; grid-template-columns: minmax(0,1fr) 44px; align-items: center; gap: 2px; margin-bottom: 3px; }
.conversation-item { min-width: 0; min-height: 54px; padding: 9px 10px; overflow: hidden; border: 0; border-radius: 10px; background: transparent; color: #39445b; cursor: pointer; text-align: left; }
.conversation-item:hover { background: #eef1f6; }
.conversation-item.active { background: #e9edff; color: #3654d8; }
.conversation-item span, .conversation-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-item span { font-size: 12px; font-weight: 700; }
.conversation-item small { margin-top: 5px; color: #8791a4; font-size: 10px; }
.delete-conversation { display: grid; width: 44px; height: 44px; place-items: center; border: 0; border-radius: 9px; background: transparent; color: #8b94a6; cursor: pointer; }
.delete-conversation:hover { background: #f6eae6; color: #a95035; }
.delete-conversation svg { width: 15px; }
.history-status { margin: 8px 14px; color: #6f7a90; font-size: 11px; line-height: 1.6; }
.history-status.error { color: #a85236; }
.history-empty { display: grid; flex: 1; align-content: center; justify-items: center; padding: 25px 18px; color: #7a8497; text-align: center; }
.history-empty svg { width: 35px; }
.history-empty p { margin: 11px 0 3px; color: #39445b; font-size: 12px; font-weight: 800; }
.history-empty span { font-size: 10px; line-height: 1.55; }
.history-note { margin: 0; padding: 12px 14px; border-top: 1px solid #e0e5ef; color: #7a8497; font-size: 10px; line-height: 1.5; }
.sidebar-backdrop { display: none; }
.chat-shell { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; background: #fff; }
.messages { flex: 1; overflow-y: auto; padding: clamp(22px, 4vw, 42px); scroll-behavior: smooth; }
.message { display: grid; grid-template-columns: 38px minmax(0,1fr); gap: 13px; max-width: 940px; margin: 0 auto 28px; }
.message.user { max-width: 760px; margin-right: 0; }
.avatar { display: grid; width: 36px; height: 36px; place-items: center; border-radius: 11px; background: #203264; color: #dbe2ff; box-shadow: 0 5px 14px rgba(32,50,100,.18); font-size: 10px; font-weight: 800; }
.user .avatar { background: #e9edff; color: #4f63bd; box-shadow: none; }
.message-body { min-width: 0; padding-top: 2px; }
.message-body > strong { display: block; margin-bottom: 7px; font-size: 12px; }
.message-body > p { margin: 0; color: #344057; font-size: 14px; line-height: 1.85; text-wrap: pretty; white-space: pre-wrap; }
.citation-link { display: inline-flex; min-width: 28px; min-height: 26px; align-items: center; justify-content: center; margin: 0 2px; padding: 0 5px; border: 1px solid #f0d99a; border-radius: 6px; background: #fff9e8; color: #8a6412; cursor: pointer; font: 700 11px/1 inherit; vertical-align: baseline; }
.citation-link:hover { border-color: #d7b657; background: #fff4cf; color: #6f4e08; }
.user .message-body > p { display: inline-block; padding: 11px 14px; border-radius: 4px 14px 14px; background: #eef1f7; color: #29354d; }
.focus-row { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 13px; }
.focus-row > span { margin-right: 2px; color: #7a8497; font-size: 11px; }
.focus-row button, .follow-ups button { min-height: 36px; padding: 7px 10px; border: 1px solid #dce2ee; border-radius: 999px; background: #fafbfe; color: #43506a; cursor: pointer; font-size: 11px; }
.focus-row button:hover, .follow-ups button:hover { border-color: #9bacf7; color: #3654d8; }
.evidence-panel { max-width: 780px; margin-top: 17px; overflow: hidden; border: 1px solid #dfe4ed; border-radius: 13px; background: #fafbfc; }
.evidence-title { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-bottom: 1px solid #e5e9f0; }
.evidence-title strong { font-size: 12px; }
.evidence-title span { color: #7a8497; font-size: 11px; font-variant-numeric: tabular-nums; }
.evidence-item { display: grid; min-height: 44px; width: 100%; grid-template-columns: 28px minmax(90px,1fr) auto minmax(90px,1fr) 16px; align-items: center; gap: 7px; padding: 9px 11px; border: 0; border-bottom: 1px solid #e8ecf2; background: transparent; color: #39445b; cursor: pointer; text-align: left; font-size: 11px; }
.evidence-item:last-child { border-bottom: 0; }
.evidence-item:hover { background: #f1f3f8; }
.evidence-item b { color: #4f6ef7; }
.evidence-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.evidence-item em { padding: 3px 6px; border-radius: 999px; background: #eef1f6; color: #68758b; font-size: 10px; font-style: normal; }
.evidence-item svg { width: 14px; fill: none; stroke: #8a94a7; stroke-width: 1.8; }
.evidence-toggle { width: 100%; min-height: 42px; border: 0; background: #f2f4f8; color: #3654d8; cursor: pointer; font-size: 11px; font-weight: 700; }
.evidence-toggle:hover { background: #e9edff; }
.follow-ups { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 14px; }
.thinking { display: flex; align-items: center; gap: 5px; color: #6f7a90; font-size: 12px; }
.thinking i { width: 6px; height: 6px; border-radius: 50%; background: #7189f6; animation: pulse 1s infinite alternate; }
.thinking i:nth-child(2) { animation-delay: .2s; }
.thinking i:nth-child(3) { animation-delay: .4s; }
.thinking span { margin-left: 5px; }
.starter-panel { padding: 0 clamp(22px,4vw,42px) 17px 91px; }
.starter-panel > p { margin: 0 0 8px; color: #7a8497; font-size: 11px; }
.starter-panel > div { display: flex; flex-wrap: wrap; gap: 7px; }
.starter-panel button { display: inline-flex; min-height: 40px; align-items: center; gap: 8px; padding: 8px 11px; border: 1px solid #dce2ee; border-radius: 9px; background: #fafbfe; color: #4b5870; cursor: pointer; font-size: 11px; }
.starter-panel button:hover { border-color: #9bacf7; color: #3654d8; }
.composer { position: relative; display: grid; grid-template-columns: minmax(0,1fr) 48px; gap: 9px; padding: 14px 18px 11px; border-top: 1px solid #e0e5ef; background: #fafbfc; }
.composer textarea { width: 100%; min-height: 52px; max-height: 130px; resize: vertical; padding: 13px 14px; border: 1px solid #d4dbe8; border-radius: 12px; outline: 0; color: #172033; background: #fff; font: 14px/1.55 inherit; }
.composer textarea:focus-visible { border-color: #91a4fb; box-shadow: 0 0 0 3px rgba(79,110,247,.1); }
.composer > button { display: grid; height: 48px; place-items: center; align-self: start; border: 0; border-radius: 12px; background: #4f6ef7; color: #fff; cursor: pointer; }
.composer > button:hover:not(:disabled) { background: #3e5de2; }
.composer > button:disabled { opacity: .45; cursor: not-allowed; }
.composer > button svg { width: 19px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.composer small { grid-column: 1 / -1; color: #7a8497; font-size: 11px; }

/* Shared AgriReg visual language with the graph workspace. */
.ask-page { max-width: 1440px; color: #171827; }
.ask-page button,
.ask-page textarea,
.ask-page a { transition: color .18s ease, border-color .18s ease, background-color .18s ease, box-shadow .18s ease; }
.ask-page button:focus-visible,
.ask-page textarea:focus-visible,
.ask-page a:focus-visible { outline-color: #7468e8; box-shadow: 0 0 0 5px rgba(116,104,232,.13); }
.ask-intro { min-height: 48px; align-items: center; padding: 0 2px 12px; }
.ask-intro p { margin-bottom: 3px; color: #7770da; font-size: 8px; letter-spacing: .2em; }
.ask-intro h1 { font-size: clamp(20px,1.65vw,27px); letter-spacing: -.04em; }
.ask-intro span { margin-top: 4px; color: #747583; font-size: 11px; }
.graph-link,
.history-toggle { min-height: 38px; border-color: rgba(72,74,104,.14); border-radius: 11px; background: rgba(255,255,255,.72); color: #666775; box-shadow: 0 7px 22px rgba(38,34,76,.05); }
.graph-link:hover { border-color: rgba(116,104,232,.32); background: #efedff; color: #5d51cb; }
.chat-workspace { height: min(780px, calc(100vh - 154px)); border-color: rgba(72,74,104,.14); border-radius: 22px; background: #fcfbf8; box-shadow: 0 28px 80px rgba(25,22,54,.14), 0 2px 10px rgba(25,22,54,.05); }
.conversation-sidebar { border-right-color: rgba(72,74,104,.12); background: #f1efeb; }
.history-heading span { color: #898793; }
.new-conversation { border-color: rgba(72,74,104,.14); border-radius: 11px; background: #fcfbf8; color: #5d51cb; }
.new-conversation:hover { border-color: rgba(116,104,232,.3); background: #eae7ff; }
.conversation-item { border-radius: 11px; color: #484955; }
.conversation-item:hover { background: #e9e6e1; }
.conversation-item.active { background: #e8e5ff; color: #594dcc; }
.conversation-item small,
.history-note,
.history-empty { color: #85838f; }
.history-note { border-top-color: rgba(72,74,104,.12); }
.chat-shell { background: #fcfbf8; }
.avatar { background: linear-gradient(145deg,#2a2858,#171832); color: #ddd8ff; box-shadow: 0 7px 18px rgba(46,39,105,.2); }
.user .avatar { background: #e8e5ff; color: #5d51cb; }
.message-body > p { color: #383946; }
.user .message-body > p { background: #eeece8; color: #333440; }
.focus-row button,
.follow-ups button,
.starter-panel button { border-color: rgba(72,74,104,.14); background: #f8f6f2; color: #5f606c; }
.focus-row button:hover,
.follow-ups button:hover,
.starter-panel button:hover { border-color: rgba(116,104,232,.32); background: #efedff; color: #5d51cb; }
.evidence-panel { border-color: rgba(72,74,104,.13); border-radius: 14px; background: #f7f5f1; }
.evidence-title,
.evidence-item { border-color: rgba(72,74,104,.11); }
.evidence-item { color: #474854; }
.evidence-item:hover { background: #eeece8; }
.evidence-item b { color: #6659d7; }
.evidence-item em { background: #e9e6e1; color: #6c6d78; }
.evidence-toggle { background: #ece9e4; color: #5d51cb; }
.evidence-toggle:hover { background: #e6e2ff; }
.thinking i { background: #8478ed; }
.composer { border-top-color: rgba(72,74,104,.12); background: #f3f1ed; }
.composer textarea { border-color: rgba(72,74,104,.17); border-radius: 14px; background: #fdfcf9; color: #242532; }
.composer textarea:focus-visible { border-color: rgba(116,104,232,.65); box-shadow: 0 0 0 4px rgba(116,104,232,.1); }
.composer > button { border-radius: 14px; background: linear-gradient(135deg,#7668eb,#6456d9); box-shadow: 0 8px 20px rgba(91,75,199,.22); }
.composer > button:hover:not(:disabled) { background: linear-gradient(135deg,#695bdd,#5548c3); }

/* Match the AgriReg evidence-network landing and graph workspace. */
.ask-page { color: #edf7f1; }
.ask-page button:focus-visible,
.ask-page textarea:focus-visible,
.ask-page a:focus-visible { outline-color: #a4ffcb; box-shadow: 0 0 0 5px rgba(164,255,203,.1); }
.ask-intro p { color: #a4ffcb; }
.ask-intro h1 { color: #edf7f1; }
.ask-intro span { color: #91a79c; }
.graph-link,
.history-toggle { border-color: rgba(181,231,203,.14); background: rgba(12,25,20,.88); color: #a9bdb2; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
.graph-link:hover { border-color: rgba(164,255,203,.3); background: rgba(164,255,203,.08); color: #a4ffcb; }
.chat-workspace { border-color: rgba(181,231,203,.16); background: #0c1914; box-shadow: 0 28px 80px rgba(0,0,0,.3), 0 2px 10px rgba(0,0,0,.16); }
.conversation-sidebar { border-right-color: rgba(181,231,203,.12); background: #0a1612; }
.history-heading span { color: #71877c; }
.history-heading strong { color: #dbeae1; }
.new-conversation { border-color: rgba(181,231,203,.14); background: #10231b; color: #a4ffcb; }
.new-conversation:hover { border-color: rgba(164,255,203,.32); background: rgba(164,255,203,.09); }
.conversation-item { color: #a9bdb2; }
.conversation-item:hover { background: rgba(164,255,203,.05); }
.conversation-item.active { background: rgba(164,255,203,.11); color: #a4ffcb; }
.conversation-item small,
.history-note,
.history-empty,
.history-status { color: #71877c; }
.history-note { border-top-color: rgba(181,231,203,.12); }
.history-empty p { color: #dbeae1; }
.delete-conversation { color: #71877c; }
.delete-conversation:hover { background: rgba(255,178,123,.08); color: #ffb27b; }
.chat-shell { background: #0c1914; }
.messages { background: radial-gradient(circle at 72% 8%, rgba(72,196,128,.055), transparent 24rem); }
.avatar { background: #a4ffcb; color: #07110e; box-shadow: 0 7px 18px rgba(164,255,203,.12); }
.user .avatar { background: rgba(123,229,255,.12); color: #7be5ff; }
.message-body > strong { color: #edf7f1; }
.message-body > p { color: #c2d3c9; }
.user .message-body > p { border: 1px solid rgba(181,231,203,.1); background: #10231b; color: #d8e9df; }
.focus-row > span,
.starter-panel > p,
.thinking { color: #71877c; }
.focus-row button,
.follow-ups button,
.starter-panel button { border-color: rgba(181,231,203,.13); background: #10231b; color: #91a79c; }
.focus-row button:hover,
.follow-ups button:hover,
.starter-panel button:hover { border-color: rgba(164,255,203,.3); background: rgba(164,255,203,.08); color: #a4ffcb; }
.evidence-panel { border-color: rgba(181,231,203,.14); background: #0a1612; }
.evidence-title,
.evidence-item { border-color: rgba(181,231,203,.1); }
.evidence-title strong { color: #dbeae1; }
.evidence-title span { color: #71877c; }
.evidence-item { color: #a9bdb2; }
.evidence-item:hover { background: rgba(164,255,203,.05); }
.evidence-item b { color: #a4ffcb; }
.evidence-item em { background: #152a21; color: #81978c; }
.evidence-item svg { stroke: #71877c; }
.evidence-toggle { background: #10231b; color: #a4ffcb; }
.evidence-toggle:hover { background: rgba(164,255,203,.08); }
.citation-link { border-color: rgba(255,211,108,.25); background: rgba(255,211,108,.08); color: #ffd36c; }
.citation-link:hover { border-color: rgba(255,211,108,.5); background: rgba(255,211,108,.13); color: #ffe4a1; }
.thinking i { background: #a4ffcb; }
.composer { border-top-color: rgba(181,231,203,.12); background: #0a1612; }
.composer textarea { border-color: rgba(181,231,203,.16); background: #10231b; color: #edf7f1; }
.composer textarea::placeholder { color: #61776c; }
.composer textarea:focus-visible { border-color: rgba(164,255,203,.65); box-shadow: 0 0 0 4px rgba(164,255,203,.09); }
.composer > button { background: #a4ffcb; color: #07110e; box-shadow: 0 8px 20px rgba(164,255,203,.1); }
.composer > button:hover:not(:disabled) { background: #d3ffe5; }
.composer small { color: #71877c; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
@keyframes pulse { to { opacity: .25; transform: translateY(-2px); } }
@media (max-width: 680px) {
  .ask-intro { align-items: flex-start; flex-direction: column; gap: 12px; padding: 4px 4px 16px; }
  .ask-intro-actions { width: 100%; justify-content: flex-end; }
  .ask-intro > div:first-child > span, .graph-link { display: none; }
  .history-toggle { display: inline-flex; }
  .chat-workspace { display: block; height: calc(100vh - 150px); min-height: 480px; border-radius: 15px; }
  .conversation-sidebar { position: absolute; z-index: 7; inset: 0 auto 0 0; width: min(86vw, 310px); transform: translateX(-102%); border-right: 1px solid rgba(181,231,203,.14); box-shadow: 18px 0 44px rgba(0,0,0,.28); transition: transform .2s ease; }
  .sidebar-open .conversation-sidebar { transform: translateX(0); }
  .sidebar-backdrop { position: absolute; z-index: 6; inset: 0; display: block; width: 100%; height: 100%; border: 0; background: rgba(11,22,48,.34); cursor: pointer; }
  .composer textarea { font-size: 16px; }
  .mobile-close { display: grid; }
  .chat-shell { height: 100%; }
  .messages { padding: 19px 14px; }
  .message { grid-template-columns: 32px minmax(0,1fr); gap: 9px; }
  .avatar { width: 31px; height: 31px; }
  .starter-panel { padding: 0 14px 12px; }
  .evidence-item { grid-template-columns: 24px minmax(70px,1fr) auto minmax(70px,1fr); }
  .evidence-item svg { display: none; }
  .composer { padding-inline: 11px; }
}
@media (prefers-reduced-motion: reduce) { .messages { scroll-behavior: auto; } .thinking i { animation: none; } .conversation-sidebar { transition: none; } }
</style>
