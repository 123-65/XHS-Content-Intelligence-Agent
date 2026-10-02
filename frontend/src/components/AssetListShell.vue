<template>
  <section class="asset-list">
    <header><div><h1>{{ title }}</h1><p>{{ description }}</p></div><el-tag>Account {{ accountRef }}</el-tag></header>
    <el-alert v-if="!accountRef" title="请先选择账号" type="warning" :closable="false" show-icon />
    <el-alert v-else-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-card v-else v-loading="loading" shadow="never">
      <el-empty v-if="!loading && !items.length" description="当前账号暂无数据" />
      <div v-else class="items"><slot v-for="item in items" :item="item" /></div>
      <el-pagination
        v-if="total > pageSize"
        background layout="prev, pager, next, total"
        :current-page="pageNo" :page-size="pageSize" :total="total"
        @current-change="$emit('page-change', $event)"
      />
    </el-card>
  </section>
</template>

<script setup lang="ts" generic="T">
defineProps<{ title: string; description: string; accountRef: number | null; items: T[]; loading: boolean; error: string; pageNo: number; pageSize: number; total: number }>()
defineEmits<{ 'page-change': [page: number] }>()
</script>

<style scoped>
.asset-list { max-width: 1080px; margin: 0 auto; }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
h1 { margin: 0; color: #111827; font-size: 24px; }
p { margin: 6px 0 0; color: #6b7280; }
.items { display: grid; gap: 10px; }
:deep(.asset-row) { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; color: inherit; cursor: pointer; text-align: left; }
:deep(.asset-row:hover) { border-color: #2563eb; background: #f8fbff; }
:deep(.asset-row strong), :deep(.asset-row span) { display: block; }
:deep(.asset-row small) { color: #6b7280; }
.el-pagination { justify-content: flex-end; margin-top: 18px; }
</style>
