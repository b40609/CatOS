<script setup lang="ts">
import WorkspaceHybrid from '@/components/dashboard/WorkspaceHybrid.vue';
import WorkspaceRelaxed from '@/components/dashboard/WorkspaceRelaxed.vue';
import { usePreferences } from '@/state/usePreferences';
import { useWorkspace } from '@/state/useWorkspace';

const { preferences } = usePreferences();
const { modeNotice } = useWorkspace();
</script>

<template>
  <div class="dashboard-page">
    <!-- ✦ 鬆弛專業版 (Lovable Relaxed Pro) vs 原版平鋪高密版 (Tiling Bloomberg) -->
    <div class="layout-viewport" :class="{ 'is-relaxed': preferences.presentationStyle === 'relaxed_pro' }">
      <WorkspaceRelaxed v-if="preferences.presentationStyle === 'relaxed_pro'" />
      <WorkspaceHybrid v-else />
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

.layout-viewport.is-relaxed {
  overflow-y: auto;
}
</style>

