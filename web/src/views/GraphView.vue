<template>
  <section class="graph-page">
    <header class="page-intro">
      <div>
        <p><i aria-hidden="true"></i> AGRIREG GRAPH EXPLORER</p>
        <div class="intro-title">
          <h1>全球农药关联图谱</h1>
          <span>从任意实体出发，穿透登记、作物、病虫害、有效成分与作用机制。</span>
        </div>
      </div>
      <div class="mode-switch" aria-label="图谱查询模式">
        <button
          type="button"
          :class="{ active: mode === 'entity' }"
          :aria-pressed="mode === 'entity' ? 'true' : 'false'"
          @click="switchMode('entity')"
        >实体探索</button>
        <button
          type="button"
          :class="{ active: mode === 'path' }"
          :aria-pressed="mode === 'path' ? 'true' : 'false'"
          @click="switchMode('path')"
        >关系穿透</button>
        <button
          type="button"
          :class="{ active: mode === 'compare' }"
          :aria-pressed="mode === 'compare' ? 'true' : 'false'"
          @click="switchMode('compare')"
        >产品对比</button>
      </div>
    </header>

    <section class="query-dock" aria-label="图谱查询">
    <form v-if="mode === 'entity'" class="search-bar" @submit.prevent="searchGraph">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
      <label class="sr-only" for="graph-keyword">搜索知识图谱实体</label>
      <input
        id="graph-keyword"
        name="graph-keyword"
        type="search"
        v-model.trim="keyword"
        maxlength="80"
        autocomplete="off"
        placeholder="搜索农药、作物、病虫害、有效成分或登记号…"
      >
      <button type="submit" :disabled="loading || !keyword">{{ loading ? '正在探索…' : '探索关系' }}</button>
    </form>

    <form v-else-if="mode === 'path'" class="path-search" @submit.prevent="searchPath">
      <div class="path-explainer">
        <strong>它解决什么？</strong>
        <span>输入任意两个实体，查找连接它们的最短证据链，说明中间经过哪些登记、成分、作物或病虫害。</span>
      </div>
      <div>
        <label for="path-source">从哪个实体出发</label>
        <input id="path-source" name="path-source" v-model.trim="pathStart" maxlength="80" autocomplete="off" placeholder="例如 Prothioconazole…">
      </div>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg>
      <div>
        <label for="path-target">想关联到哪个实体</label>
        <input id="path-target" name="path-target" v-model.trim="pathEnd" maxlength="80" autocomplete="off" placeholder="例如 Spring barley…">
      </div>
      <button type="submit" :disabled="loading || !pathStart || !pathEnd">解释两者关系</button>
    </form>

    <form v-else class="compare-search" @submit.prevent="compareProducts">
      <div class="compare-explainer">
        <strong>登记产品差异</strong>
        <span>并列核对登记属性、有效成分、适用作物与防治对象。</span>
      </div>
      <div>
        <label for="compare-left">产品 A</label>
        <input id="compare-left" name="compare-left" v-model.trim="compareLeftKeyword" maxlength="80" autocomplete="off" placeholder="登记号或产品名…">
      </div>
      <button type="button" class="swap-products" aria-label="交换两个产品" title="交换产品" @click="swapProducts">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 3-3 3 3M10 4v14m7-1-3 3-3-3m3 3V6"/></svg>
      </button>
      <div>
        <label for="compare-right">产品 B</label>
        <input id="compare-right" name="compare-right" v-model.trim="compareRightKeyword" maxlength="80" autocomplete="off" placeholder="登记号或产品名…">
      </div>
      <button type="submit" :disabled="compareLoading || !compareLeftKeyword || !compareRightKeyword">
        {{ compareLoading ? '正在对比…' : '生成对比' }}
      </button>
    </form>

    <div v-if="mode === 'entity' && !graphData.found" class="sample-row" aria-label="搜索示例">
      <span>业务视角</span>
      <button
        v-for="sample in samples"
        :key="sample.label"
        type="button"
        @click="runSample(sample.keyword)"
      >{{ sample.label }}</button>
    </div>
    <div v-else-if="mode === 'path' && !graphData.found" class="sample-row" aria-label="路径查询示例">
      <span>穿透示例</span>
      <button type="button" @click="runPathSample('Prothioconazole', 'Spring barley')">有效成分为何关联作物？</button>
      <button type="button" @click="runPathSample('Leaf spot disease', '4387-901')">病害如何关联登记产品？</button>
    </div>
    <div v-else-if="mode === 'compare' && !comparison" class="sample-row" aria-label="产品对比示例">
      <span>对比示例</span>
      <button type="button" @click="runCompareSample('PD20150720', 'PD20050020')">两种杀虫剂登记差异</button>
    </div>
    </section>

    <section v-if="mode === 'compare'" class="compare-workspace" aria-live="polite">
      <div v-if="compareLoading" class="compare-state" role="status">
        <span class="loader"></span>
        <strong>正在汇总两个产品的登记关系…</strong>
      </div>
      <div v-else-if="compareError" class="compare-state error-state" role="alert">
        <strong>无法生成对比</strong>
        <p>{{ compareError }}</p>
        <button type="button" @click="compareProducts">重新查询</button>
      </div>
      <template v-else-if="comparison">
        <header class="comparison-header">
          <div class="product-card">
            <span>产品 A · {{ comparison.left.dataset }}</span>
            <h2>{{ comparison.left.name }}</h2>
            <p>{{ productSubtitle(comparison.left) }}</p>
            <button type="button" @click="openComparedProduct(comparison.left.name)">在图谱中查看</button>
          </div>
          <div class="comparison-score" aria-label="对比摘要">
            <strong>{{ comparisonSharedCount }}</strong>
            <span>项共同关联</span>
            <small>{{ comparisonDifferenceCount }} 项差异</small>
          </div>
          <div class="product-card right">
            <span>产品 B · {{ comparison.right.dataset }}</span>
            <h2>{{ comparison.right.name }}</h2>
            <p>{{ productSubtitle(comparison.right) }}</p>
            <button type="button" @click="openComparedProduct(comparison.right.name)">在图谱中查看</button>
          </div>
        </header>

        <div class="comparison-actions">
          <button type="button" @click="askAboutComparison">让 AI 解释差异</button>
          <button type="button" @click="exportComparison">导出对比结果</button>
        </div>

        <section class="comparison-block">
          <div class="comparison-title">
            <div><span>登记字段</span><h3>关键属性逐项核对</h3></div>
            <p>“不同”只表示当前图谱字段值不同，不推断产品优劣。</p>
          </div>
          <div class="comparison-table" role="table" aria-label="产品登记属性对比">
            <div class="comparison-row heading" role="row">
              <span role="columnheader">字段</span>
              <span role="columnheader">{{ comparison.left.name }}</span>
              <span role="columnheader">{{ comparison.right.name }}</span>
              <span role="columnheader">结果</span>
            </div>
            <div v-for="row in comparisonPropertyRows" :key="row.key" class="comparison-row" role="row">
              <strong role="cell">{{ row.label }}</strong>
              <span role="cell">{{ row.left || '暂无数据' }}</span>
              <span role="cell">{{ row.right || '暂无数据' }}</span>
              <em role="cell" :class="{ same: row.same }">{{ row.same ? '相同' : '不同' }}</em>
            </div>
          </div>
        </section>

        <section class="comparison-block relation-comparison">
          <div class="comparison-title">
            <div><span>关系网络</span><h3>共同关联与各自关联</h3></div>
            <p>直接来自两个登记产品的一跳图谱关系。</p>
          </div>
          <article v-for="section in comparisonRelationSections" :key="section.label">
            <header><h4>{{ section.label }}</h4><span>{{ section.left.length }} / {{ section.right.length }}</span></header>
            <div class="relation-diff-grid">
              <div>
                <strong>共同关联</strong>
                <p v-if="!section.common.length">暂无共同项</p>
                <div v-else><span v-for="item in section.common" :key="'c-'+item" class="common">{{ item }}</span></div>
              </div>
              <div>
                <strong>仅 {{ comparison.left.name }}</strong>
                <p v-if="!section.leftOnly.length">无独有项</p>
                <div v-else><span v-for="item in section.leftOnly" :key="'l-'+item">{{ item }}</span></div>
              </div>
              <div>
                <strong>仅 {{ comparison.right.name }}</strong>
                <p v-if="!section.rightOnly.length">无独有项</p>
                <div v-else><span v-for="item in section.rightOnly" :key="'r-'+item">{{ item }}</span></div>
              </div>
            </div>
          </article>
        </section>
      </template>
      <div v-else class="compare-state">
        <strong>选择两个登记产品开始对比</strong>
        <p>建议输入登记号以避免同名产品歧义。</p>
      </div>
    </section>

    <div
      v-else
      class="workspace"
      :class="{ 'filter-collapsed': !showFilters, 'detail-collapsed': !showDetails }"
    >
      <aside v-show="showFilters" class="filter-panel" aria-label="图谱筛选">
        <div class="panel-heading">
          <span>视图筛选</span>
          <div>
            <button v-if="typeOptions.length" type="button" @click="showAllTypes">全部显示</button>
            <button type="button" aria-label="收起视图筛选" title="收起筛选" @click="togglePanel('filter')">‹</button>
          </div>
        </div>

        <div v-if="typeOptions.length" class="type-list">
          <button
            v-for="type in typeOptions"
            :key="type.label"
            type="button"
            :class="{ inactive: !isTypeActive(type.label) }"
            :aria-pressed="isTypeActive(type.label) ? 'true' : 'false'"
            @click="toggleType(type.label)"
          >
            <i :style="{ background: typeColor(type.label) }"></i>
            <span><strong>{{ labelName(type.label) }}</strong><small>{{ type.count }} 个实体</small></span>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 12 3 3 7-7"/></svg>
          </button>
        </div>

        <div v-else class="filter-empty">
          <span>搜索后可按实体类型筛选结果。</span>
        </div>

        <section v-if="coverageItems.length" class="coverage-strip" aria-label="全球图谱数据覆盖">
          <div v-for="item in coverageItems" :key="item.label">
            <strong>{{ formatCount(item.value) }}</strong>
            <span>{{ item.label }}</span>
          </div>
          <p>全球登记关联网络</p>
        </section>

        <section id="graph-interaction-help" class="interaction-help">
          <p>画布操作</p>
          <dl>
            <div><dt>拖动</dt><dd>调整节点位置</dd></div>
            <div><dt>滚轮</dt><dd>缩放关系网络</dd></div>
            <div><dt>双击 / 按钮</dt><dd>增量展开实体</dd></div>
          </dl>
        </section>
      </aside>

      <main class="network-panel">
        <div class="network-toolbar">
          <div class="result-summary" :class="{ 'path-result': mode === 'path' && graphData.found }">
            <template v-if="mode === 'path' && graphData.found">
              <span class="result-eyebrow">最短关系路径</span>
              <strong>{{ resultTitle }}</strong>
              <p>{{ pathNarrative }}</p>
              <ol aria-label="关系路径步骤">
                <li v-for="step in pathSteps" :key="step.key">
                  <span>{{ step.from.name }}</span>
                  <small>{{ pathRelationName(step) }}</small>
                  <span>{{ step.to.name }}</span>
                </li>
              </ol>
              <span class="result-metrics">{{ visibleNodeCount }} 个实体 · {{ visibleEdgeCount }} 条关系</span>
            </template>
            <template v-else>
              <strong>{{ resultTitle }}</strong>
              <span v-if="graphData.found">{{ visibleNodeCount }} 个实体 · {{ visibleEdgeCount }} 条关系</span>
              <span v-else>搜索后将在这里展开关系</span>
            </template>
          </div>
          <div class="tool-actions" aria-label="图谱视图工具">
            <button
              type="button"
              title="切换筛选栏"
              aria-label="切换筛选栏"
              :aria-pressed="showFilters ? 'true' : 'false'"
              @click="togglePanel('filter')"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16M7 12h10m-7 7h4"/></svg>
            </button>
            <button type="button" title="缩小" aria-label="缩小关系图" @click="zoomBy(.82)">−</button>
            <span>{{ Math.round(zoom * 100) }}%</span>
            <button type="button" title="放大" aria-label="放大关系图" @click="zoomBy(1.22)">＋</button>
            <button type="button" title="适合画布" aria-label="让图谱适合画布" @click="fitView">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>
            </button>
            <button type="button" title="重新布局" aria-label="重新布局关系图" @click="runLayout(true)">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4v6h6M20 20v-6h-6M5 9a8 8 0 0 1 13-3l2 2M19 15a8 8 0 0 1-13 3l-2-2"/></svg>
            </button>
            <button type="button" title="全屏查看" aria-label="全屏查看关系图" @click="toggleFullscreen">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>
            </button>
            <button
              type="button"
              title="导出查询结果"
              aria-label="导出查询结果"
              :disabled="!graphData.found"
              @click="exportGraph"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M5 19h14"/></svg>
            </button>
            <button
              type="button"
              title="切换实体详情"
              aria-label="切换实体详情"
              :aria-pressed="showDetails ? 'true' : 'false'"
              @click="togglePanel('detail')"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5zM9 8h6m-6 4h6m-6 4h4"/></svg>
            </button>
          </div>
        </div>

        <section v-if="evidenceHighlight" class="evidence-highlight-banner" aria-live="polite">
          <div>
            <span>AI 回答依据 [{{ evidenceHighlight.index || 1 }}]</span>
            <strong>{{ evidenceHighlight.sourceName }} — {{ relationName(evidenceHighlight.relation) }} — {{ evidenceHighlight.targetName }}</strong>
          </div>
          <button type="button" aria-label="关闭证据高亮" @click="clearEvidenceHighlight">关闭高亮</button>
        </section>

        <div ref="graphStage" class="graph-stage">
          <div class="network-grid" aria-hidden="true"></div>
          <svg
            v-if="graphData.found"
            ref="cyCanvas"
            class="cy-canvas"
            aria-label="可拖动和缩放的农药知识图谱"
            aria-describedby="graph-interaction-help"
            @wheel.prevent="handleWheel"
            @pointerdown="startPan"
            @pointermove="handlePointerMove"
            @pointerup="endPointerAction"
            @pointercancel="endPointerAction"
          >
            <defs>
              <clipPath id="graph-node-image-clip-lg">
                <circle cx="0" cy="0" r="44"></circle>
              </clipPath>
              <clipPath id="graph-node-image-clip-sm">
                <circle cx="0" cy="0" r="29"></circle>
              </clipPath>
              <filter id="graph-node-glow" x="-80%" y="-80%" width="260%" height="260%">
                <feGaussianBlur stdDeviation="7" result="blur"></feGaussianBlur>
                <feMerge><feMergeNode in="blur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge>
              </filter>
              <marker id="graph-edge-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z"></path>
              </marker>
            </defs>
            <g :transform="graphTransform">
              <g
                v-if="centerNode"
                class="graph-orbits"
                :transform="`translate(${nodePosition(centerNode.id).x} ${nodePosition(centerNode.id).y})`"
                aria-hidden="true"
              >
                <circle r="82"></circle>
                <circle r="196"></circle>
                <circle r="318"></circle>
              </g>
              <g
                v-for="edge in visibleEdges"
                :key="edgeKey(edge)"
                class="svg-edge"
                :class="{ dimmed: edgeIsDimmed(edge), focused: edgeIsFocused(edge), evidence: edgeIsEvidence(edge) }"
              >
                <line
                  :x1="nodePosition(edge.source).x"
                  :y1="nodePosition(edge.source).y"
                  :x2="nodePosition(edge.target).x"
                  :y2="nodePosition(edge.target).y"
                  marker-end="url(#graph-edge-arrow)"
                ></line>
                <title>{{ relationName(edge.type) }}</title>
                <text
                  v-if="showEdgeLabel(edge)"
                  :x="edgeMidpoint(edge).x"
                  :y="edgeMidpoint(edge).y - 6"
                >{{ relationName(edge.type) }}</text>
              </g>

              <g
                v-for="(node, nodeIndex) in visibleNodes"
                :key="String(node.id)"
                class="svg-node"
                :style="{
                  '--node-delay': `${Math.min(nodeIndex, 18) * 28}ms`,
                  '--node-color': typeColor(node.label)
                }"
                :class="{
                  center: node.center,
                  selected: selectedNode && String(selectedNode.id) === String(node.id),
                  dimmed: nodeIsDimmed(node),
                  evidence: nodeIsEvidence(node)
                }"
                :transform="`translate(${nodePosition(node.id).x} ${nodePosition(node.id).y})`"
                role="button"
                tabindex="0"
                :aria-label="`${labelName(node.label)}：${node.name}`"
                @pointerdown.stop="startNodeDrag(node, $event)"
                @click.stop="selectNode(node)"
                @dblclick.stop="exploreNode(node.id)"
                @keydown.enter.prevent="selectNode(node)"
                @keydown.space.prevent="selectNode(node)"
              >
                <title>{{ labelName(node.label) }}：{{ node.name }}</title>
                <circle
                  v-if="node.center || (selectedNode && String(selectedNode.id) === String(node.id))"
                  class="node-halo"
                  :r="node.center ? 59 : 39"
                  fill="none"
                  :stroke="typeColor(node.label)"
                ></circle>
                <circle
                  class="node-backplate"
                  :r="node.center ? 50 : 34"
                  :fill="typeColor(node.label)"
                ></circle>
                <circle
                  class="node-core"
                  :r="node.center ? 46 : 31"
                  :fill="node.center ? '#121936' : nodeFill(node.label)"
                  :stroke="typeColor(node.label)"
                ></circle>
                <image
                  v-if="isHttpUrl(node.imageUrl)"
                  aria-hidden="true"
                  :href="node.imageUrl"
                  :x="node.center ? -44 : -29"
                  :y="node.center ? -44 : -29"
                  :width="node.center ? 88 : 58"
                  :height="node.center ? 88 : 58"
                  preserveAspectRatio="xMidYMid slice"
                  :clip-path="node.center ? 'url(#graph-node-image-clip-lg)' : 'url(#graph-node-image-clip-sm)'"
                ></image>
                <text
                  v-else
                  class="node-glyph"
                  :fill="typeColor(node.label)"
                >{{ nodeGlyph(node.label) }}</text>
                <rect
                  class="node-label-bg"
                  :x="-nodeLabelWidth(node) / 2"
                  :y="nodeLabelY(node)"
                  :width="nodeLabelWidth(node)"
                  :height="nodeLabelHeight(node)"
                  :rx="nodeLabelHeight(node) / 2"
                ></rect>
                <text class="node-caption" :y="nodeLabelY(node) + 13">
                  <tspan
                    v-for="(line, index) in nodeLabelLines(node)"
                    :key="`${node.id}-${index}`"
                    x="0"
                    :dy="index === 0 ? 0 : '12px'"
                  >{{ line }}</tspan>
                </text>
              </g>
            </g>
          </svg>

          <div v-if="loading" class="canvas-state" role="status" aria-live="polite">
            <span class="loader"></span>
            <h2>{{ mode === 'path' ? '正在解释关系链…' : '正在加载关系网络…' }}</h2>
          </div>

          <div v-else-if="errorMessage" class="canvas-state error-state" role="alert">
            <svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 5 5 40h38L24 5Zm0 13v10m0 6v.01"/></svg>
            <h2>暂时没有加载成功</h2>
            <p>{{ errorMessage }}</p>
            <button type="button" @click="retrySearch">再试一次</button>
          </div>

          <div v-else-if="searched && !graphData.found" class="canvas-state">
            <svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="21" cy="21" r="13"/><path d="m42 42-12-12M15 21h12"/></svg>
            <h2>{{ mode === 'path' ? '没有找到关系链' : '没有找到这个实体' }}</h2>
            <p>{{ mode === 'path' ? '可以换用更准确的起点和终点名称。' : '可以换一个名称，或从上方示例开始探索。' }}</p>
          </div>

          <div v-else-if="!graphData.found" class="canvas-state">
            <div class="seed-graph" aria-hidden="true"><i></i><i></i><i></i><i></i><strong>KG</strong></div>
            <h2>搜索一个实体，展开关系网络</h2>
            <p>农药、作物、病虫害与有效成分都可以成为探索起点。</p>
          </div>

          <div v-if="graphData.truncated && !loading" class="truncate-badge">已展示主要关联，可继续增量展开</div>
          <div
            v-if="expandingNodeId || statusMessage"
            class="expand-status"
            :class="{ error: statusError }"
            role="status"
            aria-live="polite"
          >
            <span v-if="expandingNodeId" class="mini-loader" aria-hidden="true"></span>
            {{ expandingNodeId ? '正在添加关联实体…' : statusMessage }}
          </div>
        </div>
      </main>

      <aside v-show="showDetails" class="detail-panel" aria-label="实体详情">
        <div class="panel-heading detail-heading">
          <span>实体详情</span>
          <div>
            <i v-if="selectedNode" :style="{ background: typeColor(selectedNode.label) }"></i>
            <button type="button" aria-label="收起实体详情" title="收起详情" @click="togglePanel('detail')">×</button>
          </div>
        </div>

        <template v-if="selectedNode">
          <div class="entity-summary" :class="{ 'without-image': !selectedImageUrl || detailImageError }">
            <div v-if="selectedImageUrl && !detailImageError" class="entity-image">
              <img
                :src="selectedImageUrl"
                :alt="selectedNode.name + ' 的图像资料'"
                width="160"
                height="160"
                loading="lazy"
                @error="detailImageError = true"
              >
            </div>
            <div class="entity-identity">
              <span>{{ labelName(selectedNode.label) }}</span>
              <h2>{{ selectedNode.name }}</h2>
            </div>
          </div>

          <div class="entity-actions">
            <button type="button" :disabled="loading || !!expandingNodeId" @click="exploreNode(selectedNode.id)">
              {{ expandingNodeId === String(selectedNode.id)
                ? '正在展开…'
                : (expandedNodeIds.includes(String(selectedNode.id)) ? '查看已展开关系' : '展开关系') }}
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
            </button>
            <button type="button" @click="askAboutNode(selectedNode.name)">
              问 AI
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v11H9l-4 3V5Z"/></svg>
            </button>
          </div>

          <div class="detail-tabs" role="tablist" aria-label="实体详情分类">
            <button
              id="detail-relations-tab"
              type="button"
              role="tab"
              :aria-selected="detailTab === 'relations' ? 'true' : 'false'"
              :aria-controls="'detail-relations-panel'"
              :class="{ active: detailTab === 'relations' }"
              :disabled="!selectedRelations.length"
              @click="detailTab = 'relations'"
            >
              直接关联 <span>{{ selectedRelations.length }}</span>
            </button>
            <button
              id="detail-properties-tab"
              type="button"
              role="tab"
              :aria-selected="detailTab === 'properties' ? 'true' : 'false'"
              :aria-controls="'detail-properties-panel'"
              :class="{ active: detailTab === 'properties' }"
              @click="detailTab = 'properties'"
            >
              属性信息 <span>{{ propertyEntries.length }}</span>
            </button>
            <button
              id="detail-evidence-tab"
              type="button"
              role="tab"
              :aria-selected="detailTab === 'evidence' ? 'true' : 'false'"
              :aria-controls="'detail-evidence-panel'"
              :class="{ active: detailTab === 'evidence' }"
              :disabled="!evidenceAvailable"
              @click="detailTab = 'evidence'"
            >
              登记证据
            </button>
          </div>

          <div class="detail-scroll">
            <section
              v-show="detailTab === 'relations'"
              id="detail-relations-panel"
              class="relation-list"
              role="tabpanel"
              aria-labelledby="detail-relations-tab"
            >
              <button
                v-for="relation in selectedRelations"
                :key="relation.key"
                type="button"
                @click="selectNodeById(relation.node.id)"
              >
                <span>{{ relation.node.name }}</span>
                <small>{{ relationName(relation.type) }}</small>
              </button>
              <div v-if="!selectedRelations.length" class="no-properties">当前视图中没有直接关联。</div>
            </section>

            <section
              v-show="detailTab === 'properties'"
              id="detail-properties-panel"
              class="property-list"
              role="tabpanel"
              aria-labelledby="detail-properties-tab"
            >
              <dl v-if="propertyEntries.length">
                <div v-for="entry in propertyEntries" :key="entry[0]" class="property-item">
                  <dt>{{ propertyName(entry[0]) }}</dt>
                  <dd>
                    <a v-if="isHttpUrl(entry[1])" :href="entry[1]" target="_blank" rel="noopener">查看资料 ↗</a>
                    <template v-else>
                      <span :class="{ expanded: isPropertyExpanded(entry[0]) }">{{ entry[1] }}</span>
                      <button
                        v-if="isLongProperty(entry[1])"
                        type="button"
                        :aria-expanded="isPropertyExpanded(entry[0]) ? 'true' : 'false'"
                        @click="toggleProperty(entry[0])"
                      >{{ isPropertyExpanded(entry[0]) ? '收起' : '展开全文' }}</button>
                    </template>
                  </dd>
                </div>
              </dl>
              <div v-else class="no-properties">暂无更多属性。</div>
            </section>

            <section
              v-show="detailTab === 'evidence'"
              id="detail-evidence-panel"
              class="evidence-panel"
              role="tabpanel"
              aria-labelledby="detail-evidence-tab"
            >
              <div class="evidence-status">
                <span>全球登记记录</span>
                <strong>{{ selectedEvidence.dataset || '全球农药登记字段集' }}</strong>
              </div>
              <dl v-if="evidenceEntries.length">
                <div v-for="entry in evidenceEntries" :key="entry.key">
                  <dt>{{ entry.label }}</dt>
                  <dd>{{ entry.value }}</dd>
                </div>
              </dl>
              <a
                v-if="selectedEvidence.sourceUrl"
                :href="selectedEvidence.sourceUrl"
                target="_blank"
                rel="noopener"
              >查看原始登记资料 ↗</a>
              <p v-else>该记录已纳入全球登记关联网络。</p>
            </section>
          </div>
        </template>

        <div v-else class="detail-empty">
          <svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="17" r="8"/><path d="M9 43c2-10 7-15 15-15s13 5 15 15"/></svg>
          <p>选择图中的节点，在这里查看图片、属性与直接关联。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script>
