<template>
  <span>{{ shown }}<span v-if="!finished" class="typing-cursor"></span></span>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  speed: { type: Number, default: 25 }  // 每字符间隔 ms
})

const shown = ref('')
const finished = ref(false)
let timer = null

function clearTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startTyping(target) {
  clearTimer()
  finished.value = false

  // 从当前进度继续（增量流式）
  let i = target.startsWith(shown.value) ? shown.value.length : 0
  if (i === 0) shown.value = ''

  timer = setInterval(() => {
    i++
    shown.value = target.slice(0, i)
    if (i >= target.length) {
      clearTimer()
      finished.value = true
    }
  }, props.speed)
}

watch(() => props.text, (val) => {
  if (!val) return
  startTyping(val)
}, { immediate: true })

onBeforeUnmount(clearTimer)
</script>
