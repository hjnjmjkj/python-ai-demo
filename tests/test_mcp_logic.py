from decimal import Decimal
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent import _record_tool_results
from app.schemas import ChatRequest, KnowledgeSearchRequest
from app.services.mcp_logic import (
    browse_construction_project,
    calculate,
    draw_geometry_region,
    locate_equipment,
    view_hosted_layer,
)


def test_calculate_returns_exact_decimal_result():
    result = calculate("DIVIDE", "12.5", "4")
    assert result["result"] == Decimal("3.125")
    assert result["expression"] == "12.5 / 4"


def test_calculate_rejects_division_by_zero():
    with pytest.raises(ValueError, match="除数不能为零"):
        calculate("DIVIDE", 2, 0)


def test_locate_equipment_requires_confirmation_for_multiple_matches():
    result = locate_equipment("春山线")
    assert result["status"] == "NEED_CONFIRMATION"
    assert {item["name"] for item in result["candidates"]} == {"春山线", "春山线备用支线"}


def test_locate_equipment_returns_frontend_action_for_unique_match():
    result = locate_equipment("1516289")
    assert result["status"] == "COMPLETED"
    assert result["action"] == "LOCATE_EQUIPMENT"
    assert result["actionParams"]["equipment"]["name"] == "中闽线"


def test_hosted_layer_returns_confirmation_if_multiple_matches():
    result = view_hosted_layer("配网运检应用", "图层")
    assert result["status"] == "NEED_CONFIRMATION"
    assert len(result["candidates"]) == 2


def test_draw_region_supports_org_boundary_and_equipment_buffer():
    org = draw_geometry_region("厦门市供电公司", 0)
    assert org["status"] == "COMPLETED"
    assert org["action"] == "DRAW_REGION"
    assert org["actionParams"]["mode"] == "ORGANIZATION_BOUNDARY"

    buffer = draw_geometry_region("中闽线", 500)
    assert buffer["status"] == "COMPLETED"
    assert buffer["actionParams"]["bufferDistanceMeters"] == 500
    assert buffer["actionParams"]["geometry"]["type"] == "Polygon"


def test_project_lookup_returns_default_model():
    result = browse_construction_project("厦门同安输变电工程")
    assert result["status"] == "COMPLETED"
    assert result["action"] == "SHOW_CONSTRUCTION_PROJECT"
    assert result["actionParams"]["defaultModel"]["modelId"] == "MODEL-001-A"


def test_project_ambiguous_search_requires_confirmation():
    result = browse_construction_project("同安")
    assert result["status"] == "NEED_CONFIRMATION"
    assert len(result["candidates"]) == 2


def test_chat_request_validates_uuid_and_message_limit():
    payload = ChatRequest(
        conversationId=UUID("7f3ad908-937f-4d5f-b4d1-fd5aef7d44a1"),
        message="你好",
    )
    assert payload.message == "你好"
    with pytest.raises(ValueError):
        ChatRequest(conversationId="not-a-uuid", message="hi")
    with pytest.raises(ValueError):
        ChatRequest(
            conversationId=UUID("7f3ad908-937f-4d5f-b4d1-fd5aef7d44a1"),
            message="x" * 4001,
        )


def test_knowledge_search_defaults_match_java_contract():
    request = KnowledgeSearchRequest(query="产品保修多久")
    assert request.topK == 5
    assert request.similarityThreshold == 0.65
    with pytest.raises(ValueError):
        KnowledgeSearchRequest(query="query", topK=21)


def test_recorded_mcp_json_is_preserved_as_json_values():
    messages = [
        AIMessage(content="", tool_calls=[{
            "name": "mcp__gis__locateEquipment",
            "args": {"keyword": "中闽线"},
            "id": "call-1",
            "type": "tool_call",
        }]),
        ToolMessage(
            content=[{"type": "text", "text": '{"status":"COMPLETED","candidates":[]}'}],
            tool_call_id="call-1",
        ),
    ]
    result = _record_tool_results(messages)
    assert result == [{
        "toolName": "locateEquipment",
        "arguments": {"keyword": "中闽线"},
        "result": {"status": "COMPLETED", "candidates": []},
    }]
