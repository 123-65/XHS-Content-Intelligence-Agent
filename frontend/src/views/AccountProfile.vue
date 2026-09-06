<template>
  <div class="page">
    <PageHeader title="账号配置" description="配置单账号定位、目标用户和商业转化目标。">
      <el-button :icon="RotateCcw" @click="reset">重置</el-button>
      <el-button type="primary" :icon="Save" @click="save">保存配置</el-button>
    </PageHeader>

    <div class="grid grid-3">
      <MetricCard title="当前账号" :value="form.name" :icon="UserRound" />
      <MetricCard title="主要目标" :value="`${form.primaryGoal}线索`" :icon="Target" />
      <MetricCard title="线索价值" :value="`¥${form.leadValue}`" :icon="CircleDollarSign" />
    </div>

    <div class="grid account-grid">
      <el-card shadow="never">
        <template #header><strong>账号目标配置</strong></template>
        <el-form :model="form" label-width="126px">
          <el-form-item label="账号名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="小红书主页 URL"><el-input v-model="form.homepageUrl" /></el-form-item>
          <el-form-item label="账号定位"><el-input v-model="form.positioning" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="目标用户"><el-input v-model="form.targetUser" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="商业模式"><el-input v-model="form.businessModel" /></el-form-item>
          <el-form-item label="核心产品"><el-input v-model="form.coreProduct" /></el-form-item>
          <div class="grid grid-3">
            <el-form-item label="线索价值"><el-input-number v-model="form.leadValue" :min="0" /></el-form-item>
            <el-form-item label="平均客单价"><el-input-number v-model="form.averageOrderValue" :min="0" /></el-form-item>
            <el-form-item label="单笔毛利"><el-input-number v-model="form.grossProfit" :min="0" /></el-form-item>
          </div>
          <el-form-item label="主要目标">
            <el-radio-group v-model="form.primaryGoal">
              <el-radio-button label="曝光" />
              <el-radio-button label="收藏" />
              <el-radio-button label="私信" />
              <el-radio-button label="成交" />
            </el-radio-group>
          </el-form-item>
          <el-form-item label="内容风格偏好"><el-input v-model="form.stylePreference" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="禁用内容方向"><el-input v-model="form.forbiddenTopics" type="textarea" :rows="3" /></el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>当前账号策略摘要</strong></template>
        <ul class="compact-list">
          <li class="list-item" v-for="item in form.strategySummary" :key="item">
            <span>{{ item }}</span>
            <el-tag type="primary" effect="plain">策略</el-tag>
          </li>
        </ul>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleDollarSign, RotateCcw, Save, Target, UserRound } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useAccountStore } from '@/stores/account'

const account = useAccountStore()
const form = reactive({ ...account.profile })

const save = () => {
  account.saveProfile({ ...form })
  ElMessage.success('账号配置已保存到 Demo 状态')
}

const reset = () => {
  account.resetProfile()
  Object.assign(form, account.profile)
  ElMessage.info('已恢复默认 mock 配置')
}
</script>

<style scoped>
.account-grid {
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
}
</style>
