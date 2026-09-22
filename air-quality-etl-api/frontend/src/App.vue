<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { BarChart, HeatmapChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

import { buildDashboardQuery, requestJson, toApiDate } from "./lib/api";
import { AQI_LEVELS, aqiLevel, aqiStatusText } from "./lib/aqi";
import { formatCompact, formatDateTime, formatDuration, formatNumber, statusText } from "./lib/formatters";
import { groupOpenApi, parameterDescription, parameterType, responseSchema } from "./lib/openapi";

use([
  BarChart,
  HeatmapChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

const NAV_ITEMS = [
  { id: "dashboard", label: "数据分析" },
  { id: "quality", label: "数据质量" },
  { id: "docs", label: "API 文档" },
];
const loading = ref(true);
const errorMessage = ref("");
const healthStatus = ref("检查中");
const currentView = ref(window.location.hash.replace("#", "") || "dashboard");
const stats = ref(null);
const overview = ref(null);
const stations = ref([]);
const imports = ref([]);
const measurements = ref([]);
const selectedCounty = ref("");
const startDate = ref("");
const endDate = ref("");
const trendType = ref("line");
const openapiDocument = ref(null);
const selectedApiTag = ref("");
const openOperationId = ref("");

const trendRef = ref(null);
const histogramRef = ref(null);
const pieRef = ref(null);
const correlationRef = ref(null);
const charts = new Map();
const chartData = ref({ trend: [], ranking: [], distribution: null, correlation: null });

const counties = computed(() => [...new Set(stations.value.map((item) => item.county))].sort((a, b) => a.localeCompare(b, "zh-CN")));
const selectedStations = computed(() => stations.value.filter((item) => item.county === selectedCounty.value));
const regionTitle = computed(() => selectedCounty.value ? `${selectedCounty.value}空气质量概览` : "全台空气质量概览");
const rankingTitle = computed(() => selectedCounty.value ? `${selectedCounty.value}监测站平均 AQI 排名` : "县市平均 AQI 排名");

const apiGroups = computed(() => groupOpenApi(openapiDocument.value));
const visibleApiGroups = computed(() => selectedApiTag.value
  ? apiGroups.value.filter((group) => group.tag === selectedApiTag.value)
  : apiGroups.value);

function switchView(view) {
  currentView.value = view;
}

function initializeDateRange(latestObservation) {
  const latest = new Date(latestObservation);
  const end = new Date(latest);
  end.setDate(end.getDate() + 1);
  const start = new Date(end);
  start.setDate(start.getDate() - 30);
  startDate.value = start.toISOString().slice(0, 10);
  endDate.value = end.toISOString().slice(0, 10);
}

function chartFor(elementRef, key) {
  if (!elementRef.value) return null;
  let chart = charts.get(key);
  if (!chart) {
    chart = init(elementRef.value);
    charts.set(key, chart);
  }
  return chart;
}

const baseAxis = {
  axisLine: { lineStyle: { color: "#bfddeb" } },
  axisLabel: { color: "#67869a" },
  splitLine: { lineStyle: { color: "#e4f2f8" } },
};

function renderTrend() {
  const chart = chartFor(trendRef, "trend");
  if (!chart) return;
  const rows = chartData.value.trend;
  chart.setOption({
    color: ["#278fc7", "#d78a2e"],
    tooltip: { trigger: "axis" },
    legend: { top: 4, right: 18, textStyle: { color: "#67869a", fontSize: 11 } },
    grid: { left: 48, right: 22, top: 46, bottom: 38 },
    xAxis: {
      ...baseAxis,
      type: "category",
      boundaryGap: trendType.value === "bar",
      data: rows.map((item) => item.bucket.slice(5, 10)),
    },
    yAxis: { ...baseAxis, type: "value", name: "AQI" },
    series: [
      {
        name: "日均 AQI",
        type: trendType.value,
        smooth: true,
        symbolSize: 6,
        data: rows.map((item) => item.average_aqi),
        itemStyle: { color: "#278fc7" },
        lineStyle: { width: 2.5, color: "#278fc7" },
        areaStyle: trendType.value === "line" ? { color: "rgba(88,180,232,.14)" } : undefined,
      },
      {
        name: "7 日移动平均",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: rows.map((item) => item.moving_average),
        lineStyle: { width: 2, type: "dashed", color: "#d78a2e" },
      },
    ],
  }, true);
}

function renderHistogram() {
  const chart = chartFor(histogramRef, "histogram");
  if (!chart || !chartData.value.distribution) return;
  const rows = chartData.value.distribution.histogram;
  chart.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 58, right: 20, top: 22, bottom: 48 },
    xAxis: { ...baseAxis, type: "category", name: "AQI 区间", data: rows.map((item) => item.label), axisLabel: { ...baseAxis.axisLabel, rotate: 30 } },
    yAxis: { ...baseAxis, type: "value", name: "记录数" },
    series: [{ type: "bar", data: rows.map((item) => item.count), barMaxWidth: 34, itemStyle: { color: "#58b4e8", borderRadius: [5, 5, 0, 0] } }],
  }, true);
}

