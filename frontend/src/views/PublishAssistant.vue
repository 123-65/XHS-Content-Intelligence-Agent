<template>
  <div class="page">
    <PageHeader title="发布辅助" description="辅助把已审核草稿复制到小红书网页端，由用户手动发布。">
      <el-button type="primary" :icon="ExternalLink" @click="openCreator">打开创作服务平台</el-button>
      <el-button type="success" :icon="ArrowRight" @click="$router.push('/metrics')">进入效果复盘</el-button>
    </PageHeader>

    <div class="grid publish-grid">
      <el-card shadow="never">
        <template #header><strong>发布内容预览</strong></template>
        <h3>{{ draft.titleCandidates[0] }}</h3>
        <p class="copy-box">{{ draft.body }}</p>
        <div class="action-row"><el-tag v-for="tag in draft.tags" :key="tag">#{{ tag }}</el-tag></div>
        <el-divider />
        <p><strong>封面文案</strong>：{{ draft.coverCopy }}</p>
        <el-timeline>
          <el-timeline-item v-for="item in draft.imageScript" :key="item">{{ item }}</el-timeline-item>
        </el-timeline>
      </el-card>

      <div class="grid">
        <el-card shadow="never">
          <template #header><strong>一键复制</strong></template>
          <div class="copy-actions">
            <el-button :icon="Copy" @click="copyText(draft.titleCandidates[0])">复制标题</el-button>
            <el-button :icon="Copy" @click="copyText(draft.body)">复制正文</el-button>
            <el-button :icon="Copy" @click="copyText(draft.tags.map((tag) => `#${tag}`).join(' '))">复制标签</el-button>
            <el-button type="primary" :icon="Copy" @click="copyText(fullNote)">复制完整笔记</el-button>
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header><strong>发布检查清单</strong></template>
          <el-checkbox-group v-model="checklistDone">
            <el-checkbox v-for="item in checklist" :key="item" :label="item" />
          </el-checkbox-group>
        </el-card>

        <el-card shadow="never">
          <template #header><strong>发布后填写</strong></template>
          <el-form label-width="88px">
            <el-form-item label="发布 URL"><el-input v-model="publishUrl" placeholder="粘贴发布后的笔记链接" /></el-form-item>
            <el-form-item label="发布时间"><el-date-picker v-model="publishedAt" type="datetime" style="width: 100%" /></el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Save" @click="savePublishRecord">保存发布记录</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Copy, ExternalLink, Save } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { useExperimentStore } from '@/stores/experiment'

const store = useExperimentStore()
const draft = store.draft
const checklist = ['标题是否明确', '正文是否有价值', '是否有 CTA', '是否符合账号定位', '是否没有夸大承诺', '是否已准备图片']
const checklistDone = ref([...checklist])
const publishUrl = ref(store.demoPublishUrl || 'https://www.xiaohongshu.com/explore/demo-ai-agent-roadmap')
const publishedAt = ref(new Date())

const fullNote = computed(() => `${draft.titleCandidates[0]}\n\n${draft.body}\n\n${draft.tags.map((tag) => `#${tag}`).join(' ')}\n\n${draft.cta}`)

const copyText = async (text: string) => {
  await navigator.clipboard?.writeText(text)
  ElMessage.success('已复制到剪贴板')
}

const openCreator = () => {
  window.open('https://creator.xiaohongshu.com/', '_blank')
}

const savePublishRecord = () => {
  store.savePublishUrl(publishUrl.value)
  ElMessage.success('发布 URL 已写入实验记录')
}
</script>

<style scoped>
.publish-grid {
  grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.8fr);
}

.copy-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.copy-actions .el-button {
  margin-left: 0;
}

.el-checkbox {
  display: flex;
  height: 32px;
  align-items: center;
}
</style>
