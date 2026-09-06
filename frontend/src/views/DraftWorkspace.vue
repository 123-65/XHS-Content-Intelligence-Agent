<template>
  <div class="page">
    <PageHeader title="内容生成" description="基于账号定位、竞品洞察和策略记忆生成小红书图文草稿并审核。">
      <el-button :icon="Sparkles" @click="generate">生成草稿</el-button>
      <el-button :icon="RefreshCw" @click="generate">重新生成</el-button>
      <el-button type="primary" :icon="ShieldCheck" @click="review">审核内容</el-button>
      <el-button :icon="Save" @click="saveDraft">保存草稿</el-button>
      <el-button type="success" :icon="ArrowRight" @click="$router.push('/publish')">进入发布辅助</el-button>
    </PageHeader>

    <div class="workspace-grid">
      <el-card shadow="never">
        <template #header><strong>上下文</strong></template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="账号定位">{{ account.profile.positioning }}</el-descriptions-item>
          <el-descriptions-item label="目标用户">{{ account.profile.targetUser }}</el-descriptions-item>
          <el-descriptions-item label="商业目标">{{ account.profile.primaryGoal }}线索 · {{ account.profile.coreProduct }}</el-descriptions-item>
          <el-descriptions-item label="竞品洞察">{{ store.analysisReport.learnings[0] }}</el-descriptions-item>
          <el-descriptions-item label="历史策略">{{ strategyMemories[0].content }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>草稿编辑区</strong></template>
        <el-form label-position="top">
          <el-form-item label="标题候选">
            <el-select v-model="selectedTitle" style="width: 100%"><el-option v-for="title in draft.titleCandidates" :key="title" :label="title" :value="title" /></el-select>
          </el-form-item>
          <el-form-item label="正文"><el-input v-model="draft.body" type="textarea" :rows="11" /></el-form-item>
          <el-form-item label="标签">
            <div class="action-row"><el-tag v-for="tag in draft.tags" :key="tag">#{{ tag }}</el-tag></div>
          </el-form-item>
          <el-form-item label="封面文案"><el-input v-model="draft.coverCopy" /></el-form-item>
          <el-form-item label="图片脚本">
            <el-timeline>
              <el-timeline-item v-for="item in draft.imageScript" :key="item">{{ item }}</el-timeline-item>
            </el-timeline>
          </el-form-item>
          <el-form-item label="CTA"><el-input v-model="draft.cta" type="textarea" :rows="2" /></el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>审核报告</strong></template>
        <div class="audit-score">
          <el-result :icon="store.reviewReport.passed ? 'success' : 'warning'" :title="store.reviewReport.passed ? '审核通过' : '需要修改'" />
          <StatusTag :status="store.reviewReport.riskLevel" />
        </div>
        <el-progress :percentage="store.reviewReport.qualityScore" :stroke-width="10" />
        <p class="muted">质量评分</p>
        <el-progress :percentage="store.reviewReport.conversionScore" :stroke-width="10" color="#16a34a" />
        <p class="muted">转化评分</p>
        <h4>问题列表</h4>
        <ul class="compact-list"><li class="list-item" v-for="item in store.reviewReport.issues" :key="item">{{ item }}</li></ul>
        <h4>修改建议</h4>
        <ul class="compact-list"><li class="list-item" v-for="item in store.reviewReport.suggestions" :key="item">{{ item }}</li></ul>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, RefreshCw, Save, ShieldCheck, Sparkles } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { strategyMemories } from '@/mock/strategy'
import { useAccountStore } from '@/stores/account'
import { useExperimentStore } from '@/stores/experiment'

const account = useAccountStore()
const store = useExperimentStore()
const draft = reactive({ ...store.draft, titleCandidates: [...store.draft.titleCandidates], tags: [...store.draft.tags], imageScript: [...store.draft.imageScript] })
const selectedTitle = ref(draft.titleCandidates[0])

const generate = () => {
  store.markDraftGenerated()
  ElMessage.success('已生成小红书图文草稿')
}

const review = () => {
  store.markReviewed()
  ElMessage.success('内容审核通过，低风险')
}

const saveDraft = () => ElMessage.success('草稿已保存到 Demo 状态')
</script>

<style scoped>
.workspace-grid {
  display: grid;
  grid-template-columns: 310px minmax(0, 1fr) 330px;
  gap: 16px;
}

.audit-score {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.audit-score :deep(.el-result) {
  padding: 0;
}
</style>
