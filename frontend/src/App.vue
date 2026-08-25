<template>
  <div class="h-screen flex bg-surface text-gray-200">
    <Sidebar
      :conversations="conversations"
      :active-id="activeConvId"
      @select="selectConv"
      @new="newConv"
      @delete="deleteConv"
      @pin="pinConv"
    />
    <div class="flex-1 flex flex-col min-w-0">
      <ChatPanel
        :messages="currentMessages"
        :loading="loading"
        :thoughts="currentThoughts"
        :is-thinking="isThinking"
        :tool-logs="currentToolLogs"
        :streaming-text="streamingText"
        :tool-hint="currentToolHint"
        :interrupt-info="interruptInfo"
        @send="sendMessage"
        @resume="sendResume"
        @stop="stopCurrent"
      />
    </div>
    <Dashboard :charts="currentCharts" @remove="removeChart" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import Dashboard from './components/Dashboard.vue'

const STORAGE_KEY = 'datacopilot_conversations'

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) { /* ignore */ }
  return []
}
function saveConversations() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
}

const conversations = ref(loadConversations())
const activeConvId = ref(conversations.value[0]?.id || '')
const loading = ref(false)
const isThinking = ref(false)
const streamingText = ref('')  // 当前回答的打字机内容
const currentToolHint = ref('')  // 当前工具调用提示（气泡内显示）
const interruptInfo = ref(null)  // 工具失败中断信息 {tool, message}，显示"继续执行"按钮
let abortController = null   // 用于中途停止当前任务的 fetch controller

if (!conversations.value.length) {
  const c = createConv()
  conversations.value.push(c)
  activeConvId.value = c.id
}
saveConversations()

function createConv(title = '新对话') {
  return {
    id: crypto.randomUUID(),
    threadId: crypto.randomUUID(),
    title,
    pinned: false,
    messages: [],
    charts: [],
    thoughts: [],
    toolLogs: [],
    createdAt: Date.now()
  }
}

const activeConv = computed(() =>
  conversations.value.find(c => c.id === activeConvId.value)
)

const currentMessages = computed(() => activeConv.value?.messages || [])
const currentCharts = computed(() => activeConv.value?.charts || [])
const currentThoughts = computed(() => activeConv.value?.thoughts || [])
const currentToolLogs = computed(() => activeConv.value?.toolLogs || [])

function selectConv(id) {
  activeConvId.value = id
}
function newConv() {
  const c = createConv()
  conversations.value.unshift(c)
  activeConvId.value = c.id
  saveConversations()
}
function deleteConv(id) {
  const idx = conversations.value.findIndex(c => c.id === id)
  if (idx < 0) return
  conversations.value.splice(idx, 1)
  if (activeConvId.value === id) {
    activeConvId.value = conversations.value[0]?.id || ''
    if (!activeConvId.value) {
      const c = createConv()
      conversations.value.push(c)
      activeConvId.value = c.id
    }
  }
  saveConversations()
}
function removeChart(i) {
  if (!activeConv.value) return
  activeConv.value.charts.splice(i, 1)
  saveConversations()
}

function pinConv(id) {
  const idx = conversations.value.findIndex(c => c.id === id)
  if (idx < 0) return
  const item = conversations.value.splice(idx, 1)[0]
  item.pinned = !item.pinned
  if (item.pinned) {
    conversations.value.unshift(item)
  } else {
    const insertAt = conversations.value.filter(c => c.pinned).length
    conversations.value.splice(insertAt, 0, item)
  }
  saveConversations()
}

