<script setup lang="ts">
import WorkspaceHybrid from '@/components/dashboard/WorkspaceHybrid.vue';
</script>

<template>
  <div class="dashboard-page">
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

.layout-viewport {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>

