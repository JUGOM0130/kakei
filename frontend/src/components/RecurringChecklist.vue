<script setup>
import { computed } from 'vue'
import { yen } from '../utils/format'

const props = defineProps({
  items: { type: Array, required: true },
})
const emit = defineEmits(['pay'])

const sorted = computed(() =>
  [...props.items].sort((a, b) => a.paid - b.paid || a.day_of_month - b.day_of_month)
)
</script>

<template>
  <div class="card">
    <div class="heading">定期支払</div>
    <p v-if="!items.length" class="empty-message">
      固定費が未登録です。「固定費」タブから登録できます。
    </p>
    <ul v-else class="list">
      <li v-for="item in sorted" :key="item.id" class="row" :class="{ paid: item.paid }">
        <span class="dot" :style="{ background: item.category.color }"></span>
        <div class="info">
          <div class="name">{{ item.name }}</div>
          <div class="sub">{{ item.day_of_month }}日 ・ {{ item.category.name }}</div>
        </div>
        <div class="amount">{{ yen(item.amount) }}</div>
        <span v-if="item.paid" class="status">✓ 支払済</span>
        <button v-else class="btn btn-small" @click="emit('pay', item.id)">支払済にする</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.heading {
  font-weight: 700;
  margin-bottom: 8px;
}

.list {
  list-style: none;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.row:last-child {
  border-bottom: none;
}

.row.paid {
  opacity: 0.55;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0;
}

.name {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub {
  font-size: 0.75rem;
  color: var(--color-text-sub);
}

.amount {
  font-weight: 700;
  white-space: nowrap;
}

.status {
  color: var(--color-primary);
  font-size: 0.8rem;
  font-weight: 700;
  white-space: nowrap;
}
</style>
