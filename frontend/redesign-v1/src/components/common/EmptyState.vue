<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
  icon?: string;
}>();
</script>

<template>
  <div class="empty-state-box">
    <div class="empty-icon">{{ icon || '∅' }}</div>
    <div class="empty-title">{{ title }}</div>
    <div class="empty-desc">{{ description }}</div>
  </div>
</template>

<style scoped>
.empty-state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  text-align: center;
  color: var(--text-muted);
  background: var(--bg-surface-elevated);
  border: 1px dashed var(--border-secondary);
  border-radius: var(--radius-sm);
  min-height: 140px;
}

.empty-icon {
  font-size: 24px;
  color: var(--text-disabled);
  margin-bottom: var(--space-2);
}

.empty-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  max-width: 320px;
  margin-top: 4px;
}
</style>
