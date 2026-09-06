<template>
  <div class="page">
    <PageHeader title="内容实验详情" description="查看单次内容实验从创建到策略更新的完整生命周期。">
      <el-button :icon="PenLine" @click="$router.push('/drafts')">生成草稿</el-button>
      <el-button type="primary" :icon="UploadCloud" @click="$router.push('/publish')">进入发布辅助</el-button>
    </PageHeader>

    <div class="grid grid-4">
      <MetricCard title="目标指标" :value="experiment.targetMetric" :icon="Target" />
      <MetricCard title="当前状态" :value="statusText" :icon="Activity" />
      <MetricCard title="商业价值" :value="`¥${experiment.businessValue}`" :icon="CircleDollarSign" />
      <MetricCard title="关联策略" value="5 条" :icon="BrainCircuit" />
    </div>

    <div class="grid detail-grid">
      <el-card shadow="never">
        <template #header><strong>实验基本信息</strong></template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="实验名称">{{ experiment.name }}</el-descriptions-item>
          <el-descriptions-item label="实验假设">{{ experiment.hypothesis }}</el-descriptions-item>
          <el-descriptions-item label="预期结果">{{ experiment.expectedResult }}</el-descriptions-item>
          <el-descriptions-item label="选题角度">{{ experiment.topicAngle }}</el-descriptions-item>
          <el-descriptions-item label="状态"><StatusTag :status="experiment.status" /></el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ experiment.publishedAt || '未发布' }}</el-descriptions-item>
          <el-descriptions-item label="发布链接">{{ experiment.publishUrl || store.demoPublishUrl || '待填写' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>关联数据</strong></template>
        <ul class="compact-list">
          <li class="list-item" v-for="item in relatedData" :key="item.name">
            <span>{{ item.name }}</span>
            <el-tag :type="item.done ? 'success' : 'info'">{{ item.done ? '已就绪' : '待补充' }}</el-tag>
          </li>
        </ul>
      </el-card>
    </div>

    <el-card shadow="never">
      <template #header><strong>生命周期时间线</strong></template>
      <el-steps :active="activeStep" finish-status="success" process-status="process" align-center>
        <el-step v-for="step in steps" :key="step" :title="step" />
      </el-steps>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Activity, BrainCircuit, CircleDollarSign, PenLine, Target, UploadCloud } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useExperimentStore } from '@/stores/experiment'

const store = useExperimentStore()
const experiment = computed(() => store.selectedExperiment)

const statusText = computed(() => {
  const map: Record<string, string> = { DRAFT: '草稿', READY: '待发布', PUBLISHED: '已发布', METRICS_COLLECTED: '已回采', ANALYZED: '已复盘', FAILED: '失败' }
  return map[experiment.value.status]
})

const activeStep = computed(() => (experiment.value.status === 'ANALYZED' ? 7 : experiment.value.status === 'PUBLISHED' ? 3 : store.draftGenerated ? 2 : 1))
const steps = ['创建实验', '生成草稿', '审核通过', '人工发布', '回采指标', '补充商业数据', '生成复盘', '更新策略']
const relatedData = computed(() => [
  { name: '账号配置', done: true },
  { name: '竞品分析报告', done: true },
  { name: '策略记忆', done: true },
  { name: '草稿版本', done: store.draftGenerated },
  { name: '审核报告', done: store.reviewGenerated },
  { name: '公开指标快照', done: experiment.value.published },
  { name: '商业数据', done: experiment.value.businessValue > 0 },
  { name: '复盘报告', done: experiment.value.status === 'ANALYZED' }
])
</script>

<style scoped>
.detail-grid {
  grid-template-columns: minmax(0, 1.6fr) minmax(360px, 1fr);
}
</style>
