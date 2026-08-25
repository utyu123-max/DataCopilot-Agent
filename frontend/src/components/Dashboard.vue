<template>
  <div class="w-[420px] h-full flex flex-col bg-surface-light border-l border-border shrink-0">
    <div class="p-3 border-b border-border">
      <h2 class="text-sm font-medium text-gray-300 flex items-center gap-2">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
          <rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/>
          <rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/>
        </svg>
        图表看板
        <span v-if="charts.length" class="text-xs text-gray-600 ml-auto">{{ charts.length }} 张</span>
      </h2>
    </div>

    <div class="flex-1 overflow-y-auto p-3 space-y-3">
      <div v-if="!charts.length" class="h-full flex items-center justify-center text-center">
        <div>
          <div class="text-3xl mb-2">📈</div>
          <p class="text-sm text-gray-500">生成的图表会出现在这里</p>
          <p class="text-xs text-gray-600 mt-1">试试让我画张图</p>
        </div>
      </div>

      <ChartCard
        v-for="(chart, i) in charts"
        :key="i"
        :chart="chart"
        @remove="removeChart(i)"
      />
    </div>
  </div>
</template>

<script setup>
import ChartCard from './ChartCard.vue'

defineProps({ charts: Array })
const emit = defineEmits(['remove'])

function removeChart(i) {
  emit('remove', i)
}
</script>
