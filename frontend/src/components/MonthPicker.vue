<script setup>
import { useLedgerStore } from '../stores/ledger'
import { monthLabel } from '../utils/format'

const ledger = useLedgerStore()
const emit = defineEmits(['change'])

function prev() {
  ledger.prevMonth()
  emit('change')
}
function next() {
  ledger.nextMonth()
  emit('change')
}
</script>

<template>
  <div class="month-picker">
    <button class="arrow" aria-label="前の月" @click="prev">‹</button>
    <span class="label">{{ monthLabel(ledger.month) }}</span>
    <button class="arrow" aria-label="次の月" @click="next">›</button>
  </div>
</template>

<style scoped>
.month-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.arrow {
  width: 44px;
  height: 44px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: #fff;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--color-text);
}

.label {
  font-size: 1.15rem;
  font-weight: 700;
}
</style>
