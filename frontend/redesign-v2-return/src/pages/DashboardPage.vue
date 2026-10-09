<script setup lang="ts">
import WorkspaceHybrid from '@/components/dashboard/WorkspaceHybrid.vue';
import { useWorkspace } from '@/state/useWorkspace';

const { modeNotice } = useWorkspace();
</script>

<template>
  <div class="dashboard-page">


    <!-- 定案架構：方案 1 · Bloomberg 平鋪工作台 -->
    <div class="layout-viewport">
      <WorkspaceHybrid />
    </div>
  </div>
</template>

<style scoped>
.dashboard-page {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.mode-notice-banner {
  margin: var(--space-2) var(--space-4) 0 var(--space-4);
}

.layout-viewport {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
