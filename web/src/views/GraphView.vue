<template>
  <section class="graph-page">
    <header class="view-heading">
      <div>
        <h1>知识图谱</h1>
        <p>从登记号、作物或有效成分出发，查看它们的关联和登记依据。</p>
      </div>
      <div class="mode-switch" role="group" aria-label="图谱查询模式">
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
    <form v-if="mode === 'entity'" class="search-bar" role="search" aria-label="登记实体检索" @submit.prevent="searchGraph">
      <label for="graph-keyword">检索登记实体</label>
      <div class="search-field">
        <UiIcon name="search" />
        <input
          id="graph-keyword"
          name="graph-keyword"
          type="search"
          v-model.trim="keyword"
          maxlength="80"
          autocomplete="off"
          class="ui-input"
          required
          placeholder="输入登记号、有效成分或作物"
        >
        <button class="ui-button primary" type="submit" :disabled="loading">{{ loading ? '正在检索…' : '检索实体' }}</button>
      </div>
    </form>

    <form v-else-if="mode === 'path'" class="path-search" @submit.prevent="searchPath">
      <div class="path-explainer">
        <strong>查询最短关系路径</strong>
        <span>输入两个实体，查看它们经过哪些登记、成分、作物或病虫害发生关联。</span>
      </div>
      <div>
        <label for="path-source">从哪个实体出发</label>
        <input id="path-source" name="path-source" class="ui-input" required v-model.trim="pathStart" maxlength="80" autocomplete="off" placeholder="例如 Prothioconazole…">
      </div>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg>
      <div>
        <label for="path-target">想关联到哪个实体</label>
        <input id="path-target" name="path-target" class="ui-input" required v-model.trim="pathEnd" maxlength="80" autocomplete="off" placeholder="例如 Spring barley…">
      </div>
      <button class="ui-button primary" type="submit" :disabled="loading">{{ loading ? '正在查询…' : '解释两者关系' }}</button>
    </form>

    <form v-else class="compare-search" @submit.prevent="compareProducts">
      <div class="compare-explainer">
        <strong>登记产品差异</strong>
        <span>并列核对登记属性、有效成分、适用作物与防治对象。</span>
      </div>
      <div>
        <label for="compare-left">产品 A</label>
        <input id="compare-left" name="compare-left" class="ui-input" required v-model.trim="compareLeftKeyword" maxlength="80" autocomplete="off" placeholder="登记号或产品名…">
      </div>
      <button type="button" class="ui-button swap-products" aria-label="交换两个产品" title="交换产品" :disabled="compareLoading" @click="swapProducts">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 3-3 3 3M10 4v14m7-1-3 3-3-3m3 3V6"/></svg>
      </button>
      <div>
        <label for="compare-right">产品 B</label>
        <input id="compare-right" name="compare-right" class="ui-input" required v-model.trim="compareRightKeyword" maxlength="80" autocomplete="off" placeholder="登记号或产品名…">
      </div>
      <button class="ui-button primary" type="submit" :disabled="compareLoading">
        {{ compareLoading ? '正在对比…' : '生成对比' }}
      </button>
    </form>

    <div v-if="mode === 'entity'" class="sample-row" aria-label="搜索示例">
      <span>检索示例</span>
      <button
        v-for="sample in samples"
        :key="sample.label"
        type="button"
        :disabled="loading"
        @click="runSample(sample.keyword)"
      >{{ sample.label }}</button>
    </div>
    <div v-else-if="mode === 'path'" class="sample-row" aria-label="路径查询示例">
      <span>穿透示例</span>
      <button type="button" :disabled="loading" @click="runPathSample('Prothioconazole', 'Spring barley')">有效成分为何关联作物？</button>
      <button type="button" :disabled="loading" @click="runPathSample('Leaf spot disease', '4387-901')">病害如何关联登记产品？</button>
    </div>
    <div v-else-if="mode === 'compare'" class="sample-row" aria-label="产品对比示例">
      <span>对比示例</span>
      <button type="button" :disabled="compareLoading" @click="runCompareSample('PD20150720', 'PD20050020')">两种杀虫剂登记差异</button>
    </div>
    </section>

    <section v-if="mode === 'compare'" class="compare-workspace" aria-label="产品对比结果" :aria-busy="String(compareLoading)">
      <div v-if="compareLoading" class="compare-state" role="status">
        <span class="ui-skeleton" aria-hidden="true"></span>
        <strong>正在汇总两个产品的登记关系…</strong>
      </div>
      <div v-else-if="compareError" class="compare-state error-state" role="alert">
        <strong>无法生成对比</strong>
        <p>{{ compareError }}</p>
        <button class="ui-button" type="button" @click="compareProducts">重新查询</button>
      </div>
      <template v-else-if="comparison">
        <header class="comparison-header">
          <div class="product-card">
            <span>产品 A · {{ comparison.left.dataset }}</span>
            <h2>{{ comparison.left.name }}</h2>
            <p>{{ productSubtitle(comparison.left) }}</p>
            <button type="button" class="ui-button" @click="openComparedProduct(comparison.left.name)">在图谱中查看</button>
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
            <button type="button" class="ui-button" @click="openComparedProduct(comparison.right.name)">在图谱中查看</button>
          </div>
        </header>

        <div class="comparison-actions">
          <button type="button" class="ui-button primary" @click="askAboutComparison">让 AI 解释差异</button>
          <button type="button" class="ui-button" @click="exportComparison">导出对比结果</button>
        </div>

        <section class="comparison-block">
          <div class="comparison-title">
            <h3>登记属性</h3>
            <p>“不同”只表示当前图谱字段值不同，不推断产品优劣。</p>
          </div>
          <div class="comparison-table" tabindex="0" role="region" aria-label="产品登记属性对比">
            <table>
              <thead>
                <tr>
                  <th scope="col">字段</th>
                  <th scope="col">{{ comparison.left.name }}</th>
                  <th scope="col">{{ comparison.right.name }}</th>
                  <th scope="col">结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in comparisonPropertyRows" :key="row.key">
                  <th scope="row">{{ row.label }}</th>
                  <td>{{ row.left || '暂无数据' }}</td>
                  <td>{{ row.right || '暂无数据' }}</td>
                  <td><span class="difference" :class="{ same: row.same }">{{ row.same ? '相同' : '不同' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="comparison-block relation-comparison">
          <div class="comparison-title">
            <h3>共同关联与各自关联</h3>
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
      <aside v-show="showFilters" id="graph-filters" class="filter-panel" aria-label="图谱筛选">
        <div class="panel-heading">
          <span>视图筛选</span>
          <div>
            <button v-if="typeOptions.length" type="button" @click="showAllTypes">全部显示</button>
            <button type="button" aria-label="收起视图筛选" title="收起筛选" @click="closePanel('filter')">×</button>
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
          <p>图谱数据覆盖</p>
        </section>

        <section class="interaction-help">
          <p>画布操作</p>
          <dl>
            <div><dt>拖动</dt><dd>调整节点位置</dd></div>
            <div><dt>滚轮</dt><dd>缩放关系网络</dd></div>
            <div><dt>双击 / 按钮</dt><dd>展开直接关联</dd></div>
            <div><dt>Tab / Enter</dt><dd>选择节点</dd></div>
          </dl>
        </section>
      </aside>

      <section ref="networkPanel" class="network-panel" aria-label="知识图谱画布">
        <p id="graph-interaction-help" class="sr-only">使用 Tab 在节点之间切换，按回车选中。方向键平移，加号和减号缩放，数字 0 适配画布。</p>
        <div class="network-toolbar">
          <div class="result-summary" role="status" :class="{ 'path-result': mode === 'path' && graphData.found }">
            <template v-if="mode === 'path' && graphData.found">
              <h2>{{ resultTitle }}</h2>
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
              <h2>{{ resultTitle }}</h2>
              <span v-if="graphData.found && !loading">{{ visibleNodeCount }} 个实体 · {{ visibleEdgeCount }} 条关系</span>
            </template>
          </div>
          <div class="tool-actions" role="group" aria-label="图谱视图工具">
            <button
              type="button"
              ref="filterToggle"
              title="切换筛选栏"
              aria-controls="graph-filters"
              :aria-expanded="String(showFilters)"
              @click="togglePanel('filter')"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16M7 12h10m-7 7h4"/></svg>
              筛选
            </button>
            <button type="button" title="缩小" aria-label="缩小关系图" :disabled="loading || !graphData.found" @click="zoomBy(.82)">−</button>
            <span>{{ Math.round(zoom * 100) }}%</span>
            <button type="button" title="放大" aria-label="放大关系图" :disabled="loading || !graphData.found" @click="zoomBy(1.22)">＋</button>
            <button type="button" title="适合画布" aria-label="让图谱适合画布" :disabled="loading || !graphData.found" @click="fitView()">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>
            </button>
            <button type="button" title="重新布局" aria-label="重新布局关系图" :disabled="loading || !graphData.found" @click="runLayout(true)">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4v6h6M20 20v-6h-6M5 9a8 8 0 0 1 13-3l2 2M19 15a8 8 0 0 1-13 3l-2-2"/></svg>
            </button>
            <button v-if="fullscreenSupported" type="button" :title="fullscreen ? '退出全屏' : '全屏查看'"
              :aria-label="fullscreen ? '退出图谱全屏' : '全屏查看关系图'"
              :disabled="loading || !graphData.found" @click="toggleFullscreen">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="fullscreen ? 'M3 8h5V3m13 5h-5V3M3 16h5v5m13-5h-5v5' : 'M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6'"/></svg>
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
              class="detail-toggle"
              ref="detailToggle"
              title="切换实体详情"
              aria-controls="graph-details"
              :aria-expanded="String(showDetails)"
              @click="togglePanel('detail')"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5zM9 8h6m-6 4h6m-6 4h4"/></svg>
              详情
            </button>
          </div>
        </div>

        <section v-if="evidenceHighlight" class="evidence-highlight-banner" aria-live="polite">
          <div>
            <span>AI 回答依据 [{{ evidenceHighlight.index || 1 }}]</span>
            <strong>{{ evidenceHighlight.sourceName }} · {{ relationName(evidenceHighlight.relation) }} · {{ evidenceHighlight.targetName }}</strong>
          </div>
          <button type="button" aria-label="关闭证据高亮" @click="clearEvidenceHighlight">关闭高亮</button>
        </section>

        <button v-if="selectedNode && showDetails && !fullscreen" class="graph-skip sr-only" type="button" @click="focusDetails">
          跳到实体详情
        </button>
        <div ref="graphStage" class="graph-stage" :aria-busy="String(loading)">
          <div class="network-grid" aria-hidden="true"></div>
          <svg
            v-if="graphData.found && !loading"
            ref="cyCanvas"
            role="group"
            class="cy-canvas"
            aria-label="可拖动和缩放的农药知识图谱"
            aria-describedby="graph-interaction-help"
            @wheel="handleWheel"
            @keydown="handleCanvasKeydown"
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
                  :x2="edgeEndpoint(edge).x"
                  :y2="edgeEndpoint(edge).y"
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
                v-for="node in visibleNodes"
                :key="String(node.id)"
                class="svg-node"
                :style="{ '--node-color': typeColor(node.label) }"
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
                :aria-pressed="String(selectedNode && String(selectedNode.id) === String(node.id) || false)"
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
                  :fill="nodeFill(node.label)"
                  :stroke="typeColor(node.label)"
                ></circle>
                <text
                  aria-hidden="true"
                  class="node-glyph"
                  :fill="typeColor(node.label)"
                >{{ nodeGlyph(node.label) }}</text>
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
            <span class="ui-skeleton" aria-hidden="true"></span>
            <h2>{{ mode === 'path' ? '正在解释关系链…' : '正在加载关系网络…' }}</h2>
          </div>

          <div v-else-if="errorMessage" class="canvas-state error-state" role="alert">
            <svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 5 5 40h38L24 5Zm0 13v10m0 6v.01"/></svg>
            <h2>暂时没有加载成功</h2>
            <p>{{ errorMessage }}</p>
            <button class="ui-button" type="button" @click="retrySearch">再试一次</button>
          </div>

          <div v-else-if="searched && !graphData.found" class="canvas-state" role="status">
            <svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="21" cy="21" r="13"/><path d="m42 42-12-12M15 21h12"/></svg>
            <h2>{{ mode === 'path' ? '没有找到关系链' : '没有找到这个实体' }}</h2>
            <p>{{ mode === 'path' ? '可以换用更准确的起点和终点名称。' : '可以换一个名称，或从上方示例开始探索。' }}</p>
          </div>

          <div v-else-if="!graphData.found" class="canvas-state">
            <UiIcon name="graph" />
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
        <button v-if="selectedNode && !loading" type="button" ref="jumpDetail" class="jump-detail ui-button" @click="focusDetails">
          查看 {{ selectedNode.name }} 的详情 <UiIcon name="chevron" />
        </button>
      </section>

      <aside v-show="showDetails" ref="details" id="graph-details" class="detail-panel" aria-label="实体详情" tabindex="-1">
        <div class="panel-heading detail-heading">
          <span>实体详情</span>
          <div>
            <i v-if="selectedNode" :style="{ background: typeColor(selectedNode.label) }"></i>
            <button type="button" aria-label="收起实体详情" title="收起详情" @click="closePanel('detail')">×</button>
          </div>
        </div>

        <div v-if="loading" class="detail-empty" role="status"><span class="ui-skeleton" aria-hidden="true"></span><p>正在载入实体详情…</p></div>
        <template v-else-if="selectedNode">
          <div class="entity-summary">
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
            <button class="ui-button primary" type="button" :disabled="loading || !!expandingNodeId" @click="exploreNode(selectedNode.id)">
              {{ expandingNodeId === String(selectedNode.id)
                ? '正在展开…'
                : (expandedNodeIds.includes(String(selectedNode.id)) ? '查看已展开关系' : '展开关系') }}
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
            </button>
            <button class="ui-button" type="button" @click="askAboutNode(selectedNode.name)">
              问 AI
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v11H9l-4 3V5Z"/></svg>
            </button>
          </div>

          <div class="detail-tabs" role="tablist" aria-label="实体详情分类" @keydown="handleDetailTabKeydown">
            <button
              id="detail-relations-tab"
              type="button"
              role="tab"
              :aria-selected="detailTab === 'relations' ? 'true' : 'false'"
              :aria-controls="'detail-relations-panel'"
              :tabindex="detailTab === 'relations' ? 0 : -1"
              :class="{ active: detailTab === 'relations' }"
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
              :tabindex="detailTab === 'properties' ? 0 : -1"
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
              :tabindex="detailTab === 'evidence' ? 0 : -1"
              :class="{ active: detailTab === 'evidence' }"
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
              tabindex="0"
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
              tabindex="0"
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
              tabindex="0"
              aria-labelledby="detail-evidence-tab"
            >
              <template v-if="evidenceAvailable">
              <div class="evidence-status">
                <strong>{{ selectedEvidence.dataset || '农药登记记录' }}</strong>
              </div>
              <dl v-if="evidenceEntries.length">
                <div v-for="entry in evidenceEntries" :key="entry.key">
                  <dt>{{ entry.label }}</dt>
                  <dd>{{ entry.value }}</dd>
                </div>
              </dl>
              <a
                v-if="isHttpUrl(selectedEvidence.sourceUrl)"
                class="ui-link"
                :href="selectedEvidence.sourceUrl"
                target="_blank"
                rel="noopener"
              >查看原始登记资料 ↗</a>
              <p v-else>暂无原始登记资料链接。</p>
              </template>
              <p v-else class="no-properties">此实体没有登记记录。可以沿直接关联查看登记产品。</p>
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
import UiIcon from '@/components/UiIcon.vue';

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
  components: { UiIcon },
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
        { label: '有效成分', keyword: 'Chlorantraniliprole' },
        { label: '作物关联', keyword: 'Spring barley' },
        { label: 'PD20150720', keyword: 'PD20150720' }
      ],
      loading: false,
      graphRequestId: 0,
      expandingNodeId: null,
      searched: false,
      errorMessage: '',
      statusMessage: '',
      statusError: false,
      zoom: 1,
      fullscreen: false,
      fullscreenSupported: Boolean(document.fullscreenEnabled),
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
        RegisterNumber: '#475e8f',
        Crop: '#386644',
        Disease: '#8c492f',
        ActiveSubstance: '#286660',
        ChemicalClasses: '#67507c',
        PesticideCategory: '#796018',
        TargetSite: '#854666',
        ModeOfAction: '#396872'
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
      handler(query) {
        this.loadGraphRoute(query);
      }
    },
    selectedNode() {
      this.detailImageError = false;
      this.expandedPropertyKeys = [];
      this.$nextTick(() => {
        this.detailTab = this.selectedNode?.label === 'RegisterNumber'
          ? 'evidence'
          : (this.selectedRelations.length ? 'relations' : 'properties');
      });
    }
  },
  async mounted() {
    document.title = '知识图谱 · AgriReg AI';
    window.addEventListener('resize', this.handleCanvasResize);
    document.addEventListener('fullscreenchange', this.handleFullscreenChange);
    this.loadGraphStats();
    if (!await this.loadGraphRoute(this.$route.query)) await this.searchGraph();
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleCanvasResize);
    document.removeEventListener('fullscreenchange', this.handleFullscreenChange);
    if (this.renderFrame) window.cancelAnimationFrame(this.renderFrame);
    if (this.statusTimer) window.clearTimeout(this.statusTimer);
  },
  methods: {
    async loadGraphRoute(query) {
      const { pathStart, pathEnd } = query;
      if (typeof pathStart === 'string' && pathStart.trim() && pathStart.length <= 80
          && typeof pathEnd === 'string' && pathEnd.trim() && pathEnd.length <= 80) {
        if (this.mode !== 'path' || pathStart !== this.pathStart || pathEnd !== this.pathEnd || !this.graphData.found) {
          this.switchMode('path');
          this.pathStart = pathStart;
          this.pathEnd = pathEnd;
          this.clearEvidenceHighlight(false);
          await this.fetchGraph('/api/graph/path', { source: pathStart, target: pathEnd });
        }
        return true;
      }
      if (!query.q) return false;
      const keyword = String(query.q);
      if (keyword !== this.keyword || this.mode !== 'entity' || !this.graphData.found) {
        this.switchMode('entity');
        this.keyword = keyword;
        await this.fetchGraph('/api/graph/search', { keyword });
      }
      if (query === this.$route.query) await this.applyEvidenceFromRoute();
      return true;
    },
    switchMode(nextMode) {
      if (this.mode === nextMode) return;
      this.mode = nextMode;
      this.graphRequestId += 1;
      this.loading = false;
      this.expandingNodeId = null;
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
      const requestId = this.graphRequestId;
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
          if (requestId !== this.graphRequestId || query !== this.$route.query) return;
          this.mergeGraph(response.data || EMPTY_GRAPH());
          source = findNode(sourceId, sourceName);
          target = findNode(targetId, targetName);
          await this.$nextTick();
          this.scheduleGraphRender();
        } catch (error) {
          if (requestId === this.graphRequestId && query === this.$route.query) {
            this.announceStatus('已打开图谱，但未能补全这条回答依据。', true);
          }
          return;
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
      this.$nextTick(() => this.fitView(new Set([String(source.id), String(target.id)])));
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

      const requestId = this.graphRequestId;
      this.expandingNodeId = id;
      this.statusMessage = '';
      this.statusError = false;
      try {
        const response = await service.get('/api/graph/node/' + encodeURIComponent(id));
        if (requestId !== this.graphRequestId) return;
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
        if (requestId === this.graphRequestId) this.announceStatus(message, true);
      } finally {
        if (requestId === this.graphRequestId) this.expandingNodeId = null;
      }
    },
    async fetchGraph(url, params) {
      const requestId = ++this.graphRequestId;
      const requestMode = this.mode;
      this.loading = true;
      this.expandingNodeId = null;
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
          : '无法连接图谱服务。请确认服务可用后重试。';
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
      this.$nextTick(() => window.requestAnimationFrame(() => this.handleCanvasResize()));
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
      if (value.length <= 11 || /^[a-z0-9_.…-]+$/i.test(value)) return [value];
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
      const lineWidth = line => [...line].reduce((total, char) => total + (char.charCodeAt(0) < 127 ? 7 : 12), 0);
      return Math.max(node.center ? 96 : 66, Math.max(...lines.map(lineWidth)) + 15);
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
    edgeEndpoint(edge) {
      const source = this.nodePosition(edge.source);
      const target = this.nodePosition(edge.target);
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const length = Math.hypot(dx, dy);
      if (!length) return target;
      const isCenter = String(edge.target) === String(this.graphData.centerId);
      const trim = Math.min(length, isCenter ? 54 : 37);
      return { x: target.x - dx * trim / length, y: target.y - dy * trim / length };
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
      this.$nextTick(() => window.requestAnimationFrame(() => this.handleCanvasResize()));
    },
    closePanel(panel) {
      this.togglePanel(panel);
      this.$nextTick(() => {
        const toggle = this.$refs[panel + 'Toggle'];
        const target = toggle?.getClientRects().length ? toggle : this.$refs.jumpDetail;
        target?.focus();
      });
    },
    focusDetails() {
      if (this.fullscreen) return;
      this.showDetails = true;
      this.$nextTick(() => this.$refs.details?.focus());
    },
    handleDetailTabKeydown(event) {
      const tabs = ['relations', 'properties', 'evidence'];
      const index = tabs.indexOf(this.detailTab);
      const target = {
        ArrowLeft: (index + tabs.length - 1) % tabs.length,
        ArrowRight: (index + 1) % tabs.length,
        Home: 0,
        End: tabs.length - 1
      }[event.key];
      if (target === undefined) return;
      event.preventDefault();
      this.detailTab = tabs[target];
      this.$nextTick(() => document.getElementById('detail-' + this.detailTab + '-tab')?.focus());
    },
    handleCanvasKeydown(event) {
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      const positions = { ArrowLeft: [40, 0], ArrowRight: [-40, 0], ArrowUp: [0, 40], ArrowDown: [0, -40] };
      const shift = positions[event.key];
      if (shift) {
        this.viewport = { ...this.viewport, x: this.viewport.x + shift[0], y: this.viewport.y + shift[1] };
      } else if (event.key === '+' || event.key === '=') {
        this.zoomBy(1.22);
      } else if (event.key === '-') {
        this.zoomBy(.82);
      } else if (event.key === '0') {
        this.fitView();
      } else {
        return;
      }
      event.preventDefault();
    },
    handleCanvasResize() {
      const highlight = this.evidenceHighlight;
      this.fitView(highlight ? new Set([highlight.sourceId, highlight.targetId]) : undefined);
    },
    handleFullscreenChange() {
      this.fullscreen = Boolean(this.$refs.networkPanel && document.fullscreenElement === this.$refs.networkPanel);
      this.$nextTick(() => this.handleCanvasResize());
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
      const node = this.graphData.nodes.find(item => String(item.id) === String(nodeId));
      if (!node) return;
      if (!this.isTypeActive(node.label)) this.activeTypes.push(node.label);
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
      if (event.ctrlKey || event.metaKey || event.deltaX) return;
      if (window.matchMedia('(pointer: coarse)').matches) return;
      event.preventDefault();
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

      const positions = nodes.map(node => ({ node, ...this.nodePosition(node.id) }));
      const minX = Math.min(...positions.map(({ node, x }) => x - this.nodeLabelWidth(node) / 2));
      const maxX = Math.max(...positions.map(({ node, x }) => x + this.nodeLabelWidth(node) / 2));
      const minY = Math.min(...positions.map(({ node, y }) => y - (node.center ? 59 : 39)));
      const maxY = Math.max(...positions.map(({ node, y }) => y + this.nodeLabelY(node) + this.nodeLabelHeight(node)));
      const rect = this.$refs.cyCanvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const padding = Math.min(38, rect.width * .09);
      const scale = Math.min(
        2.2,
        Math.max(.25, Math.min(
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
      const next = Math.min(2.2, Math.max(.25, value));
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
      const element = this.$refs.networkPanel;
      try {
        if (!document.fullscreenElement && element.requestFullscreen) await element.requestFullscreen();
        else if (document.exitFullscreen) await document.exitFullscreen();
      } catch (error) {
        this.announceStatus('当前浏览器无法切换全屏。', true);
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
    isHttpUrl(value) {
      return typeof value === 'string' && /^https?:\/\/[^\s]+$/i.test(value);
    }
  }
};
</script>

<style scoped>
.graph-page { min-width: 0; }
.mode-switch {
  display: flex;
  width: fit-content;
  max-width: 100%;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: var(--control-radius);
  background: var(--wash);
}
.mode-switch button {
  min-height: 36px;
  padding: 6px 13px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font-size: 14px;
  font-weight: 650;
  white-space: nowrap;
}
.mode-switch button:hover { color: var(--accent); }
.mode-switch .active { border-color: var(--line); background: var(--surface); color: var(--accent); font-weight: 750; }

.query-dock {
  margin-bottom: 16px;
  padding: 16px 20px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}
.query-dock form { margin: 0; }
.query-dock label, .path-explainer strong, .compare-explainer strong { display: block; margin-bottom: 6px; font-weight: 700; }
.search-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
}
.search-field > .ui-icon { z-index: 1; grid-area: 1 / 1; margin-left: 13px; color: var(--accent); pointer-events: none; }
.search-field > input { grid-area: 1 / 1; padding-left: 41px; background: var(--surface); }
.search-field > button { min-height: 46px; white-space: nowrap; }

.path-search, .compare-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px 12px;
}
.path-search > svg, .swap-products { align-self: end; margin-bottom: 1px; color: var(--accent); }
.path-search > svg { width: 19px; height: 19px; margin-bottom: 14px; }
.swap-products { width: 44px; min-height: 44px; padding: 0; }
.path-explainer, .compare-explainer { grid-column: 1 / -1; color: var(--muted); font-size: 14px; }
.path-explainer strong, .compare-explainer strong { margin-bottom: 3px; color: var(--ink); }
.query-dock svg, .tool-actions svg, .entity-actions svg, .type-list svg {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.sample-row { display: flex; align-items: center; flex-wrap: wrap; gap: 5px 8px; margin-top: 9px; color: var(--muted); font-size: 13px; }
.sample-row > span { margin-right: 4px; }
.sample-row button {
  min-height: 33px;
  padding: 2px 9px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--wash);
  color: var(--accent);
  font-size: inherit;
  text-align: left;
}
.sample-row button:not(:disabled):hover { border-color: var(--field-line); }
.sample-row button:disabled { background: transparent; color: var(--muted); }

.workspace { display: grid; grid-template-columns: 204px minmax(0, 1fr) minmax(282px, 314px); align-items: start; gap: 14px; }
.workspace.filter-collapsed { grid-template-columns: minmax(0, 1fr) minmax(282px, 314px); }
.workspace.detail-collapsed { grid-template-columns: 204px minmax(0, 1fr); }
.workspace.filter-collapsed.detail-collapsed { grid-template-columns: minmax(0, 1fr); }
.network-panel, .filter-panel, .detail-panel, .compare-workspace {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}
.network-panel:fullscreen { display: flex; flex-direction: column; border: 0; border-radius: 0; }
.network-panel:fullscreen .graph-stage { flex: 1 1 auto; min-height: 0; border-radius: 0; }
.network-panel:fullscreen .jump-detail { display: none; }
.panel-heading {
  display: flex;
  min-height: 55px;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
  padding: 7px 12px 7px 15px;
  border-bottom: 1px solid var(--line);
  font-weight: 750;
}
.panel-heading > div { display: flex; align-items: center; gap: 5px; }
.panel-heading button {
  min-width: 34px;
  min-height: 36px;
  padding: 2px 4px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--accent);
  font-size: 12px;
  font-weight: 650;
}
.panel-heading button:last-child { font-size: 20px; font-weight: 500; }
.panel-heading button:hover { background: var(--wash); }
.detail-heading i, .type-list i { width: 9px; height: 9px; flex: 0 0 9px; border-radius: 50%; }
.type-list { display: grid; gap: 5px; padding: 10px; }
.type-list button {
  display: grid;
  min-height: 44px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  padding: 6px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--wash);
  text-align: left;
}
.type-list button:hover { border-color: var(--field-line); }
.type-list button.inactive { background: transparent; }
.type-list button.inactive svg { visibility: hidden; }
.type-list strong, .type-list small { display: block; }
.type-list strong { font-size: 13px; }
.type-list small { color: var(--muted); font-size: 12px; }
.type-list svg { width: 15px; height: 15px; color: var(--accent); }
.filter-empty, .detail-empty { display: grid; gap: 9px; justify-items: start; padding: 18px 15px; color: var(--muted); font-size: 14px; }
.detail-empty svg { width: 30px; height: 30px; }
.coverage-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 12px 14px; border-top: 1px solid var(--line); gap: 10px; }
.coverage-strip > div { display: grid; }
.coverage-strip strong { color: var(--accent); font-size: 17px; font-variant-numeric: tabular-nums; }
.coverage-strip span, .coverage-strip p { color: var(--muted); font-size: 12px; }
.coverage-strip p { grid-column: 1 / -1; }
.interaction-help { padding: 11px 14px 14px; border-top: 1px solid var(--line); font-size: 12px; }
.interaction-help > p { margin-bottom: 6px; font-weight: 700; }
.interaction-help dl > div { display: flex; flex-wrap: wrap; gap: 0 6px; }
.interaction-help dd { color: var(--muted); }

