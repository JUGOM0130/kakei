<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { yen } from '../utils/format'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const props = defineProps({
  // [{ month: 'YYYY-MM', realized: n, dividends: n }]
  monthly: { type: Array, required: true },
})

const chartData = computed(() => ({
  labels: props.monthly.map((m) => `${Number(m.month.split('-')[1])}月`),
  datasets: [
    {
      label: '実現損益',
      data: props.monthly.map((m) => m.realized),
      backgroundColor: props.monthly.map((m) => (m.realized < 0 ? '#c62828' : '#2e7d32')),
      stack: 'pnl',
    },
    {
      label: '配当',
      data: props.monthly.map((m) => m.dividends),
      backgroundColor: '#ffb300',
      stack: 'pnl',
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: { stacked: true, grid: { display: false } },
    y: { stacked: true, ticks: { callback: (v) => yen(v) } },
  },
  plugins: {
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${yen(ctx.raw)}`,
      },
    },
  },
}
</script>

<template>
  <div class="chart-box">
    <Bar :data="chartData" :options="options" />
  </div>
</template>
