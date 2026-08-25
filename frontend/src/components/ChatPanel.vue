<template>
  <div class="flex-1 flex flex-col h-full min-h-0">
    <div ref="scrollContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
      <div v-if="!messages.length && !loading" class="h-full flex items-center justify-center">
        <div class="text-center">
          <div class="text-4xl mb-4">📊</div>
          <h2 class="text-lg font-medium text-gray-300 mb-2">DataCopilot</h2>
          <p class="text-sm text-gray-500 max-w-md">
            试着问我：<br/>
            "抖音和小红书这个月的销售额对比"<br/>
            "各渠道ROI排名，画个柱状图"<br/>
            "双十一期间哪个品类卖得最好"
          </p>
        </div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="fade-in">
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <div class="max-w-[70%] px-4 py-2.5 rounded-2xl bg-accent/30 text-gray-100 text-sm leading-relaxed">
            {{ msg.content }}
          </div>
        </div>
        <div v-else class="flex gap-3">
          <div class="w-7 h-7 rounded-full bg-accent/30 flex items-center justify-center shrink-0 mt-0.5">
            <span class="text-xs">AI</span>
          </div>
          <div class="max-w-[80%] text-sm leading-relaxed text-gray-300">
            <div v-if="msg.content" v-html="cleanContent(msg.content)"></div>
            <ThoughtPanel
              v-if="i === messages.length - 1"
              :thoughts="thoughts"
              :tool-logs="toolLogs"
              :collapsed="!isThinking"
            />
          </div>
        </div>
      </div>

      <!-- loading 时：AI 气泡只显示思考面板（流式思考 + 工具日志），回答区空着 -->
      <div v-if="loading && (!messages.length || messages[messages.length-1]?.role === 'user')" class="flex gap-3">
        <div class="w-7 h-7 rounded-full bg-accent/30 flex items-center justify-center shrink-0 mt-0.5">
          <span class="text-xs">AI</span>
        </div>
        <div class="max-w-[80%]">
          <div class="text-xs text-gray-500 mb-1">
            <span v-if="toolHint">{{ toolHint }}</span>
            <span v-else>思考中...</span>
          </div>
          <ThoughtPanel
            :thoughts="thoughts"
            :tool-logs="toolLogs"
            :streaming-text="streamingText"
            :is-thinking="true"
            :collapsed="false"
          />
        </div>
      </div>
    </div>

    <div class="px-6 pb-4 pt-2">
      <!-- 工具失败中断横幅：等待用户决定继续/放弃 -->
      <div
        v-if="interruptInfo"
        class="mb-2 flex items-center gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5"
      >
        <div class="flex-1 min-w-0">
          <div class="text-sm text-amber-300/90 font-medium">执行中断：工具 {{ interruptInfo.tool }} 执行失败</div>
          <div class="text-xs text-gray-400 truncate mt-0.5">{{ interruptInfo.message }}</div>
        </div>
        <button
          @click="$emit('resume', 'retry')"
          :disabled="loading"
          class="shrink-0 px-3 py-1.5 bg-amber-500/80 hover:bg-amber-500 text-sm rounded-lg transition-colors disabled:opacity-40"
        >重试继续</button>
        <button
          @click="$emit('resume', 'abort')"
          :disabled="loading"
          class="shrink-0 px-3 py-1.5 bg-transparent hover:bg-white/10 text-gray-300 text-sm rounded-lg border border-gray-600 transition-colors disabled:opacity-40"
        >放弃</button>
      </div>

      <div class="flex gap-2">
        <input
          v-model="input"
          @keydown.enter="handleSend"
          :disabled="loading"
          placeholder="输入你的分析问题..."
          class="flex-1 bg-surface-lighter border border-border rounded-xl px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 outline-none focus:border-accent/50 transition-colors disabled:opacity-50"
        />
        <!-- 任务未执行：发送按钮 -->
        <button
          v-if="!loading"
          @click="handleSend"
          :disabled="!input.trim()"
          class="w-10 h-10 flex items-center justify-center bg-accent hover:bg-accent-light disabled:opacity-40 rounded-xl transition-colors"
          title="发送"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7"/>
          </svg>
        </button>
        <!-- 任务执行中：停止按钮（方块图标） -->
        <button
          v-else
          @click="$emit('stop')"
          class="w-10 h-10 flex items-center justify-center bg-amber-500/90 hover:bg-amber-500 rounded-xl transition-colors"
          title="停止任务"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import ThoughtPanel from './ThoughtPanel.vue'
import { renderMarkdown } from '../utils/md.js'

const props = defineProps({
  messages: Array,
  loading: Boolean,
  thoughts: Array,
  isThinking: Boolean,
  toolLogs: Array,
  streamingText: String,
  toolHint: String,
  interruptInfo: Object
})

const emit = defineEmits(['send', 'resume', 'stop'])

const input = ref('')
const scrollContainer = ref(null)

function scrollToBottom() {
  nextTick(() => {
    const el = scrollContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// 消息变化时自动滚到底部（immediate: 刷新时已有的消息也滚）
watch(
  [() => props.messages?.length, () => props.loading],
  scrollToBottom,
  { immediate: true }
)

function cleanContent(text) {
  if (!text) return ''
  // 去掉 [CHART]...[/CHART] 和 ```json...``` 块
  const clean = text
    .replace(/\[CHART\][\s\S]*?\[\/CHART\]/g, '')
    .replace(/```json[\s\S]*?```/g, '')
    .trim()
  return renderMarkdown(clean)
}

function handleSend() {
  const text = input.value.trim()
  if (!text) return
  emit('send', text)
  input.value = ''
}
</script>
