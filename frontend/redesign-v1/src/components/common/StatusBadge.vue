<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  status: string;
}>();

const badgeClass = computed(() => {
  const s = props.status.toUpperCase();
  if (['RUNNING', 'COMPLETED', 'NORMAL', 'SUCCESS'].includes(s)) {
    return 'badge-success';
  }
  if (['WARNING', 'STARTING', 'SOFT_LATCH', 'PENDING', 'WARN'].includes(s)) {
    return 'badge-warning';
  }
  if (['FAILED', 'STOPPED_409', 'HARD_LATCH', 'DANGER', 'ERROR', 'RECOVERY_REQUIRED'].includes(s)) {
    return 'badge-danger';
  }
  if (['INFO', 'RESEARCH'].includes(s)) {
    return 'badge-info';
  }
  return 'badge-neutral';
});

const labelText = computed(() => {
  const s = props.status.toUpperCase();
  switch (s) {
    case 'RUNNING': return '運行中';
    case 'STARTING': return '啟動中';
    case 'STOPPED': return '已停止';
    case 'COMPLETED': return '已完成';
    case 'NORMAL': return '正常';
    case 'SOFT_LATCH': return '軟限鎖存';
    case 'HARD_LATCH': return '硬限鎖存';
    case 'MISSING': return '資料缺失';
    case 'RECOVERY_REQUIRED': return '需手動恢復';
    default: return props.status;
  }
});
</script>

<template>
  <span :class="['badge', badgeClass]">
    <span class="badge-dot">●</span>
    <span>{{ labelText }}</span>
  </span>
</template>

<style scoped>
.badge-dot {
  font-size: 8px;
  line-height: 1;
}
</style>
