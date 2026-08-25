"""
LangGraph 单 Agent ReAct 循环
"""

import asyncio

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import agent_node, tools_node
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage

from chart.mapper import parse_chart_from_code_output, map_chart_intent


async def classify_node(state: AgentState) -> dict:
    """
    意图分类：数据分析请求 → 进 Agent；闲聊/领域外 → 友好拒答。
    用便宜模型 + to_thread（同步调用不阻塞事件循环，且不产生 LangChain 流式事件）。
    """
    from agent.classifier import classify_intent

    messages = state["messages"]
    last = messages[-1]
    user_text = last.content if isinstance(last, HumanMessage) else str(last.content)
    intent = await asyncio.to_thread(classify_intent, user_text)
    print(f"[Classifier] intent={intent} | {user_text[:40]}")
    return {"intent": intent}


def route_by_intent(state: AgentState) -> str:
    """分类路由：business → agent；casual → domain_reject"""
    return "business" if state.get("intent", "business") == "business" else "casual"


def domain_reject(state: AgentState) -> dict:
    """领域外友好拒答：不调主 LLM，固定文案 + 引导回正题（零成本零延迟）"""
    last = state["messages"][-1]
    user_text = str(last.content)[:50] if last else ""
    reply = (
        "我是 DataCopilot，一个数据智能分析助手，主要负责数据查询、分析和可视化。\n\n"
        f"「{user_text}」不在我的能力范围内。\n\n"
        "您可以试试这样问我：\n"
        "- 「7月各渠道销售额对比，画个柱状图」\n"
        "- 「抖音和小红书这个月的销售额对比」\n"
        "- 「哪个渠道的 ROI 最高」"
    )
    return {"messages": [AIMessage(content=reply)], "task_complete": True}


def should_continue(state: AgentState) -> str:
    """
    判断 Agent 是否应该继续调用工具。
    条件:
    1. 最后一条消息是 AIMessage 且包含 tool_calls → 继续调用工具
    2. 其他情况 → 结束
    """
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue_tools"
    return "end"


def finalize(state: AgentState) -> dict:
    """
    结束前处理：
    1. 检查最后一条 AI 消息是否包含图表意图 JSON
    2. 如果有，解析并映射为 ECharts Option
    3. 更新 charts 列表
    """
    messages = state["messages"]
    #复制状态中的charts，不直接修改
    charts = list(state.get("charts", []))
    #拿到本轮对话的LLM最后输出
    if messages:
        last_ai = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                last_ai = msg
                break

        if last_ai:
            #从 AI 文本中提取图表意图 JSON。
            chart_intent = parse_chart_from_code_output(last_ai.content)
            if chart_intent:
                echarts_option = map_chart_intent(chart_intent)
                charts.append({
                    "intent": chart_intent,
                    "echarts_option": echarts_option,
                })

    return {"charts": charts, "task_complete": True}


def trim_context(state: AgentState) -> dict:
    """
    滑动窗口修剪：防止上下文 token 暴涨。
    保留第一轮 + 最近 3 轮，中间消息用便宜模型生成摘要（而非直接删除）。
    """
    messages = state["messages"]
    if len(messages) <= 8:
        return {}  # 不触发修剪

    def is_keepable(m) -> bool:
        """可保留的消息：Human / 无 tool_calls 的 AIMessage"""
        if isinstance(m, HumanMessage):
            return True
        if isinstance(m, AIMessage) and not m.tool_calls:
            return True
        return False

    # 保留：第一轮（索引 0,1，若可保留）+ 最近 3 轮 Human/AI（不含 tool_calls 轮）
    keep = set()

    for m in messages[:2]:
        if is_keepable(m) and hasattr(m, "id") and m.id:
            keep.add(m.id)

    count = 0
    for m in reversed(messages):
        if is_keepable(m):
            if hasattr(m, "id") and m.id:
                keep.add(m.id)
            count += 1
            if count >= 6:
                break

    # 中间消息 → 送去摘要
    middle = [
        m for m in messages
        if hasattr(m, "id") and m.id and m.id not in keep
    ]

    summary_text = "[中间对话已压缩]"
    if middle:
        from agent.summarizer import summarize_messages
        summary_text = summarize_messages(middle)

    # 删除旧中间消息
    removes = [
        RemoveMessage(id=m.id)
        for m in middle
    ]

    # 摘要作为 SystemMessage 插入（用户不可见，但 LLM 可读）
    summary_msg = SystemMessage(content=f"[历史对话摘要] {summary_text}")

    # 保留的消息
    survivors = [m for m in messages if hasattr(m, "id") and m.id in keep]

    print(f"[Trimmer] {len(messages)} 条 → 保留 {len(survivors)} 条 + 1 条摘要 (压缩 {len(middle)} 条)")
    return {"messages": removes + [summary_msg] + survivors}

# 构建 Graph
def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)

    graph.add_node("classify", classify_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("finalize", finalize)
    graph.add_node("trimmer", trim_context)
    graph.add_node("domain_reject", domain_reject)

    # 入口：意图分类
    graph.set_entry_point("classify")

    # 分类路由：business → Agent 主流程；casual → 领域外拒答（不调主 LLM）
    graph.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "business": "agent",
            "casual": "domain_reject",
        },
    )
    graph.add_edge("domain_reject", END)

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue_tools": "tools",
            "end": "finalize",
        },
    )

    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", "trimmer")
    graph.add_edge("trimmer", END)

    if checkpointer is None:
        # fallback - 没有提供 checkpointer 就是无状态模式
        compiled = graph.compile()
    else:
        compiled = graph.compile(checkpointer=checkpointer)#开启持久化模式
    return compiled
