<script setup>
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { Chart, ArcElement, Tooltip, Legend } from 'chart.js'
import { yen } from '../utils/format'

Chart.register(ArcElement, Tooltip, Legend)

const props = defineProps({
  items: { type: Array, required: true }, // [{name, color, total}]
})

const chartData = computed(() => ({
  labels: props.items.map((i) => i.name),
  datasets: [
    {
      data: props.items.map((i) => i.total),
      backgroundColor: props.items.map((i) => i.color),
      borderWidth: 1,
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom', labels: { boxWidth: 12 } },
    tooltip: {
      callbacks: {
        label: (ctx) => ` ${ctx.label}: ${yen(ctx.parsed)}`,
      },
    },
  },
}
</script>

<template>
  <div class="chart-box">
    <Doughnut :data="chartData" :options="options" />
  </div>
</template>
