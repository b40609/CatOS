<script setup lang="ts">
import ScenarioBar from '@/components/common/ScenarioBar.vue';
import WorkspaceTiling from '@/components/dashboard/WorkspaceTiling.vue';
import WorkspaceFreeform from '@/components/dashboard/WorkspaceFreeform.vue';
import WorkspaceHybrid from '@/components/dashboard/WorkspaceHybrid.vue';
import { usePreferences } from '@/state/usePreferences';
import { useWorkspace } from '@/state/useWorkspace';

const { preferences } = usePreferences();
const { modeNotice } = useWorkspace();
</script>

<template>
  <div class="dashboard-page">
    <ScenarioBar />

    <div v-if="modeNotice" class="mode-notice-banner banner banner-warning">
      <span>{{ modeNotice }}</span>
    </div>

    <!-- Active Candidate Interactive Workspace (A: Tiling | B: Freeform | C: Hybrid) -->
    <div class="layout-viewport">
      <WorkspaceTiling v-if="preferences.workspaceMode === 'tiling'" />
      <WorkspaceFreeform v-else-if="preferences.workspaceMode === 'freeform'" />
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
</style>
