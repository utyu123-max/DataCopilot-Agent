<template>
  <div class="w-64 h-full flex flex-col bg-surface-light border-r border-border shrink-0">
    <div class="p-3 flex items-center justify-between">
      <h1 class="text-sm font-medium text-accent-light">DataCopilot</h1>
      <button
        @click="$emit('new')"
        class="w-7 h-7 flex items-center justify-center rounded-md hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors"
        title="新建对话"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 2a.75.75 0 01.75.75v4.5h4.5a.75.75 0 010 1.5h-4.5v4.5a.75.75 0 01-1.5 0v-4.5h-4.5a.75.75 0 010-1.5h4.5v-4.5A.75.75 0 018 2z"/>
        </svg>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
      <div
        v-for="conv in sortedList"
        :key="conv.id"
        :class="[
          'group relative px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm',
          conv.id === activeId
            ? 'bg-accent/20 text-white'
            : 'hover:bg-white/5 text-gray-400'
        ]"
        @click="$emit('select', conv.id)"
      >
        <div class="flex items-center gap-2">
          <span class="text-xs shrink-0">{{ conv.pinned ? '📌' : '💬' }}</span>
          <span class="truncate flex-1">{{ conv.title }}</span>
          <div class="shrink-0 relative">
            <button
              class="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"
              @click.stop="toggleMenu(conv.id)"
              title="更多"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <circle cx="8" cy="3" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="8" cy="13" r="1.5"/>
              </svg>
            </button>
            <div
              v-if="menuId === conv.id"
              class="absolute right-0 top-8 w-32 bg-surface border border-border rounded-lg shadow-xl z-50 py-1 text-xs"
            >
              <button
                class="w-full text-left px-3 py-2 hover:bg-white/5 flex items-center gap-2"
                @click.stop="handlePin(conv.id)"
              >
                <span>{{ conv.pinned ? '取消置顶' : '置顶' }}</span>
              </button>
              <button
                class="w-full text-left px-3 py-2 hover:bg-white/5 text-red-400 flex items-center gap-2"
                @click.stop="handleDelete(conv.id)"
              >
                <span>删除</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="menuId" class="fixed inset-0 z-40" @click="menuId = ''"></div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  conversations: Array,
  activeId: String
})
const emit = defineEmits(['select', 'new', 'delete', 'pin'])

const menuId = ref('')

const sortedList = computed(() => {
  const arr = [...props.conversations]
  arr.sort((a, b) => {
    if (a.pinned && !b.pinned) return -1
    if (!a.pinned && b.pinned) return 1
    return b.createdAt - a.createdAt
  })
  return arr
})

function toggleMenu(id) { menuId.value = menuId.value === id ? '' : id }
function handlePin(id) { emit('pin', id); menuId.value = '' }
function handleDelete(id) { emit('delete', id); menuId.value = '' }
</script>
