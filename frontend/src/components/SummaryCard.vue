<script setup>
import { computed } from 'vue'
import { yen } from '../utils/format'

const props = defineProps({
  income: { type: Number, default: 0 },
  expense: { type: Number, default: 0 },
  balance: { type: Number, default: 0 },
  month: { type: String, default: '' },
  incomeMonth: { type: String, default: '' },
})

// 「前月収入でやりくり」設定時は収入の対象月を明示する
const incomeLabel = computed(() => {
  if (!props.incomeMonth || props.incomeMonth === props.month) return '収入'
  return `収入 (${Number(props.incomeMonth.slice(5))}月分)`
})
</script>

<template>
  <div class="card summary">
    <div class="col">
      <div class="label">{{ incomeLabel }}</div>
      <div class="value amount-income">{{ yen(income) }}</div>
    </div>
    <div class="col">
      <div class="label">支出</div>
      <div class="value amount-expense">{{ yen(expense) }}</div>
    </div>
    <div class="col">
      <div class="label">収支</div>
      <div class="value" :class="balance >= 0 ? 'amount-income' : 'amount-expense'">
        {{ yen(balance) }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.summary {
  display: flex;
  text-align: center;
}

.col {
  flex: 1;
}

.col + .col {
  border-left: 1px solid var(--color-border);
}

.label {
  font-size: 0.75rem;
  color: var(--color-text-sub);
  margin-bottom: 4px;
}

.value {
  font-size: 0.95rem;
}
</style>
