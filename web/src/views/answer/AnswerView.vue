<template>
  <section class="ask-page">
    <header class="view-heading">
      <div>
        <h1>AI 问答</h1>
        <p>用自然语言查登记、作物和病虫害，点击回答中的引用核对依据。</p>
      </div>
      <router-link to="/graph" class="ui-button">打开知识图谱 <UiIcon name="arrow" /></router-link>
    </header>

    <div class="chat-workspace">
      <div class="chat-shell" :class="{ 'has-messages': messages.length || restoring }">
        <div v-if="restoring" class="restore-state" role="status">
          <span class="ui-skeleton" aria-hidden="true"></span> 正在打开对话…
        </div>

        <section v-else-if="!messages.length" class="ask-start" aria-labelledby="ask-start-title">
          <span class="ask-mark" aria-hidden="true"><UiIcon name="chat" /></span>
          <h2 id="ask-start-title">你想查哪条登记线索？</h2>
          <p>输入登记号或实体名称，可以让检索更准确。</p>
        </section>

        <div v-else ref="messages" class="messages" role="log" aria-label="问答消息" aria-relevant="additions">
          <article v-for="message in messages" :key="message.id" :id="'answer-' + message.id" class="message" :class="message.role">
            <div class="avatar" aria-hidden="true">{{ message.role === 'user' ? '你' : 'AR' }}</div>
            <div class="message-body">
              <strong class="message-author">{{ message.role === 'user' ? '你' : 'AgriReg AI' }}</strong>
              <div v-if="message.retryQuestion" class="ui-error" role="alert">
                <p>{{ message.content }}</p>
                <button v-if="message === messages[messages.length - 1]" type="button" class="ui-button"
                  :disabled="loading" @click="submitQuestion(message.retryQuestion, message.id)">重新发送</button>
              </div>
              <p v-else-if="message.role === 'user'" class="message-text">{{ message.content }}</p>
              <p v-else class="message-text">
                <template v-for="(part, partIndex) in answerParts(message)">
                  <a v-if="part.fact && isSourceLink(part.fact.sourceUrl)" :key="'source-' + partIndex"
                    class="citation-link" :href="part.fact.sourceUrl" target="_blank" rel="noopener noreferrer"
                    :aria-label="'查看来源 ' + (part.fact.sourceTitle || part.fact.index)">[{{ part.fact.index }}]</a>
                  <router-link v-else-if="part.fact" :key="'citation-' + partIndex" :to="evidenceLocation(part.fact)"
                    class="citation-link" :aria-label="'在图谱中查看第 ' + part.fact.index + ' 条依据'">[{{ part.fact.index }}]</router-link>
                  <span v-else :key="'text-' + partIndex">{{ part.text }}</span>
                </template>
              </p>

              <div v-if="message.focusEntities && message.focusEntities.length" class="focus-row">
                <span>识别实体</span>
                <router-link v-for="entity in message.focusEntities" :key="entity" :to="graphLocation(entity)">{{ entity }}</router-link>
              </div>

              <section v-if="message.evidence && message.evidence.length" class="evidence-panel"
                :aria-labelledby="'answer-evidence-title-' + message.id">
                <div class="evidence-title">
                  <h2 :id="'answer-evidence-title-' + message.id">图谱依据</h2>
                  <span>{{ message.evidence.length }} 条</span>
                </div>
                <ol :id="'answer-evidence-' + message.id">
                  <li v-for="fact in visibleEvidence(message)" :key="fact.index">
                    <router-link class="evidence-item" :to="evidenceLocation(fact)">
                      <b>[{{ fact.index }}]</b>
                      <span class="fact-summary">
                        <strong>{{ fact.sourceName || fact.targetName }}</strong>
                        <em>{{ fact.sourceTitle || (fact.factType === 'attribute' ? '属性' : relationName(fact.relation)) }}</em>
                        <span>{{ fact.factType === 'attribute' ? fact.property + '：' + fact.value : fact.targetName }}</span>
                      </span>
                      <UiIcon name="arrow" />
                    </router-link>
                  </li>
                </ol>
                <button v-if="message.evidence.length > 8" type="button" class="ui-link text-button evidence-toggle"
                  :aria-expanded="String(Boolean(message.showAllEvidence))" :aria-controls="'answer-evidence-' + message.id"
                  @click="message.showAllEvidence = !message.showAllEvidence">
                  {{ message.showAllEvidence ? '收起其余依据' : '查看全部 ' + message.evidence.length + ' 条依据' }}
                </button>
              </section>

              <section v-if="message.followUps && message.followUps.length" class="follow-ups"
                :aria-labelledby="'follow-ups-' + message.id">
                <h2 :id="'follow-ups-' + message.id">继续追问</h2>
                <button v-for="followUp in message.followUps" :key="followUp" class="ui-button" type="button"
                  :disabled="loading || restoring" @click="submitQuestion(followUp)">{{ followUp }}</button>
              </section>
            </div>
          </article>

          <div v-if="loading" class="thinking" role="status">
            <span class="ui-skeleton" aria-hidden="true"></span>
            正在检索关系并组织答案…
          </div>
        </div>

        <form class="composer" @submit.prevent="submitQuestion()">
          <label class="sr-only" for="assistant-input">输入农药知识问题</label>
          <textarea id="assistant-input" ref="question" name="assistant-question" v-model="input" rows="2"
            required minlength="2" maxlength="300" class="ui-input" aria-describedby="assistant-note"
            placeholder="例如，哪些登记产品关联了小麦叶斑病？" @keydown.enter.exact="handleComposerEnter"></textarea>
          <button class="ui-button primary" type="submit" :disabled="loading || restoring">
            <UiIcon name="send" /> {{ loading ? '回答中…' : '发送问题' }}
          </button>
          <small id="assistant-note">至少输入 2 个字。Enter 发送，Shift + Enter 换行。</small>
        </form>

        <section v-if="!messages.length && !restoring" class="starter-panel" aria-labelledby="ask-examples-title">
          <h2 id="ask-examples-title">可以这样问</h2>
          <div>
            <button v-for="question in starters" :key="question" type="button" @click="submitQuestion(question)">
              <UiIcon name="chat" /> <span>{{ question }}</span> <UiIcon name="arrow" />
            </button>
          </div>
        </section>
      </div>
      <aside class="conversation-sidebar" aria-labelledby="history-title">
        <div class="history-heading">
          <h2 id="history-title">最近对话</h2>
          <button class="ui-button history-toggle" type="button" aria-controls="recent-conversations"
            :aria-expanded="String(historyExpanded)" @click="historyExpanded = !historyExpanded">
            {{ historyExpanded ? '收起' : '查看记录' }} <UiIcon name="chevron" />
          </button>
          <button class="ui-button sidebar-new" type="button" :disabled="loading || restoring" @click="newConversation">
            <UiIcon name="plus" /> 新建对话
          </button>
        </div>
        <div id="recent-conversations" class="conversation-history" :class="{ expanded: historyExpanded }">
          <p v-if="historyLoading" class="history-status" role="status">正在载入对话…</p>
          <div v-if="historyError" class="history-status">
            <p role="alert">{{ historyError }}</p>
            <button type="button" class="ui-link text-button" @click="loadConversations">刷新对话列表</button>
          </div>
          <ul v-if="conversations.length" class="conversation-list">
            <li v-for="conversation in conversations" :key="conversation.id" class="conversation-row"
              :class="{ active: String(conversation.id) === String(activeConversationId) }">
              <button type="button" class="conversation-item"
                :aria-current="String(conversation.id) === String(activeConversationId) ? 'true' : undefined"
                :disabled="loading || restoring" @click="openConversation(conversation.id)">
                <span>{{ conversation.title }}</span>
                <small>{{ formatConversationTime(conversation.updatedAt) }}</small>
              </button>
              <button type="button" class="delete-conversation" :disabled="loading || restoring"
                :aria-label="'删除对话：' + conversation.title" @click="deleteConversation(conversation)">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5"/></svg>
              </button>
            </li>
          </ul>
          <p v-else-if="!historyLoading && !historyError" class="history-status">提问后，问题、回答和依据会保存在这里。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script>
