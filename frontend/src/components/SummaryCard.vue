<script setup>
import { yen } from '../utils/format'

defineProps({
  income: { type: Number, default: 0 },
  expense: { type: Number, default: 0 },
  balance: { type: Number, default: 0 },
})
</script>

<template>
  <div class="card summary">
    <div class="col">
      <div class="label">収入</div>
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
