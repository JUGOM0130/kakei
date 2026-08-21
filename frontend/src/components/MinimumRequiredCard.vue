<script setup>
import { computed } from 'vue'
import { yen } from '../utils/format'

const props = defineProps({
  recurring: { type: Object, required: true },
})

const progress = computed(() => {
  if (!props.recurring.required_total) return 0
  const paidRequired = props.recurring.required_total - props.recurring.remaining_total
  return Math.min(100, Math.round((paidRequired / props.recurring.required_total) * 100))
})
</script>

<template>
  <div class="card required-card">
    <div class="title">今月の最低必要額</div>
    <div class="total">{{ yen(recurring.required_total) }}</div>
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: progress + '%' }"></div>
    </div>
    <div class="detail">
      <span>支払済 {{ yen(recurring.paid_total) }}</span>
      <span class="remaining">残り {{ yen(recurring.remaining_total) }}</span>
    </div>
  </div>
</template>

<style scoped>
.required-card {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: #fff;
}

.title {
  font-size: 0.85rem;
  opacity: 0.9;
}

.total {
  font-size: 2rem;
  font-weight: 800;
  margin: 4px 0 10px;
}

.progress-track {
  height: 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.3);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #fff;
  border-radius: 4px;
  transition: width 0.3s;
}

.detail {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  margin-top: 8px;
}

.remaining {
  font-weight: 700;
}
</style>
