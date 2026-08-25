/**
 * 轻量级 Markdown → HTML 渲染
 */
export function renderMarkdown(text) {
  if (!text) return ''

  let html = text
    // 转义 HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 代码块 ```...```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="bg-black/30 rounded-lg p-3 my-2 overflow-x-auto text-xs text-green-400"><code>${code.trim()}</code></pre>`
  })
  // 行内代码 `...`
  html = html.replace(/`([^`]+)`/g, '<code class="bg-black/30 px-1.5 py-0.5 rounded text-xs text-green-400">$1</code>')

  // 表格
  html = html.replace(/^\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)/gm, (_, header, body) => {
    const hcols = header.split('|').map(c => c.trim()).filter(Boolean)
    const thead = '<tr>' + hcols.map(c => `<th class="border border-gray-600 px-3 py-1.5 text-left text-xs text-gray-300 font-medium">${c}</th>`).join('') + '</tr>'
    const rows = body.trim().split('\n')
    const tbody = rows.map(row => {
      const cols = row.split('|').map(c => c.trim()).filter(Boolean)
      return '<tr>' + cols.map(c => `<td class="border border-gray-600 px-3 py-1.5 text-xs text-gray-200">${c}</td>`).join('') + '</tr>'
    }).join('')
    return `<table class="w-full border-collapse border border-gray-600 rounded-lg overflow-hidden my-2"><thead>${thead}</thead><tbody>${tbody}</tbody></table>`
  })

  // 粗体 **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-white">$1</strong>')

  // 换行
  html = html.replace(/\n/g, '<br>')

  // 水平线
  html = html.replace(/^---$/gm, '<hr class="border-gray-700 my-2">')

  return html
}
