<template>
  <div class="page-header">
    <div>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </div>
    <div class="action-row">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

h1 {
  margin: 0;
  color: #111827;
  font-size: 24px;
  letter-spacing: 0;
}

p {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 14px;
}
</style>
