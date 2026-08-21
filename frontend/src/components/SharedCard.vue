<script setup>
import { yen } from '../utils/format'

const props = defineProps({
  shared: { type: Object, required: true },
})
const emit = defineEmits(['settle', 'unsettle'])
</script>

<template>
  <div class="card">
    <div class="heading">共有・精算 ({{ shared.group_name }})</div>

    <p v-if="!shared.partner" class="empty-message">
      相手がまだ参加していません。設定画面の招待コードを伝えてください。
    </p>

    <template v-else>
      <div class="grid">
        <div class="cell">
          <div class="label">あなたの立替</div>
          <div class="value">{{ yen(shared.my_paid) }}</div>
        </div>
        <div class="cell">
          <div class="label">{{ shared.partner.username }}さんの立替</div>
          <div class="value">{{ yen(shared.partner_paid) }}</div>
        </div>
        <div class="cell">
          <div class="label">あなたの負担</div>
          <div class="value">{{ yen(shared.my_burden) }}</div>
        </div>
        <div class="cell">
          <div class="label">{{ shared.partner.username }}さんの負担</div>
          <div class="value">{{ yen(shared.partner_burden) }}</div>
        </div>
      </div>

      <div v-if="shared.settlement" class="transfer settled">
        ✓ 精算済み: {{ shared.settlement.from }} → {{ shared.settlement.to }}
        {{ yen(shared.settlement.amount) }}
        <button class="btn btn-secondary btn-small" @click="emit('unsettle', shared.settlement.id)">
          取消
        </button>
      </div>
      <div v-else-if="shared.transfer" class="transfer">
        <span>
          精算: <strong>{{ shared.transfer.from }} → {{ shared.transfer.to }}
          {{ yen(shared.transfer.amount) }}</strong>
        </span>
        <button class="btn btn-small" @click="emit('settle')">精算済みにする</button>
      </div>
      <div v-else class="transfer even">今月の精算は不要です (負担どおり)</div>
    </template>
  </div>
</template>

<style scoped>
.heading {
  font-weight: 700;
  margin-bottom: 8px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin-bottom: 12px;
}

.label {
  font-size: 0.72rem;
  color: var(--color-text-sub);
}

.value {
  font-weight: 700;
}

.transfer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  background: var(--color-bg);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 0.9rem;
  flex-wrap: wrap;
}

.transfer.settled {
  color: var(--color-primary);
  font-weight: 600;
}

.transfer.even {
  color: var(--color-text-sub);
  justify-content: center;
}
</style>
