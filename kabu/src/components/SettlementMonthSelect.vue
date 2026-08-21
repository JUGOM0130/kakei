<script setup>
import { useStocksStore } from '../stores/stocks'

const props = defineProps({
  code: { type: String, required: true },
  month: { type: Number, default: null },
})

const stocks = useStocksStore()

async function onChange(e) {
  const v = e.target.value
  await stocks.setSettlementMonth(props.code, v ? Number(v) : null)
}
</script>

<template>
  <label class="sm-label">
    決算月
    <select class="sm-select" :value="month ?? ''" @change="onChange">
      <option value="">未設定</option>
      <option v-for="m in 12" :key="m" :value="m">{{ m }}月</option>
    </select>
  </label>
</template>

<style scoped>
.sm-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--color-text-sub);
  margin: 0;
}

.sm-select {
  width: auto;
  min-height: 32px;
  padding: 2px 8px;
  font-size: 0.8rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: #fff;
}
</style>
