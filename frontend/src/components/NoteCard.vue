<template>
  <div class="note-card">
    <div class="note-thumb">{{ note.imageCount }} 图</div>
    <div class="note-body">
      <div class="toolbar">
        <strong>{{ note.title }}</strong>
        <StatusTag :status="note.status" />
      </div>
      <p>{{ note.content }}</p>
      <div class="note-meta">
        <span>{{ note.author }}</span>
        <span>赞 {{ note.likes }}</span>
        <span>藏 {{ note.collects }}</span>
        <span>评 {{ note.comments }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import StatusTag from './StatusTag.vue'
import type { NoteSnapshot } from '@/types/note'

defineProps<{ note: NoteSnapshot }>()
</script>

<style scoped>
.note-card {
  display: flex;
  gap: 14px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.note-thumb {
  display: grid;
  flex: 0 0 76px;
  height: 76px;
  place-items: center;
  border-radius: 8px;
  background: #f0f7f4;
  color: #047857;
  font-weight: 700;
}

.note-body {
  min-width: 0;
}

.note-body p {
  margin: 8px 0;
  color: #4b5563;
  line-height: 1.6;
}

.note-meta {
  display: flex;
  gap: 14px;
  color: #6b7280;
  font-size: 12px;
}
</style>
