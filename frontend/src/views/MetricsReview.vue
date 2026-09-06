<template>
  <div class="page">
    <PageHeader title="效果复盘" description="回采公开指标，补充商业数据，并生成可沉淀策略的复盘报告。">
      <el-button :icon="RefreshCw" @click="collectMetrics">回采公开指标</el-button>
      <el-button type="primary" :icon="FileText" @click="generateReport">生成复盘报告</el-button>
      <el-button type="success" :icon="ArrowRight" @click="$router.push('/strategy')">查看策略记忆更新</el-button>
    </PageHeader>

    <el-card shadow="never">
      <el-form :inline="true" label-width="116px">
        <el-form-item label="已发布实验">
          <el-select v-model="selectedExperimentId" style="width: 280px">
            <el-option v-for="item in publishedExperiments" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="grid grid-4">
      <MetricCard title="点赞" :value="publicMetrics.likes" :icon="ThumbsUp" />
      <MetricCard title="收藏" :value="publicMetrics.collects" :icon="Bookmark" />
      <MetricCard title="评论" :value="publicMetrics.comments" :icon="MessageSquare" />
      <MetricCard title="回采时间" :value="publicMetrics.collectedAt" :icon="Clock3" />
    </div>

    <div class="grid metrics-grid">
      <el-card shadow="never">
        <template #header><strong>增长趋势</strong></template>
        <VChart class="chart" :option="trendOption" autoresize />
      </el-card>
      <el-card shadow="never">
        <template #header><strong>商业数据补充</strong></template>
        <el-form label-width="88px">
          <el-form-item label="私信数"><el-input-number v-model="business.privateMessages" :min="0" /></el-form-item>
          <el-form-item label="线索数"><el-input-number v-model="business.leads" :min="0" /></el-form-item>
          <el-form-item label="成交数"><el-input-number v-model="business.deals" :min="0" /></el-form-item>
          <el-form-item label="成交金额"><el-input-number v-model="business.revenue" :min="0" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="business.note" type="textarea" :rows="3" /></el-form-item>
        </el-form>
      </el-card>
    </div>

    <div class="grid grid-4">
      <MetricCard title="点赞率" :value="performanceReport.likeRate" :icon="Gauge" />
      <MetricCard title="收藏率" :value="performanceReport.collectRate" :icon="Gauge" />
      <MetricCard title="线索率" :value="performanceReport.leadRate" :icon="Target" />
      <MetricCard title="ROI" :value="performanceReport.roi" :icon="CircleDollarSign" />
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="toolbar">
          <strong>复盘报告</strong>
          <el-tag :type="performanceReport.goalReached ? 'success' : 'warning'">{{ performanceReport.goalReached ? '目标达成' : '待优化' }}</el-tag>
        </div>
      </template>
      <div class="grid grid-3">
        <div><h4>成功原因</h4><ul class="compact-list"><li class="list-item" v-for="item in performanceReport.successReasons" :key="item">{{ item }}</li></ul></div>
        <div><h4>失败原因</h4><ul class="compact-list"><li class="list-item" v-for="item in performanceReport.failureReasons" :key="item">{{ item }}</li></ul></div>
        <div><h4>下次优化建议</h4><ul class="compact-list"><li class="list-item" v-for="item in performanceReport.nextActions" :key="item">{{ item }}</li></ul></div>
      </div>
      <el-divider />
      <el-checkbox :model-value="performanceReport.updateStrategyMemory" disabled>生成后更新策略记忆</el-checkbox>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import 'echarts'
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { ArrowRight, Bookmark, CircleDollarSign, Clock3, FileText, Gauge, MessageSquare, RefreshCw, Target, ThumbsUp } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import { businessMetrics, performanceReport, publicMetrics } from '@/mock/metrics'
import { useExperimentStore } from '@/stores/experiment'

const store = useExperimentStore()
const publishedExperiments = store.experiments.filter((item) => item.published || item.id === store.selectedExperimentId)
const selectedExperimentId = ref(store.selectedExperimentId)
const business = reactive({ ...businessMetrics })

const trendOption = {
  tooltip: { trigger: 'axis' },
  legend: { top: 0 },
  grid: { left: 40, right: 18, top: 40, bottom: 24 },
  xAxis: { type: 'category', data: publicMetrics.trend.map((item) => item.date) },
  yAxis: { type: 'value' },
  series: [
    { name: '点赞', type: 'line', smooth: true, data: publicMetrics.trend.map((item) => item.likes) },
    { name: '收藏', type: 'line', smooth: true, data: publicMetrics.trend.map((item) => item.collects) },
    { name: '评论', type: 'line', smooth: true, data: publicMetrics.trend.map((item) => item.comments) }
  ]
}

const collectMetrics = () => ElMessage.success('已模拟回采公开指标')
const generateReport = () => {
  store.markAnalyzed(performanceReport.businessValue)
  ElMessage.success('复盘报告已生成，策略记忆可更新')
}
</script>

<style scoped>
.metrics-grid {
  grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.8fr);
}
</style>