function renderPie() {
  const chart = chartFor(pieRef, "pie");
  if (!chart || !chartData.value.distribution) return;
  chart.setOption({
    tooltip: { trigger: "item", formatter: "{b}<br/>{c} 条（{d}%）" },
    legend: { type: "scroll", bottom: 0, textStyle: { color: "#67869a", fontSize: 10 } },
    color: AQI_LEVELS.map((item) => item.color),
    series: [{
      name: "AQI 等级",
      type: "pie",
      radius: ["44%", "70%"],
      center: ["50%", "43%"],
      minShowLabelAngle: 2,
      itemStyle: { borderColor: "#fff", borderWidth: 3, borderRadius: 6 },
      label: { formatter: (item) => item.percent >= 2 ? `${item.name}\n${item.percent}%` : "" },
      data: chartData.value.distribution.categories.map((item) => ({ name: item.name, value: item.count })),
    }],
  }, true);
}

function renderCorrelation() {
  const chart = chartFor(correlationRef, "correlation");
  if (!chart || !chartData.value.correlation) return;
  const { labels, matrix } = chartData.value.correlation;
  const data = [];
  matrix.forEach((row, y) => row.forEach((value, x) => {
    if (value !== null) data.push([x, y, value]);
  }));
  chart.setOption({
    tooltip: { formatter: (item) => `${labels[item.value[1]]} × ${labels[item.value[0]]}<br/>相关系数：${item.value[2]}` },
    grid: { left: 62, right: 70, top: 18, bottom: 48 },
    xAxis: { ...baseAxis, type: "category", data: labels, splitArea: { show: true } },
    yAxis: { ...baseAxis, type: "category", data: labels, splitArea: { show: true } },
    visualMap: { min: -1, max: 1, calculable: true, orient: "vertical", right: 4, top: "center", inRange: { color: ["#3c7ba4", "#f6fbfe", "#d95d5d"] } },
    series: [{ type: "heatmap", data, label: { show: true, formatter: (item) => item.value[2].toFixed(2), color: "#183b52" } }],
  }, true);
}

async function renderAllCharts() {
  await nextTick();
  renderTrend();
  renderHistogram();
  renderPie();
  renderCorrelation();
  charts.forEach((chart) => chart.resize());
}

async function loadDashboard() {
  if (!startDate.value || !endDate.value) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    const baseQuery = buildDashboardQuery(startDate.value, endDate.value, selectedCounty.value);
    const rankingParams = new URLSearchParams({
      start: toApiDate(startDate.value),
      end: toApiDate(endDate.value),
      limit: "100",
    });
    if (selectedCounty.value) rankingParams.set("county", selectedCounty.value);
    const rankingEndpoint = selectedCounty.value ? "stations" : "counties";
    const [overviewData, trendData, distributionData, rankingData, correlationData, importData, measurementData] = await Promise.all([
      requestJson(`/api/v1/dashboard/overview?${baseQuery}`),
      requestJson(`/api/v1/dashboard/trend?${baseQuery}&interval=day`),
      requestJson(`/api/v1/dashboard/distribution?${baseQuery}`),
      requestJson(`/api/v1/analytics/${rankingEndpoint}?${rankingParams}`),
      requestJson(`/api/v1/dashboard/correlation?${baseQuery}`),
      requestJson("/api/v1/imports?status=COMPLETED&limit=5"),
      requestJson(`/api/v1/measurements?${baseQuery}&limit=8`),
    ]);
    overview.value = overviewData;
    imports.value = importData;
    measurements.value = measurementData.items;
    chartData.value = { trend: trendData, ranking: rankingData, distribution: distributionData, correlation: correlationData };
    await renderAllCharts();
  } catch (error) {
    errorMessage.value = error.message || "加载看板失败";
  } finally {
    loading.value = false;
  }
}

