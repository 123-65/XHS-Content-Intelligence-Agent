<template>
  <ArtifactDetailShell kind="草稿" :title="selectedVersion?.content.title || data?.current_content.title || '草稿详情'" :artifact-ref="refId" :loading="loading" :error="error" :selection="{ draft_ref: refId }" selection-label="草稿" :selection-title="selectedVersion?.content.title" :selection-version="selectedVersion ? `V${selectedVersion.version}` : undefined">
    <template v-if="data && selectedVersion">
      <el-descriptions :column="2" border><el-descriptions-item label="草稿编号">{{data.ref}}</el-descriptions-item><el-descriptions-item label="状态">{{statusLabel(data.status)}}</el-descriptions-item><el-descriptions-item label="最新版本">V{{data.latest_version}}</el-descriptions-item><el-descriptions-item label="实际发布版本">{{publishedVersion?`V${publishedVersion}`:'尚未发布'}}</el-descriptions-item><el-descriptions-item label="更新时间" :span="2">{{formatTime(data.updated_at)}}</el-descriptions-item></el-descriptions>
      <div class="title-row"><el-tag>{{ statusLabel(data.status) }}</el-tag><strong>选择要查看或发布的版本</strong></div>
      <el-select v-model="selectedVersionId" class="version-select">
        <el-option v-for="version in data.versions" :key="version.ref" :value="version.ref" :label="`V${version.version} · ${sourceLabel(version.created_from)}${version.ref === data.latest_version_ref ? ' · 当前最新' : ''}`" />
      </el-select>
      <h2>{{ selectedVersion.content.title }}</h2>
      <article>{{ selectedVersion.content.body }}</article>
      <div class="tags"><el-tag v-for="tag in selectedVersion.content.tags" :key="tag" effect="plain">#{{ tag }}</el-tag></div>

      <section class="publish-box">
        <el-button type="primary" :loading="creating" @click="generatePackage">生成 V{{ selectedVersion.version }} 发布包</el-button>
        <template v-if="publishPackage">
          <el-alert title="请复制标题、正文和标签，前往小红书人工发布；系统不会自动发帖。" type="info" :closable="false" />
          <div class="copy-actions"><el-button @click="copyText(publishPackage.title)">复制标题</el-button><el-button @click="copyText(publishPackage.body)">复制正文</el-button><el-button @click="copyText(publishPackage.suggested_tags.join(' '))">复制标签</el-button></div>
          <el-input v-model="publishUrl" placeholder="人工发布完成后粘贴小红书笔记 URL" />
          <el-date-picker v-model="publishedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss.SSSZ" placeholder="发布时间" />
          <el-button :loading="registering" :disabled="!publishUrl || !publishedAt" @click="registerPublication">登记已发布</el-button>
          <el-alert v-if="registeredRef" :title="`已登记 PublishedNote #${registeredRef}，绑定 V${publishPackage.version_number}`" type="success" :closable="false" />
        </template>
      </section>

      <h3>版本记录</h3>
      <el-timeline><el-timeline-item v-for="version in data.versions" :key="version.ref" :timestamp="version.created_at">V{{ version.version }} · {{ version.created_from || '历史版本' }}</el-timeline-item></el-timeline>
      <h3>评审</h3><el-empty v-if="!data.reviews.length" description="暂无评审"/><el-card v-for="review in data.reviews" :key="review.ref" shadow="never">{{ review.summary || review.status }} · {{ review.score }}</el-card>
    </template>
  </ArtifactDetailShell>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { createPublishPackage, getDraftDetail, getPublicationList, registerPublishedNote } from '@/api/unifiedAgent'
import { useAgentChatStore } from '@/stores/agentChat'
import type { DraftDetail, PublishPackageResult } from '@/types/productRead'
import ArtifactDetailShell from '@/components/ArtifactDetailShell.vue'
import { formatTime, sourceLabel, statusLabel } from '@/utils/presentation'

const route=useRoute(),store=useAgentChatStore(),refId=computed(()=>Number(route.params.draftRef)),loading=ref(true),error=ref(''),data=ref<DraftDetail|null>(null),controller=new AbortController()
const selectedVersionId=ref<number|null>(null),publishedVersion=ref<number|null>(null),creating=ref(false),registering=ref(false),publishPackage=ref<PublishPackageResult|null>(null),publishUrl=ref(''),publishedAt=ref(''),registeredRef=ref<number|null>(null)
const selectedVersion=computed(()=>data.value?.versions.find(item=>item.ref===selectedVersionId.value) || null)
onMounted(async()=>{if(!store.account_ref){error.value='请先选择账号';loading.value=false;return}try{data.value=await getDraftDetail(refId.value,store.account_ref,controller.signal);selectedVersionId.value=data.value.latest_version_ref;const publications=await getPublicationList(store.account_ref,1,100,controller.signal);publishedVersion.value=publications.items.find(item=>item.draft_ref===refId.value)?.version_number||null}catch(e){if(!controller.signal.aborted)error.value=store.clearRejectedAccount(e)?'账号不可用，请重新选择账号':'草稿详情加载失败'}finally{loading.value=false}})
onBeforeUnmount(()=>controller.abort())
async function generatePackage(){if(!store.account_ref||!selectedVersionId.value)return;creating.value=true;registeredRef.value=null;try{publishPackage.value=await createPublishPackage({account_id:store.account_ref,draft_version_id:selectedVersionId.value})}finally{creating.value=false}}
async function registerPublication(){if(!store.account_ref||!publishPackage.value||!publishedAt.value)return;registering.value=true;try{const result=await registerPublishedNote({account_id:store.account_ref,publish_package_ref:publishPackage.value.package_ref,publish_url:publishUrl.value,published_at:publishedAt.value});registeredRef.value=result.published_note_ref}finally{registering.value=false}}
async function copyText(value:string){await navigator.clipboard.writeText(value)}
</script>
<style scoped>.title-row{display:flex;justify-content:space-between;align-items:center}.version-select{width:360px;margin:14px 0}article{padding:20px;margin:15px 0;background:#f8fafc;line-height:1.9;white-space:pre-wrap}.tags,.copy-actions{display:flex;gap:7px}.publish-box{display:grid;gap:12px;margin-top:24px;padding:18px;border:1px solid #e2e8f0;border-radius:8px}h3{margin-top:28px}.el-card{margin:8px 0}</style>
