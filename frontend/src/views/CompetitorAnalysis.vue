<template>
  <div class="page">
    <PageHeader title="竞品分析" description="基于采集笔记生成选题、标题、结构和 CTA 模式分析。">
      <el-button type="primary" :icon="FlaskConical" @click="createExperiment">基于该分析创建内容实验</el-button>
    </PageHeader>

    <el-card shadow="never">
      <template #header><strong>分析条件</strong></template>
      <el-form :inline="true" label-width="100px">
        <el-form-item label="关键词"><el-select v-model="keyword" style="width: 210px"><el-option label="AI Agent 学习路线" value="AI Agent 学习路线" /><el-option label="FastAPI + OpenAI SDK 项目" value="FastAPI + OpenAI SDK 项目" /></el-select></el-form-item>
        <el-form-item label="竞品笔记"><el-select v-model="noteCount" style="width: 160px"><el-option label="高表现 12 篇" value="12" /><el-option label="全部 36 篇" value="36" /></el-select></el-form-item>
        <el-form-item label="时间范围"><el-date-picker type="daterange" start-placeholder="开始" end-placeholder="结束" /></el-form-item>
        <el-form-item label="分析目标"><el-select v-model="objective" style="width: 180px"><el-option label="收藏" value="收藏" /><el-option label="评论" value="评论" /><el-option label="私信转化参考" value="私信转化参考" /></el-select></el-form-item>
      </el-form>
    </el-card>

    <div class="grid grid-3">
      <MetricCard title="分析笔记" value="12" :icon="Library" />
      <MetricCard title="高频选题" :value="report.topics.length" :icon="Layers" />
      <MetricCard title="可复用 CTA" :value="report.ctas.length" :icon="MousePointerClick" />
    </div>

    <div class="grid grid-2">
      <el-card v-for="block in reportBlocks" :key="block.title" shadow="never">
        <template #header><strong>{{ block.title }}</strong></template>
        <ul class="compact-list">
          <li class="list-item" v-for="item in block.items" :key="item">
            <span>{{ item }}</span>
            <el-tag :type="block.tagType" effect="plain">{{ block.tag }}</el-tag>
          </li>
        </ul>
      </el-card>
    </div>

    <el-card shadow="never">
      <template #header><strong>高表现样本</strong></template>
      <div class="grid grid-2">
        <NoteCard v-for="sample in sampleNotes" :key="sample.id" :note="sample" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { FlaskConical, Layers, Library, MousePointerClick } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import NoteCard from '@/components/NoteCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import { competitorAnalysisReport } from '@/mock/experiments'
import { noteSnapshots } from '@/mock/notes'
import { useExperimentStore } from '@/stores/experiment'

const router = useRouter()
const store = useExperimentStore()
const keyword = ref('AI Agent 学习路线')
const noteCount = ref('12')
const objective = ref('私信转化参考')
const report = competitorAnalysisReport
const sampleNotes = noteSnapshots.slice(0, 2)

const reportBlocks = computed(() => [
  { title: '高频选题方向', items: report.topics, tag: 'Topic', tagType: 'primary' },
  { title: '高互动标题结构', items: report.titleStructures, tag: 'Title', tagType: 'success' },
  { title: '常见标签', items: report.tags.map((tag) => `#${tag}`), tag: 'Tag', tagType: 'info' },
  { title: '常见内容结构', items: report.contentStructures, tag: 'Structure', tagType: 'warning' },
  { title: '常见 CTA', items: report.ctas, tag: 'CTA', tagType: 'success' },
  { title: '值得借鉴点', items: report.learnings, tag: 'Learn', tagType: 'primary' },
  { title: '不建议模仿点', items: report.avoidances, tag: 'Avoid', tagType: 'danger' }
])

const createExperiment = () => {
  store.createFromAnalysis()
  ElMessage.success('已基于竞品分析创建内容实验')
  router.push('/experiments/exp-001')
}
</script>