.network-toolbar {
  display: flex;
  min-height: 55px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px 12px;
  padding: 6px 12px 6px 16px;
  border-bottom: 1px solid var(--line);
}
.result-summary { min-width: 0; overflow-wrap: anywhere; }
.result-summary h2 { font-size: 16px; }
.result-summary p, .result-summary > span { color: var(--muted); font-size: 13px; }
.result-summary.path-result { flex-basis: 100%; padding-block: 7px; }
.path-result ol { display: flex; flex-wrap: wrap; gap: 4px 12px; margin: 8px 0 5px; padding-left: 20px; color: var(--accent); font-size: 13px; }
.path-result li { padding-right: 10px; }
.path-result li small { margin-inline: 6px; padding: 2px 3px; color: var(--muted); font-size: 12px; }
.tool-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 3px; color: var(--muted); }
.tool-actions > span { min-width: 4ch; text-align: center; font: 12px/1.4 var(--mono); }
.tool-actions button, .evidence-highlight-banner button {
  display: inline-flex;
  min-width: 34px;
  min-height: 36px;
  justify-content: center;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
}
.tool-actions button:disabled { color: var(--muted); opacity: .58; }
.tool-actions button:not(:disabled):hover, .evidence-highlight-banner button:hover { border-color: var(--field-line); }
.tool-actions button[aria-expanded="true"] { border-color: var(--line); background: var(--tint); }
.tool-actions svg { width: 16px; height: 16px; }
.evidence-highlight-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 13px;
  border-bottom: 1px solid var(--line);
  background: var(--tint);
  color: var(--accent);
  overflow-wrap: anywhere;
}
.evidence-highlight-banner span { display: block; font-size: 12px; }
.evidence-highlight-banner strong { display: block; font-size: 14px; }
.evidence-highlight-banner button { flex: 0 0 auto; border-color: var(--field-line); }

