<template>
  <div class="page">
    <PageHeader title="策略记忆" description="沉淀历史内容实验中的有效模式、失败经验和转化洞察。">
      <el-button type="primary" :icon="Plus">新增策略记忆</el-button>
      <el-button type="success" :icon="ArrowRight" @click="$router.push('/workflow-logs')">查看运行日志</el-button>
    </PageHeader>

    <div class="grid grid-4">
      <MetricCard title="策略总数" :value="strategyMemories.length" :icon="BrainCircuit" />
      <MetricCard title="启用策略" :value="enabledCount" :icon="ToggleRight" />
      <MetricCard title="平均权重" :value="averageWeight" :icon="Gauge" />
      <MetricCard title="本周更新" value="2" :icon="RefreshCw" />
    </div>

    <el-card shadow="never">
      <el-tabs v-model="activeCategory">
        <el-tab-pane v-for="category in categories" :key="category" :label="category" :name="category">
          <div class="grid grid-3">
            <StrategyCard v-for="memory in filteredMemories" :key="memory.id" :memory="memory" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, BrainCircuit, Gauge, Plus, RefreshCw, ToggleRight } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StrategyCard from '@/components/StrategyCard.vue'
import { strategyMemories } from '@/mock/strategy'

const categories = ['有效选题模式', '失败选题模式', '标题结构', 'CTA 模式', '目标用户洞察', '转化洞察']
const activeCategory = ref('有效选题模式')
const filteredMemories = computed(() => strategyMemories.filter((item) => item.category === activeCategory.value))
const enabledCount = computed(() => strategyMemories.filter((item) => item.enabled).length)
const averageWeight = computed(() => Math.round(strategyMemories.reduce((sum, item) => sum + item.weight, 0) / strategyMemories.length))
</script>