import service from '@/utils/axios';
import UiIcon from '@/components/UiIcon.vue';
import { citationParts, isSourceLink } from '@/utils/citations';

function visitorId() {
  const key = 'agrireg.visitorId';
  let value = localStorage.getItem(key);
  if (!value) {
    value = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID()
      : 'visitor-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    localStorage.setItem(key, value);
  }
  return value;
}

export default {
  name: 'AnswerView',
  components: { UiIcon },
  data() {
    return {
      input: '',
      loading: false,
      historyLoading: false,
      historyVersion: 0,
      restoring: false,
      historyError: '',
      historyExpanded: false,
      visitorId: '',
      activeConversationId: '',
      conversations: [],
      lastQuery: '',
      messageSequence: 1,
      messages: [],
      starters: [
        'Chlorantraniliprole 与哪些作物或病虫害有关？',
        '哪些农药登记可以防治 Leaf spot disease？',
        'Spring barley 关联了哪些病害和有效成分？'
      ],
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
      if (conversationId && String(conversationId) !== String(this.activeConversationId)) {
        this.openConversation(String(conversationId), false);
      }
    }
  },
  mounted() {
    document.title = 'AI 问答 · AgriReg AI';
    this.visitorId = visitorId();
    this.loadConversations();
    const conversationId = String(this.$route.query.conversation || '');
    if (conversationId) this.openConversation(conversationId, false);
    else if (this.$route.query.q) this.submitQuestion(this.$route.query.q);
  },
  methods: {
    async loadConversations() {
      const version = ++this.historyVersion;
      this.historyLoading = true;
      this.historyError = '';
      try {
        const response = await service.get('/api/conversations', {
          params: { visitorId: this.visitorId },
          timeout: 8000
        });
        if (version === this.historyVersion) this.conversations = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        if (version !== this.historyVersion) return;
        this.historyError = '对话记录暂时无法载入。';
        this.historyExpanded = true;
      } finally {
        if (version === this.historyVersion) this.historyLoading = false;
      }
    },
    async openConversation(conversationId, updateRoute = true) {
      if (!conversationId || this.loading || this.restoring) return;
      this.restoring = true;
      this.historyError = '';
      try {
        const response = await service.get('/api/conversations/' + encodeURIComponent(conversationId), {
          params: { visitorId: this.visitorId },
          timeout: 10000
        });
        const stored = Array.isArray(response.data?.messages) ? response.data.messages : [];
        this.messages = stored.map(message => ({
          ...message,
          id: 'db-' + message.id,
          focusEntities: message.focusEntities || [],
          evidence: message.evidence || [],
          followUps: message.followUps || [],
          showAllEvidence: false
        }));
        this.activeConversationId = conversationId;
        this.lastQuery = '';
        this.input = '';
        this.historyExpanded = false;
        if (updateRoute) {
          this.$router.push({ path: '/ask', query: { conversation: conversationId } }).catch(() => {});
          this.$nextTick(() => this.$refs.question?.focus({ preventScroll: true }));
        }
      } catch (error) {
        this.historyError = error.response?.status === 404
          ? '这条对话不存在或已被删除。'
          : '暂时无法打开这条对话，请重试。';
        this.historyExpanded = true;
      } finally {
        this.restoring = false;
        this.revealMessage(this.messages[this.messages.length - 1]?.id);
      }
    },
    newConversation() {
      this.activeConversationId = '';
      this.lastQuery = '';
      this.input = '';
      this.messages = [];
      this.historyExpanded = false;
      this.$router.push({ path: '/ask' }).catch(() => {});
      this.$nextTick(() => this.$refs.question?.focus());
    },
    async deleteConversation(conversation) {
      if (!window.confirm('删除“' + conversation.title + '”？')) return;
      try {
        await service.delete('/api/conversations/' + encodeURIComponent(conversation.id), {
          params: { visitorId: this.visitorId }
        });
        this.conversations = this.conversations.filter(item => item.id !== conversation.id);
        if (String(this.activeConversationId) === String(conversation.id)) this.newConversation();
      } catch (error) {
        this.historyError = '这条对话没有删除成功，请重试。';
      }
    },
    async submitQuestion(preset, retryMessageId) {
      const question = String(preset || this.input).trim();
      if (this.loading || this.restoring) return;
      if (question.length < 2 || question.length > 300) {
        if (!preset) {
          const input = this.$refs.question;
          input.setCustomValidity('请输入 2 至 300 个字。');
          input.reportValidity();
          input.setCustomValidity('');
        }
        return;
      }
      this.lastQuery = question;
      if (retryMessageId) {
        this.messages = this.messages.filter(message => message.id !== retryMessageId);
      } else {
        const id = 'local-' + this.messageSequence++;
        this.messages.push({ id, role: 'user', content: question });
        this.input = '';
      }
      this.loading = true;
      this.$nextTick(() => {
        const messages = this.$refs.messages;
        if (messages) messages.scrollTop = messages.scrollHeight;
      });

      const id = 'local-' + this.messageSequence++;
      try {
        const response = await service.post('/api/assistant/ask', {
          question,
          visitorId: this.visitorId,
          conversationId: this.activeConversationId || undefined
        });
        const result = response.data || {};
        this.activeConversationId = result.conversationId || this.activeConversationId;
        this.messages.push({
          id,
          role: 'assistant',
          content: result.answer || '没有找到能够支持回答的图谱关系。',
          focusEntities: result.focusEntities || [],
          evidence: result.evidence || [],
          followUps: result.followUps || [],
          showAllEvidence: false
        });
        this.loadConversations();
        if (this.activeConversationId) {
          this.$router.replace({ path: '/ask', query: { conversation: this.activeConversationId } }).catch(() => {});
        }
      } catch (error) {
        const content = error.response?.data?.message || '问答服务暂时没有返回结果，请重试。';
        this.messages.push({ id, role: 'assistant', content, retryQuestion: question });
      } finally {
        this.loading = false;
        this.revealMessage(id);
      }
    },
    relationName(relation) {
      return this.relationNames[relation] || relation || '相关';
    },
    visibleEvidence(message) {
      return message.showAllEvidence ? message.evidence : message.evidence.slice(0, 8);
    },
    handleComposerEnter(event) {
      if (event.isComposing || event.keyCode === 229) return;
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    },
    answerParts(message) {
      return citationParts(message.content, message.evidence);
    },
    isSourceLink,
    evidenceLocation(fact) {
      const location = this.graphLocation(fact.sourceName || fact.targetName);
      if (fact.factType === 'attribute') return location;
      return {
        ...location,
        query: {
          ...location.query,
          evidenceSourceId: fact.sourceId == null ? undefined : String(fact.sourceId),
          evidenceTargetId: fact.targetId == null ? undefined : String(fact.targetId),
          evidenceSource: fact.sourceName || '',
          evidenceTarget: fact.targetName || '',
          evidenceRelation: fact.relation || 'RELATED_TO',
          evidenceIndex: fact.index == null ? '1' : String(fact.index)
        }
      };
    },
    graphLocation(keyword) {
      return { path: '/graph', query: { q: keyword } };
    },
    formatConversationTime(value) {
      const time = new Date(value);
      if (Number.isNaN(time.getTime())) return '';
      if (time.toDateString() === new Date().toDateString()) {
        return time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      }
      return time.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    },
    revealMessage(id) {
      if (!id) return;
      this.$nextTick(() => {
        const messages = this.$refs.messages;
        const message = document.getElementById('answer-' + id);
        if (!messages || !message) return;
        if (messages.scrollHeight > messages.clientHeight) {
          const previous = message.previousElementSibling;
          const context = previous?.classList.contains('user') && previous.offsetHeight < 140 ? previous : message;
          messages.scrollTop += context.getBoundingClientRect().top - messages.getBoundingClientRect().top - 12;
        } else if (message.getBoundingClientRect().top >= window.innerHeight) {
          message.scrollIntoView({ block: 'start' });
        }
      });
    }
  }
};
</script>

