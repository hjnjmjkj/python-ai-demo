from __future__ import annotations

import json
from collections import OrderedDict
from threading import Lock
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.config import settings

SYSTEM_PROMPT = """你是一个友好、严谨的中文电网 GIS 智能助手。
优先使用提供的知识库上下文；知识库没有相关内容时，不要编造来源。
数学计算必须调用 calculate 工具，不要自行估算。
用户要求定位设备时调用 locateEquipment；打开托管图层时调用 viewHostedLayer；
组织范围或设备缓冲区绘制时调用 drawGeometryRegion；浏览工程时调用 browseConstructionProject。
地图工具返回 NEED_CONFIRMATION 时列出 candidates 并等待用户选择；不得擅自选择。
只有 COMPLETED 结果才可以交给网页端执行地图动作；不得改写 action 或 actionParams。
NOT_FOUND 时说明未找到并请用户提供更准确名称或ID。普通问题用中文直接回答。
"""


def _decode_content(content: Any) -> Any:
    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        content = "".join(text_parts)
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content


def _tool_name(name: str) -> str:
    return name.split("__")[-1]


def _record_tool_results(messages: list[Any]) -> list[dict[str, Any]]:
    calls: dict[str, dict[str, Any]] = {}
    results = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                calls[call["id"]] = {
                    "toolName": _tool_name(call["name"]),
                    "arguments": call.get("args", {}),
                }
        elif isinstance(message, ToolMessage) and message.tool_call_id in calls:
            call = calls[message.tool_call_id]
            results.append({
                **call,
                "result": _decode_content(message.content),
            })
    return results


class AgentService:
    def __init__(self) -> None:
        self._client = MultiServerMCPClient({
            "gis": {
                "transport": "streamable_http",
                "url": f"{settings.mcp_server_url.rstrip('/')}/mcp",
            }
        })
        self._sessions: OrderedDict[str, list[Any]] = OrderedDict()
        self._session_lock = Lock()
        self._graph = None

    async def initialize(self) -> None:
        if not settings.dashscope_api_key:
            raise RuntimeError("请设置 DASHSCOPE_API_KEY 后再启动 Agent 服务")
        tools = await self._client.get_tools()
        model = ChatOpenAI(
            model=settings.qwen_model,
            api_key=settings.dashscope_api_key,
            base_url=settings.qwen_base_url,
            temperature=0.2,
            timeout=120,
        ).bind_tools(tools)

        async def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
            return {"messages": [await model.ainvoke(state["messages"])]}

        builder = StateGraph(MessagesState)
        builder.add_node("agent", call_model)
        builder.add_node("tools", ToolNode(tools))
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        builder.add_edge("tools", "agent")
        self._graph = builder.compile()

    async def chat(self, conversation_id: str, message: str, knowledge_context: str = "") -> dict[str, Any]:
        if self._graph is None:
            raise RuntimeError("Agent 尚未初始化")
        with self._session_lock:
            history = list(self._sessions.get(conversation_id, []))

        system_content = SYSTEM_PROMPT
        if knowledge_context:
            system_content += f"\n\n知识库检索上下文：\n{knowledge_context}"
        initial_messages = [SystemMessage(content=system_content), *history, HumanMessage(content=message)]
        state = await self._graph.ainvoke({"messages": initial_messages})
        messages = state["messages"]
        response = next((item for item in reversed(messages) if isinstance(item, AIMessage)), None)
        content = str(response.content if response else "")

        conversation_messages = [item for item in messages if not isinstance(item, SystemMessage)]
        with self._session_lock:
            self._sessions[conversation_id] = conversation_messages[-settings.max_history_messages:]
            self._sessions.move_to_end(conversation_id)

        return {"content": content, "toolResults": _record_tool_results(messages)}


def parse_mcp_result(value: str | list[Any] | dict[str, Any]) -> Any:
    return _decode_content(value)
