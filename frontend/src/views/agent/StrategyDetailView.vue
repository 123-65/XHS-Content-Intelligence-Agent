<template><ArtifactDetailShell kind="内容策略" :title="data?.goal||'策略详情'" :artifact-ref="refId" :loading="loading" :error="error" :selection="{strategy_ref:refId}" selection-label="策略" :selection-title="data?.goal"><template v-if="data"><p class="intro">这份策略来自 Research {{data.research_ref}}，用于把研究结论转化为可创作的内容方向。</p><el-descriptions :column="1" border><el-descriptions-item label="策略目标">{{ data.goal }}</el-descriptions-item><el-descriptions-item label="目标受众">{{ data.audience }}</el-descriptions-item><el-descriptions-item label="为什么这样做">{{ data.rationale }}</el-descriptions-item></el-descriptions><h3>下一步：选择内容机会</h3><el-card v-for="item in data.opportunities" :key="item.ref" shadow="never"><div class="opportunity"><div><strong>{{ item.topic }}</strong><p>{{ item.angle }}</p><small>{{ item.why_now }}</small></div><el-button type="primary" plain @click="choose(item.ref,item.topic)">选择到对话</el-button></div></el-card></template></ArtifactDetailShell></template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getStrategyDetail } from '@/api/unifiedAgent'
import { useAgentChatStore } from '@/stores/agentChat'
import type { StrategyDetail } from '@/types/productRead'
import ArtifactDetailShell from '@/components/ArtifactDetailShell.vue'
const route=useRoute(), router=useRouter(), store=useAgentChatStore(), refId=computed(()=>Number(route.params.artifactRef)), loading=ref(true), error=ref(''), data=ref<StrategyDetail|null>(null), controller=new AbortController()
onMounted(async()=>{if(!store.account_ref){error.value='请先选择账号';loading.value=false;return}try{data.value=await getStrategyDetail(refId.value,store.account_ref,controller.signal)}catch(e){if(!controller.signal.aborted)error.value=store.clearRejectedAccount(e)?'账号不可用，请重新选择账号':e instanceof Error?e.message:'加载失败'}finally{loading.value=false}})
onBeforeUnmount(()=>controller.abort())
const choose=async(ref:number,title:string)=>{store.setWorkspaceSelection({opportunity_ref:ref},{type:'内容机会',title,detail_route:route.fullPath});await router.push(store.conversation_id?`/agent/chat/${store.conversation_id}`:'/agent/chat')}
</script>
<style scoped>.intro{color:#64748b;line-height:1.7}h3{margin-top:26px}.el-card{margin:10px 0}.opportunity{display:flex;justify-content:space-between;gap:20px}.opportunity p,.opportunity small{color:#657083}</style>