<style scoped>
.chat-workspace { display: grid; grid-template-columns: 224px minmax(0, 1fr); align-items: start; gap: 16px; }
.chat-shell { grid-area: 1 / 2; }
.conversation-sidebar { grid-area: 1 / 1; }
.conversation-sidebar, .chat-shell { min-width: 0; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
.history-heading { display: grid; gap: 11px; padding: 14px; border-bottom: 1px solid var(--line); }
.history-heading h2 { font-size: 16px; }
.history-toggle { display: none; }
.sidebar-new { justify-content: flex-start; color: var(--accent); }
.history-status { display: grid; gap: 4px; padding: 14px; color: var(--muted); font-size: 13px; }
.history-status [role="alert"] { color: var(--danger); }
.conversation-list { display: grid; gap: 4px; margin: 0; padding: 7px; list-style: none; }
.conversation-row { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) auto; align-items: center; border-radius: var(--control-radius); }
.conversation-row.active, .conversation-row:hover { background: var(--wash); }
.conversation-item { min-width: 0; padding: 7px 2px 7px 7px; border: 0; background: transparent; text-align: left; }
.conversation-item span, .conversation-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-item span { font-size: 13px; font-weight: 650; }
.conversation-item small { color: var(--muted); font-size: 12px; }
.delete-conversation { display: grid; min-width: 36px; min-height: 40px; place-items: center; padding: 2px; border: 0; border-radius: 5px; background: transparent; color: var(--muted); }
.delete-conversation:hover { background: var(--danger-bg); color: var(--danger); }
.delete-conversation svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linejoin: round; }

