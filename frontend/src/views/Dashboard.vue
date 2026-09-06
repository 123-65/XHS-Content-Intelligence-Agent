<template>
  <div class="page">
    <PageHeader title="仪表盘" description="查看账号目标、内容增长漏斗和最近实验表现。">
      <el-button type="primary" :icon="ArrowRight" @click="$router.push('/competitor/collect')">开始竞品采集</el-button>
    </PageHeader>

    <div class="kpi-strip">
      <MetricCard title="累计采集笔记数" :value="128" delta="+16 本周" :icon="Database" />
      <MetricCard title="内容实验数" :value="experiments.length" delta="+1 今日" :icon="FlaskConical" />
      <MetricCard title="已发布内容数" :value="2" delta="发布率 67%" :icon="UploadCloud" />
      <MetricCard title="累计线索数" :value="42" delta="+18 本周" :icon="MessageCircle" />
      <MetricCard title="累计成交金额" value="¥3,956" delta="ROI 6.2" :icon="CircleDollarSign" />
      <MetricCard title="策略记忆条数" :value="strategyMemories.length" delta="+2 更新" :icon="BrainCircuit" />
    </div>

    <el-card shadow="never">
      <template #header><strong>内容增长漏斗</strong></template>
      <el-steps :active="5" finish-status="success" process-status="process" align-center>
        <el-step title="公开笔记采集" />
        <el-step title="内容实验" />
        <el-step title="发布" />
        <el-step title="回采指标" />
        <el-step title="商业复盘" />
        <el-step title="策略更新" />
      </el-steps>
    </el-card>

    <div class="grid grid-2">
      <el-card shadow="never">
        <template #header><strong>最近 7 篇内容互动趋势</strong></template>
        <VChart class="chart" :option="trendOption" autoresize />
      </el-card>
      <el-card shadow="never">
        <template #header><strong>不同内容类型商业价值</strong></template>
        <VChart class="chart" :option="valueOption" autoresize />
      </el-card>
    </div>

    <div class="grid grid-2">
      <el-card shadow="never">
        <template #header><strong>最近内容实验</strong></template>
        <el-table :data="experiments" stripe>
          <el-table-column prop="name" label="实验名称" min-width="190" />
          <el-table-column prop="targetMetric" label="目标指标" width="130" />
          <el-table-column label="状态" width="110"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
          <el-table-column label="商业价值" width="120"><template #default="{ row }">¥{{ row.businessValue }}</template></el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="155" />
        </el-table>
      </el-card>
      <el-card shadow="never">
        <template #header><strong>近期策略洞察</strong></template>
        <ul class="compact-list">
          <li class="list-item" v-for="item in insights" :key="item">
            <span>{{ item }}</span>
            <el-tag type="success" effect="plain">已沉淀</el-tag>
          </li>
        </ul>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import 'echarts'
import VChart from 'vue-echarts'
import { ArrowRight, BrainCircuit, CircleDollarSign, Database, FlaskConical, MessageCircle, UploadCloud } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { experiments } from '@/mock/experiments'
import { businessValueByType, dashboardTrend } from '@/mock/metrics'
import { strategyMemories } from '@/mock/strategy'

const insights = ['项目拆解类内容私信率高', '学习路线类内容收藏率高', '纯工具推荐类内容曝光高但转化低']

const trendOption = {
  tooltip: { trigger: 'axis' },
  legend: { top: 0 },
  grid: { left: 36, right: 18, bottom: 28, top: 40 },
  xAxis: { type: 'category', data: dashboardTrend.map((item) => item.title), axisLabel: { interval: 0, rotate: 25 } },
  yAxis: { type: 'value' },
  series: [
    { name: '点赞', type: 'line', smooth: true, data: dashboardTrend.map((item) => item.likes) },
    { name: '收藏', type: 'line', smooth: true, data: dashboardTrend.map((item) => item.collects) },
    { name: '评论', type: 'line', smooth: true, data: dashboardTrend.map((item) => item.comments) }
  ]
}

const valueOption = {
  tooltip: { trigger: 'axis' },
  grid: { left: 48, right: 18, bottom: 30, top: 28 },
  xAxis: { type: 'category', data: businessValueByType.map((item) => item.type) },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: businessValueByType.map((item) => item.value), itemStyle: { color: '#2563eb', borderRadius: [4, 4, 0, 0] } }]
}
</script>
