<script setup>
import { yen } from '../utils/format'

defineProps({
  items: { type: Array, required: true }, // [{id, name, total}]
})
</script>

<template>
  <div class="card">
    <div class="heading">支払方法別の支出</div>
    <p v-if="!items.length" class="empty-message">今月の支出はまだありません。</p>
    <ul v-else class="list">
      <li v-for="item in items" :key="item.id ?? 'none'" class="row">
        <span class="name">{{ item.name }}</span>
        <span class="total">{{ yen(item.total) }}</span>
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
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}

.row:last-child {
  border-bottom: none;
}

.name {
  font-weight: 600;
}

.total {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
