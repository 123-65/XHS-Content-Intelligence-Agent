<template>
  <div class="metric-card">
    <div class="metric-icon">
      <component :is="icon" :size="18" />
    </div>
    <div>
      <p>{{ title }}</p>
      <strong>{{ value }}</strong>
      <span v-if="delta">{{ delta }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  delta?: string
  icon: object
}>()
</script>

<style scoped>
.metric-card {
  display: flex;
  min-height: 92px;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.metric-icon {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 8px;
  background: #eef6ff;
  color: #2563eb;
}

p {
  margin: 0 0 5px;
  color: #6b7280;
  font-size: 13px;
}

strong {
  display: block;
  color: #111827;
  font-size: 22px;
}

span {
  color: #16a34a;
  font-size: 12px;
}
</style>
