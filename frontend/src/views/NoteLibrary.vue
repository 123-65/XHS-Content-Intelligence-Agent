<template>
  <div class="page">
    <PageHeader title="笔记库" description="管理自己账号与竞品账号采集到的公开笔记快照。">
      <el-button type="primary" :icon="RefreshCw">刷新快照</el-button>
    </PageHeader>

    <el-card shadow="never">
      <el-form :inline="true" label-width="86px">
        <el-form-item label="来源类型"><el-select v-model="sourceType" style="width: 150px"><el-option label="全部" value="" /><el-option label="自己账号" value="自己账号" /><el-option label="竞品" value="竞品" /><el-option label="关键词" value="关键词" /><el-option label="手动链接" value="手动链接" /></el-select></el-form-item>
        <el-form-item label="关键词"><el-input v-model="keyword" placeholder="AI Agent" /></el-form-item>
        <el-form-item label="作者"><el-input v-model="author" placeholder="作者名" /></el-form-item>
        <el-form-item label="采集状态"><el-select v-model="status" style="width: 140px"><el-option label="全部" value="" /><el-option label="成功" value="SUCCESS" /><el-option label="失败" value="FAILED" /></el-select></el-form-item>
        <el-form-item label="时间范围"><el-date-picker type="daterange" start-placeholder="开始" end-placeholder="结束" /></el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header><strong>公开笔记快照</strong></template>
      <el-table :data="filteredNotes" stripe @row-click="openDetail">
        <el-table-column prop="title" label="标题" min-width="240" />
        <el-table-column prop="author" label="作者" width="130" />
        <el-table-column prop="sourceType" label="来源类型" width="110" />
        <el-table-column prop="likes" label="点赞数" width="90" />
        <el-table-column prop="collects" label="收藏数" width="90" />
        <el-table-column prop="comments" label="评论数" width="90" />
        <el-table-column prop="imageCount" label="图片数量" width="95" />
        <el-table-column label="OCR" width="80"><template #default="{ row }"><el-tag :type="row.hasOcr ? 'success' : 'info'">{{ row.hasOcr ? '有' : '无' }}</el-tag></template></el-table-column>
        <el-table-column prop="collectedAt" label="采集时间" width="165" />
        <el-table-column label="状态" width="110"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="笔记详情" size="42%">
      <template v-if="selectedNote">
        <h3>{{ selectedNote.title }}</h3>
        <p class="muted">{{ selectedNote.author }} · {{ selectedNote.originalUrl }}</p>
        <el-divider />
        <p class="copy-box">{{ selectedNote.content }}</p>
        <div class="action-row"><el-tag v-for="tag in selectedNote.tags" :key="tag">#{{ tag }}</el-tag></div>
        <el-divider />
        <p><strong>图片 URL 列表</strong></p>
        <div class="code-box">{{ selectedNote.imageUrls.join('\n') }}</div>
        <p><strong>OCR 文本</strong></p>
        <div class="copy-box">{{ selectedNote.ocrText }}</div>
        <p><strong>merged_text</strong></p>
        <div class="copy-box">{{ selectedNote.mergedText }}</div>
        <p><strong>公开互动数</strong>：赞 {{ selectedNote.likes }} / 藏 {{ selectedNote.collects }} / 评 {{ selectedNote.comments }}</p>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { noteSnapshots } from '@/mock/notes'
import type { NoteSnapshot } from '@/types/note'

const sourceType = ref('')
const keyword = ref('')
const author = ref('')
const status = ref('')
const selectedNote = ref<NoteSnapshot>()
const drawerVisible = ref(false)

const filteredNotes = computed(() =>
  noteSnapshots.filter((note) => {
    const matchSource = !sourceType.value || note.sourceType === sourceType.value
    const matchKeyword = !keyword.value || note.keyword.includes(keyword.value) || note.title.includes(keyword.value)
    const matchAuthor = !author.value || note.author.includes(author.value)
    const matchStatus = !status.value || note.status === status.value
    return matchSource && matchKeyword && matchAuthor && matchStatus
  })
)

const openDetail = (note: NoteSnapshot) => {
  selectedNote.value = note
  drawerVisible.value = true
}
</script>