.ask-start, .starter-panel, .composer { width: min(100% - 40px, 770px); margin-inline: auto; }
.ask-start { display: grid; justify-items: start; gap: 9px; margin-block: clamp(28px, 5vw, 68px) 19px; }
.ask-mark { display: grid; width: 44px; height: 44px; place-items: center; margin-bottom: 3px; border-radius: var(--control-radius); background: var(--tint); color: var(--accent); }
.ask-mark .ui-icon { width: 24px; height: 24px; }
.ask-start h2 { font-size: 1.65rem; }
.ask-start p { color: var(--muted); }
.composer { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 7px 10px; margin-bottom: 15px; }
.composer textarea { min-height: 70px; }
.composer .ui-button { min-width: 108px; }
.composer small { grid-column: 1 / -1; color: var(--muted); font-size: 12px; }
.starter-panel { margin-block: 18px clamp(26px, 4vw, 52px); }
.starter-panel h2, .follow-ups h2 { margin-bottom: 6px; font-size: 14px; }
.starter-panel button {
  display: grid;
  width: 100%;
  min-height: 47px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 7px 4px 7px 0;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: var(--accent);
  font-size: 14px;
  text-align: left;
  overflow-wrap: anywhere;
}
.starter-panel button:hover { background: var(--wash); }
.starter-panel .ui-icon { width: 16px; height: 16px; }

