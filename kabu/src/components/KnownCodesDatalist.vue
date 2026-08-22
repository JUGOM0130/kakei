<script setup>
// 銘柄コード入力欄の候補 (過去に取引・配当のある銘柄)。
// 使う側は <input list="known-codes"> を付けてこのコンポーネントを1つ置く。
import { onMounted } from 'vue'
import { useStocksStore } from '../stores/stocks'

const stocks = useStocksStore()

onMounted(() => {
  stocks.fetchKnownStocks().catch(() => {})
})
</script>

<template>
  <datalist id="known-codes">
    <option v-for="s in stocks.knownStocks" :key="s.code" :value="s.code">{{ s.name }}</option>
  </datalist>
</template>