.graph-stage {
  position: relative;
  isolation: isolate;
  min-height: clamp(398px, 57vh, 620px);
  overflow: hidden;
  border-radius: 0 0 var(--radius) var(--radius);
  background: var(--canvas);
}
.network-grid { position: absolute; inset: 0; background-image: radial-gradient(#d1dac8 1px, transparent 1px); background-size: 20px 20px; pointer-events: none; }
.cy-canvas { position: absolute; inset: 0; width: 100%; height: 100%; outline: none; cursor: grab; touch-action: none; }
.cy-canvas:active { cursor: grabbing; }
.graph-orbits { fill: none; stroke: #d7dfce; stroke-width: 1; stroke-dasharray: 3 6; pointer-events: none; }
#graph-edge-arrow path { fill: #647d68; }
.svg-edge { pointer-events: none; }
.svg-edge line { stroke: #8b9e8b; stroke-width: 1.6; }
.svg-edge text { fill: var(--muted); stroke: var(--canvas); stroke-width: 3px; paint-order: stroke; text-anchor: middle; font-size: 11px; font-weight: 700; }
.svg-edge.focused line { stroke: var(--accent); stroke-width: 2.5; }
.svg-edge.evidence line { stroke: #46602c; stroke-width: 4; }
.svg-edge.evidence text { fill: #294c25; font-weight: 800; }
.svg-edge.dimmed { opacity: .28; }
.svg-node { cursor: pointer; outline: none; }
.svg-node.dimmed { opacity: .43; }
.svg-node:is(:focus-visible, :hover, .selected, .evidence) { opacity: 1; }
.node-backplate { opacity: .16; }
.node-core { stroke-width: 2; }
.node-halo { stroke-width: 1.2; opacity: .65; }
.svg-node.selected .node-core, .svg-node.evidence .node-core { stroke-width: 4; }
.svg-node:focus-visible .node-core { stroke: var(--ink); stroke-width: 5; }
.node-glyph { text-anchor: middle; dominant-baseline: central; font-size: 25px; font-weight: 800; }
.center .node-glyph { font-size: 34px; }
.node-label-bg { fill: var(--surface); stroke: #c0cdbd; }
.selected .node-label-bg, .evidence .node-label-bg { fill: var(--tint); stroke: var(--node-color); }
.svg-node:focus-visible .node-label-bg { stroke: var(--ink); stroke-width: 2.5; }
.node-caption { fill: var(--ink); text-anchor: middle; font-size: 12px; font-weight: 700; }
.canvas-state {
  position: absolute;
  inset: 0;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 10px;
  padding: 18px;
  text-align: center;
}
.canvas-state > svg, .detail-empty > svg { width: 39px; height: 39px; fill: none; stroke: currentColor; stroke-width: 1.45; stroke-linecap: round; stroke-linejoin: round; color: var(--accent); }
.canvas-state h2 { font-size: 19px; }
.canvas-state p { max-width: 420px; color: var(--muted); font-size: 14px; }
.error-state h2, .error-state > svg, .error-state > strong { color: var(--danger); }
.expand-status, .truncate-badge {
  position: absolute;
  bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: calc(100% - 24px);
  padding: 6px 9px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  color: var(--accent);
  font-size: 12px;
}
.truncate-badge { right: 12px; }
.expand-status { left: 12px; z-index: 1; }
.expand-status.error { color: var(--danger); }
.mini-loader { width: 11px; height: 11px; border: 2px solid var(--field-line); border-top-color: var(--accent); border-radius: 50%; animation: spin 900ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.jump-detail { display: none; }
.graph-skip:focus-visible {
  position: static;
  width: auto;
  height: auto;
  margin: 8px;
  padding: 7px;
  clip-path: none;
  border: 0;
  border-radius: 5px;
  background: var(--wash);
  color: var(--accent);
}

.entity-summary { padding: 13px 15px 0; }
.entity-image { display: grid; height: 132px; place-items: center; margin-bottom: 12px; border: 1px solid var(--line); border-radius: var(--control-radius); background: var(--wash); }
.entity-image img { width: 100%; height: 100%; max-height: 130px; object-fit: contain; }
.entity-identity span { color: var(--accent); font-size: 12px; font-weight: 700; }
.entity-identity h2 { margin-top: 3px; font-size: 19px; overflow-wrap: anywhere; }
.entity-actions { display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 15px; }
.entity-actions .ui-button { min-height: 38px; gap: 4px; padding-inline: 8px; font-size: 13px; }
.entity-actions svg { width: 15px; height: 15px; }
.detail-tabs { display: flex; margin: 0 12px; border-bottom: 1px solid var(--line); }
.detail-tabs button {
  min-width: 0;
  min-height: 39px;
  flex: 1;
  padding: 4px 3px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
}
.detail-tabs button:hover, .detail-tabs .active { color: var(--accent); }
.detail-tabs .active { border-bottom-color: var(--accent); }
.detail-tabs span { font-variant-numeric: tabular-nums; }
.detail-scroll { max-height: 394px; padding: 4px 13px 12px; overflow-y: auto; }
.detail-scroll [role="tabpanel"]:focus-visible, .comparison-table:focus-visible { outline-offset: -2px; }
.relation-list button {
  display: flex;
  width: 100%;
  min-height: 40px;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 6px 4px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  text-align: left;
  font-size: 14px;
  overflow-wrap: anywhere;
}
.relation-list button:hover { background: var(--wash); }
.relation-list button small { flex: 0 0 auto; padding: 2px 5px; border-radius: 4px; background: var(--wash); color: var(--accent); font-size: 11px; }
.property-list dt, .evidence-panel dt { color: var(--muted); font-size: 12px; }
.property-list dl > div, .evidence-panel dl > div { padding: 8px 4px; border-bottom: 1px solid var(--line); }
.property-list dd, .evidence-panel dd { font-size: 14px; overflow-wrap: anywhere; }
.property-list dd span { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.property-list dd span.expanded { display: block; }
.property-list button, .property-list a { padding: 4px 0; border: 0; background: transparent; color: var(--accent); font-size: 13px; font-weight: 750; text-decoration: underline; }
.evidence-status { margin-top: 7px; padding: 9px; border-radius: 6px; background: var(--wash); color: var(--accent); font-size: 14px; overflow-wrap: anywhere; }
.evidence-panel > a, .evidence-panel > p { display: block; margin-top: 8px; font-size: 13px; }
.no-properties { padding: 12px 4px; color: var(--muted); font-size: 14px; }

.compare-workspace { padding: 18px; }
.compare-state { display: grid; min-height: 196px; align-content: center; justify-items: start; gap: 8px; padding: 12px; }
.compare-state > p { color: var(--muted); }
.comparison-header { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: stretch; gap: 12px; }
.product-card { min-width: 0; padding: 15px; border-radius: var(--control-radius); background: var(--wash); overflow-wrap: anywhere; }
.product-card > span { color: var(--muted); font-size: 13px; }
.product-card h2 { margin-block: 3px; font-size: 20px; }
.product-card p { margin-bottom: 10px; }
.comparison-score { display: grid; align-content: center; min-width: 110px; padding: 8px; text-align: center; }
.comparison-score strong { color: var(--accent); font-size: 27px; }
.comparison-score span, .comparison-score small { color: var(--muted); font-size: 13px; }
.comparison-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-block: 16px 22px; }
.comparison-block { margin-top: 18px; }
.comparison-title { padding-block: 10px; border-top: 1px solid var(--line); }
.comparison-title h3 { font-size: 17px; }
.comparison-title p { margin-top: 4px; color: var(--muted); font-size: 13px; }
.comparison-table { overflow-x: auto; }
.comparison-table table { width: 100%; min-width: 400px; border-collapse: collapse; table-layout: fixed; text-align: left; font-size: 14px; }
.comparison-table th, .comparison-table td { padding: 8px; border-bottom: 1px solid var(--line); vertical-align: top; overflow-wrap: anywhere; }
.comparison-table th:first-child { width: 22%; }
.comparison-table th:last-child { width: 14%; }
.comparison-table thead { background: var(--wash); }
.difference { display: inline-block; padding: 3px 5px; border-radius: 4px; background: var(--warn-bg); color: var(--warn); font-size: 12px; white-space: nowrap; }
.difference.same { background: var(--tint); color: var(--accent); }
.relation-comparison article { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
.relation-comparison article header { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.relation-comparison article header span { color: var(--muted); font-size: 13px; }
.relation-diff-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.relation-diff-grid > div { display: grid; align-content: start; gap: 5px; padding: 10px; border-radius: var(--control-radius); background: var(--wash); font-size: 13px; overflow-wrap: anywhere; }
.relation-diff-grid p { color: var(--muted); }
.relation-diff-grid span { display: inline-block; margin: 3px 4px 0 0; padding: 3px 5px; border-radius: 4px; background: var(--surface); }

@media (max-width: 1140px) {
  .workspace, .workspace.filter-collapsed { grid-template-columns: minmax(0, 1fr) 280px; }
  .workspace.detail-collapsed { grid-template-columns: minmax(0, 1fr); }
  .filter-panel { grid-column: 1 / -1; }
  .type-list { grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); }
  .coverage-strip, .interaction-help { display: none; }
}
@media (max-width: 800px) {
  .workspace, .workspace.filter-collapsed, .workspace.detail-collapsed { grid-template-columns: minmax(0, 1fr); }
  .graph-stage { min-height: clamp(320px, 44vh, 420px); }
  .network-panel:fullscreen .graph-stage { min-height: 0; }
  .jump-detail { display: flex; min-height: 44px; width: calc(100% - 20px); margin: 10px; overflow-wrap: anywhere; }
  .detail-scroll { max-height: none; overflow: visible; }
}
@media (max-width: 720px) {
  .mode-switch { width: 100%; }
  .mode-switch button { min-height: 44px; flex: 1; padding-inline: 5px; font-size: 13px; }
  .query-dock { padding: 12px; }
  .sample-row button { min-height: 42px; }
  .path-search, .compare-search { grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 8px; }
  .path-search > button[type="submit"], .compare-search > button[type="submit"] { grid-column: 1 / -1; }
  .tool-actions button, .detail-tabs button, .panel-heading button, .entity-actions .ui-button { min-height: 44px; }
  .network-toolbar { padding-inline: 10px; }
  .tool-actions .detail-toggle { display: none; }
  .relation-diff-grid, .comparison-header { grid-template-columns: minmax(0, 1fr); }
  .comparison-score { grid-row: 3; justify-items: start; padding: 0; }
  .compare-workspace { padding: 12px; }
}
@media (pointer: coarse) {
  .cy-canvas { touch-action: pan-y pinch-zoom; }
  .network-panel:fullscreen .cy-canvas { touch-action: none; }
}
</style>