import service from '@/utils/axios';

const EMPTY_GRAPH = () => ({
  found: false,
  centerId: null,
  nodes: [],
  edges: [],
  truncated: false
});

const MAX_GRAPH_NODES = 180;
const MAX_GRAPH_EDGES = 280;

export default {
  name: 'GraphView',
  data() {
    return {
      mode: 'entity',
      keyword: 'Chlorantraniliprole',
      pathStart: 'Prothioconazole',
      pathEnd: 'Spring barley',
      compareLeftKeyword: 'PD20150720',
      compareRightKeyword: 'PD20050020',
      compareLoading: false,
      compareError: '',
      comparison: null,
      samples: [
        { label: '有效成分全景', keyword: 'Chlorantraniliprole' },
        { label: '作物—病虫害—登记产品', keyword: 'Spring barley' },
        { label: '登记产品穿透', keyword: 'PD20150720' }
      ],
      loading: false,
      graphRequestId: 0,
      expandingNodeId: null,
      searched: false,
      errorMessage: '',
      statusMessage: '',
      statusError: false,
      zoom: 1,
      showFilters: false,
      showDetails: true,
      activeTypes: [],
      expandedNodeIds: [],
      graphLimitReached: false,
      selectedNode: null,
      detailImageError: false,
      detailTab: 'relations',
      expandedPropertyKeys: [],
      graphData: EMPTY_GRAPH(),
      graphStats: {
        registrationCount: 0,
        entityCounts: {},
        jurisdictions: []
      },
      nodePositions: {},
      viewport: { x: 0, y: 0, scale: 1 },
      pointerState: null,
      focusedNodeId: null,
      evidenceHighlight: null,
      renderFrame: null,
      statusTimer: null,
      labelColors: {
        RegisterNumber: '#7695ff',
        Crop: '#79c8a3',
        Disease: '#ff987a',
        ActiveSubstance: '#64c5d5',
        ChemicalClasses: '#ad8cf0',
        PesticideCategory: '#f0c36b',
        TargetSite: '#eb8bb5',
        ModeOfAction: '#83beb8'
      },
      labelFills: {
        RegisterNumber: '#e8edff',
        Crop: '#e5f4ec',
        Disease: '#ffebe5',
        ActiveSubstance: '#e2f3f5',
        ChemicalClasses: '#eee7fb',
        PesticideCategory: '#f8efd9',
        TargetSite: '#f8e5ed',
        ModeOfAction: '#e5f2f0'
      },
      labelNames: {
        RegisterNumber: '农药登记',
        Crop: '作物',
        Disease: '病虫害',
        ActiveSubstance: '有效成分',
        ChemicalClasses: '化学类别',
        PesticideCategory: '农药类型',
        TargetSite: '作用靶点',
        ModeOfAction: '作用方式'
      },
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
  computed: {
    coverageItems() {
      const counts = this.graphStats.entityCounts || {};
      return [
        { label: '登记记录', value: this.graphStats.registrationCount || counts.RegisterNumber },
        { label: '有效成分', value: counts.ActiveSubstance },
        { label: '作物', value: counts.Crop },
        { label: '病虫害', value: counts.Disease }
      ].filter(item => Number(item.value) > 0);
    },
    typeOptions() {
      const counts = {};
      this.graphData.nodes.forEach(node => {
        counts[node.label] = (counts[node.label] || 0) + 1;
      });
      return Object.keys(counts).map(label => ({ label, count: counts[label] }));
    },
    centerNode() {
      return this.graphData.nodes.find(node => String(node.id) === String(this.graphData.centerId))
        || this.graphData.nodes[0]
        || null;
    },
    resultTitle() {
      if (!this.graphData.found) return this.mode === 'path' ? '关系穿透' : '关系网络';
      if (this.mode === 'path') {
        const first = this.pathSteps[0];
        const last = this.pathSteps[this.pathSteps.length - 1];
        return first && last
          ? `${first.from.name} → ${last.to.name}`
          : `${this.pathStart} → ${this.pathEnd}`;
      }
      return this.centerNode ? this.centerNode.name : this.keyword;
    },
    visibleNodeCount() {
      return this.graphData.nodes.filter(node => node.center || this.isTypeActive(node.label)).length;
    },
    visibleEdgeCount() {
      const ids = new Set(this.graphData.nodes
        .filter(node => node.center || this.isTypeActive(node.label))
        .map(node => String(node.id)));
      return this.graphData.edges.filter(edge => ids.has(String(edge.source)) && ids.has(String(edge.target))).length;
    },
    visibleNodes() {
      return this.graphData.nodes.filter(node => node.center || this.isTypeActive(node.label));
    },
    visibleEdges() {
      const ids = new Set(this.visibleNodes.map(node => String(node.id)));
      return this.graphData.edges.filter(edge => ids.has(String(edge.source)) && ids.has(String(edge.target)));
    },
    graphTransform() {
      return `translate(${this.viewport.x} ${this.viewport.y}) scale(${this.viewport.scale})`;
    },
    focusedNodeIds() {
      if (!this.focusedNodeId) return null;
      const ids = new Set([String(this.focusedNodeId)]);
      this.visibleEdges.forEach(edge => {
        if (String(edge.source) === String(this.focusedNodeId)) ids.add(String(edge.target));
        if (String(edge.target) === String(this.focusedNodeId)) ids.add(String(edge.source));
      });
      return ids;
    },
    focusedEdgeCount() {
      if (!this.focusedNodeId) return 0;
      return this.visibleEdges.filter(edge => this.edgeIsFocused(edge)).length;
    },
    pathSteps() {
      if (this.mode !== 'path' || !this.graphData.found || !this.graphData.nodes.length) return [];
      const nodes = new Map(this.graphData.nodes.map(node => [String(node.id), node]));
      const adjacency = new Map(Array.from(nodes.keys()).map(id => [id, []]));
      this.graphData.edges.forEach((edge, index) => {
        const source = String(edge.source);
        const target = String(edge.target);
        if (!adjacency.has(source) || !adjacency.has(target)) return;
        adjacency.get(source).push({ next: target, edge, index });
        adjacency.get(target).push({ next: source, edge, index });
      });

      const start = String(this.graphData.centerId);
      const target = this.graphData.targetId != null
        ? String(this.graphData.targetId)
        : String(this.graphData.nodes[this.graphData.nodes.length - 1].id);
      const queue = [start];
      const parent = new Map([[start, null]]);
      while (queue.length && !parent.has(target)) {
        const current = queue.shift();
        adjacency.get(current).forEach(item => {
          if (parent.has(item.next)) return;
          parent.set(item.next, { previous: current, edge: item.edge, index: item.index });
          queue.push(item.next);
        });
      }
      if (!parent.has(target)) return [];

      const steps = [];
      let current = target;
      while (current !== start) {
        const entry = parent.get(current);
        steps.unshift({
          key: `${entry.previous}:${current}:${entry.index}`,
          from: nodes.get(entry.previous),
          to: nodes.get(current),
          edge: entry.edge
        });
        current = entry.previous;
      }
      return steps;
    },
    pathNarrative() {
      if (!this.pathSteps.length) return '已找到两个实体之间的最短关系链。';
      const source = this.pathSteps[0].from;
      const target = this.pathSteps[this.pathSteps.length - 1].to;
      const intermediates = this.pathSteps.slice(0, -1).map(step => step.to);
      const registration = intermediates.find(node => node.label === 'RegisterNumber');
      if (registration) {
        return `${source.name} 通过登记产品 ${registration.name} 与 ${target.name} 建立关联，共 ${this.pathSteps.length} 跳。`;
      }
      const via = intermediates.length ? `，中间经过 ${intermediates.map(node => node.name).join('、')}` : '';
      return `${source.name} 与 ${target.name} 之间存在 ${this.pathSteps.length} 跳最短关系${via}。`;
    },
    comparisonPropertyRows() {
      if (!this.comparison) return [];
      const fields = [
        { key: 'Trade name', label: '商品名', aliases: ['Trade name', 'Pesticide name'] },
        { key: 'Active Ingredient', label: '有效成分', aliases: ['Active Ingredient', 'English name of active ingredient'] },
        { key: 'Pesticide category', label: '农药类别', aliases: ['Pesticide category', 'Effect Type'] },
        { key: 'Formulation', label: '剂型', aliases: ['Formulation', 'delivery mechanism of a medicine (e.g. pill, powder etc)'] },
        { key: 'Method of application', label: '施用方法', aliases: ['Method of application'] },
        { key: 'Member State of origin', label: '登记地区', aliases: ['Member State of origin'] },
        { key: 'valid until', label: '有效期至', aliases: ['valid until', 'Time expiry date_y'] },
        { key: 'Authorization holder', label: '登记持有人', aliases: ['Authorization holder', 'holder of registration certificate'] }
      ];
      return fields.map(field => {
        const left = this.firstPropertyValue(this.comparison.left.properties, field.aliases);
        const right = this.firstPropertyValue(this.comparison.right.properties, field.aliases);
        return {
          key: field.key,
          label: field.label,
          left,
          right,
          same: this.normalizedValue(left) === this.normalizedValue(right)
        };
      });
    },
    comparisonRelationSections() {
      if (!this.comparison) return [];
      const sections = [
        { key: 'ActiveSubstance', label: '有效成分' },
        { key: 'Crop', label: '适用作物' },
        { key: 'Disease', label: '防治病虫害' }
      ];
      return sections.map(section => {
        const left = this.comparison.left.relations[section.key] || [];
        const right = this.comparison.right.relations[section.key] || [];
        const rightKeys = new Set(right.map(this.normalizedValue));
        const leftKeys = new Set(left.map(this.normalizedValue));
        return {
          ...section,
          left,
          right,
          common: left.filter(item => rightKeys.has(this.normalizedValue(item))),
          leftOnly: left.filter(item => !rightKeys.has(this.normalizedValue(item))),
          rightOnly: right.filter(item => !leftKeys.has(this.normalizedValue(item)))
        };
      });
    },
    comparisonSharedCount() {
      return this.comparisonRelationSections.reduce((total, section) => total + section.common.length, 0);
    },
    comparisonDifferenceCount() {
      const propertyDifferences = this.comparisonPropertyRows.filter(row => !row.same).length;
      const relationDifferences = this.comparisonRelationSections.reduce(
        (total, section) => total + section.leftOnly.length + section.rightOnly.length,
        0
      );
      return propertyDifferences + relationDifferences;
    },
    selectedProperties() {
      return this.selectedNode && this.selectedNode.properties ? this.selectedNode.properties : {};
    },
    selectedEvidence() {
      return this.selectedNode && this.selectedNode.evidence ? this.selectedNode.evidence : {};
    },
    evidenceAvailable() {
      return !!this.selectedNode && (
        this.selectedNode.label === 'RegisterNumber'
        || Object.keys(this.selectedEvidence).some(key => !['traceable', 'jurisdictionInferred'].includes(key))
      );
    },
    evidenceEntries() {
      const evidence = this.selectedEvidence;
      const fields = [
        ['jurisdiction', '登记地区'],
        ['status', '登记状态'],
        ['validUntil', '有效期至'],
        ['sourceName', '来源机构'],
        ['collectedAt', '采集时间'],
        ['updatedAt', '更新时间']
      ];
      return fields
        .filter(item => evidence[item[0]])
        .map(item => ({ key: item[0], label: item[1], value: evidence[item[0]] }));
    },
    selectedImageUrl() {
      if (!this.selectedNode) return '';
      if (this.isHttpUrl(this.selectedNode.imageUrl)) return this.selectedNode.imageUrl;
      const entry = Object.entries(this.selectedProperties).find(item =>
        /(image|photo|picture|structure)/i.test(item[0]) && this.isHttpUrl(item[1])
      );
      return entry ? entry[1] : '';
    },
    propertyEntries() {
      return Object.entries(this.selectedProperties)
        .filter(entry => entry[0] !== 'name' && entry[1] !== this.selectedImageUrl);
    },
    selectedRelations() {
      if (!this.selectedNode) return [];
      const selectedId = String(this.selectedNode.id);
      const nodes = {};
      this.graphData.nodes.forEach(node => { nodes[String(node.id)] = node; });
      return this.graphData.edges.reduce((items, edge, index) => {
        const source = String(edge.source);
        const target = String(edge.target);
        if (source !== selectedId && target !== selectedId) return items;
        const node = nodes[source === selectedId ? target : source];
        if (node) items.push({ key: `${source}:${target}:${edge.type}:${index}`, type: edge.type, node });
        return items;
      }, []);
    }
  },
  watch: {
    '$route.query': {
      deep: true,
      async handler(query) {
        if (!query.q) return;
        const keyword = String(query.q);
        if (keyword !== this.keyword || this.mode !== 'entity') {
          this.switchMode('entity');
          this.keyword = keyword;
          await this.searchGraph();
        }
        await this.applyEvidenceFromRoute();
      }
    },
    selectedNode() {
      this.detailImageError = false;
      this.expandedPropertyKeys = [];
      this.$nextTick(() => {
        this.detailTab = this.selectedRelations.length ? 'relations' : 'properties';
      });
    }
  },
  async mounted() {
    if (this.$route.query.q) this.keyword = String(this.$route.query.q);
    this.loadGraphStats();
    await this.searchGraph();
    await this.applyEvidenceFromRoute();
  },
  beforeDestroy() {
    if (this.renderFrame) window.cancelAnimationFrame(this.renderFrame);
    if (this.statusTimer) window.clearTimeout(this.statusTimer);
  },
  methods: {
    switchMode(nextMode) {
      if (this.mode === nextMode) return;
      this.mode = nextMode;
      this.graphRequestId += 1;
      this.loading = false;
      this.searched = false;
      this.errorMessage = '';
      this.statusMessage = '';
      this.statusError = false;
      this.graphData = EMPTY_GRAPH();
      this.activeTypes = [];
      this.expandedNodeIds = [];
      this.graphLimitReached = false;
      this.selectedNode = null;
      this.clearEvidenceHighlight(false);
      this.destroyGraph();
    },
    async loadGraphStats() {
      try {
        const response = await service.get('/api/graph/stats', { timeout: 8000 });
        this.graphStats = { ...this.graphStats, ...(response.data || {}) };
      } catch (error) {
        this.graphStats = { ...this.graphStats };
      }
    },
    async searchGraph() {
      if (!this.keyword || this.loading) return;
      this.switchMode('entity');
      this.clearEvidenceHighlight(false);
      await this.fetchGraph('/api/graph/search', { keyword: this.keyword });
    },
    async searchPath() {
      if (!this.pathStart || !this.pathEnd || this.loading) return;
      this.switchMode('path');
      this.clearEvidenceHighlight(false);
      await this.fetchGraph('/api/graph/path', { source: this.pathStart, target: this.pathEnd });
    },
    async compareProducts() {
      if (!this.compareLeftKeyword || !this.compareRightKeyword || this.compareLoading) return;
      this.switchMode('compare');
      this.compareLoading = true;
      this.compareError = '';
      try {
        const [leftResponse, rightResponse] = await Promise.all([
          service.get('/api/graph/search', { params: { keyword: this.compareLeftKeyword }, timeout: 10000 }),
          service.get('/api/graph/search', { params: { keyword: this.compareRightKeyword }, timeout: 10000 })
        ]);
        const left = this.createComparableProduct(leftResponse.data);
        const right = this.createComparableProduct(rightResponse.data);
        if (!left || !right) {
          throw new Error('请确认两个输入都能定位到登记产品，建议直接使用登记号。');
        }
        if (left.id === right.id) {
          throw new Error('请选择两个不同的登记产品。');
        }
        this.comparison = { left, right, comparedAt: new Date().toISOString() };
        this.compareLeftKeyword = left.name;
        this.compareRightKeyword = right.name;
      } catch (error) {
        this.comparison = null;
        this.compareError = error.response && error.response.data && error.response.data.message
          ? error.response.data.message
          : (error.message || '产品对比失败，请稍后再试。');
      } finally {
        this.compareLoading = false;
      }
    },
    createComparableProduct(graph) {
      if (!graph || !graph.found || !Array.isArray(graph.nodes)) return null;
      const center = graph.nodes.find(node => String(node.id) === String(graph.centerId))
        || graph.nodes.find(node => node.center);
      if (!center || center.label !== 'RegisterNumber') return null;
      const centerId = String(center.id);
      const relatedIds = new Set();
      (graph.edges || []).forEach(edge => {
        if (String(edge.source) === centerId) relatedIds.add(String(edge.target));
        if (String(edge.target) === centerId) relatedIds.add(String(edge.source));
      });
      const relations = {};
      graph.nodes.forEach(node => {
        if (!relatedIds.has(String(node.id))) return;
        if (['', '-', '/', 'n/a', 'null'].includes(this.normalizedValue(node.name))) return;
        if (!relations[node.label]) relations[node.label] = [];
        if (!relations[node.label].includes(node.name)) relations[node.label].push(node.name);
      });
      Object.values(relations).forEach(items => items.sort((a, b) => a.localeCompare(b)));
      return {
        id: centerId,
        name: center.name,
        properties: center.properties || {},
        evidence: center.evidence || {},
        dataset: (center.evidence && center.evidence.dataset) || '全球农药登记',
        relations
      };
    },
    swapProducts() {
      const previous = this.compareLeftKeyword;
      this.compareLeftKeyword = this.compareRightKeyword;
      this.compareRightKeyword = previous;
      if (this.comparison) this.compareProducts();
    },
    runCompareSample(left, right) {
      this.compareLeftKeyword = left;
      this.compareRightKeyword = right;
      this.compareProducts();
    },
    productSubtitle(product) {
      const tradeName = this.firstPropertyValue(product.properties, ['Trade name', 'Pesticide name']);
      const active = this.firstPropertyValue(product.properties, ['Active Ingredient', 'English name of active ingredient']);
      return [tradeName, active].filter(Boolean).join(' · ') || '登记产品';
    },
    firstPropertyValue(properties, aliases) {
      const key = aliases.find(alias => properties && properties[alias] != null && String(properties[alias]).trim());
      return key ? String(properties[key]).trim() : '';
    },
    normalizedValue(value) {
      return String(value == null ? '' : value).trim().toLocaleLowerCase();
    },
    openComparedProduct(name) {
      this.switchMode('entity');
      this.keyword = name;
      this.clearEvidenceHighlight();
      this.searchGraph();
    },
    askAboutComparison() {
      if (!this.comparison) return;
      this.$router.push({
        path: '/ask',
        query: { q: `请比较登记产品 ${this.comparison.left.name} 和 ${this.comparison.right.name} 的有效成分、适用作物、防治对象与登记属性差异，并引用图谱依据。` }
      }).catch(() => {});
    },
    exportComparison() {
      if (!this.comparison) return;
      const payload = {
        ...this.comparison,
        propertyComparison: this.comparisonPropertyRows,
        relationComparison: this.comparisonRelationSections
      };
      this.downloadJson(payload, `agrireg-ai-product-comparison-${Date.now()}.json`);
      this.announceStatus('产品对比结果已导出。');
    },
    async applyEvidenceFromRoute() {
      const query = this.$route.query || {};
      const sourceName = String(query.evidenceSource || '').trim();
      const targetName = String(query.evidenceTarget || '').trim();
      const relation = String(query.evidenceRelation || '').trim();
      const sourceId = String(query.evidenceSourceId || '').trim();
      const targetId = String(query.evidenceTargetId || '').trim();
      if ((!sourceName && !sourceId) || (!targetName && !targetId) || !relation || !this.graphData.found) return;

      const findNode = (id, name) => this.graphData.nodes.find(node => id && String(node.id) === id)
        || this.graphData.nodes.find(node => name && this.normalizedValue(node.name) === this.normalizedValue(name));
      let source = findNode(sourceId, sourceName);
      let target = findNode(targetId, targetName);

      if (source && !target) {
        try {
          const response = await service.get('/api/graph/node/' + encodeURIComponent(source.id), { timeout: 10000 });
          this.mergeGraph(response.data || EMPTY_GRAPH());
          source = findNode(sourceId, sourceName);
          target = findNode(targetId, targetName);
          await this.$nextTick();
          this.scheduleGraphRender();
        } catch (error) {
          this.announceStatus('已打开图谱，但未能补全这条回答依据。', true);
        }
      }

      if (!source || !target) {
        this.announceStatus('回答依据中的实体不在当前图谱结果中。', true);
        return;
      }

      [source.label, target.label].forEach(label => {
        if (!this.activeTypes.includes(label)) this.activeTypes.push(label);
      });
      this.evidenceHighlight = {
        sourceId: String(source.id),
        targetId: String(target.id),
        sourceName: source.name,
        targetName: target.name,
        relation,
        index: String(query.evidenceIndex || '1')
      };
      this.selectedNode = target;
      this.focusedNodeId = null;
      this.showDetails = true;
      this.announceStatus(`已定位回答中的第 ${this.evidenceHighlight.index} 条图谱依据。`);
      window.setTimeout(() => this.fitView(new Set([String(source.id), String(target.id)])), 100);
    },
    clearEvidenceHighlight(updateRoute = true) {
      this.evidenceHighlight = null;
      if (!updateRoute) return;
      const query = { ...this.$route.query };
      ['evidenceSource', 'evidenceTarget', 'evidenceRelation', 'evidenceSourceId', 'evidenceTargetId', 'evidenceIndex']
        .forEach(key => { delete query[key]; });
      this.$router.replace({ path: '/graph', query }).catch(() => {});
    },
    async exploreNode(nodeId) {
      if (this.loading || this.expandingNodeId) return;
      this.mode = 'entity';
      const id = String(nodeId);
      const currentNode = this.graphData.nodes.find(node => String(node.id) === id);
      if (!currentNode) return;
      this.selectedNode = currentNode;

      if (this.expandedNodeIds.includes(id)) {
        this.focusExpandedNeighborhood(id);
        this.announceStatus('这个实体的直接关系已经展开。');
        return;
      }

      this.expandingNodeId = id;
      this.statusMessage = '';
      this.statusError = false;
      try {
        const response = await service.get('/api/graph/node/' + encodeURIComponent(id));
        const change = this.mergeGraph(response.data || EMPTY_GRAPH());
        this.expandedNodeIds.push(id);
        this.selectedNode = this.graphData.nodes.find(node => String(node.id) === id) || currentNode;
        await this.$nextTick();
        this.addGraphElements(change, id);

        if (change.newNodeIds.length || change.newEdgeKeys.length) {
          const limitHint = this.graphLimitReached ? ' 已达到当前视图的展示上限。' : '';
          this.announceStatus(`已添加 ${change.newNodeIds.length} 个实体和 ${change.newEdgeKeys.length} 条关系。${limitHint}`);
        } else {
          this.announceStatus('没有发现新的直接关系。');
        }
      } catch (error) {
        const message = error.response && error.response.data && error.response.data.message
          ? error.response.data.message
          : '关系展开失败，请再试一次。';
        this.announceStatus(message, true);
      } finally {
        this.expandingNodeId = null;
      }
    },
    async fetchGraph(url, params) {
      const requestId = ++this.graphRequestId;
      const requestMode = this.mode;
      this.loading = true;
      this.errorMessage = '';
      this.statusMessage = '';
      this.searched = true;
      let shouldRender = false;
      try {
        const response = await service.get(url, { params, timeout: 10000 });
        if (requestId !== this.graphRequestId || requestMode !== this.mode) return;
        this.graphData = response.data || EMPTY_GRAPH();
        this.activeTypes = this.typeOptions.map(type => type.label);
        this.expandedNodeIds = this.graphData.centerId == null ? [] : [String(this.graphData.centerId)];
        this.graphLimitReached = false;
        this.selectedNode = this.centerNode;
        if (this.mode === 'entity' && this.selectedNode) this.keyword = this.selectedNode.name;
        shouldRender = true;
      } catch (error) {
        if (requestId !== this.graphRequestId || requestMode !== this.mode) return;
        this.graphData = EMPTY_GRAPH();
        this.selectedNode = null;
        this.destroyGraph();
        this.errorMessage = error.response && error.response.data && error.response.data.message
          ? error.response.data.message
          : '请稍后再试。';
      } finally {
        if (requestId === this.graphRequestId) this.loading = false;
      }

      if (shouldRender) {
        await this.$nextTick();
        this.scheduleGraphRender();
      }
    },
    scheduleGraphRender() {
      if (this.renderFrame) window.cancelAnimationFrame(this.renderFrame);
      this.renderFrame = window.requestAnimationFrame(() => {
        this.renderFrame = window.requestAnimationFrame(() => {
          this.renderFrame = null;
          try {
            this.renderGraph();
          } catch (error) {
            this.destroyGraph();
            this.errorMessage = '关系网络绘制失败，请刷新页面后重试。';
          }
        });
      });
    },
    mergeGraph(incoming) {
      const existingLabels = new Set(this.graphData.nodes.map(node => node.label));
      const nodesById = new Map(this.graphData.nodes.map(node => [String(node.id), node]));
      const newNodeIds = [];

      (incoming.nodes || []).forEach(node => {
        const id = String(node.id);
        const existing = nodesById.get(id);
        if (existing) {
          nodesById.set(id, {
            ...existing,
            ...node,
            center: existing.center,
            properties: { ...(existing.properties || {}), ...(node.properties || {}) },
            evidence: { ...(existing.evidence || {}), ...(node.evidence || {}) }
          });
          return;
        }
        if (nodesById.size >= MAX_GRAPH_NODES) {
          this.graphLimitReached = true;
          return;
        }
        nodesById.set(id, { ...node, center: false });
        newNodeIds.push(id);
        if (!existingLabels.has(node.label) && !this.activeTypes.includes(node.label)) {
          this.activeTypes.push(node.label);
        }
      });

      const allowedNodeIds = new Set(nodesById.keys());
      const edgesByKey = new Map(this.graphData.edges.map(edge => [this.edgeKey(edge), edge]));
      const newEdgeKeys = [];
      (incoming.edges || []).forEach(edge => {
        const key = this.edgeKey(edge);
        if (edgesByKey.has(key)) return;
        if (!allowedNodeIds.has(String(edge.source)) || !allowedNodeIds.has(String(edge.target))) return;
        if (edgesByKey.size >= MAX_GRAPH_EDGES) {
          this.graphLimitReached = true;
          return;
        }
        edgesByKey.set(key, edge);
        newEdgeKeys.push(key);
      });

      this.graphData = {
        ...this.graphData,
        found: true,
        nodes: Array.from(nodesById.values()),
        edges: Array.from(edgesByKey.values()),
        truncated: this.graphData.truncated || !!incoming.truncated || this.graphLimitReached
      };
      return { newNodeIds, newEdgeKeys };
    },
    renderGraph() {
      this.destroyGraph();
      if (!this.graphData.found || !this.$refs.cyCanvas) return;
      const positions = this.initialPositions();
      const nextPositions = {};
      positions.forEach((position, id) => { nextPositions[id] = position; });
      this.nodePositions = nextPositions;
      this.focusedNodeId = null;
      this.$nextTick(() => window.requestAnimationFrame(() => this.fitView()));
    },
    initialPositions(randomize = false) {
      const positions = new Map();
      if (!this.graphData.nodes.length) return positions;
      if (this.mode === 'path') return this.pathPositions();

      const centerId = this.centerNode ? String(this.centerNode.id) : '';
      const nodes = this.graphData.nodes
        .filter(node => String(node.id) !== centerId)
        .slice()
        .sort((left, right) => {
          const byType = String(left.label).localeCompare(String(right.label));
          return byType || String(left.name).localeCompare(String(right.name));
        });

      if (centerId) positions.set(centerId, { x: 0, y: 0 });
      const perRing = 14;
      const rotation = randomize ? Math.random() * Math.PI * 2 : 0;
      nodes.forEach((node, index) => {
        const ring = Math.floor(index / perRing);
        const slot = index % perRing;
        const count = Math.min(perRing, nodes.length - ring * perRing);
        const angle = -Math.PI / 2 + rotation + slot / Math.max(1, count) * Math.PI * 2 + ring * .14;
        const radius = 218 + ring * 142;
        positions.set(String(node.id), {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius
        });
      });
      return positions;
    },
    pathPositions() {
      const positions = new Map();
      const nodesById = new Map(this.graphData.nodes.map(node => [String(node.id), node]));
      const neighbors = new Map(Array.from(nodesById.keys()).map(id => [id, []]));
      this.graphData.edges.forEach(edge => {
        const source = String(edge.source);
        const target = String(edge.target);
        if (!neighbors.has(source) || !neighbors.has(target)) return;
        neighbors.get(source).push(target);
        neighbors.get(target).push(source);
      });

      const start = this.centerNode ? String(this.centerNode.id) : String(this.graphData.nodes[0].id);
      const depth = new Map([[start, 0]]);
      const queue = [start];
      while (queue.length) {
        const current = queue.shift();
        neighbors.get(current).forEach(next => {
          if (depth.has(next)) return;
          depth.set(next, depth.get(current) + 1);
          queue.push(next);
        });
      }

      const columns = new Map();
      nodesById.forEach((node, id) => {
        const value = depth.has(id) ? depth.get(id) : depth.size;
        if (!columns.has(value)) columns.set(value, []);
        columns.get(value).push(node);
      });
      columns.forEach((column, columnDepth) => {
        column.sort((left, right) => String(left.name).localeCompare(String(right.name)));
        column.forEach((node, index) => {
          positions.set(String(node.id), {
            x: columnDepth * 220,
            y: (index - (column.length - 1) / 2) * 115
          });
        });
      });
      return positions;
    },
    edgeKey(edge) {
      return `${edge.source}:${edge.type || 'RELATED_TO'}:${edge.target}`;
    },
    nodeLabelLines(node) {
      const value = this.shortName(node.name, node.center ? 22 : 20);
      if (value.length <= 11) return [value];
      const midpoint = Math.ceil(value.length / 2);
      const breakAt = value.lastIndexOf(' ', midpoint);
      const index = breakAt > 3 ? breakAt : midpoint;
      return [value.slice(0, index).trim(), value.slice(index).trim()].filter(Boolean);
    },
    nodeGlyph(label) {
      const glyphs = {
        RegisterNumber: '登',
        Crop: '作',
        Disease: '害',
        ActiveSubstance: '成',
        ChemicalClasses: '类',
        PesticideCategory: '剂',
        TargetSite: '靶',
        ModeOfAction: '机'
      };
      return glyphs[label] || '·';
    },
    nodeLabelWidth(node) {
      const lines = this.nodeLabelLines(node);
      const longest = Math.max(...lines.map(line => line.length), 6);
      return Math.min(
        node.center ? 174 : 144,
        Math.max(node.center ? 96 : 66, longest * 6.2 + 22)
      );
    },
    nodeLabelY(node) {
      return node.center ? 56 : 40;
    },
    nodeLabelHeight(node) {
      return this.nodeLabelLines(node).length > 1 ? 34 : 24;
    },
    nodePosition(nodeId) {
      return this.nodePositions[String(nodeId)] || { x: 0, y: 0 };
    },
    edgeMidpoint(edge) {
      const source = this.nodePosition(edge.source);
      const target = this.nodePosition(edge.target);
      return { x: (source.x + target.x) / 2, y: (source.y + target.y) / 2 };
    },
    showEdgeLabel(edge) {
      return this.mode === 'path'
        || this.edgeIsEvidence(edge)
        || (this.edgeIsFocused(edge) && this.focusedEdgeCount <= 10);
    },
    edgeIsFocused(edge) {
      if (!this.focusedNodeId) return false;
      return String(edge.source) === String(this.focusedNodeId)
        || String(edge.target) === String(this.focusedNodeId);
    },
    edgeIsEvidence(edge) {
      if (!this.evidenceHighlight) return false;
      const source = String(edge.source);
      const target = String(edge.target);
      const direct = source === this.evidenceHighlight.sourceId && target === this.evidenceHighlight.targetId;
      const reverse = source === this.evidenceHighlight.targetId && target === this.evidenceHighlight.sourceId;
      return (direct || reverse) && String(edge.type || 'RELATED_TO') === this.evidenceHighlight.relation;
    },
    edgeIsDimmed(edge) {
      if (this.evidenceHighlight) return !this.edgeIsEvidence(edge);
      return !!this.focusedNodeId && !this.edgeIsFocused(edge);
    },
    nodeIsDimmed(node) {
      if (this.evidenceHighlight) return !this.nodeIsEvidence(node);
      return !!this.focusedNodeIds && !this.focusedNodeIds.has(String(node.id));
    },
    nodeIsEvidence(node) {
      if (!this.evidenceHighlight) return false;
      const id = String(node.id);
      return id === this.evidenceHighlight.sourceId || id === this.evidenceHighlight.targetId;
    },
    addGraphElements(change, sourceNodeId) {
      if (!Object.keys(this.nodePositions).length) {
        this.renderGraph();
        return;
      }

      let nextPositions = { ...this.nodePositions };
      if (change.newNodeIds.length > 8) {
        nextPositions = {};
        this.initialPositions().forEach((position, id) => { nextPositions[id] = position; });
      } else {
        const origin = this.nodePosition(sourceNodeId);
        change.newNodeIds.forEach((id, index) => {
          nextPositions[String(id)] = this.expansionPosition(index, change.newNodeIds.length, origin);
        });
      }
      this.nodePositions = nextPositions;
      this.applyTypeFilter(false);
      this.focusExpandedNeighborhood(sourceNodeId, true);
    },
    expansionPosition(index, total, origin) {
      const perRing = 12;
      const ring = Math.floor(index / perRing);
      const slot = index % perRing;
      const countInRing = Math.min(perRing, total - ring * perRing);
      const angle = -Math.PI / 2 + (slot / Math.max(1, countInRing)) * Math.PI * 2 + ring * .18;
      const radius = 145 + ring * 105;
      return {
        x: origin.x + Math.cos(angle) * radius,
        y: origin.y + Math.sin(angle) * radius
      };
    },
    destroyGraph() {
      if (this.renderFrame) window.cancelAnimationFrame(this.renderFrame);
      this.renderFrame = null;
      this.nodePositions = {};
      this.viewport = { x: 0, y: 0, scale: 1 };
      this.pointerState = null;
      this.focusedNodeId = null;
      this.zoom = 1;
    },
    runLayout(randomize) {
      if (!this.graphData.found) return;
      const positions = this.initialPositions(randomize);
      const nextPositions = {};
      positions.forEach((position, id) => { nextPositions[id] = position; });
      this.nodePositions = nextPositions;
      this.$nextTick(() => this.fitView());
    },
    selectNode(node) {
      this.clearEvidenceHighlight(false);
      this.selectedNode = node;
      this.focusedNodeId = String(node.id);
      this.showDetails = true;
    },
    togglePanel(panel) {
      if (panel === 'filter') this.showFilters = !this.showFilters;
      if (panel === 'detail') this.showDetails = !this.showDetails;
      this.$nextTick(() => window.requestAnimationFrame(() => this.fitView()));
    },
    clearNeighborhoodFocus() {
      this.focusedNodeId = null;
    },
    focusExpandedNeighborhood(nodeId, fit) {
      const node = this.graphData.nodes.find(item => String(item.id) === String(nodeId));
      if (!node) return;
      this.selectNode(node);
      if (fit) this.$nextTick(() => this.fitView(this.focusedNodeIds));
    },
    selectNodeById(nodeId) {
      const node = this.visibleNodes.find(item => String(item.id) === String(nodeId));
      if (!node) return;
      this.selectNode(node);
      this.centerNodeInView(node.id);
    },
    toggleType(label) {
      const index = this.activeTypes.indexOf(label);
      if (index >= 0) this.activeTypes.splice(index, 1);
      else this.activeTypes.push(label);
      this.applyTypeFilter();
    },
    showAllTypes() {
      this.activeTypes = this.typeOptions.map(type => type.label);
      this.applyTypeFilter();
    },
    applyTypeFilter(shouldFit = true) {
      this.clearNeighborhoodFocus();
      if (shouldFit) this.$nextTick(() => this.fitView());
    },
    startPan(event) {
      if (event.button !== 0) return;
      this.clearNeighborhoodFocus();
      this.pointerState = {
        type: 'pan',
        pointerId: event.pointerId,
        captureTarget: event.currentTarget,
        clientX: event.clientX,
        clientY: event.clientY,
        viewportX: this.viewport.x,
        viewportY: this.viewport.y
      };
      if (event.currentTarget.setPointerCapture) event.currentTarget.setPointerCapture(event.pointerId);
    },
    startNodeDrag(node, event) {
      if (event.button !== 0) return;
      event.preventDefault();
      this.selectNode(node);
      const point = this.graphPoint(event);
      const position = this.nodePosition(node.id);
      this.pointerState = {
        type: 'node',
        nodeId: String(node.id),
        pointerId: event.pointerId,
        captureTarget: event.currentTarget,
        offsetX: position.x - point.x,
        offsetY: position.y - point.y
      };
      if (event.currentTarget.setPointerCapture) event.currentTarget.setPointerCapture(event.pointerId);
    },
    handlePointerMove(event) {
      if (!this.pointerState || this.pointerState.pointerId !== event.pointerId) return;
      if (this.pointerState.type === 'pan') {
        this.viewport = {
          ...this.viewport,
          x: this.pointerState.viewportX + event.clientX - this.pointerState.clientX,
          y: this.pointerState.viewportY + event.clientY - this.pointerState.clientY
        };
        return;
      }
      const point = this.graphPoint(event);
      this.$set(this.nodePositions, this.pointerState.nodeId, {
        x: point.x + this.pointerState.offsetX,
        y: point.y + this.pointerState.offsetY
      });
    },
    endPointerAction(event) {
      if (!this.pointerState || this.pointerState.pointerId !== event.pointerId) return;
      const captureTarget = this.pointerState.captureTarget;
      if (captureTarget && captureTarget.releasePointerCapture
        && captureTarget.hasPointerCapture(event.pointerId)) {
        captureTarget.releasePointerCapture(event.pointerId);
      }
      this.pointerState = null;
    },
    graphPoint(event) {
      const rect = this.$refs.cyCanvas.getBoundingClientRect();
      return {
        x: (event.clientX - rect.left - this.viewport.x) / this.viewport.scale,
        y: (event.clientY - rect.top - this.viewport.y) / this.viewport.scale
      };
    },
    handleWheel(event) {
      const rect = this.$refs.cyCanvas.getBoundingClientRect();
      const anchorX = event.clientX - rect.left;
      const anchorY = event.clientY - rect.top;
      this.setZoom(this.viewport.scale * (event.deltaY > 0 ? .88 : 1.14), anchorX, anchorY);
    },
    isTypeActive(label) {
      return this.activeTypes.includes(label);
    },
    fitView(nodeIds) {
      if (!this.$refs.cyCanvas || !this.visibleNodes.length) return;
      const nodes = nodeIds
        ? this.visibleNodes.filter(node => nodeIds.has(String(node.id)))
        : this.visibleNodes;
      if (!nodes.length) return;

      const positions = nodes.map(node => this.nodePosition(node.id));
      const minX = Math.min(...positions.map(position => position.x)) - 44;
      const maxX = Math.max(...positions.map(position => position.x)) + 44;
      const minY = Math.min(...positions.map(position => position.y)) - 44;
      const maxY = Math.max(...positions.map(position => position.y)) + 44;
      const rect = this.$refs.cyCanvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const padding = 54;
      const scale = Math.min(
        2.2,
        Math.max(.35, Math.min(
          (rect.width - padding * 2) / Math.max(88, maxX - minX),
          (rect.height - padding * 2) / Math.max(88, maxY - minY)
        ))
      );
      this.viewport = {
        x: rect.width / 2 - (minX + maxX) / 2 * scale,
        y: rect.height / 2 - (minY + maxY) / 2 * scale,
        scale
      };
      this.zoom = scale;
    },
    centerNodeInView(nodeId) {
      if (!this.$refs.cyCanvas) return;
      const rect = this.$refs.cyCanvas.getBoundingClientRect();
      const position = this.nodePosition(nodeId);
      this.viewport = {
        ...this.viewport,
        x: rect.width / 2 - position.x * this.viewport.scale,
        y: rect.height / 2 - position.y * this.viewport.scale
      };
    },
    setZoom(value, anchorX, anchorY) {
      const next = Math.min(2.2, Math.max(.35, value));
      const worldX = (anchorX - this.viewport.x) / this.viewport.scale;
      const worldY = (anchorY - this.viewport.y) / this.viewport.scale;
      this.viewport = {
        x: anchorX - worldX * next,
        y: anchorY - worldY * next,
        scale: next
      };
      this.zoom = next;
    },
    zoomBy(factor) {
      if (!this.$refs.cyCanvas) return;
      const rect = this.$refs.cyCanvas.getBoundingClientRect();
      this.setZoom(this.viewport.scale * factor, rect.width / 2, rect.height / 2);
    },
    async toggleFullscreen() {
      const element = this.$refs.graphStage;
      try {
        if (!document.fullscreenElement && element.requestFullscreen) await element.requestFullscreen();
        else if (document.exitFullscreen) await document.exitFullscreen();
        window.setTimeout(() => this.fitView(), 120);
      } catch (error) {
        this.errorMessage = '当前浏览器无法进入全屏模式。';
      }
    },
    retrySearch() {
      if (this.mode === 'path') this.searchPath();
      else if (this.mode === 'compare') this.compareProducts();
      else this.searchGraph();
    },
    runSample(sample) {
      this.keyword = sample;
      this.searchGraph();
    },
    runPathSample(source, target) {
      this.pathStart = source;
      this.pathEnd = target;
      this.searchPath();
    },
    exportGraph() {
      if (!this.graphData.found) return;
      const payload = {
        title: this.resultTitle,
        queryMode: this.mode,
        query: this.mode === 'path'
          ? { source: this.pathStart, target: this.pathEnd }
          : { keyword: this.keyword },
        exportedAt: new Date().toISOString(),
        nodes: this.visibleNodes,
        relationships: this.visibleEdges,
        pathExplanation: this.mode === 'path' ? this.pathNarrative : null
      };
      this.downloadJson(payload, `agrireg-ai-${this.mode}-${Date.now()}.json`);
      this.announceStatus('查询结果已导出。');
    },
    downloadJson(payload, filename) {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    },
    askAboutNode(name) {
      this.$router.push({
        path: '/ask',
        query: { q: `${name} 与哪些作物、病虫害或有效成分有关？` }
      }).catch(() => {});
    },
    typeColor(label) {
      return this.labelColors[label] || '#6d7e74';
    },
    nodeFill(label) {
      return this.labelFills[label] || '#f4f7f5';
    },
    labelName(label) {
      return this.labelNames[label] || label || '实体';
    },
    relationName(relation) {
      return this.relationNames[relation] || relation || '相关';
    },
    pathRelationName(step) {
      if (step.edge.type === 'INCLUDES'
        && step.from.label === 'ActiveSubstance'
        && step.to.label === 'RegisterNumber') return '出现在登记';
      if (step.edge.type === 'INCLUDES'
        && step.from.label === 'RegisterNumber'
        && step.to.label === 'ActiveSubstance') return '包含成分';
      return this.relationName(step.edge.type);
    },
    isLongProperty(value) {
      return String(value == null ? '' : value).length > 120;
    },
    isPropertyExpanded(key) {
      return this.expandedPropertyKeys.includes(key);
    },
    toggleProperty(key) {
      const index = this.expandedPropertyKeys.indexOf(key);
      if (index >= 0) this.expandedPropertyKeys.splice(index, 1);
      else this.expandedPropertyKeys.push(key);
    },
    propertyName(property) {
      const names = {
        name: '名称',
        'Trade name': '商品名',
        'Pesticide name': '农药名称',
        'Active Ingredient': '有效成分',
        'Field of application': '适用领域',
        'Area of application': '适用范围',
        'Pesticide category': '农药类别',
        'Symptoms of infestation': '危害症状',
        pathogen: '病原体',
        'geographic distribution': '地理分布',
        'Method of application': '施用方法',
        Introduction: '简介',
        'Mode of action': '作用方式',
        'CAS registry number': 'CAS 登记号',
        '2D Chemical structure': '二维结构图',
        'Member State of origin': '登记地区',
        Status: '登记状态',
        'Registration Status': '登记状态',
        'End of approval': '批准有效期',
        'Time expiry date_y': '有效期至',
        'valid until': '有效期至',
        'Start of admission': '准入日期',
        'Date of approval:': '批准日期',
        'Date of reauthorization:': '续展日期'
      };
      return names[property] || property;
    },
    formatCount(value) {
      return Number(value || 0).toLocaleString('zh-CN');
    },
    shortName(name, maxLength) {
      const text = String(name || '未命名实体').replace(/\s+/g, ' ').trim();
      return text.length > maxLength ? text.slice(0, maxLength - 1) + '…' : text;
    },
    announceStatus(message, error = false) {
      if (this.statusTimer) window.clearTimeout(this.statusTimer);
      this.statusMessage = message;
      this.statusError = error;
      this.statusTimer = window.setTimeout(() => {
        this.statusMessage = '';
        this.statusError = false;
        this.statusTimer = null;
      }, 3600);
    },
    prefersReducedMotion() {
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    },
    isHttpUrl(value) {
      return typeof value === 'string' && /^https?:\/\/[^\s]+$/i.test(value);
    }
  }
};
</script>

<style scoped>
.graph-page { max-width: 1680px; margin: 0 auto; color: #163b2e; }
.graph-page button, .graph-page a { touch-action: manipulation; }
.graph-page button:focus-visible, .graph-page input:focus-visible, .graph-page a:focus-visible { outline: 3px solid rgba(23,107,69,.42); outline-offset: 2px; }
.page-intro { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 5px 4px 22px; }
.page-intro p { margin: 0 0 7px; color: #2d7d58; font-size: 12px; font-weight: 800; letter-spacing: .13em; }
.page-intro h1 { margin: 0; font-size: clamp(28px, 3.25vw, 45px); line-height: 1.14; letter-spacing: -.045em; }
.page-intro span { display: block; margin-top: 10px; color: #657c70; font-size: 14px; }
.coverage-strip { display: flex; min-height: 48px; align-items: center; gap: 0; max-width: 980px; margin: -8px auto 14px; overflow: hidden; border: 1px solid #dce7df; border-radius: 12px; background: rgba(255,255,255,.76); }
.coverage-strip > div { display: flex; min-width: 120px; align-items: baseline; gap: 6px; padding: 9px 14px; border-right: 1px solid #e4ebe6; }
.coverage-strip strong { color: #1c6544; font-size: 15px; font-variant-numeric: tabular-nums; }
.coverage-strip span { color: #6d8176; font-size: 10px; white-space: nowrap; }
.coverage-strip p { margin: 0 14px 0 auto; color: #557064; font-size: 10px; line-height: 1.4; text-align: right; }
.mode-switch { display: flex; flex: 0 0 auto; gap: 4px; padding: 4px; border: 1px solid #d5e0d8; border-radius: 12px; background: #fff; }
.mode-switch button { min-height: 40px; padding: 8px 13px; border: 0; border-radius: 8px; background: transparent; color: #61786c; cursor: pointer; font-size: 12px; font-weight: 700; }
.mode-switch button.active { background: #e7f0e9; color: #176b45; }
.search-bar { display: flex; min-height: 58px; align-items: center; max-width: 980px; margin: 0 auto; overflow: hidden; border: 1px solid #c9d9cf; border-radius: 15px; background: #fff; box-shadow: 0 13px 40px rgba(31,71,52,.08); }
.search-bar:focus-within { border-color: #368461; box-shadow: 0 0 0 4px rgba(42,127,87,.1), 0 13px 40px rgba(31,71,52,.08); }
.search-bar > svg { width: 21px; flex: 0 0 auto; margin-left: 18px; fill: none; stroke: #72877b; stroke-width: 1.8; stroke-linecap: round; }
.search-bar input { min-width: 0; height: 56px; flex: 1; padding: 0 14px; border: 0; outline: 0; color: #183b2e; font-size: 14px; }
.search-bar button, .path-search > button, .compare-search > button:last-child { align-self: stretch; min-width: 118px; border: 0; background: #176b45; color: #fff; cursor: pointer; font-size: 12px; font-weight: 800; }
.search-bar button:hover:not(:disabled), .path-search > button:hover:not(:disabled), .compare-search > button:last-child:hover:not(:disabled) { background: #0f5a38; }
.search-bar button:disabled, .path-search > button:disabled, .compare-search > button:last-child:disabled { opacity: .45; cursor: not-allowed; }
.path-search { display: grid; grid-template-columns: minmax(180px,1fr) 32px minmax(180px,1fr) 118px; align-items: end; gap: 12px; max-width: 980px; margin: 0 auto; padding: 13px; border: 1px solid #c9d9cf; border-radius: 15px; background: #fff; box-shadow: 0 13px 40px rgba(31,71,52,.08); }
.path-search div { min-width: 0; }
.path-search .path-explainer { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 8px; padding: 0 2px 2px; color: #657c70; font-size: 11px; line-height: 1.5; }
.path-explainer strong { flex: 0 0 auto; color: #245f45; }
.path-search label { display: block; margin-bottom: 5px; color: #61786c; font-size: 11px; font-weight: 700; }
.path-search input { width: 100%; height: 40px; padding: 0 10px; border: 1px solid #d8e3db; border-radius: 9px; outline: 0; color: #183b2e; font-size: 13px; }
.path-search input:focus { border-color: #6c9d82; box-shadow: 0 0 0 3px rgba(42,127,87,.08); }
.path-search > svg { width: 20px; margin: 0 auto 10px; fill: none; stroke: #759084; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.path-search > button { min-height: 39px; border-radius: 9px; }
.compare-search { display: grid; grid-template-columns: minmax(190px,1fr) 42px minmax(190px,1fr) 118px; align-items: end; gap: 10px; max-width: 980px; margin: 0 auto; padding: 13px; border: 1px solid #c9d9cf; border-radius: 15px; background: #fff; box-shadow: 0 13px 40px rgba(31,71,52,.08); }
.compare-explainer { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 8px; color: #657c70; font-size: 11px; }
.compare-explainer strong { color: #245f45; }
.compare-search label { display: block; margin-bottom: 5px; color: #61786c; font-size: 11px; font-weight: 700; }
.compare-search input { width: 100%; height: 40px; padding: 0 10px; border: 1px solid #d8e3db; border-radius: 9px; outline: 0; color: #183b2e; font-size: 13px; }
.compare-search input:focus { border-color: #6c9d82; box-shadow: 0 0 0 3px rgba(42,127,87,.08); }
.compare-search .swap-products { display: grid; width: 40px; height: 40px; place-items: center; padding: 0; border: 1px solid #d2dfd6; border-radius: 9px; background: #f7faf8; color: #557467; cursor: pointer; }
.swap-products:hover { border-color: #80a591; color: #176b45; }
.swap-products svg { width: 17px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.compare-search > button:last-child { min-height: 40px; border-radius: 9px; }
.sample-row { display: flex; min-height: 46px; align-items: center; justify-content: center; flex-wrap: wrap; gap: 7px; padding: 8px 0; }
.sample-row > span { color: #6d8377; font-size: 12px; }
.sample-row button { min-height: 34px; padding: 7px 11px; border: 1px solid #d7e2da; border-radius: 999px; background: #fbfdfb; color: #516c5d; cursor: pointer; font-size: 11px; }
.sample-row button:hover { border-color: #84aa94; color: #176b45; }
.compare-workspace { min-height: 600px; padding: clamp(18px,2.4vw,34px); border: 1px solid #d9e4dc; border-radius: 18px; background: #f8faf8; box-shadow: 0 22px 60px rgba(28,63,47,.08); }
.compare-state { display: grid; min-height: 530px; align-content: center; justify-items: center; color: #365748; text-align: center; }
.compare-state strong { font-size: 16px; }
.compare-state p { margin: 8px 0 0; color: #72877c; font-size: 12px; }
.compare-state button { min-height: 40px; margin-top: 14px; padding: 8px 14px; border: 0; border-radius: 9px; background: #176b45; color: #fff; cursor: pointer; }
.comparison-header { display: grid; grid-template-columns: minmax(0,1fr) 132px minmax(0,1fr); align-items: stretch; gap: 14px; }
.product-card { min-width: 0; padding: 22px; border: 1px solid #d9e5dd; border-radius: 15px; background: #fff; }
.product-card > span { color: #668074; font-size: 10px; font-weight: 800; letter-spacing: .05em; }
.product-card h2 { margin: 8px 0 0; overflow-wrap: anywhere; font-size: 22px; line-height: 1.25; }
.product-card p { margin: 8px 0 0; color: #657c70; font-size: 12px; line-height: 1.55; }
.product-card button { min-height: 38px; margin-top: 17px; padding: 8px 11px; border: 1px solid #cfded4; border-radius: 9px; background: #fff; color: #266c4d; cursor: pointer; font-size: 11px; font-weight: 800; }
.product-card button:hover { border-color: #79a28b; }
.product-card.right { text-align: right; }
.comparison-score { display: grid; align-content: center; justify-items: center; padding: 14px 6px; border-radius: 15px; background: #173c2e; color: #fff; text-align: center; }
.comparison-score strong { color: #c9ef78; font-size: 34px; font-variant-numeric: tabular-nums; }
.comparison-score span { margin-top: 1px; font-size: 11px; font-weight: 800; }
.comparison-score small { margin-top: 8px; color: #b9cbc2; font-size: 10px; }
.comparison-actions { display: flex; justify-content: flex-end; gap: 8px; margin: 13px 0 22px; }
.comparison-actions button { min-height: 40px; padding: 8px 13px; border: 1px solid #cddbd2; border-radius: 9px; background: #fff; color: #3e6251; cursor: pointer; font-size: 11px; font-weight: 800; }
.comparison-actions button:first-child { border-color: #176b45; background: #176b45; color: #fff; }
.comparison-block { margin-top: 16px; overflow: hidden; border: 1px solid #dce6df; border-radius: 15px; background: #fff; }
.comparison-title { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding: 18px 20px; border-bottom: 1px solid #e4ebe6; }
.comparison-title span { color: #2d7d58; font-size: 10px; font-weight: 800; letter-spacing: .08em; }
.comparison-title h3 { margin: 4px 0 0; font-size: 16px; }
.comparison-title p { max-width: 380px; margin: 0; color: #71867b; font-size: 10px; line-height: 1.5; text-align: right; }
.comparison-table { overflow-x: auto; }
.comparison-row { display: grid; min-width: 720px; grid-template-columns: 130px minmax(190px,1fr) minmax(190px,1fr) 70px; align-items: start; border-bottom: 1px solid #edf1ee; }
.comparison-row:last-child { border-bottom: 0; }
.comparison-row > * { min-width: 0; padding: 12px 14px; overflow-wrap: anywhere; color: #3e5e50; font-size: 11px; line-height: 1.55; }
.comparison-row.heading { background: #f5f8f6; }
.comparison-row.heading span { color: #637a6e; font-size: 10px; font-weight: 800; }
.comparison-row em { display: inline-flex; min-height: 24px; width: max-content; align-items: center; align-self: center; margin: 8px 14px; padding: 3px 7px; border-radius: 999px; background: #fff0eb; color: #a54e32; font-size: 10px; font-style: normal; font-weight: 800; }
.comparison-row em.same { background: #e8f3eb; color: #27704f; }
.relation-comparison article { padding: 0 20px 20px; }
.relation-comparison article + article { border-top: 1px solid #e6ede8; }
.relation-comparison article > header { display: flex; align-items: center; justify-content: space-between; padding: 17px 0 10px; }
.relation-comparison h4 { margin: 0; font-size: 13px; }
.relation-comparison article > header span { color: #70867a; font-size: 10px; font-variant-numeric: tabular-nums; }
.relation-diff-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; }
.relation-diff-grid > div { min-width: 0; padding: 13px; border: 1px solid #e2eae5; border-radius: 11px; background: #fafcfa; }
.relation-diff-grid strong { display: block; margin-bottom: 9px; color: #5c7468; font-size: 10px; }
.relation-diff-grid p { margin: 0; color: #91a097; font-size: 10px; }
.relation-diff-grid > div > div { display: flex; flex-wrap: wrap; gap: 6px; }
.relation-diff-grid span { max-width: 100%; padding: 5px 7px; overflow-wrap: anywhere; border-radius: 7px; background: #edf2ee; color: #426151; font-size: 10px; }
.relation-diff-grid span.common { background: #e3f1e7; color: #206a48; font-weight: 800; }
.workspace { display: grid; grid-template-columns: 224px minmax(520px,1fr) 310px; height: clamp(620px, calc(100dvh - 220px), 760px); min-height: 0; overflow: hidden; border: 1px solid #d9e4dc; border-radius: 18px; background: #fff; box-shadow: 0 22px 60px rgba(28,63,47,.08); }
.workspace.filter-collapsed { grid-template-columns: minmax(520px,1fr) 310px; }
.workspace.detail-collapsed { grid-template-columns: 224px minmax(520px,1fr); }
.workspace.filter-collapsed.detail-collapsed { grid-template-columns: minmax(520px,1fr); }
.filter-panel, .detail-panel { min-width: 0; min-height: 0; background: #fff; }
.filter-panel { display: flex; flex-direction: column; border-right: 1px solid #e0e8e2; }
.detail-panel { display: flex; overflow: hidden; flex-direction: column; border-left: 1px solid #e0e8e2; }
.panel-heading { display: flex; min-height: 58px; align-items: center; justify-content: space-between; padding: 12px 15px; border-bottom: 1px solid #e5ece7; }
.panel-heading > span { font-size: 12px; font-weight: 800; }
.panel-heading button { min-height: 32px; border: 0; background: transparent; color: #2f7756; cursor: pointer; font-size: 11px; }
.panel-heading > div { display: flex; align-items: center; gap: 4px; }
.detail-heading i { width: 9px; height: 9px; border-radius: 50%; }
.detail-heading button { width: 32px; padding: 0; color: #6c8176; font-size: 18px; line-height: 1; }
.type-list { display: grid; min-height: 0; gap: 4px; padding: 10px; overflow-y: auto; }
.type-list button { display: grid; min-height: 46px; grid-template-columns: 10px 1fr 16px; align-items: center; gap: 8px; width: 100%; padding: 9px 8px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: #3e5e50; cursor: pointer; text-align: left; }
.type-list button:hover { background: #f3f7f4; }
.type-list button.inactive { opacity: .4; }
.type-list i { width: 8px; height: 8px; border-radius: 50%; }
.type-list strong, .type-list small { display: block; }
.type-list strong { font-size: 12px; }
.type-list small { margin-top: 3px; color: #70867a; font-size: 10px; }
.type-list svg { width: 15px; fill: none; stroke: #4c8468; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.type-list button.inactive svg { visibility: hidden; }
.filter-empty { padding: 20px 16px; color: #71867b; font-size: 11px; line-height: 1.65; }
.interaction-help { margin-top: auto; padding: 16px; border-top: 1px solid #e5ece7; background: #fafcf9; }
.interaction-help > p { margin: 0 0 9px; color: #526e60; font-size: 11px; font-weight: 800; }
.interaction-help dl { display: grid; gap: 7px; margin: 0; }
.interaction-help dl div { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; }
.interaction-help dt { color: #557065; font-weight: 700; }
.interaction-help dd { margin: 0; color: #93a299; }
.network-panel { min-width: 0; min-height: 0; display: flex; flex-direction: column; background: #f8faf8; }
.network-toolbar { display: flex; min-height: 59px; align-items: center; justify-content: space-between; padding: 10px 13px 10px 17px; border-bottom: 1px solid #e0e8e2; background: #fff; }
.result-summary strong, .result-summary span { display: block; }
.result-summary strong { max-width: 430px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.result-summary span { margin-top: 4px; color: #6e8378; font-size: 11px; font-variant-numeric: tabular-nums; }
.tool-actions { display: flex; align-items: center; gap: 4px; }
.tool-actions button { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid #cbd9d0; border-radius: 9px; background: #fff; color: #506b5c; cursor: pointer; }
.tool-actions button:hover { border-color: #8db09b; color: #176b45; }
.tool-actions button:disabled { opacity: .38; cursor: not-allowed; }
.tool-actions svg { width: 14px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.tool-actions span { min-width: 40px; color: #60786b; text-align: center; font-size: 11px; font-variant-numeric: tabular-nums; }
.evidence-highlight-banner { display: flex; min-height: 54px; align-items: center; justify-content: space-between; gap: 14px; padding: 9px 16px; border-bottom: 1px solid #ead9a8; background: #fff9e8; }
.evidence-highlight-banner span, .evidence-highlight-banner strong { display: block; }
.evidence-highlight-banner span { color: #8a681d; font-size: 9px; font-weight: 800; letter-spacing: .06em; }
.evidence-highlight-banner strong { margin-top: 3px; color: #5f4a1f; font-size: 11px; line-height: 1.45; }
.evidence-highlight-banner button { min-height: 34px; flex: 0 0 auto; padding: 7px 9px; border: 1px solid #dbc784; border-radius: 8px; background: #fffdf5; color: #75591b; cursor: pointer; font-size: 10px; font-weight: 800; }
.graph-stage { position: relative; min-height: 0; flex: 1; overflow: hidden; background: radial-gradient(circle at 50% 44%, #fff 0, #f7faf7 66%, #eef4ef 100%); }
.graph-stage:fullscreen { width: 100vw; height: 100vh; background: #f7faf7; }
.network-grid { position: absolute; inset: 0; opacity: .42; background-image: radial-gradient(#c7d7cc 1px, transparent 1px); background-size: 25px 25px; mask-image: radial-gradient(circle at center, #000 28%, transparent 88%); }
.cy-canvas { position: absolute; z-index: 1; inset: 0; width: 100%; height: 100%; overflow: hidden; touch-action: none; user-select: none; cursor: grab; }
.cy-canvas:active { cursor: grabbing; }
.svg-edge { opacity: 1; transition: opacity .16s ease; }
.svg-edge line { stroke: #aebfb4; stroke-width: 1.4; vector-effect: non-scaling-stroke; }
.svg-edge text { fill: #667e71; stroke: rgba(255,255,255,.94); stroke-width: 5px; paint-order: stroke; text-anchor: middle; font-size: 8px; font-weight: 700; pointer-events: none; }
.svg-edge.focused line { stroke: #6f9d82; stroke-width: 2.2; }
.svg-edge.dimmed, .svg-node.dimmed { opacity: .13; }
.svg-edge.evidence { opacity: 1; }
.svg-edge.evidence line { stroke: #c18a12; stroke-width: 4; }
.svg-edge.evidence text { fill: #7c580d; font-size: 9px; }
.svg-node { outline: none; cursor: grab; transition: opacity .16s ease; }
.svg-node:active { cursor: grabbing; }
.svg-node circle { stroke-width: 2; vector-effect: non-scaling-stroke; }
.svg-node.center circle { stroke: #0d5937; stroke-width: 3; }
.svg-node.selected circle, .svg-node:focus-visible circle { stroke: #122f25; stroke-width: 5; }
.svg-node.evidence { opacity: 1; }
.svg-node.evidence circle { stroke: #c18a12; stroke-width: 6; filter: drop-shadow(0 0 7px rgba(193,138,18,.42)); }
.svg-node text { fill: #294e3e; stroke: rgba(255,255,255,.92); stroke-width: 4px; paint-order: stroke; text-anchor: middle; dominant-baseline: middle; font-size: 9px; font-weight: 700; pointer-events: none; }
.svg-node.center text:not(.image-label) { fill: #fff; stroke: rgba(13,89,55,.8); }
.svg-node text.image-label { transform: translateY(49px); }
.canvas-state { position: absolute; z-index: 3; inset: 0; display: grid; align-content: center; justify-items: center; padding: 30px; background: rgba(248,250,248,.7); text-align: center; backdrop-filter: blur(2px); }
.canvas-state > svg { width: 48px; margin-bottom: 14px; fill: none; stroke: #8da295; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.canvas-state h2 { margin: 0; font-size: 16px; }
.canvas-state p { max-width: 380px; margin: 8px 0 0; color: #7b8f83; font-size: 11px; line-height: 1.6; }
.canvas-state button { margin-top: 14px; padding: 9px 14px; border: 0; border-radius: 8px; background: #176b45; color: #fff; cursor: pointer; }
.error-state > svg { stroke: #c86743; }
.loader { width: 32px; height: 32px; margin-bottom: 14px; border: 3px solid #dbe6de; border-top-color: #176b45; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.seed-graph { position: relative; display: grid; width: 132px; height: 116px; margin-bottom: 16px; place-items: center; }
.seed-graph strong { display: grid; z-index: 2; width: 62px; height: 62px; place-items: center; border-radius: 50%; background: #176b45; color: #fff; font-size: 13px; }
.seed-graph i { position: absolute; width: 25px; height: 25px; border: 2px solid #87a795; border-radius: 50%; background: #fff; }
.seed-graph i::after { position: absolute; top: 10px; width: 42px; height: 1px; background: #aec2b6; content: ''; }
.seed-graph i:nth-child(1) { top: 0; left: 53px; }.seed-graph i:nth-child(1)::after { transform: rotate(90deg); transform-origin: left; }
.seed-graph i:nth-child(2) { top: 45px; right: 0; }.seed-graph i:nth-child(2)::after { right: 21px; }
.seed-graph i:nth-child(3) { bottom: 0; left: 53px; }.seed-graph i:nth-child(3)::after { transform: rotate(90deg); transform-origin: left; }
.seed-graph i:nth-child(4) { top: 45px; left: 0; }.seed-graph i:nth-child(4)::after { left: 21px; }
.truncate-badge { position: absolute; z-index: 2; right: 13px; bottom: 13px; padding: 7px 10px; border: 1px solid #d4dfd7; border-radius: 999px; background: rgba(255,255,255,.91); color: #60776b; font-size: 10px; backdrop-filter: blur(8px); }
.expand-status { position: absolute; z-index: 4; left: 50%; bottom: 17px; display: flex; min-height: 38px; align-items: center; gap: 8px; max-width: min(420px,calc(100% - 32px)); padding: 8px 13px; transform: translateX(-50%); border: 1px solid #cbded2; border-radius: 999px; background: rgba(255,255,255,.96); box-shadow: 0 8px 24px rgba(32,70,52,.13); color: #315f49; font-size: 11px; font-weight: 700; }
.expand-status.error { border-color: #e4b8aa; color: #a34f32; }
.mini-loader { width: 15px; height: 15px; flex: 0 0 auto; border: 2px solid #d9e6dd; border-top-color: #176b45; border-radius: 50%; animation: spin .7s linear infinite; }
.entity-summary { display: grid; grid-template-columns: 76px minmax(0,1fr); align-items: center; gap: 12px; padding: 14px 15px 12px; }
.entity-summary.without-image { grid-template-columns: 1fr; }
.entity-image { width: 76px; height: 76px; overflow: hidden; border: 1px solid #dfe8e2; border-radius: 12px; background: #eef3ef; }
.entity-image img { width: 100%; height: 100%; object-fit: cover; }
.entity-identity { min-width: 0; }
.entity-identity span { display: inline-block; padding: 4px 7px; border-radius: 999px; background: #edf3ee; color: #4f6b5c; font-size: 10px; font-weight: 700; }
.entity-identity h2 { margin: 7px 0 0; overflow-wrap: anywhere; font-size: 16px; line-height: 1.3; }
.entity-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; padding: 0 15px 15px; }
.entity-actions button { display: flex; min-height: 42px; align-items: center; justify-content: center; gap: 6px; border: 1px solid #d3e0d7; border-radius: 9px; background: #fff; color: #416051; cursor: pointer; font-size: 11px; font-weight: 700; }
.entity-actions button:first-child { border-color: #176b45; background: #176b45; color: #fff; }
.entity-actions button:hover:not(:disabled) { border-color: #79a28b; }
.entity-actions button:disabled { opacity: .45; cursor: not-allowed; }
.entity-actions svg { width: 13px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.detail-tabs { display: grid; grid-template-columns: repeat(3,1fr); gap: 4px; margin: 0 15px; padding: 4px; border: 1px solid #dfe8e2; border-radius: 10px; background: #f5f8f6; }
.detail-tabs button { min-height: 36px; border: 0; border-radius: 7px; background: transparent; color: #667c70; cursor: pointer; font-size: 11px; font-weight: 700; }
.detail-tabs button span { margin-left: 4px; color: #87998f; font-variant-numeric: tabular-nums; }
.detail-tabs button.active { background: #fff; box-shadow: 0 1px 5px rgba(28,63,47,.1); color: #176b45; }
.detail-tabs button:disabled { opacity: .42; cursor: not-allowed; }
.detail-scroll { min-height: 0; flex: 1; margin-top: 10px; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.relation-list, .property-list { padding: 4px 15px 18px; }
.relation-list button { display: flex; min-height: 38px; width: 100%; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 0; border: 0; border-bottom: 1px solid #edf1ee; background: transparent; color: #365b49; cursor: pointer; text-align: left; font-size: 11px; }
.relation-list button:last-child { border-bottom: 0; }
.relation-list button:hover span { color: #176b45; }
.relation-list button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.relation-list button small { flex: 0 0 auto; padding: 3px 6px; border-radius: 999px; background: #edf3ee; color: #637a6e; font-size: 10px; }
.property-list dl { display: grid; gap: 0; margin: 0; }
.property-item { display: grid; grid-template-columns: 82px minmax(0,1fr); gap: 10px; padding: 10px 0; border-bottom: 1px solid #edf1ee; }
.property-item:last-child { border-bottom: 0; }
.property-list dt { color: #74887e; font-size: 10px; line-height: 1.45; }
.property-list dd { min-width: 0; margin: 0; overflow-wrap: anywhere; color: #365748; font-size: 11px; line-height: 1.55; }
.property-list dd > span { display: -webkit-box; overflow: hidden; white-space: pre-wrap; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.property-list dd > span.expanded { display: block; overflow: visible; -webkit-line-clamp: unset; }
.property-list dd button { min-height: 28px; margin-top: 5px; padding: 2px 0; border: 0; background: transparent; color: #277451; cursor: pointer; font-size: 10px; font-weight: 800; }
.property-list a { color: #24714f; }
.evidence-panel { padding: 4px 15px 20px; }
.evidence-status { padding: 13px; border: 1px solid #d9e8de; border-radius: 11px; background: linear-gradient(135deg,#f1f7f3,#fbfdfb); }
.evidence-status span, .evidence-status strong { display: block; }
.evidence-status span { color: #648073; font-size: 9px; font-weight: 800; letter-spacing: .08em; }
.evidence-status strong { margin-top: 5px; color: #21563e; font-size: 12px; line-height: 1.45; }
.evidence-panel dl { display: grid; gap: 0; margin: 10px 0 0; }
.evidence-panel dl div { display: grid; grid-template-columns: 78px minmax(0,1fr); gap: 9px; padding: 9px 0; border-bottom: 1px solid #edf1ee; }
.evidence-panel dt { color: #7b8d83; font-size: 10px; }
.evidence-panel dd { margin: 0; overflow-wrap: anywhere; color: #365748; font-size: 11px; line-height: 1.5; }
.evidence-panel > a { display: inline-flex; min-height: 34px; align-items: center; margin-top: 12px; color: #24714f; font-size: 10px; font-weight: 800; }
.evidence-panel > p { margin: 13px 0 0; color: #71867b; font-size: 10px; line-height: 1.6; }
.no-properties { padding: 18px 0; color: #71867b; font-size: 11px; }
.detail-empty { display: grid; min-height: 0; flex: 1; align-content: center; justify-items: center; padding: 28px; text-align: center; }
.detail-empty svg { width: 46px; fill: none; stroke: #a3b2aa; stroke-width: 1.4; }
.detail-empty p { max-width: 210px; margin: 13px 0 0; color: #71867b; font-size: 11px; line-height: 1.65; }
.graph-page {
  --ink: #172033;
  --muted: #667085;
  --line: #dbe2ef;
  --glass: rgba(255, 255, 255, .92);
  --glass-strong: #f8f9fc;
  --accent: #4f6ef7;
  --accent-strong: #3654d8;
  --canvas: #0b1630;
  max-width: 1860px;
  color: var(--ink);
}
.graph-page button:focus-visible,
.graph-page input:focus-visible,
.graph-page a:focus-visible { outline-color: #4f6ef7; box-shadow: 0 0 0 5px rgba(79, 110, 247, .13); }
.page-intro { align-items: center; min-height: 62px; padding: 0 4px 14px; }
.page-intro p { margin-bottom: 4px; color: #4f6ef7; font-size: 9px; letter-spacing: .22em; }
.page-intro h1 { font-size: clamp(25px, 2.2vw, 34px); letter-spacing: -.035em; }
.page-intro span { margin-top: 5px; color: #667085; font-size: 12px; }
.mode-switch { border-color: var(--line); border-radius: 14px; background: #fff; box-shadow: 0 5px 18px rgba(32, 49, 83, .06); }
.mode-switch button { min-height: 38px; color: #667085; }
.mode-switch button:hover { color: #2946be; }
.mode-switch button.active { background: #eef2ff; color: #3654d8; box-shadow: inset 0 0 0 1px #dce4ff; }
.coverage-strip { display: grid; min-height: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); max-width: none; margin: auto 11px 10px; border-color: var(--line); background: #fff; box-shadow: none; }
.coverage-strip > div { display: grid; min-width: 0; gap: 1px; padding: 9px 10px; border-right-color: var(--line); border-bottom: 1px solid var(--line); }
.coverage-strip > div:nth-child(even) { border-right: 0; }
.coverage-strip > div:nth-last-child(-n+2) { border-bottom: 0; }
.coverage-strip strong { color: #3654d8; }
.coverage-strip span, .coverage-strip p { color: #7a8497; }
.coverage-strip p { grid-column: 1 / -1; margin: 0; padding: 8px 10px; border-top: 1px solid var(--line); text-align: left; }
.search-bar, .path-search, .compare-search {
  max-width: 1080px;
  border-color: #dbe2ef;
  background: #fff;
  box-shadow: 0 12px 34px rgba(32, 49, 83, .08);
}
.search-bar { min-height: 54px; }
.search-bar:focus-within { border-color: #96a9ff; box-shadow: 0 0 0 4px rgba(79, 110, 247, .09), 0 12px 34px rgba(32, 49, 83, .08); }
.search-bar > svg { color: #74809a; stroke: currentColor; }
.search-bar input, .path-search input, .compare-search input { color: #172033; caret-color: #4f6ef7; }
.search-bar input { height: 52px; background: transparent; }
.search-bar input::placeholder, .path-search input::placeholder, .compare-search input::placeholder { color: #8a94a7; opacity: 1; }
.search-bar button, .path-search > button, .compare-search > button:last-child { background: #4f6ef7; }
.search-bar button:hover:not(:disabled), .path-search > button:hover:not(:disabled), .compare-search > button:last-child:hover:not(:disabled) { background: #3e5de2; }
.path-search .path-explainer, .compare-explainer, .path-search label, .compare-search label { color: #667085; }
.path-explainer strong, .compare-explainer strong { color: #3654d8; }
.path-search input, .compare-search input, .compare-search .swap-products { border-color: var(--line); background: #f8f9fc; }
.compare-search .swap-products { color: #56627a; }
.sample-row { min-height: 40px; padding: 5px 0 8px; }
.sample-row > span { color: #7a8497; }
.sample-row button { min-height: 31px; border-color: var(--line); background: #fff; color: #56627a; }
.sample-row button:hover { border-color: #9bacf7; color: #3654d8; }
.graph-page button:active:not(:disabled) { filter: brightness(1.12); }
.workspace {
  grid-template-columns: 232px minmax(520px, 1fr) 328px;
  height: clamp(460px, calc(100dvh - 252px), 820px);
  border-color: #d7dfec;
  border-radius: 24px;
  background: var(--canvas);
  box-shadow: 0 22px 60px rgba(35, 48, 82, .12);
}
.filter-panel, .detail-panel { background: var(--glass-strong); }
.filter-panel { border-right-color: var(--line); }
.detail-panel { border-left-color: var(--line); }
.panel-heading { min-height: 56px; border-bottom-color: var(--line); }
.panel-heading > span { color: #26324a; letter-spacing: .04em; }
.panel-heading button { color: #4f6ef7; }
.detail-heading button { color: #7a8497; }
.type-list { flex: 1; gap: 5px; padding: 11px; scrollbar-color: #c7d0e0 transparent; }
.type-list button { color: #39445b; }
.type-list button:hover { border-color: #e1e6f0; background: #f0f3f9; }
.type-list button.inactive { opacity: .35; }
.type-list small, .filter-empty { color: #7b8497; }
.type-list svg { stroke: #6076dd; }
.interaction-help { margin-top: 0; border-top-color: var(--line); background: #f2f4f8; }
.interaction-help > p, .interaction-help dt { color: #56627a; }
.interaction-help dd { color: #8a94a7; }
.network-panel { position: relative; background: var(--canvas); }
.network-toolbar {
  position: absolute;
  z-index: 6;
  inset: 14px;
  min-height: 0;
  padding: 0;
  border: 0;
  background: transparent;
  pointer-events: none;
}
.result-summary {
  max-width: min(420px, calc(100% - 100px));
  padding: 10px 14px;
  border: 1px solid rgba(175, 191, 225, .24);
  border-radius: 13px;
  background: rgba(19, 31, 66, .82);
  box-shadow: 0 10px 30px rgba(3, 8, 25, .22);
  backdrop-filter: blur(16px);
  pointer-events: auto;
}
.result-summary strong { color: #f7f9ff; }
.result-summary span { color: #a7b3ce; }
.result-summary.path-result { max-width: min(620px, calc(100% - 80px)); padding: 13px 15px 12px; }
.result-summary .result-eyebrow { margin-bottom: 5px; color: #98a9ff; font-size: 9px; font-weight: 800; letter-spacing: .12em; }
.result-summary.path-result strong { font-size: 14px; }
.result-summary.path-result p { margin: 6px 0 8px; color: #d5dced; font-size: 11px; line-height: 1.5; }
.result-summary.path-result ol { display: flex; min-width: 0; align-items: center; gap: 6px; margin: 0; padding: 0 0 8px; overflow-x: auto; list-style: none; }
.result-summary.path-result li { display: flex; flex: 0 0 auto; align-items: center; gap: 6px; color: #e9edfa; font-size: 10px; white-space: nowrap; }
.result-summary.path-result li small { padding: 3px 7px; border-radius: 999px; background: rgba(116, 138, 245, .18); color: #b8c4ff; font-size: 9px; font-weight: 800; }
.result-summary .result-metrics { padding-top: 7px; border-top: 1px solid rgba(177,190,222,.16); }
.tool-actions {
  position: absolute;
  bottom: 0;
  left: 50%;
  gap: 5px;
  padding: 6px;
  transform: translateX(-50%);
  border: 1px solid rgba(175, 191, 225, .22);
  border-radius: 15px;
  background: rgba(16, 28, 61, .86);
  box-shadow: 0 18px 42px rgba(3,8,25,.3), inset 0 1px rgba(255,255,255,.04);
  backdrop-filter: blur(18px);
  pointer-events: auto;
}
.tool-actions button { border-color: transparent; background: transparent; color: #aab5ce; }
.tool-actions button:hover { border-color: rgba(151, 170, 255, .24); background: rgba(114, 137, 248, .13); color: #dbe2ff; }
.tool-actions span { color: #aab5ce; }
.evidence-highlight-banner { position: absolute; z-index: 5; top: 76px; right: 16px; left: 16px; border: 1px solid rgba(231, 191, 90, .27); border-radius: 13px; background: rgba(49, 40, 15, .9); box-shadow: 0 12px 34px rgba(0,0,0,.24); }
.evidence-highlight-banner span { color: #dfbd63; }
.evidence-highlight-banner strong { color: #f3e7bd; }
.evidence-highlight-banner button { border-color: rgba(232, 195, 99, .28); background: rgba(255,255,255,.04); color: #e5cb83; }
.graph-stage, .graph-stage:fullscreen {
  background:
    radial-gradient(circle at 52% 46%, rgba(78, 101, 205, .26), transparent 28rem),
    radial-gradient(circle at 84% 12%, rgba(55, 137, 190, .14), transparent 24rem),
    linear-gradient(145deg, #0b1630 0%, #101d3d 48%, #081126 100%);
}
.network-grid {
  opacity: .58;
  background-image:
    radial-gradient(circle, rgba(190, 201, 255, .52) 0 1px, transparent 1.4px),
    radial-gradient(circle, rgba(115, 184, 225, .34) 0 1px, transparent 1.4px),
    linear-gradient(rgba(148, 164, 225, .03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 164, 225, .03) 1px, transparent 1px);
  background-position: 0 0, 42px 66px, 0 0, 0 0;
  background-size: 132px 132px, 181px 181px, 34px 34px, 34px 34px;
  mask-image: radial-gradient(circle at center, #000 18%, rgba(0,0,0,.68) 66%, transparent 100%);
}
.svg-edge line { stroke: rgba(131, 151, 220, .38); stroke-width: 1.25; }
.svg-edge text { fill: #a6b3d3; stroke: rgba(8, 17, 38, .94); stroke-width: 5px; }
.svg-edge.focused line { stroke: rgba(145, 164, 255, .86); stroke-width: 2.1; filter: drop-shadow(0 0 4px rgba(99, 124, 242, .38)); }
.svg-edge.dimmed, .svg-node.dimmed { opacity: .1; }
.svg-edge.evidence line { stroke: #e2b84f; filter: drop-shadow(0 0 5px rgba(226,184,79,.5)); }
.svg-edge.evidence text { fill: #f0cc70; }
.svg-node .node-core { filter: drop-shadow(0 5px 10px rgba(0,0,0,.34)); }
.svg-node .node-halo { opacity: .72; stroke-width: 2; stroke-dasharray: 3 5; filter: url(#graph-node-glow); }
.svg-node.center .node-core { stroke: #9baaff; stroke-width: 3; }
.svg-node.selected .node-core, .svg-node:focus-visible .node-core { stroke: #d9e0ff; stroke-width: 4; filter: drop-shadow(0 0 12px rgba(118, 142, 255, .62)); }
.svg-node:hover .node-core { stroke-width: 3; filter: drop-shadow(0 0 9px rgba(118, 142, 255, .42)); }
.svg-node.evidence .node-core { stroke: #e7bd54; filter: drop-shadow(0 0 10px rgba(226,184,79,.56)); }
.svg-node text { fill: #edf1ff; stroke: rgba(7, 15, 34, .96); stroke-width: 5px; font-size: 9px; }
.svg-node.center text:not(.image-label) { fill: #fff; stroke: rgba(7, 15, 34, .94); }
.svg-node text.image-label { transform: translateY(39px); }
.svg-node text.image-label.center-label { transform: translateY(54px); }
.canvas-state { background: rgba(9, 18, 41, .78); color: #f1f4ff; backdrop-filter: blur(7px); }
.canvas-state > svg { stroke: #8493bd; }
.canvas-state p { color: #9da8c3; }
.canvas-state button { background: #4f6ef7; }
.loader { border-color: rgba(142, 159, 218, .22); border-top-color: #8fa2ff; }
.seed-graph strong { background: #4f6ef7; box-shadow: 0 0 35px rgba(79, 110, 247, .28); }
.seed-graph i { border-color: #60709c; background: #162347; }
.seed-graph i::after { background: #46577f; }
.truncate-badge, .expand-status { border-color: rgba(176,190,225,.22); background: rgba(17, 29, 62, .9); color: #b1bdd8; }
.detail-panel { box-shadow: -14px 0 36px rgba(35,48,82,.06); }
.entity-summary { grid-template-columns: 1fr; align-items: start; gap: 12px; padding: 15px; }
.entity-image { width: 100%; height: 138px; border-color: var(--line); border-radius: 14px; background: #eef1f7; }
.entity-identity span { background: #eef2ff; color: #4963d4; }
.entity-identity h2 { color: #172033; font-size: 18px; }
.entity-actions button { border-color: var(--line); background: #fff; color: #56627a; }
.entity-actions button:first-child { border-color: #4f6ef7; background: #4f6ef7; color: #fff; }
.detail-tabs { border-color: var(--line); background: #eef1f6; }
.detail-tabs button { color: #667085; }
.detail-tabs button.active { background: #fff; box-shadow: 0 2px 7px rgba(35,48,82,.08); color: #3654d8; }
.detail-tabs button span { color: #8993a6; }
.detail-scroll { scrollbar-color: #c7d0e0 transparent; }
.relation-list button { border-bottom-color: var(--line); color: #39445b; }
.relation-list button:hover span { color: #3654d8; }
.relation-list button small { background: #eef1f6; color: #69758b; }
.property-item, .evidence-panel dl div { border-bottom-color: var(--line); }
.property-list dt, .evidence-panel dt { color: #7a8497; }
.property-list dd, .evidence-panel dd { color: #39445b; }
.property-list dd button, .property-list a, .evidence-panel > a { color: #3654d8; }
.evidence-status { border-color: #e1e6f0; background: #f5f7fb; }
.evidence-status span { color: #7a8497; }
.evidence-status strong { color: #34425e; }
.evidence-panel > p, .no-properties, .detail-empty p { color: #7a8497; }
.detail-empty svg { stroke: #8d98ad; }
.compare-workspace { border-color: var(--line); background: #f8f9fc; box-shadow: 0 20px 54px rgba(35,48,82,.1); color: #172033; }
.compare-state { color: #26324a; }
.compare-state p { color: #7a8497; }
.compare-state button { background: #4f6ef7; }
.product-card, .comparison-block { border-color: var(--line); background: #fff; }
.product-card > span, .product-card p, .comparison-title p { color: #7a8497; }
.product-card button, .comparison-actions button { border-color: var(--line); background: #fff; color: #4b5870; }
.product-card button:hover, .comparison-actions button:hover { border-color: #9bacf7; color: #3654d8; }
.comparison-actions button:first-child { border-color: #4f6ef7; background: #4f6ef7; color: #fff; }
.comparison-score { background: #203264; }
.comparison-title, .relation-comparison article + article, .comparison-row { border-color: var(--line); }
.comparison-title span { color: #4f6ef7; }
.comparison-row > * { color: #39445b; }
.comparison-row.heading, .relation-diff-grid > div { background: #f6f7fa; }
.comparison-row.heading span, .relation-diff-grid strong, .relation-comparison article > header span { color: #7a8497; }
.relation-diff-grid > div { border-color: var(--line); }
.relation-diff-grid span { background: #edf0f5; color: #56627a; }
.relation-diff-grid span.common { background: #eef2ff; color: #3654d8; }

/* Editorial graph workspace: warm application shell, focused cosmic canvas. */
.graph-page {
  --ink: #171827;
  --muted: #6f7180;
  --line: rgba(72, 74, 104, .14);
  --glass: rgba(252, 251, 248, .92);
  --glass-strong: #faf9f6;
  --accent: #7468e8;
  --accent-strong: #5e52d4;
  --coral: #f3a477;
  --canvas: #0b0d20;
  max-width: none;
}
.graph-page button,
.graph-page input,
.graph-page a { transition: color .18s ease, border-color .18s ease, background-color .18s ease, box-shadow .18s ease, opacity .18s ease; }
.graph-page button:focus-visible,
.graph-page input:focus-visible,
.graph-page a:focus-visible { outline-color: var(--accent); box-shadow: 0 0 0 5px rgba(116, 104, 232, .13); }
.page-intro { min-height: 48px; align-items: center; padding: 0 2px 10px; }
.page-intro > div:first-child { min-width: 0; }
.page-intro p { display: flex; align-items: center; gap: 7px; margin: 0 0 3px; color: #7770da; font-size: 8px; letter-spacing: .2em; }
.page-intro p i { width: 5px; height: 5px; border-radius: 50%; background: var(--coral); box-shadow: 0 0 0 5px rgba(243, 164, 119, .14); }
.intro-title { display: flex; min-width: 0; align-items: baseline; gap: 14px; }
.page-intro h1 { flex: 0 0 auto; color: var(--ink); font-size: clamp(20px, 1.65vw, 27px); letter-spacing: -.04em; }
.page-intro span { min-width: 0; margin: 0; overflow: hidden; color: #747583; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.mode-switch { gap: 3px; padding: 3px; border-color: var(--line); border-radius: 13px; background: rgba(255, 255, 255, .78); box-shadow: 0 8px 26px rgba(38, 34, 76, .06); backdrop-filter: blur(16px); }
.mode-switch button { min-height: 34px; padding: 6px 12px; border-radius: 10px; color: #6c6d7a; font-size: 11px; }
.mode-switch button:hover { color: #5146c4; }
.mode-switch button.active { background: #ebe9ff; color: #5b4ed0; box-shadow: inset 0 0 0 1px rgba(116, 104, 232, .12); }
.query-dock { position: relative; z-index: 3; max-width: 1180px; margin: 0 auto 10px; }
.query-dock .search-bar,
.query-dock .path-search,
.query-dock .compare-search { max-width: none; margin: 0; border-color: rgba(91, 91, 126, .16); border-radius: 16px; background: rgba(255, 255, 255, .9); box-shadow: 0 15px 38px rgba(34, 31, 68, .08); backdrop-filter: blur(18px); }
.query-dock .search-bar { min-height: 48px; }
.query-dock .search-bar input { height: 46px; color: var(--ink); }
.query-dock .search-bar > svg { width: 18px; margin-left: 17px; color: #898a99; }
.query-dock .search-bar:focus-within { border-color: rgba(116, 104, 232, .58); box-shadow: 0 0 0 4px rgba(116, 104, 232, .09), 0 15px 38px rgba(34, 31, 68, .08); }
.search-bar button,
.path-search > button,
.compare-search > button:last-child { background: linear-gradient(135deg, #7668eb, #6456d9); }
.search-bar button:hover:not(:disabled),
.path-search > button:hover:not(:disabled),
.compare-search > button:last-child:hover:not(:disabled) { background: linear-gradient(135deg, #695bdd, #5548c3); }
.path-explainer strong,
.compare-explainer strong { color: #6256d2; }
.path-search input,
.compare-search input,
.compare-search .swap-products { border-color: var(--line); background: #f6f4f1; }
.sample-row { min-height: 33px; justify-content: flex-start; gap: 6px; padding: 5px 2px 0; }
.sample-row > span { color: #858691; font-size: 10px; }
.sample-row button { min-height: 27px; padding: 5px 10px; border-color: transparent; background: rgba(255, 255, 255, .58); color: #686a78; font-size: 10px; }
.sample-row button:hover { border-color: rgba(116, 104, 232, .24); background: #f0eeff; color: #5d51cb; }
.workspace {
  grid-template-columns: 204px minmax(560px, 1fr) 306px;
  height: clamp(560px, calc(100dvh - 218px), 880px);
  border-color: rgba(57, 57, 86, .18);
  border-radius: 22px;
  background: var(--canvas);
  box-shadow: 0 28px 80px rgba(25, 22, 54, .18), 0 2px 10px rgba(25, 22, 54, .05);
}
.workspace.filter-collapsed { grid-template-columns: minmax(560px, 1fr) 306px; }
.workspace.detail-collapsed { grid-template-columns: 204px minmax(560px, 1fr); }
.workspace.filter-collapsed.detail-collapsed { grid-template-columns: minmax(560px, 1fr); }
.filter-panel,
.detail-panel { background: var(--glass-strong); }
.filter-panel { border-right-color: var(--line); }
.detail-panel { border-left-color: var(--line); box-shadow: -18px 0 44px rgba(7, 8, 24, .1); }
.panel-heading { min-height: 52px; padding: 10px 14px; border-bottom-color: var(--line); }
.panel-heading > span { color: #323341; font-size: 11px; letter-spacing: .05em; }
.panel-heading button { color: #6659d7; }
.type-list { gap: 3px; padding: 8px; }
.type-list button { min-height: 44px; padding: 7px 8px; border-radius: 12px; color: #454653; }
.type-list button:hover { border-color: rgba(116, 104, 232, .1); background: #efedff; }
.type-list strong { font-size: 11px; }
.type-list small { color: #898a95; }
.interaction-help { padding: 13px; border-top-color: var(--line); background: #f2f0ec; }
.interaction-help > p { margin-bottom: 7px; color: #666774; font-size: 10px; }
.interaction-help dl { gap: 5px; }
.interaction-help dl div { font-size: 10px; }
.network-panel { isolation: isolate; background: var(--canvas); }
.network-panel::before { position: absolute; z-index: 0; top: -25%; left: 8%; width: 52%; height: 60%; border-radius: 50%; background: rgba(116, 104, 232, .12); filter: blur(80px); content: ''; pointer-events: none; }
.network-toolbar { inset: 14px; }
.result-summary { position: relative; max-width: min(360px, calc(100% - 96px)); padding: 10px 13px 10px 16px; overflow: hidden; border-color: rgba(186, 184, 233, .17); border-radius: 14px; background: rgba(21, 22, 48, .74); box-shadow: 0 14px 40px rgba(2, 3, 14, .25), inset 0 1px rgba(255, 255, 255, .05); backdrop-filter: blur(22px) saturate(1.15); }
.result-summary::before { position: absolute; top: 11px; bottom: 11px; left: 0; width: 3px; border-radius: 0 3px 3px 0; background: linear-gradient(#8d82f8, #efaa80); content: ''; }
.result-summary strong { color: #f6f5ff; font-size: 12px; }
.result-summary span { margin-top: 3px; color: #aaa9bf; font-size: 10px; }
.result-summary.path-result { max-width: min(560px, calc(100% - 88px)); }
.result-summary .result-eyebrow { color: #aea5ff; }
.result-summary.path-result p { color: #d7d5e5; }
.result-summary.path-result li small { background: rgba(134, 119, 241, .16); color: #c5bdff; }
.tool-actions { bottom: 0; gap: 3px; padding: 5px; border-color: rgba(190, 187, 233, .17); border-radius: 16px; background: rgba(18, 19, 42, .78); box-shadow: 0 18px 50px rgba(0, 1, 12, .42), inset 0 1px rgba(255,255,255,.05); backdrop-filter: blur(22px) saturate(1.15); }
.tool-actions button { width: 38px; height: 38px; border-radius: 11px; color: #b0aec3; }
.tool-actions button:hover { border-color: rgba(166, 153, 249, .2); background: rgba(129, 113, 236, .14); color: #e2deff; }
.tool-actions span { color: #aaa9bc; }
.graph-stage,
.graph-stage:fullscreen {
  background:
    radial-gradient(circle at 49% 43%, rgba(123, 107, 238, .23), transparent 25rem),
    radial-gradient(circle at 13% 78%, rgba(243, 164, 119, .08), transparent 24rem),
    radial-gradient(circle at 88% 14%, rgba(100, 197, 213, .09), transparent 25rem),
    linear-gradient(145deg, #0b0d20 0%, #11142f 54%, #090b1b 100%);
}
.network-grid {
  opacity: .5;
  background-image:
    radial-gradient(circle, rgba(209, 203, 255, .55) 0 1px, transparent 1.5px),
    radial-gradient(circle, rgba(105, 196, 211, .35) 0 1px, transparent 1.5px);
  background-position: 0 0, 53px 71px;
  background-size: 157px 157px, 223px 223px;
  mask-image: radial-gradient(ellipse at center, #000 15%, rgba(0,0,0,.64) 67%, transparent 100%);
}
.graph-orbits circle { fill: none; stroke: rgba(176, 166, 247, .12); stroke-width: 1; stroke-dasharray: 2 11; vector-effect: non-scaling-stroke; }
.graph-orbits circle:first-child { stroke: rgba(243, 164, 119, .18); }
.graph-orbits circle:last-child { stroke: rgba(100, 197, 213, .09); }
#graph-edge-arrow path { fill: #7278ad; }
.svg-edge { transition-duration: .22s; }
.svg-edge line { stroke: rgba(139, 145, 205, .34); stroke-width: 1.25; stroke-dasharray: 900; stroke-dashoffset: 900; animation: edge-draw .7s cubic-bezier(.22,.61,.36,1) forwards; }
.svg-edge text { fill: #b8b6cc; stroke: rgba(10, 11, 29, .95); stroke-width: 4px; font-size: 8px; letter-spacing: .02em; }
.svg-edge.focused line { stroke: rgba(172, 159, 255, .92); stroke-width: 2.15; filter: drop-shadow(0 0 5px rgba(133, 116, 244, .46)); }
.svg-edge.dimmed,
.svg-node.dimmed { opacity: .08; }
.svg-node { opacity: 0; animation: node-arrive .44s cubic-bezier(.22,.78,.31,1) forwards; animation-delay: var(--node-delay); }
.svg-node .node-backplate { opacity: .13; }
.svg-node .node-core { stroke-width: 2; filter: drop-shadow(0 7px 14px rgba(0, 0, 0, .38)); }
.svg-node .node-halo { opacity: .78; stroke-width: 1.6; stroke-dasharray: 2 6; filter: url(#graph-node-glow); animation: halo-breathe 3.8s ease-in-out infinite; }
.svg-node.center .node-core { stroke: #a99eff; stroke-width: 3; }
.svg-node.selected .node-core,
.svg-node:focus-visible .node-core { stroke: #f2efff; stroke-width: 4; filter: drop-shadow(0 0 15px rgba(143, 125, 248, .68)); }
.svg-node:hover .node-core { stroke-width: 3; filter: drop-shadow(0 0 12px rgba(143, 125, 248, .52)); }
.svg-node image { filter: saturate(.88) contrast(1.04) brightness(.94); }
.svg-node .node-label-bg { fill: rgba(15, 16, 38, .88); stroke: rgba(190, 184, 239, .17); stroke-width: 1; vector-effect: non-scaling-stroke; filter: drop-shadow(0 6px 12px rgba(0, 0, 0, .22)); }
.svg-node text.node-glyph { fill: var(--node-color); stroke: none; font-size: 12px; font-weight: 850; letter-spacing: 0; }
.svg-node.center text.node-glyph { font-size: 16px; }
.svg-node text.node-caption,
.svg-node.center text.node-caption { fill: #f7f5ff; stroke: none; font-size: 9px; font-weight: 700; letter-spacing: .01em; }
.svg-node.evidence .node-core { stroke: #efc265; filter: drop-shadow(0 0 12px rgba(239, 194, 101, .62)); }
.entity-summary { grid-template-columns: 1fr; gap: 10px; padding: 13px 14px; }
.entity-image { height: 112px; border-color: var(--line); border-radius: 13px; background: #efede8; }
.entity-identity span { background: #ece9ff; color: #6154ce; }
.entity-identity h2 { color: #20212e; font-size: 17px; }
.entity-actions { gap: 7px; }
.entity-actions button { border-color: var(--line); border-radius: 10px; background: #fff; color: #656674; }
.entity-actions button:first-child { border-color: var(--accent); background: var(--accent); color: #fff; }
.detail-tabs { border-color: var(--line); border-radius: 11px; background: #eeece8; }
.detail-tabs button { color: #747581; }
.detail-tabs button.active { color: #594dcc; }
.relation-list button:hover span,
.property-list dd button,
.property-list a,
.evidence-panel > a { color: #5e52d4; }
.evidence-status { border-color: var(--line); background: #f2f0ec; }

/* Match the product landing page: dark evidence workspace with green/cyan signals. */
.graph-page {
  --ink: #edf7f1;
  --muted: #91a79c;
  --line: rgba(181,231,203,.14);
  --glass: rgba(11,27,21,.93);
  --glass-strong: #0c1914;
  --accent: #a4ffcb;
  --accent-strong: #75dda0;
  --coral: #ffb27b;
  --canvas: #07110e;
  color: var(--ink);
}
.page-intro p { color: #a4ffcb; }
.page-intro p i { background: #7be5ff; box-shadow: 0 0 0 5px rgba(123,229,255,.1), 0 0 13px rgba(123,229,255,.4); }
.page-intro h1 { color: #edf7f1; }
.page-intro span { color: #91a79c; }
.mode-switch { border-color: var(--line); background: rgba(12,25,20,.88); box-shadow: 0 10px 28px rgba(0,0,0,.14); }
.mode-switch button { color: #91a79c; }
.mode-switch button:hover { color: #d8e9df; }
.mode-switch button.active { background: rgba(164,255,203,.11); color: #a4ffcb; box-shadow: inset 0 0 0 1px rgba(164,255,203,.12); }
.query-dock .search-bar,
.query-dock .path-search,
.query-dock .compare-search { border-color: var(--line); background: rgba(12,25,20,.92); box-shadow: 0 15px 38px rgba(0,0,0,.18); }
.query-dock .search-bar input,
.path-search input,
.compare-search input { background: transparent; color: #edf7f1; }
.query-dock input::placeholder { color: #61776c; }
.query-dock .search-bar > svg,
.path-search > svg { color: #7e9589; stroke: currentColor; }
.query-dock .search-bar:focus-within,
.path-search input:focus,
.compare-search input:focus { border-color: rgba(164,255,203,.54); box-shadow: 0 0 0 4px rgba(164,255,203,.08), 0 15px 38px rgba(0,0,0,.18); }
.search-bar button,
.path-search > button,
.compare-search > button:last-child { background: #a4ffcb; color: #07110e; }
.search-bar button:hover:not(:disabled),
.path-search > button:hover:not(:disabled),
.compare-search > button:last-child:hover:not(:disabled) { background: #d3ffe5; }
.path-search label,
.compare-search label,
.path-search .path-explainer,
.compare-explainer { color: #81978c; }
.path-explainer strong,
.compare-explainer strong { color: #a4ffcb; }
.path-search input,
.compare-search input,
.compare-search .swap-products { border-color: var(--line); background: #10231b; color: #d8e9df; }
.sample-row > span { color: #71877c; }
.sample-row button { border-color: rgba(164,255,203,.08); background: rgba(164,255,203,.035); color: #91a79c; }
.sample-row button:hover { border-color: rgba(164,255,203,.3); background: rgba(164,255,203,.08); color: #a4ffcb; }
.coverage-strip { border-color: var(--line); background: rgba(12,25,20,.92); }
.coverage-strip > div { border-right-color: var(--line); }
.coverage-strip strong { color: #a4ffcb; }
.coverage-strip span,
.coverage-strip p { color: #81978c; }
.workspace { border-color: rgba(181,231,203,.18); background: #07110e; box-shadow: 0 28px 80px rgba(0,0,0,.32), 0 2px 10px rgba(0,0,0,.16); }
.filter-panel,
.detail-panel { background: #0c1914; color: #d9e9df; }
.filter-panel { border-right-color: var(--line); }
.detail-panel { border-left-color: var(--line); box-shadow: -18px 0 44px rgba(0,0,0,.16); }
.panel-heading { border-bottom-color: var(--line); }
.panel-heading > span { color: #d9e9df; }
.panel-heading button { color: #a4ffcb; }
.type-list button { color: #bdcec4; }
.type-list button:hover { border-color: rgba(164,255,203,.1); background: rgba(164,255,203,.055); }
.type-list small,
.filter-empty { color: #71877c; }
.interaction-help { border-top-color: var(--line); background: #0a1612; }
.interaction-help > p,
.interaction-help dt { color: #91a79c; }
.interaction-help dd { color: #61776c; }
.network-panel { background: #07110e; }
.network-panel::before { background: rgba(72,196,128,.1); }
.result-summary { border-color: rgba(164,255,203,.16); background: rgba(8,26,19,.78); }
.result-summary::before { background: linear-gradient(#a4ffcb, #7be5ff); }
.result-summary strong { color: #edf7f1; }
.result-summary span { color: #91a79c; }
.result-summary .result-eyebrow { color: #a4ffcb; }
.result-summary.path-result p { color: #c9d9cf; }
.result-summary.path-result li small { background: rgba(164,255,203,.1); color: #a4ffcb; }
.tool-actions { border-color: rgba(164,255,203,.16); background: rgba(8,24,18,.82); }
.tool-actions button { color: #91a79c; }
.tool-actions button:hover { border-color: rgba(164,255,203,.2); background: rgba(164,255,203,.1); color: #a4ffcb; }
.tool-actions span { color: #71877c; }
.graph-stage,
.graph-stage:fullscreen {
  background:
    radial-gradient(circle at 49% 43%, rgba(72,196,128,.18), transparent 25rem),
    radial-gradient(circle at 14% 78%, rgba(123,229,255,.065), transparent 24rem),
    radial-gradient(circle at 88% 14%, rgba(164,255,203,.055), transparent 25rem),
    linear-gradient(145deg, #07110e 0%, #0a1913 54%, #060d0b 100%);
}
.network-grid { background-image: radial-gradient(circle, rgba(164,255,203,.42) 0 1px, transparent 1.5px), radial-gradient(circle, rgba(123,229,255,.25) 0 1px, transparent 1.5px); }
.graph-orbits circle { stroke: rgba(164,255,203,.12); }
.graph-orbits circle:first-child { stroke: rgba(123,229,255,.14); }
.graph-orbits circle:last-child { stroke: rgba(255,178,123,.08); }
#graph-edge-arrow path { fill: #5f8f78; }
.svg-edge line { stroke: rgba(116,169,143,.36); }
.svg-edge text { fill: #a6bbae; stroke: rgba(5,17,12,.95); }
.svg-edge.focused line { stroke: rgba(164,255,203,.9); filter: drop-shadow(0 0 5px rgba(164,255,203,.36)); }
.svg-node.center .node-core { stroke: #a4ffcb; }
.svg-node.selected .node-core,
.svg-node:focus-visible .node-core { stroke: #edf7f1; filter: drop-shadow(0 0 15px rgba(164,255,203,.55)); }
.svg-node:hover .node-core { filter: drop-shadow(0 0 12px rgba(164,255,203,.42)); }
.svg-node .node-label-bg { fill: rgba(7,20,15,.9); stroke: rgba(164,255,203,.16); }
.svg-node text.node-caption,
.svg-node.center text.node-caption { fill: #edf7f1; }
.canvas-state { background: rgba(7,17,14,.72); color: #edf7f1; }
.canvas-state > svg { stroke: #91a79c; }
.canvas-state p { color: #81978c; }
.loader { border-color: rgba(164,255,203,.14); border-top-color: #a4ffcb; }
.entity-image { border-color: var(--line); background: #10231b; }
.entity-identity span { background: rgba(164,255,203,.1); color: #a4ffcb; }
.entity-identity h2 { color: #edf7f1; }
.entity-actions button { border-color: var(--line); background: #10231b; color: #a9bdb2; }
.entity-actions button:first-child { border-color: #a4ffcb; background: #a4ffcb; color: #07110e; }
.detail-tabs { border-color: var(--line); background: #10231b; }
.detail-tabs button { color: #81978c; }
.detail-tabs button.active,
.relation-list button:hover span,
.property-list dd button,
.property-list a,
.evidence-panel > a { color: #a4ffcb; }
.property-list,
.relation-list,
.evidence-panel { color: #b8cabf; }
.property-list dt,
.relation-list small { color: #71877c; }
.evidence-status { border-color: var(--line); background: #10231b; }
.compare-workspace,
.product-card,
.comparison-block { border-color: var(--line); background: #0c1914; color: #edf7f1; }
.product-card p,
.comparison-title p,
.compare-state p { color: #81978c; }
.comparison-score { background: #102b20; color: #edf7f1; }
.comparison-score strong { color: #a4ffcb; }
.comparison-actions button,
.product-card button { border-color: var(--line); background: #10231b; color: #a4ffcb; }
.comparison-actions button:first-child { border-color: #a4ffcb; background: #a4ffcb; color: #07110e; }
.comparison-title,
.relation-comparison article + article,
.comparison-row { border-color: var(--line); }
.comparison-title span { color: #a4ffcb; }
.comparison-row > * { color: #b8cabf; }
.comparison-row.heading,
.relation-diff-grid > div { background: #10231b; }
.comparison-row.heading span,
.relation-diff-grid strong,
.relation-comparison article > header span { color: #81978c; }
.relation-diff-grid > div { border-color: var(--line); }
.relation-diff-grid span { background: #152a21; color: #a9bdb2; }
.relation-diff-grid span.common { background: rgba(164,255,203,.11); color: #a4ffcb; }
@keyframes edge-draw { to { stroke-dashoffset: 0; } }
@keyframes node-arrive { from { opacity: 0; } to { opacity: 1; } }
@keyframes halo-breathe { 0%, 100% { opacity: .48; } 50% { opacity: .9; } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
@media (max-width: 1180px) {
  .workspace { grid-template-columns: 188px minmax(460px,1fr) 282px; }
  .workspace.filter-collapsed { grid-template-columns: minmax(460px,1fr) 282px; }
  .workspace.detail-collapsed { grid-template-columns: 188px minmax(460px,1fr); }
}
@media (max-width: 980px) {
  .comparison-header { grid-template-columns: minmax(0,1fr) 108px minmax(0,1fr); }
  .workspace { grid-template-columns: 180px minmax(0,1fr); height: auto; overflow: hidden; }
  .workspace.filter-collapsed { grid-template-columns: minmax(0,1fr); }
  .workspace.detail-collapsed { grid-template-columns: 180px minmax(0,1fr); }
  .workspace.filter-collapsed.detail-collapsed { grid-template-columns: minmax(0,1fr); }
  .network-panel { min-height: 620px; grid-column: 2; grid-row: 1; }
  .workspace.filter-collapsed .network-panel { grid-column: 1; }
  .detail-panel { grid-column: 1 / -1; grid-row: 2; height: 420px; border-top: 1px solid var(--line); border-left: 0; }
  .entity-summary { grid-template-columns: 96px minmax(0,1fr); align-items: center; gap: 12px; padding: 12px 15px; }
  .entity-summary.without-image { grid-template-columns: 1fr; }
  .entity-image { width: 96px; height: 72px; }
}
@media (max-width: 720px) {
  .page-intro { align-items: flex-start; padding-bottom: 15px; }
  .page-intro span { display: none; }
  .mode-switch { margin-top: 4px; }
  .mode-switch button { min-height: 44px; }
  .coverage-strip { justify-content: flex-start; margin-top: 0; overflow-x: auto; }
  .coverage-strip > div { min-width: 105px; }
  .coverage-strip p { display: none; }
  .path-search { grid-template-columns: 1fr; gap: 8px; }
  .path-search .path-explainer { display: block; }
  .path-explainer strong { display: block; margin-bottom: 3px; }
  .path-search > svg { display: none; }
  .path-search > button { min-height: 40px; }
  .search-bar input, .path-search input, .compare-search input { min-height: 44px; font-size: 16px; }
  .compare-search { grid-template-columns: 1fr 42px 1fr; }
  .compare-search > button:last-child { grid-column: 1 / -1; min-height: 42px; }
  .comparison-header { grid-template-columns: 1fr; }
  .comparison-score { min-height: 112px; }
  .product-card.right { text-align: left; }
  .comparison-title { align-items: flex-start; flex-direction: column; gap: 8px; }
  .comparison-title p { text-align: left; }
  .relation-diff-grid { grid-template-columns: 1fr; }
  .workspace, .workspace.filter-collapsed, .workspace.detail-collapsed, .workspace.filter-collapsed.detail-collapsed { display: block; height: auto; min-height: 0; }
  .filter-panel { display: block; border-right: 0; border-bottom: 1px solid var(--line); }
  .type-list { display: flex; overflow-x: auto; overscroll-behavior-x: contain; }
  .type-list button { min-width: 145px; }
  .interaction-help { display: none; }
  .graph-stage { min-height: 560px; }
  .detail-panel { display: flex; height: 460px; max-height: 460px; }
  .detail-heading button { width: 44px; height: 44px; }
  .tool-actions { gap: 4px; }
  .tool-actions button { width: 44px; height: 44px; }
  .tool-actions span { display: none; }
}
@media (max-width: 520px) {
  .page-intro { display: block; }
  .mode-switch { width: max-content; margin-top: 13px; }
  .mode-switch button { padding-inline: 9px; font-size: 11px; }
  .search-bar button { min-width: 88px; }
  .search-bar input { font-size: 16px; }
  .compare-search { grid-template-columns: 1fr; }
  .compare-search .swap-products { margin: 0 auto; transform: rotate(90deg); }
  .compare-search > button:last-child { grid-column: auto; }
  .compare-workspace { padding: 12px; }
  .comparison-actions { justify-content: stretch; }
  .comparison-actions button { flex: 1; }
  .network-toolbar { align-items: flex-start; }
  .result-summary strong { max-width: 160px; }
  .tool-actions button:nth-of-type(1), .tool-actions button:nth-of-type(2) { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .loader, .mini-loader { animation: none; }
  .expand-status { transition: none; }
  .svg-edge line, .svg-node, .svg-node .node-halo { animation: none; }
  .svg-node { opacity: 1; }
}
</style>
