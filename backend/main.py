"""
DataCopilot 后端入口
FastAPI + LangGraph Agent + SSE 流式
"""

import json
import uuid
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_core.messages import HumanMessage
from langgraph.types import Command




# LangGraph 初始化（延迟到 app 启动时 async 创建）
_graph = None
async def init_graph():
    global _graph
    from agent.graph import build_graph
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    import os

    db_path = os.path.join(os.path.dirname(__file__), ".memory.db")
    conn = await aiosqlite.connect(db_path)
    #异步持久化检查点
    checkpointer = AsyncSqliteSaver(conn)
    _graph = build_graph(checkpointer=checkpointer)
    print(f"[DataCopilot] Graph 初始化完成 (memory: {db_path})")

def get_graph():
    if _graph is None:
        raise RuntimeError("Graph 未初始化！请先调用 init_graph()")
    return _graph



# 应用生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_graph()
    yield
    print("服务关闭，释放资源")

app = FastAPI(title="DataCopilot", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,        # 跨域资源共享中间件，让后端允许前端跨域访问接口。
    allow_origins=["*"],   #允许哪些来源
    allow_credentials=True,#是否允许携带token\cookie凭证
    allow_methods=["*"],   #允许请求方式 GET/POST/PUT/DELETE...
    allow_headers=["*"],   # 允许客户端自定义请求头
)



# 请求模型
class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""
    resume: str | None = None  # 断点恢复：用户对 interrupt 的决策（retry / abort）


class DataSourceRequest(BaseModel):
    type: str  # "csv" or "mysql"
    mysql_config: dict | None = None



# Prompt Injection 检测
import re

_INJECTION_PATTERNS = [
    # 中文注入
    r"忽略(之前|前面|上面|所有).*(指令|提示|要求|命令|规则)",
    r"不要(遵守|遵循|执行|按照).*(指令|提示|要求|命令|规则)",
    r"修改.*系统(提示|指令|prompt)",
    r"覆盖.*(规则|指令|设定)",
    r"删除.*(表|数据|数据库)",
    r"DROP\s+TABLE",
    r"TRUNCATE\s+TABLE",
    r"DELETE\s+FROM",
    r"执行.*(命令|脚本|shell|cmd|terminal)",
    r"获取.*(密码|token|密钥|API_KEY|api_key)",
    r"(告诉|泄露|给我|暴露|交出).*(密码|token|密钥|secret|API_KEY)",
    # 英文注入
    r"ignore\s+(previous|all|above|below)\s+(instructions|prompts|commands|rules)",
    r"forget\s+(all|previous|above).*(instructions|rules)",
    r"you\s+are\s+now\s+(free|released|not\s+bound)",
    r"do\s+not\s+(follow|obey|respect)\s+(instructions|prompts|rules)",
    r"override\s+(instructions|rules|prompt)",
    r"modify\s+(your\s+)?(system\s+)?(prompt|instructions)",
    r"execute\s+(shell|command|system|cmd|terminal)",
    r"get\s+(password|token|key|secret|api_key)",
    r"access\s+(root|admin|sudo)",
]

def check_injection(text: str) -> str | None:
    """
    检测用户输入是否存在 Prompt Injection。
    返回警告消息（命中时）或 None（安全）。
    """
    if not text:
        return None
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return (
                f"检测到异常请求，已拦截。\n"
                f"请正常使用数据分析功能。"
            )
    return None
# SSE 事件发送辅助函数标准的sse输出格式
async def sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"



# 流式对话接口
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话，SSE 推送 Agent 思考过程"""
    #前端传入thread_id复用对话加载上下文，不传入生成新的uuid，开启新对话
    thread_id = req.thread_id or str(uuid.uuid4())
    # recursion_limit: ReAct 循环上限（防死循环），
    # 超过 15 个超步抛 GraphRecursionError，由外层 try-except 兜底
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 15,
    }
    #异步生成器
    async def generate() -> AsyncGenerator[str, None]:
        #第一条推送元数据把对话id发送给前端
        yield await sse_event("meta", {"thread_id": thread_id})

        # Prompt Injection 预检（仅在普通请求时，resume 恢复请求跳过）
        if req.resume is None:
            warning = check_injection(req.message)
            #预警输出警告信息并终止流程
            if warning:
                yield await sse_event("thought_stream", {"content": warning})
                yield await sse_event("done", {"status": "blocked", "reason": "injection"})
                return

        # 构建输入：
        #  - resume 请求：Command(resume=决策) 从断点恢复（不重跑已完成步骤）
        #  - 普通请求：只传新消息，其余由 checkpointer 续接
        if req.resume is not None:
            input_state = Command(resume=req.resume)
        else:
            input_state = {
                "messages": [HumanMessage(content=req.message)],
            }

        try:
            async for event in get_graph().astream_events(input_state, config, version="v2"):
                kind = event["event"] #事件大类
                name = event.get("name", "") #节点名称
                data = event.get("data", {}) #事件携带负载数据

                # LLM 流式 token（LangChain 封装恢复，逐字推送思考/回答）
                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        yield await sse_event("thought_stream", {"content": chunk.content})

                # 工具开始执行
                if kind == "on_tool_start":
                    yield await sse_event("tool_start", {
                        "tool": name,
                        "input": data.get("input", {}),
                    })

                # 工具执行完成
                if kind == "on_tool_end":
                    output_str = str(data.get("output", ""))
                    # 截断过长输出
                    if len(output_str) > 2000:
                        output_str = output_str[:2000] + "...(已截断)"
                    yield await sse_event("tool_result", {
                        "tool": name,
                        "output": output_str,
                    })

                # 图表生成事件
                if kind == "on_chain_end" and name == "finalize":
                    final_output = data.get("output", {})
                    charts = final_output.get("charts", [])
                    if charts:
                        yield await sse_event("chart", {
                            "charts": charts,
                        })

                # 领域外友好拒答（domain_reject 不调 LLM，无流式事件，从节点输出提取）
                if kind == "on_chain_end" and name == "domain_reject":
                    node_output = data.get("output", {})
                    node_msgs = node_output.get("messages", []) if isinstance(node_output, dict) else []
                    if node_msgs:
                        last = node_msgs[-1]
                        if hasattr(last, "content") and last.content:
                            yield await sse_event("thought_stream", {"content": last.content})

            # 事件流结束后检查：是否有 pending interrupt（工具失败等待用户决策）
            snapshot = await get_graph().aget_state(config)
            interrupts = []
            if snapshot.next:
                for task in snapshot.tasks:
                    for it in getattr(task, "interrupts", []) or []:
                        interrupts.append(it.value)

            if interrupts:
                # 图暂停在中断点：推送 interrupt 事件，前端展示"继续执行"按钮
                yield await sse_event("interrupt", {
                    "message": interrupts[0].get("message", ""),
                    "tool": interrupts[0].get("tool", ""),
                })
            else:
                yield await sse_event("done", {"status": "complete"})

        except Exception as e:
            yield await sse_event("error", {"message": str(e)})
            yield await sse_event("done", {"status": "error"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream", #标准 SSEMIME 类型
        headers={
            "Cache-Control": "no-cache",#禁止浏览器缓存流
            "Connection": "keep-alive", #长连接
            "X-Accel-Buffering": "no",  #关闭 Nginx 缓冲；部署后端如果有Nginx反向代理必须加这个，否则流式卡顿、攒包
        },
    )



# 健康检查
@app.get("/health")
def health():
    return {"status": "ok", "service": "DataCopilot"}


# 启动
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