async function sendMessage(text) {
  const conv = activeConv.value
  if (!conv || loading.value) return

  // "继续"语义分流：
  //  - 工具失败中断后输入"继续" → 从断点恢复（sendResume）
  //  - 其他情况（普通暂停后输入"继续"）→ 当新消息发（LLM 看到上下文自然继续分析）
  if (text.trim() === '继续' && interruptInfo.value) {
    sendResume('retry')
    return
  }

  streamingText.value = ''  // 新消息开始时清空打字机
  currentToolHint.value = ''  // 清空工具提示

  if (conv.messages.length === 0) {
    conv.title = text.slice(0, 20) + (text.length > 20 ? '...' : '')
  }

  conv.messages.push({ role: 'user', content: text })
  saveConversations()

  loading.value = true
  isThinking.value = true
  conv.thoughts = []
  conv.toolLogs = []
  const startTime = Date.now()  // 用于强制最小显示时间

  let aiContent = ''

  // 用 AbortController 实现"中途停止"
  abortController = new AbortController()
  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, thread_id: conv.threadId }),
      signal: abortController.signal
    })

    aiContent = await handleSSE(resp, conv)
  } catch (e) {
    if (e.name === 'AbortError') {
      aiContent = ''  // 用户主动停止，不显示错误
    } else {
      aiContent = '请求失败: ' + e.message
      console.error(e)
    }
  } finally {
    abortController = null
  }

  // 强制最小显示时间：让用户能看清思考过程（哪怕 LLM 答得很快）
  const minDuration = 1500
  const elapsed = Date.now() - startTime
  if (elapsed < minDuration) {
    await new Promise(r => setTimeout(r, minDuration - elapsed))
  }

  isThinking.value = false
  loading.value = false

  if (interruptInfo.value) {
    // 工具失败中断：不保存回答，等用户点击"继续执行"
    streamingText.value = ''
    conv.thoughts = []
    saveConversations()
    return
  }

  if (aiContent) {
    // 存完整内容（含 [CHART]），Agent 需要看图表上下文；前端展示时再去除
    conv.messages.push({
      role: 'assistant',
      content: aiContent.replace('[DONE]', '').trim(),
      raw: aiContent  // 保留完整内容
    })
    streamingText.value = ''  // 已存入消息，清空打字机
    conv.thoughts = []         // 清空思考记录（避免和最终回答区重复显示）
  }
  saveConversations()
}

// 统一的 SSE 流解析：返回累积的 aiContent，处理 interrupt 事件
async function handleSSE(resp, conv) {
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  // 按 event/data/空行 完整事件处理（比 lines.indexOf 回溯更稳健）
  let currentEvent = ''
  let pendingData = ''
  let aiContent = ''

  const processEvent = () => {
    if (!pendingData) return
    try {
      const data = JSON.parse(pendingData)
      if (currentEvent === 'meta') {
        conv.threadId = data.thread_id
      } else if (currentEvent === 'thought_stream') {
        aiContent += data.content
        streamingText.value += data.content
        isThinking.value = true
      } else if (currentEvent === 'tool_call') {
        conv.toolLogs.push({ type: 'call', tool: data.tool, args: data.args, time: Date.now() })
        currentToolHint.value = `🔧 正在调用 ${data.tool}...`
      } else if (currentEvent === 'tool_start') {
        conv.toolLogs.push({ type: 'start', tool: data.tool, time: Date.now() })
        currentToolHint.value = `🔧 正在调用 ${data.tool}...`
      } else if (currentEvent === 'tool_result') {
        conv.toolLogs.push({ type: 'result', tool: data.tool, output: data.output, time: Date.now() })
        currentToolHint.value = `✅ ${data.tool} 执行完成`
      } else if (currentEvent === 'chart') {
        if (data.charts) data.charts.forEach(c => conv.charts.push(c))
      } else if (currentEvent === 'interrupt') {
        // 工具失败，图已暂停：记录中断信息，前端显示"继续执行"按钮
        interruptInfo.value = { tool: data.tool, message: data.message }
      } else if (currentEvent === 'error') {
        aiContent = '⚠️ 后端错误: ' + (data.message || JSON.stringify(data))
      }
    } catch (e) {
      console.error('[SSE parse error]', currentEvent, pendingData, e)
    }
    currentEvent = ''
    pendingData = ''
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        // 新事件开始前先处理上一个
        processEvent()
        currentEvent = line.replace(/^event: /, '').trim()
      } else if (line.startsWith('data: ')) {
        pendingData = line.replace(/^data: /, '').trim()
      } else if (line === '' && pendingData) {
        // 空行 = 事件结束
        processEvent()
      }
    }
  }
  // 流结束，处理残留
  processEvent()
  return aiContent
}

// 中途停止当前任务（abort SSE fetch）
function stopCurrent() {
  if (abortController) {
    abortController.abort()
    interruptInfo.value = null  // 普通停止不是真正的 interrupt，清掉提示
  }
}

// 断点恢复：用户点击"继续执行/放弃"后，用 resume 从断点续跑
async function sendResume(decision) {
  const conv = activeConv.value
  if (!conv || loading.value) return
  loading.value = true
  isThinking.value = true
  const startTime = Date.now()

  let aiContent = ''
  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: '', thread_id: conv.threadId, resume: decision })
    })
    aiContent = await handleSSE(resp, conv)
  } catch (e) {
    aiContent = '请求失败: ' + e.message
    console.error(e)
  }

  // 恢复完成后清除中断提示
  interruptInfo.value = null
  isThinking.value = false
  loading.value = false

  if (aiContent) {
    conv.messages.push({
      role: 'assistant',
      content: aiContent.replace('[DONE]', '').trim(),
      raw: aiContent
    })
    streamingText.value = ''
    conv.thoughts = []
  }
  saveConversations()
}
</script>
