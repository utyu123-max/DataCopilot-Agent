<template>
  <div v-if="hasContent || streamingText" class="mt-2">
    <button
      @click="open = !open"
      class="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
    >
      <svg :class="['w-3 h-3 transition-transform', open && 'rotate-90']" viewBox="0 0 12 12" fill="currentColor">
        <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <span v-if="streamingText">💭 深度思考中…</span>
      <span v-else-if="isThinking">💭 思考中…</span>
      <span v-else>思考过程</span>
      <span v-if="stepCount > 0" class="text-gray-600">({{ stepCount }} 步)</span>
    </button>

    <div v-if="open" class="mt-2 bg-surface-lighter border border-border rounded-lg p-3 space-y-3 text-xs max-h-96 overflow-y-auto">
      <!-- 流式思考文字 -->
      <div v-if="streamingText" class="text-gray-300 whitespace-pre-wrap leading-relaxed">
        {{ streamingText }}<span class="typing-cursor"></span>
      </div>

      <!-- 工具调用日志 -->
      <template v-for="(log, i) in toolLogs" :key="i">
        <div v-if="log.type === 'call' || log.type === 'start'" class="flex items-start gap-2 text-yellow-400/80">
          <span class="shrink-0 mt-0.5">🔧</span>
          <div>
            <span class="font-medium">{{ log.tool }}</span>
            <span v-if="log.args" class="text-gray-500 ml-1">{{ formatArgs(log.args) }}</span>
          </div>
        </div>
        <div v-else-if="log.type === 'result'" class="flex items-start gap-2 text-blue-400/80">
          <span class="shrink-0 mt-0.5">📋</span>
          <div class="text-gray-400 whitespace-pre-wrap">{{ truncate(log.output) }}</div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  thoughts: Array,
  toolLogs: Array,
  collapsed: Boolean,
  streamingText: { type: String, default: '' },
  isThinking: { type: Boolean, default: false }
})

const open = ref(!props.collapsed)
const hasContent = computed(() => (props.toolLogs?.length || 0) > 0)
const stepCount = computed(() => props.toolLogs?.filter(l => l.type !== 'result').length || 0)

function formatArgs(args) {
  if (!args || typeof args !== 'object') return ''
  const str = JSON.stringify(args)
  return str.length > 80 ? str.slice(0, 80) + '...' : str
}
function truncate(s) {
  if (!s) return ''
  const t = typeof s === 'string' ? s : JSON.stringify(s)
  return t.length > 300 ? t.slice(0, 300) + '...' : t
}
</script>