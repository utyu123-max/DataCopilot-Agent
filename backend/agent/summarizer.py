"""
上下文摘要器：用便宜模型把中间对话压缩成摘要
LangGraph 滚动摘要（rolling summary）模式
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from config import QWEN_API_KEY, QWEN_BASE_URL, SUMMARY_MODEL

# 便宜摘要模型（单例，避免重复实例化）
_summary_llm = None


def _get_summary_llm():
    global _summary_llm
    if _summary_llm is None:
        _summary_llm = ChatOpenAI(
            model=SUMMARY_MODEL,
            temperature=0,          # 摘要要稳定，不要随机
            max_tokens=512,         # 摘要不需要太长
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
        )
    return _summary_llm


def summarize_messages(messages: list[BaseMessage], max_chars: int = 400) -> str:
    """
    将一组消息压缩为中文摘要。

    参数:
        messages: 需要被压缩的中间对话消息
        max_chars: 摘要最大长度（字符数）

    返回:
        摘要文本（失败时返回兜底占位文本）
    """
    # 把消息转成可读文本（截断每条长度）
    lines = []
    for m in messages:
        role = m.__class__.__name__.replace("Message", "")
        content = (m.content or "")[:300]
        if content:
            lines.append(f"[{role}] {content}")

    if not lines:
        return "[中间对话无实质内容]"

    text = "\n".join(lines)

    prompt = (
        f"你是对话摘要助手。以下是用户与数据分析助手的一段历史对话记录，"
        f"请用简体中文概括这段对话：用户问了什么问题、助手查了什么数据、结论是什么。"
        f"控制在{max_chars}字以内，保留关键数字和结论。\n\n"
        f"对话记录:\n{text}"
    )

    try:
        resp = _get_summary_llm().invoke([HumanMessage(content=prompt)])
        summary = (resp.content or "").strip()
        if not summary:
            return "[中间对话已压缩]"
        return summary
    except Exception as e:
        print(f"[Summarizer] 摘要生成失败，使用兜底占位: {e}")
        return "[中间对话已压缩]"