async function selectCounty(county) {
  if (loading.value || selectedCounty.value === county) return;
  selectedCounty.value = county;
  await loadDashboard();
}

async function bootstrap() {
  try {
    const [health, statsData, stationData, openapiData] = await Promise.all([
      requestJson("/health"),
      requestJson("/api/v1/stats"),
      requestJson("/api/v1/stations?limit=1000"),
      requestJson("/openapi.json"),
    ]);
    healthStatus.value = health.status;
    stats.value = statsData;
    stations.value = stationData.items;
    openapiDocument.value = openapiData;
    initializeDateRange(statsData.latest_observation);
    const firstOperation = apiGroups.value[0]?.operations[0];
    if (firstOperation) openOperationId.value = firstOperation.id;
    await loadDashboard();
  } catch (error) {
    healthStatus.value = "异常";
    errorMessage.value = error.message || "初始化失败";
    loading.value = false;
  }
}

function rankingName(row) {
  return selectedCounty.value ? row.site_name : row.county;
}

function toggleOperation(operationId) {
  openOperationId.value = openOperationId.value === operationId ? "" : operationId;
}

function resizeCharts() {
  charts.forEach((chart) => chart.resize());
}

watch(trendType, renderTrend);
watch(currentView, async (view) => {
  window.history.replaceState(null, "", `#${view}`);
  await renderAllCharts();
});

onMounted(() => {
  if (!NAV_ITEMS.some((item) => item.id === currentView.value)) currentView.value = "dashboard";
  bootstrap();
  window.addEventListener("resize", resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeCharts);
  charts.forEach((chart) => chart.dispose());
});
</script>

