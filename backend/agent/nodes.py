"""
Agent Node 和 Tools Node
LangGraph 的 ReAct 循环节点
"""

import json
import re

from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage
from openai import OpenAI

from config import (
    QWEN_API_KEY, QWEN_BASE_URL, LLM_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
)
from agent.prompt import SYSTEM_PROMPT
from agent.state import AgentState
from tools.query_mysql import query_mysql
from tools.query_csv import query_csv
from tools.execute_python import execute_python
from tools.get_schema import get_schema_info
from tools.query_clickhouse import query_clickhouse


# 工具列表
ALL_TOOLS = [query_mysql, query_csv, execute_python, get_schema_info, query_clickhouse]

# 容错 JSON 解析（Qwen 返回的 arguments 可能不标准）
def safe_json_loads(s: str) -> dict | None:
    """多级容错解析 LLM 返回的 JSON arguments"""
    if not s or not s.strip():
        return {}

    s = s.strip()
    attempts = [
        s,                                                      # 原样
        re.sub(r";\s*}$", "}", s),                  # 去掉结尾分号
        s.replace("'", '"'),                           # 单引号 -> 双引号
        re.sub(r",\s*([}\]])", r"\1", s),           # 去掉尾逗号
        re.sub(r";\s*([}\]])", r"\1", s),           # 去掉任意分号
    ]

    for candidate in attempts:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 全部失败：最后尝试从最外层括号截取
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None



# 主 LLM（LangChain 封装，保留流式事件）
llm = ChatOpenAI(
    model=LLM_MODEL,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
).bind_tools(ALL_TOOLS)



# 兜底：手动 OpenAI Client + 容错解析（仅在主路径失败时用）
_client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.args,
        },
    }
    for t in ALL_TOOLS
]


def _manual_call_with_fallback(messages: list) -> AIMessage:
    """手动调用 OpenAI Client 并容错解析 tool_calls（兜底路径）"""
    openai_messages = []
    for m in messages:
        if isinstance(m, SystemMessage):
            openai_messages.append({"role": "system", "content": m.content})
        elif isinstance(m, AIMessage):
            openai_messages.append({"role": "assistant", "content": m.content or ""})
        else:
            openai_messages.append({"role": "user", "content": m.content or ""})

    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=openai_messages,
        tools=_TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    #取第一条结果
    choice = resp.choices[0]
    #获取模型返回的原始的消息对象
    raw_msg = choice.message
    #提取文本
    content = raw_msg.content or ""

    tool_calls = []
    for tc in (raw_msg.tool_calls or []):
        args = safe_json_loads(tc.function.arguments)
        if args is None:
            print(f"[Agent] 警告: tool_call 参数解析失败, 跳过: {tc.function.arguments[:80]}")
            continue
        tool_calls.append({
            "name": tc.function.name,
            "args": args,
            "id": tc.id,
            "type": "tool_call",
        })

    return AIMessage(content=content, tool_calls=tool_calls)

# 节点
def _sanitize_messages(messages: list) -> list:
    """
    防御性清洗：移除"孤立 tool_calls AIMessage"。
    """
    #新建空列表，存放合法、干净的消息，最终返回这个列表。
    clean = []
    # 存放：已经发起工具调用，还没收到工具返回结果的tool_call_id
    pending_ids = set()

    for m in messages:
        if m.__class__.__name__ == "ToolMessage":
            clean.append(m)
            pending_ids.discard(m.tool_call_id)
            continue

        if isinstance(m, AIMessage) and m.tool_calls:
            ids = {tc.get("id") for tc in m.tool_calls if tc.get("id")}
            clean.append(m)
            pending_ids |= ids
            continue
        #：模型直接输出最终回答，中断工具流程，未完成的工具调用直接作废。
        if isinstance(m, AIMessage) and not m.tool_calls:
            pending_ids.clear()  # 新的普通回答，之前的 tool_calls 已被响应或丢弃
            clean.append(m)
            continue

        clean.append(m)

    # 流结束仍未配对 → 孤儿 tool_calls，剔除
    if pending_ids:
        clean = [
            m for m in clean
            #如果不是孤儿消息就保留
            if not (isinstance(m, AIMessage) and m.tool_calls
                    and any(tc.get("id") in pending_ids for tc in m.tool_calls))
        ]
    return clean


async def agent_node(state: AgentState) -> dict:
    """Agent 节点：LLM 思考 + 决策（异步调用保留流式事件 + 解析失败兜底）"""
    messages = state["messages"]
    # 清洗历史：剔除孤立 tool_calls（防 400 错误）
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(_sanitize_messages(messages))

    response = await llm.ainvoke(full_messages)

    # 检测 LangChain 是否丢弃了 tool_calls：
    # Qwen 返回 finish_reason=tool_calls 但 tool_calls 为空 = JSON 解析失败
    finish_reason = (response.response_metadata or {}).get("finish_reason") # finish_reason：模型停止输出原因
    if finish_reason == "tool_calls" and not response.tool_calls:
        print("[Agent] LangChain 解析 tool_calls 失败，走手动兜底...")
        response = _manual_call_with_fallback(full_messages)

    return {"messages": [response]}


# Tools Node：执行工具调用（LangChain 标准 ToolNode 作为底层执行器）
_base_tool_node = ToolNode(ALL_TOOLS)


def tools_node(state: AgentState) -> dict:
    """
    自定义 Tools Node（断点恢复版）：
    执行工具；当工具返回错误/拦截/超时文本时，interrupt 暂停图执行，
    等待用户决策（retry 重试 / abort 放弃），恢复后从本节点继续，不重跑已完成的步骤。
    """
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    tool_name = tool_calls[0]["name"] if tool_calls else "?"

    # 执行工具（LLM 提出的全部 tool_calls）
    result = _base_tool_node.invoke(state)

    # 检测工具输出是否失败（错误/安全拦截/沙箱错误）
    failed = False
    error_msg = ""
    for msg in result.get("messages", []):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.startswith(("[错误]", "[安全拦截]", "[沙箱错误]")):
            failed = True
            error_msg = content[:200]
            break

    if failed:
        # 中断：图在此暂停并持久化，等待用户决定
        decision = interrupt({
            "type": "tool_error",
            "tool": tool_name,
            "message": error_msg,
        })
        # resume 后从这里继续；decision 是用户的选择
        if decision == "retry":
            # 用户要求重试：重新执行工具（重试后不再二次中断，失败交给 LLM 自愈）
            result = _base_tool_node.invoke(state)

    return result
