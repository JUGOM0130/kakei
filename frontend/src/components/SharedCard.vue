<script setup>
import { computed, ref } from 'vue'
import { yen } from '../utils/format'

const props = defineProps({
  shared: { type: Object, required: true },
})
const emit = defineEmits(['settle', 'unsettle'])

// 'mine' | 'partner' | null — タップで立替明細を開閉
const expanded = ref(null)

function toggle(side) {
  expanded.value = expanded.value === side ? null : side
}

const expandedItems = computed(() =>
  expanded.value === 'mine' ? props.shared.my_items : props.shared.partner_items
)

const expandedTitle = computed(() =>
  expanded.value === 'mine'
    ? 'あなたの立替明細'
    : `${props.shared.partner?.username}さんの立替明細`
)

function dayLabel(dateStr) {
  return `${Number(dateStr.slice(5, 7))}/${Number(dateStr.slice(8, 10))}`
}
</script>

<template>
  <div class="card">
    <div class="heading">共有・精算 ({{ shared.group_name }})</div>

    <p v-if="!shared.partner" class="empty-message">
      相手がまだ参加していません。設定画面の招待コードを伝えてください。
    </p>

    <template v-else>
      <div class="grid">
        <button class="cell tappable" :class="{ open: expanded === 'mine' }" @click="toggle('mine')">
          <div class="label">あなたの立替 {{ expanded === 'mine' ? '▲' : '▼' }}</div>
          <div class="value">{{ yen(shared.my_paid) }}</div>
        </button>
        <button
          class="cell tappable"
          :class="{ open: expanded === 'partner' }"
          @click="toggle('partner')"
        >
          <div class="label">{{ shared.partner.username }}さんの立替 {{ expanded === 'partner' ? '▲' : '▼' }}</div>
          <div class="value">{{ yen(shared.partner_paid) }}</div>
        </button>
        <div class="cell">
          <div class="label">あなたの負担</div>
          <div class="value">{{ yen(shared.my_burden) }}</div>
        </div>
        <div class="cell">
          <div class="label">{{ shared.partner.username }}さんの負担</div>
          <div class="value">{{ yen(shared.partner_burden) }}</div>
        </div>
      </div>

      <!-- 立替明細 (元金・割合・実質支払い額) -->
      <div v-if="expanded" class="detail">
        <div class="detail-head">
          <span>{{ expandedTitle }}</span>
          <span class="detail-cols">元金 / 割合 / 実質</span>
        </div>
        <p v-if="!expandedItems.length" class="empty-message">この月の立替はありません。</p>
        <div v-for="item in expandedItems" :key="item.id" class="detail-row">
          <span class="dot" :style="{ background: item.color }"></span>
          <div class="detail-info">
            <div class="detail-name">{{ dayLabel(item.date) }} {{ item.category }}</div>
            <div v-if="item.memo" class="detail-memo">{{ item.memo }}</div>
          </div>
          <div class="detail-nums">
            {{ yen(item.amount) }}
            <span class="pct">× {{ item.percent }}%</span>
            <strong>= {{ yen(item.burden) }}</strong>
          </div>
        </div>
        <div v-if="expandedItems.length" class="detail-total">
          <span>合計</span>
          <div class="detail-nums">
            {{ yen(expandedItems.reduce((s, i) => s + i.amount, 0)) }}
            <strong>= {{ yen(expandedItems.reduce((s, i) => s + i.burden, 0)) }}</strong>
          </div>
        </div>
        <p class="detail-note">
          ※ 割合は支払った人の負担割合、実質はその人が最終的に負担する額です。差額 (元金 −
          実質) を相手が負担します。
        </p>
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

.cell {
  text-align: left;
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: inherit;
}

.cell.tappable {
  cursor: pointer;
  border-radius: 8px;
  padding: 4px 6px;
  margin: -4px -6px;
}

.cell.tappable.open {
  background: var(--color-bg);
}

.label {
  font-size: 0.72rem;
  color: var(--color-text-sub);
}

.tappable .label {
  color: var(--color-primary);
  font-weight: 600;
}

.value {
  font-weight: 700;
}

.detail {
  background: var(--color-bg);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-text-sub);
  margin-bottom: 6px;
}

.detail-cols {
  font-weight: 400;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
}

.detail-row:last-of-type {
  border-bottom: none;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.detail-info {
  flex: 1;
  min-width: 0;
}

.detail-name {
  font-size: 0.8rem;
  font-weight: 600;
}

.detail-memo {
  font-size: 0.7rem;
  color: var(--color-text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-nums {
  font-size: 0.78rem;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.detail-nums .pct {
  color: var(--color-text-sub);
}

.detail-nums strong {
  font-size: 0.85rem;
}

.detail-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  margin-top: 4px;
  border-top: 2px solid var(--color-border);
  font-size: 0.8rem;
  font-weight: 700;
}

.detail-note {
  font-size: 0.68rem;
  color: var(--color-text-sub);
  margin-top: 8px;
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
