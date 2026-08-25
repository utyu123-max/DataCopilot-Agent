"""
Agent 状态定义
LangGraph 的 StateGraph 核心状态
"""

from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Agent 状态"""

    # 消息历史（add_messages 支持追加 + RemoveMessage 删除）
    #变量 messages：类型是「BaseMessage 对象组成的序列」，并且指定更新策略为追加合并消息。sequence[]兼容列表元组
    #Annotated(类型, 标记) = 给类型打标签，框架靠这个标签识别特殊逻辑。
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 当前可用的数据源类型: "csv" / "mysql" / "both"
    datasource_active: str

    # 当前会话的图表列表
    charts: list[dict]

    # 当前任务是否完成
    task_complete: bool

    # 意图分类结果: "business"（数据分析） / "casual"（闲聊/领域外）
    # 非累积字段，classify 节点每次覆盖
    intent: str
