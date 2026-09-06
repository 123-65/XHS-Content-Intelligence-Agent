<template>
  <div class="page">
    <PageHeader title="内容实验" description="管理从竞品分析、策略记忆和账号目标生成的内容实验。">
      <el-button type="primary" :icon="Plus" @click="$router.push('/competitor/analysis')">新建实验</el-button>
    </PageHeader>

    <div class="grid grid-4">
      <MetricCard title="实验总数" :value="store.experiments.length" :icon="FlaskConical" />
      <MetricCard title="待发布" :value="readyCount" :icon="Clock3" />
      <MetricCard title="已复盘" :value="analyzedCount" :icon="CheckCircle2" />
      <MetricCard title="累计商业价值" :value="`¥${totalValue}`" :icon="CircleDollarSign" />
    </div>

    <el-card shadow="never">
      <template #header><strong>实验列表</strong></template>
      <el-table :data="store.experiments" stripe>
        <el-table-column prop="name" label="实验名称" min-width="220" />
        <el-table-column prop="topicDirection" label="选题方向" width="110" />
        <el-table-column prop="hypothesis" label="实验假设" min-width="260" />
        <el-table-column prop="targetMetric" label="目标指标" width="130" />
        <el-table-column label="状态" width="115"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="是否发布" width="100"><template #default="{ row }">{{ row.published ? '是' : '否' }}</template></el-table-column>
        <el-table-column label="商业价值" width="110"><template #default="{ row }">¥{{ row.businessValue }}</template></el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="155" />
        <el-table-column label="操作" fixed="right" width="260">
          <template #default="{ row }">
            <el-button text type="primary" @click="$router.push(`/experiments/${row.id}`)">查看详情</el-button>
            <el-button text @click="$router.push('/drafts')">生成草稿</el-button>
            <el-button text @click="$router.push('/metrics')">复盘分析</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircle2, CircleDollarSign, Clock3, FlaskConical, Plus } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useExperimentStore } from '@/stores/experiment'

const store = useExperimentStore()
const readyCount = computed(() => store.experiments.filter((item) => item.status === 'READY').length)
const analyzedCount = computed(() => store.experiments.filter((item) => item.status === 'ANALYZED').length)
const totalValue = computed(() => store.experiments.reduce((sum, item) => sum + item.businessValue, 0))
</script>