<template>
  <div class="page-shell">
    <header class="topbar">
      <div class="brand-block">
        <div>
          <strong>空气质量数据平台</strong>
          <span>AIR QUALITY DATA PLATFORM</span>
        </div>
      </div>
      <nav class="global-nav" aria-label="主导航">
        <button
          v-for="item in NAV_ITEMS"
          :key="item.id"
          :class="{ active: currentView === item.id }"
          @click="switchView(item.id)"
        >{{ item.label }}</button>
      </nav>
      <div class="top-meta">
        <span v-if="stats">数据更新至 {{ stats.latest_observation?.slice(0, 10) }}</span>
        <span class="service-state">服务{{ healthStatus }}</span>
      </div>
    </header>

    <section v-show="currentView === 'dashboard'" class="workspace">
      <aside class="sidebar">
        <div class="sidebar-title"><strong>区域范围</strong><span>树状筛选</span></div>
        <div class="tree">
          <button class="level-0" :class="{ selected: !selectedCounty }" @click="selectCounty('')">全台监测网络</button>
          <template v-for="county in counties" :key="county">
            <button class="level-1" :class="{ selected: selectedCounty === county }" @click="selectCounty(county)">{{ county }}</button>
            <div v-if="selectedCounty === county" class="station-children">
              <span v-for="station in selectedStations" :key="station.id_station">{{ station.site_name }}站</span>
            </div>
          </template>
        </div>
        <p class="tree-note">数据源没有行政区字段，因此县市的下一层按监测站展示，不推测或补造区县数据。</p>
      </aside>

      <main class="main-content">
        <div class="page-heading">
          <div><h1>{{ regionTitle }}</h1><p>监测站趋势、污染等级与数据质量统一分析</p></div>
          <span class="updated">最近刷新：刚刚</span>
        </div>

        <section class="filterbar">
          <label class="field"><span>开始日期</span><input v-model="startDate" type="date" /></label>
          <label class="field"><span>结束日期</span><input v-model="endDate" type="date" /></label>
          <label class="field"><span>指标</span><select><option>AQI 综合指数</option><option>PM2.5</option><option>PM10</option></select></label>
          <button class="primary-button" :disabled="loading" @click="loadDashboard">{{ loading ? "正在分析" : "更新分析" }}</button>
        </section>

        <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

        <section v-if="overview" class="kpi-grid">
          <article class="kpi-card"><span>观测记录</span><strong>{{ formatCompact(overview.total_measurements) }}</strong><small>精确值 {{ formatNumber(overview.total_measurements) }}</small></article>
          <article class="kpi-card"><span>覆盖站点</span><strong>{{ formatNumber(overview.total_stations) }}</strong><small>当前区域</small></article>
          <article class="kpi-card"><span>平均 AQI</span><strong>{{ overview.average_aqi ?? '--' }}</strong><small>自动按时段聚合</small></article>
          <article class="kpi-card"><span>最高 AQI</span><strong>{{ overview.maximum_aqi ?? '--' }}</strong><small>筛选范围内峰值</small></article>
          <article class="kpi-card"><span>数据完整率</span><strong>{{ (100 - overview.missing_aqi_rate).toFixed(2) }}%</strong><small>缺失 {{ formatNumber(overview.missing_aqi_count) }} 条</small></article>
        </section>

        <section class="primary-grid">
          <article class="panel">
            <div class="panel-heading"><div><p>时间趋势</p><h2>AQI 日均值与 7 日移动平均</h2></div><div class="segmented"><button :class="{ active: trendType === 'line' }" @click="trendType = 'line'">折线</button><button :class="{ active: trendType === 'bar' }" @click="trendType = 'bar'">柱状</button></div></div>
            <div ref="trendRef" class="chart trend-chart"></div>
          </article>
          <article class="panel ranking-panel">
            <div class="panel-heading"><div><p>区域对比</p><h2>{{ rankingTitle }}</h2></div><span class="updated">按真实数据</span></div>
            <div class="table-scroll ranking-scroll">
              <table class="ranking-table">
                <thead><tr><th>排名</th><th>{{ selectedCounty ? '监测站' : '县市' }}</th><th>平均 AQI</th><th>等级</th></tr></thead>
                <tbody>
                  <tr v-for="(row, index) in chartData.ranking" :key="row.id_station || row.county">
                    <td class="rank-cell">{{ String(index + 1).padStart(2, '0') }}</td>
                    <td>{{ rankingName(row) }}</td>
                    <td>{{ row.average_aqi ?? '--' }}</td>
                    <td><span :class="['aqi-pill', aqiLevel(row.average_aqi).className]">{{ aqiLevel(row.average_aqi).label }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section class="secondary-grid">
          <article class="panel"><div class="panel-heading"><div><p>等级构成</p><h2>空气质量等级分布</h2></div><span class="updated">按观测小时</span></div><div ref="pieRef" class="chart small-chart"></div></article>
          <article class="panel quality-summary"><div class="panel-heading"><div><p>质量审计</p><h2>数据质量概况</h2></div><span class="updated">规则校验</span></div>
            <div v-if="overview" class="quality-list">
              <div class="quality-row"><span>完整记录</span><b>{{ (100 - overview.missing_aqi_rate).toFixed(2) }}%</b><div class="track"><i class="complete" :style="{ width: `${100 - overview.missing_aqi_rate}%` }"></i></div></div>
              <div class="quality-row"><span>AQI 缺失</span><b>{{ overview.missing_aqi_rate }}%</b><div class="track"><i class="missing" :style="{ width: `${Math.max(overview.missing_aqi_rate, 1)}%` }"></i></div></div>
              <div class="quality-row"><span>不健康小时</span><b>{{ formatNumber(overview.unhealthy_hours) }}</b><div class="track"><i class="warning" :style="{ width: `${Math.min(100, overview.unhealthy_hours / Math.max(overview.total_measurements, 1) * 100)}%` }"></i></div></div>
            </div>
          </article>
        </section>
      </main>
    </section>

    <section v-show="currentView === 'quality'" class="standalone-view">
      <div class="page-heading quality-heading"><div><h1>数据质量与处理审计</h1><p>检查缺失值、分布、相关性与 ETL 导入结果</p></div><span class="method-tag">Pandas · NumPy · PostgreSQL</span></div>
      <section class="quality-kpis" v-if="overview && stats">
        <article class="quality-kpi"><span>累计记录</span><strong>{{ formatCompact(stats.total_measurements) }}</strong></article>
        <article class="quality-kpi"><span>AQI 缺失率</span><strong>{{ overview.missing_aqi_rate }}%</strong></article>
        <article class="quality-kpi"><span>拒绝记录</span><strong>{{ formatNumber(stats.rejected_rows) }}</strong></article>
        <article class="quality-kpi"><span>完成导入</span><strong>{{ formatNumber(stats.completed_imports) }}</strong></article>
      </section>
      <section class="quality-chart-grid">
        <article class="panel"><div class="panel-heading"><div><p>频数分析</p><h2>AQI 数值直方图</h2></div><span class="method-tag">NumPy</span></div><div ref="histogramRef" class="chart"></div></article>
        <article class="panel"><div class="panel-heading"><div><p>特征关系</p><h2>污染物相关性热力图</h2></div><span class="method-tag">{{ formatNumber(chartData.correlation?.sample_size || 0) }} 组样本</span></div><div ref="correlationRef" class="chart"></div></article>
      </section>
      <section class="table-grid">
        <article class="panel table-panel"><div class="panel-heading"><div><p>数据预览</p><h2>观测明细</h2></div><span class="method-tag">游标分页</span></div><div class="table-scroll"><table><thead><tr><th>时间</th><th>站点</th><th>县市</th><th>AQI</th><th>PM2.5</th><th>状态</th></tr></thead><tbody><tr v-for="row in measurements" :key="row.id_measurement"><td>{{ formatDateTime(row.observed_at) }}</td><td>{{ row.site_name }}</td><td>{{ row.county }}</td><td><b>{{ row.aqi ?? '--' }}</b></td><td>{{ row.pm25 ?? '--' }}</td><td>{{ aqiStatusText(row.status_code) }}</td></tr></tbody></table></div></article>
        <article class="panel table-panel"><div class="panel-heading"><div><p>流水线状态</p><h2>最近导入任务</h2></div><span class="method-tag">SHA-256 幂等</span></div><div class="table-scroll"><table><thead><tr><th>文件</th><th>状态</th><th>接收</th><th>拒绝</th><th>耗时</th></tr></thead><tbody><tr v-for="row in imports" :key="row.id_import_file"><td>{{ row.filename }}</td><td><span :class="['status-pill', row.status.toLowerCase()]">{{ statusText(row.status) }}</span></td><td>{{ formatNumber(row.accepted_rows) }}</td><td>{{ formatNumber(row.rejected_rows) }}</td><td>{{ formatDuration(row.started_at, row.completed_at) }}</td></tr></tbody></table></div></article>
      </section>
    </section>

    <section v-show="currentView === 'docs'" class="docs-layout">
      <aside class="docs-sidebar">
        <h2>接口目录</h2>
        <button :class="{ selected: !selectedApiTag }" @click="selectedApiTag = ''">全部接口</button>
        <button v-for="group in apiGroups" :key="group.tag" :class="{ selected: selectedApiTag === group.tag }" @click="selectedApiTag = group.tag">{{ group.tag }} <span>{{ group.operations.length }}</span></button>
      </aside>
      <main class="docs-main">
        <div class="docs-heading"><div><h1>{{ openapiDocument?.info?.title || '空气质量数据 API' }}</h1><p>版本 {{ openapiDocument?.info?.version || '1.0.0' }} · 接口说明、参数与响应结构均使用中文呈现</p></div><a class="outline-button" href="/openapi.json" target="_blank">下载 OpenAPI JSON</a></div>
        <template v-for="group in visibleApiGroups" :key="group.tag">
          <p class="docs-group-title">{{ group.tag }}</p>
          <article v-for="operation in group.operations" :key="operation.id" :class="['endpoint', { open: openOperationId === operation.id }]">
            <button class="endpoint-summary" @click="toggleOperation(operation.id)"><b>{{ operation.method }}</b><code>{{ operation.path }}</code><span>{{ operation.summary || '接口说明' }}</span><em>{{ openOperationId === operation.id ? '收起' : '展开' }}</em></button>
            <div v-if="openOperationId === operation.id" class="endpoint-body">
              <p>{{ operation.description || operation.summary || '该接口提供空气质量数据查询服务。' }}</p>
              <h3>请求参数</h3>
              <div class="table-scroll"><table class="parameter-table"><thead><tr><th>名称</th><th>位置</th><th>是否必填</th><th>类型</th><th>说明</th></tr></thead><tbody><tr v-if="!operation.parameters?.length"><td colspan="5">该接口不需要请求参数</td></tr><tr v-for="parameter in operation.parameters || []" :key="`${operation.id}-${parameter.name}`"><td><code>{{ parameter.name }}</code></td><td>{{ parameter.in === 'query' ? '查询参数' : parameter.in === 'path' ? '路径参数' : parameter.in }}</td><td :class="{ required: parameter.required }">{{ parameter.required ? '必填' : '选填' }}</td><td>{{ parameterType(parameter) }}</td><td>{{ parameterDescription(parameter) }}</td></tr></tbody></table></div>
              <h3 class="response-heading">成功响应 <span>200</span></h3>
              <pre class="codebox">{{ responseSchema(operation) }}</pre>
            </div>
          </article>
        </template>
      </main>
    </section>

    <footer><span>空气质量 ETL 与数据分析平台</span><span>FastAPI · PostgreSQL · Pandas · NumPy · Vue 3 · ECharts</span></footer>
  </div>
</template>
