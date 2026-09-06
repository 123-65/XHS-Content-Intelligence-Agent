<template>
  <div class="page">
    <PageHeader title="竞品采集" description="输入竞品笔记链接、主页或关键词，模拟采集公开笔记快照。">
      <el-button type="primary" :icon="Play" @click="startCollect">开始采集</el-button>
      <el-button :icon="Eraser" @click="clearForm">清空</el-button>
    </PageHeader>

    <div class="grid grid-3">
      <MetricCard title="本次成功" :value="collected ? 3 : 0" :icon="CheckCircle2" />
      <MetricCard title="本次失败" :value="collected ? failedCollectRecords.length : 0" :icon="AlertTriangle" />
      <MetricCard title="待入库笔记" :value="collected ? resultNotes.length : noteSnapshots.length" :icon="Database" />
    </div>

    <el-card shadow="never">
      <template #header><strong>采集任务输入</strong></template>
      <el-form label-width="100px">
        <el-form-item label="采集类型">
          <el-radio-group v-model="collectType">
            <el-radio-button label="单篇笔记链接" />
            <el-radio-button label="多篇笔记链接" />
            <el-radio-button label="竞品主页链接" />
            <el-radio-button label="关键词搜索" />
          </el-radio-group>
        </el-form-item>
        <el-form-item label="输入链接">
          <el-input v-model="urls" type="textarea" :rows="4" placeholder="支持粘贴多个 URL，每行一个。" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="keyword" placeholder="例如 AI Agent 学习路线、大学生求职、Python项目" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header><strong>采集结果预览</strong></template>
      <el-table :data="resultNotes" stripe>
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="author" label="作者" width="130" />
        <el-table-column prop="likes" label="点赞" width="90" />
        <el-table-column prop="collects" label="收藏" width="90" />
        <el-table-column prop="comments" label="评论" width="90" />
        <el-table-column prop="imageCount" label="图片数" width="90" />
        <el-table-column label="采集状态" width="120"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
        <el-table-column prop="collectedAt" label="采集时间" width="165" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header><strong>失败记录</strong></template>
      <el-table :data="collected ? failedCollectRecords : []">
        <el-table-column prop="url" label="URL" min-width="260" />
        <el-table-column prop="reason" label="失败原因" min-width="220" />
        <el-table-column label="是否重试" width="120">
          <template #default="{ row }"><el-tag :type="row.retryable ? 'warning' : 'info'">{{ row.retryable ? '可重试' : '不可重试' }}</el-tag></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { AlertTriangle, CheckCircle2, Database, Eraser, Play } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { failedCollectRecords, noteSnapshots } from '@/mock/notes'

const collectType = ref('关键词搜索')
const urls = ref('https://www.xiaohongshu.com/explore/mock-note-001\nhttps://www.xiaohongshu.com/explore/mock-note-002')
const keyword = ref('AI Agent 学习路线')
const collected = ref(false)

const resultNotes = computed(() => (collected.value ? noteSnapshots.slice(0, 3) : []))

const startCollect = () => {
  collected.value = true
  ElMessage.success('已模拟完成竞品公开笔记采集')
}

const clearForm = () => {
  urls.value = ''
  keyword.value = ''
  collected.value = false
}
</script>
