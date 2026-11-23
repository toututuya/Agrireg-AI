<template>
  <figure class="relation-path">
    <figcaption class="path-heading">
      <h4>{{ path.taskId ? '第 ' + path.taskId + ' 项关系图谱' : '关系图谱' }}</h4>
      <router-link :to="graphLocation" class="ui-link">
        在图谱中复查 <UiIcon name="arrow" />
      </router-link>
    </figcaption>
    <div class="path-viewport" tabindex="0" role="region" aria-label="关系路径，可横向滚动查看">
      <ol class="path-chain" role="list">
        <li v-for="(node, index) in path.nodes" :key="node.id" class="path-part">
          <div class="path-node" :class="{ endpoint: index === 0 || index === path.nodes.length - 1 }">
            <span class="node-kind">{{ nodeTypes[node.label] || '图谱实体' }}</span>
            <strong>{{ node.name }}</strong>
          </div>
          <button v-if="path.links[index]" type="button" class="path-edge"
            :aria-label="edgeTitle(index)" :title="edgeTitle(index)"
            @click="$emit('inspect-evidence', path.links[index].evidenceIndex)">
            <span>{{ path.links[index].label }} <b>[{{ path.links[index].evidenceIndex }}]</b></span>
          </button>
        </li>
      </ol>
    </div>
  </figure>
</template>

<script>
import UiIcon from '@/components/UiIcon.vue';

const NODE_TYPES = {
  RegisterNumber: '农药登记',
  Crop: '作物',
  Disease: '病虫害',
  ActiveSubstance: '有效成分',
  ChemicalClasses: '化学类别',
  PesticideCategory: '农药类型',
  TargetSite: '作用靶点',
  ModeOfAction: '作用方式'
};

export default {
  name: 'AgentRelationPath',
  components: { UiIcon },
  props: {
    path: { type: Object, required: true },
    evidence: { type: Array, required: true }
  },
  data() {
    return { nodeTypes: NODE_TYPES };
  },
  computed: {
    graphLocation() {
      return { name: 'graph', query: { pathStart: this.path.source, pathEnd: this.path.target } };
    }
  },
  methods: {
    edgeTitle(index) {
      const link = this.path.links[index];
      const fact = this.evidence.find(item => item.index === link.evidenceIndex);
      const description = fact?.summary || (this.path.nodes[index].name + '与' + this.path.nodes[index + 1].name + '的' + link.label);
      return '查看第 ' + link.evidenceIndex + ' 条依据。' + description;
    }
  }
};
</script>

<style scoped>
.relation-path { margin-block: 0 15px; border: 1px solid var(--line); border-radius: var(--radius); }
.path-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 4px 10px; padding: 6px 11px 6px 13px; }
.path-heading h4 { font-size: 14px; text-wrap: balance; }
.path-heading .ui-link { display: inline-flex; align-items: center; gap: 3px; min-height: 34px; font-size: 12px; }
.path-heading .ui-icon { width: 14px; height: 14px; }
.path-viewport { margin: 0 5px 5px; padding: 16px 13px; border-radius: var(--control-radius); background: var(--canvas); overflow-x: auto; }
.path-chain, .path-part { display: flex; align-items: center; }
.path-chain { width: max-content; min-width: 100%; justify-content: center; margin: 0; padding: 0; list-style: none; }
.path-node { display: grid; align-content: center; gap: 3px; width: max-content; min-width: 96px; max-width: 156px; min-height: 60px; padding: 8px 10px; border: 1px solid var(--field-line); border-radius: var(--control-radius); background: var(--surface); }
.path-node.endpoint { border-color: var(--accent); }
.node-kind { color: var(--muted); font-size: 11px; }
.path-node strong { font-size: 13px; line-height: 1.35; overflow-wrap: anywhere; }
.path-edge { position: relative; min-width: 85px; min-height: 44px; padding: 0 4px; border: 0; border-radius: 4px; background: transparent; color: var(--accent); font-size: 11px; white-space: nowrap; }
.path-edge::before { position: absolute; inset: 50% 0 auto; height: 1px; background: var(--field-line); content: ''; }
.path-edge span { position: relative; padding: 2px 3px; border-radius: 3px; background: var(--canvas); }
.path-edge b { font-family: var(--mono); }
.path-edge:hover span, .path-edge:focus-visible span { background: var(--tint); text-decoration: underline; }
@media (max-width: 560px) {
  .path-viewport { padding: 11px; }
  .path-chain, .path-part { flex-direction: column; }
  .path-chain { width: 100%; }
  .path-node { max-width: 100%; text-align: center; }
  .path-edge::before { inset: 0 auto 0 50%; width: 1px; height: auto; }
}
</style>
