<template>
  <el-container class="app-shell">
    <el-aside :width="app.sidebarCollapsed ? '72px' : '236px'" class="sidebar">
      <div class="brand">
        <div class="brand-mark">X</div>
        <div v-if="!app.sidebarCollapsed">
          <strong>XHS Growth</strong>
          <span>Intelligence Agent</span>
        </div>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="app.sidebarCollapsed"
        router
        class="side-menu"
        background-color="#101827"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard"><Monitor :size="18" /><span>仪表盘</span></el-menu-item>
        <el-menu-item index="/account"><Settings :size="18" /><span>账号配置</span></el-menu-item>
        <el-menu-item index="/competitor/collect"><Search :size="18" /><span>竞品采集</span></el-menu-item>
        <el-menu-item index="/notes"><Library :size="18" /><span>笔记库</span></el-menu-item>
        <el-menu-item index="/competitor/analysis"><ChartColumn :size="18" /><span>竞品分析</span></el-menu-item>
        <el-menu-item index="/experiments"><FlaskConical :size="18" /><span>内容实验</span></el-menu-item>
        <el-menu-item index="/drafts"><PenLine :size="18" /><span>内容生成</span></el-menu-item>
        <el-menu-item index="/publish"><UploadCloud :size="18" /><span>发布辅助</span></el-menu-item>
        <el-menu-item index="/metrics"><LineChart :size="18" /><span>效果复盘</span></el-menu-item>
        <el-menu-item index="/strategy"><BrainCircuit :size="18" /><span>策略记忆</span></el-menu-item>
        <el-menu-item index="/workflow-logs"><TerminalSquare :size="18" /><span>运行日志</span></el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div class="topbar-left">
          <el-button :icon="PanelLeft" circle @click="app.toggleSidebar()" />
          <div>
            <strong>XHS Growth Intelligence Agent</strong>
            <span>当前账号：{{ account.profile.name }} · 当前目标：{{ account.profile.primaryGoal }}线索</span>
          </div>
        </div>
        <el-tag type="success" effect="light">Demo Mock Mode</el-tag>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import {
  BrainCircuit,
  ChartColumn,
  FlaskConical,
  Library,
  LineChart,
  Monitor,
  PanelLeft,
  PenLine,
  Search,
  Settings,
  TerminalSquare,
  UploadCloud
} from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const account = useAccountStore()
const app = useAppStore()
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #f5f7fb;
}

.sidebar {
  overflow: hidden;
  background: #101827;
  transition: width 0.2s ease;
}

.brand {
  display: flex;
  height: 72px;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  color: #fff;
}

.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border-radius: 8px;
  background: #2563eb;
  font-weight: 800;
}

.brand strong,
.brand span {
  display: block;
  letter-spacing: 0;
}

.brand span {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 12px;
}

.side-menu {
  border-right: 0;
}

.side-menu :deep(.el-menu-item) {
  gap: 10px;
  height: 46px;
}

.side-menu :deep(.is-active) {
  background: #2563eb;
}

.topbar {
  display: flex;
  height: 72px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.topbar-left strong {
  display: block;
  color: #111827;
  font-size: 16px;
}

.topbar-left span {
  display: block;
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.main {
  padding: 22px;
}
</style>
