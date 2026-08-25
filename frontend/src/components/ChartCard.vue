<template>
  <div class="bg-surface rounded-xl border border-border p-3 fade-in">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs text-gray-400 font-medium truncate">{{ chart.intent?.title || '图表' }}</span>
      <div class="flex items-center gap-1">
        <button
          @click="downloadChart"
          class="w-5 h-5 shrink-0 flex items-center justify-center rounded hover:bg-white/10 text-gray-600 hover:text-gray-400 transition-colors"
          title="下载图表"
        >
          <svg width="11" height="11" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <path d="M7 1v9"/><path d="M4 7l3 3 3-3"/><path d="M1 11v1a1 1 0 001 1h10a1 1 0 001-1v-1"/>
          </svg>
        </button>
        <button
          @click="$emit('remove')"
          class="w-5 h-5 shrink-0 flex items-center justify-center rounded hover:bg-white/10 text-gray-600 hover:text-gray-400 transition-colors"
          title="删除图表">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
    </div>
    <div ref="chartEl" class="w-full" style="height:260px"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ chart: Object })
const emit = defineEmits(['remove'])

const chartEl = ref(null)
let chartInstance = null
let resizeObserver = null

function initChart() {
  if (!chartEl.value || !props.chart?.echarts_option) return

  // 等元素有宽高再 init
  const waitForSize = () => {
    if (chartEl.value.clientWidth === 0 || chartEl.value.clientHeight === 0) {
      requestAnimationFrame(waitForSize)
      return
    }
    if (chartInstance) {
      chartInstance.dispose()
    }
    chartInstance = echarts.init(chartEl.value)
    chartInstance.setOption(props.chart.echarts_option)

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => chartInstance.resize())
      resizeObserver.observe(chartEl.value)
    }
  }
  waitForSize()
}

// 监听数据变化（比如 chart 被替换）
watch(() => props.chart?.echarts_option, () => {
  initChart()
})

function downloadChart() {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#1a1b23'
  })
  const a = document.createElement('a')
  a.href = url
  a.download = (props.chart.intent?.title || 'chart') + '.png'
  a.click()
}

onMounted(() => {
  nextTick(initChart)
})

onBeforeUnmount(() => {
  if (chartInstance) chartInstance.dispose()
  if (resizeObserver) resizeObserver.disconnect()
})
</script>
