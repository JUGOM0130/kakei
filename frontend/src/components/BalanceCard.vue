<script setup>
import { computed } from 'vue'
import { yen } from '../utils/format'

const props = defineProps({
  forecast: { type: Object, required: true },
})

const enough = computed(() => props.forecast.after_required >= 0)
</script>

<template>
  <div class="card">
    <div class="heading">口座残高</div>

    <p v-if="!forecast.anchor" class="empty-message">
      残高は未登録です。
      <RouterLink to="/settings" class="link">設定から口座残高を登録</RouterLink>
      すると、今月足りるかがここに表示されます。
    </p>

    <template v-else>
      <div class="row">
        <span class="label">口座残高 (想定)</span>
        <span class="value">{{ yen(forecast.projected) }}</span>
      </div>
      <div class="row">
        <span class="label">今月の未払い固定費</span>
        <span class="value minus">-{{ yen(forecast.unpaid_recurring) }}</span>
      </div>
      <div class="row result" :class="enough ? 'ok' : 'ng'">
        <span class="label">差引後の残り</span>
        <span class="value">
          {{ enough ? '✓ ' : '⚠ ' }}{{ yen(forecast.after_required) }}
          {{ enough ? '' : ' 不足' }}
        </span>
      </div>
      <p class="note">
        {{ forecast.anchor.as_of_date }} 登録の残高 {{ yen(forecast.anchor.amount) }} +
        その後の収支から自動計算 (繰越)
      </p>
    </template>
  </div>
</template>

<style scoped>
.heading {
  font-weight: 700;
  margin-bottom: 8px;
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 5px 0;
}

.label {
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.value {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.minus {
  color: var(--color-expense);
}

.result {
  border-top: 1px solid var(--color-border);
  margin-top: 4px;
  padding-top: 9px;
}

.result.ok .value {
  color: var(--color-income);
}

.result.ng .value {
  color: var(--color-expense);
}

.note {
  font-size: 0.72rem;
  color: var(--color-text-sub);
  margin-top: 8px;
}

.link {
  color: var(--color-primary);
  font-weight: 600;
}
</style>