.messages { position: relative; max-height: min(56vh, 640px); min-height: min(38vh, 300px); padding: 20px max(20px, calc((100% - 820px) / 2)); overflow-y: auto; }
.has-messages .composer { width: auto; margin: 0; padding: 14px max(20px, calc((100% - 820px) / 2)); border-top: 1px solid var(--line); }
.restore-state, .thinking { display: grid; gap: 9px; padding: 18px 20px; color: var(--muted); font-size: 14px; }
.message { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: start; margin-block: 0 22px; scroll-margin-top: 6px; }
.message:last-child { margin-bottom: 4px; }
.avatar { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 6px; background: var(--tint); color: var(--accent); font-size: 12px; font-weight: 750; }
.user .avatar { background: var(--wash); }
.message-body { max-width: 74ch; min-width: 0; overflow-wrap: anywhere; }
.message-author { display: block; margin-block: 3px 5px; font-size: 14px; }
.message-text { font-size: 16px; line-height: 1.7; white-space: pre-line; }
.user .message-text { display: inline-block; padding: 6px 11px; border-radius: var(--control-radius); background: var(--wash); }
.citation-link { display: inline-flex; align-items: center; min-height: 26px; margin-inline: 3px; padding-inline: 4px; border-radius: 4px; background: var(--tint); color: var(--accent); font: 700 .82em/1.25 var(--mono); text-decoration: underline; text-underline-offset: 2px; vertical-align: baseline; }
.citation-link:hover { background: #d6e1c8; }
.focus-row { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 8px; margin-top: 10px; font-size: 13px; }
.focus-row > span, .evidence-title span { color: var(--muted); }
.focus-row a { color: var(--accent); font-weight: 650; text-decoration: underline; text-underline-offset: 2px; }
.evidence-panel { margin-top: 16px; border-block: 1px solid var(--line); }
.evidence-title { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 8px 9px; background: var(--wash); font-size: 12px; }
.evidence-title h2 { font-size: 15px; }
.evidence-panel ol { margin: 0; padding: 0; list-style: none; }
.evidence-panel li + li { border-top: 1px solid var(--line); }
.evidence-item { display: grid; min-height: 44px; grid-template-columns: auto minmax(0, 1fr) auto; align-items: start; gap: 9px; padding: 10px 9px; font-size: 14px; }
.evidence-item:hover { background: var(--wash); }
.evidence-item b { color: var(--accent); font: 700 13px/1.6 var(--mono); }
.evidence-item .ui-icon { width: 16px; height: 16px; color: var(--accent); }
.fact-summary em { display: inline-block; margin-inline: 5px; color: var(--muted); font-size: 12px; font-style: normal; }
.fact-summary strong { font-weight: 650; }
.evidence-toggle { margin-left: 9px; }
.text-button { width: fit-content; min-height: 36px; padding: 4px 0; border: 0; background: transparent; font-size: 13px; }
.follow-ups { margin-top: 15px; }
.follow-ups button { min-height: 38px; justify-content: start; margin: 0 6px 5px 0; text-align: left; font-size: 13px; }
.ui-error .ui-button { margin-top: 8px; }

@media (max-width: 850px) {
  .chat-workspace { grid-template-columns: minmax(0, 1fr); gap: 11px; }
  .chat-shell, .conversation-sidebar { grid-area: auto; }
  .history-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 9px; padding: 8px 11px; border: 0; }
  .history-heading h2 { margin-right: auto; }
  .history-toggle { display: inline-flex; }
  .sidebar-new { order: 1; }
  .conversation-history:not(.expanded) { display: none; }
  .conversation-history { border-top: 1px solid var(--line); }
  .messages { max-height: none; min-height: 0; }
  .delete-conversation { min-width: 44px; min-height: 44px; }
}
@media (max-width: 540px) {
  .ask-start, .starter-panel, .composer { width: calc(100% - 26px); }
  .ask-start { margin-top: 23px; }
  .ask-start h2 { font-size: 1.32rem; }
  .composer { grid-template-columns: minmax(0, 1fr); }
  .composer .ui-button { justify-self: end; }
  .composer small { grid-row: 2; }
  .messages, .has-messages .composer { padding-inline: 12px; }
  .message { gap: 7px; }
  .avatar { width: 27px; height: 27px; }
}
</style>
