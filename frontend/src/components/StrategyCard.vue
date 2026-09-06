<template>
  <div class="strategy-card">
    <div class="toolbar">
      <el-tag type="primary" effect="plain">{{ memory.category }}</el-tag>
      <el-switch v-model="localEnabled" inline-prompt active-text="启用" inactive-text="停用" />
    </div>
    <p>{{ memory.content }}</p>
    <div class="strategy-meta">
      <span>权重 {{ memory.weight }}</span>
      <span>{{ memory.relatedMetric }}</span>
      <span>来源：{{ memory.sourceExperiment }}</span>
    </div>
    <el-progress :percentage="memory.weight" :stroke-width="8" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { StrategyMemory } from '@/types/experiment'

const props = defineProps<{ memory: StrategyMemory }>()
const localEnabled = ref(props.memory.enabled)
</script>

<style scoped>
.strategy-card {
  display: flex;
  min-height: 190px;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

p {
  flex: 1;
  margin: 0;
  color: #374151;
  line-height: 1.7;
}

.strategy-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #6b7280;
  font-size: 12px;
}
</style>
