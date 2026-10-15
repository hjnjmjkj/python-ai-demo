from mcp.server.fastmcp import FastMCP

from app.services.mcp_logic import (
    browse_construction_project,
    calculate,
    draw_geometry_region,
    locate_equipment,
    view_hosted_layer,
)

mcp = FastMCP(
    "sggis-mcp-server",
    host="0.0.0.0",
    port=8081,
    instructions=(
        "提供精确计算、设备定位、托管图层查看、几何区域绘制和基建工程浏览工具。"
        "多候选结果必须先由用户确认；地图工具的 action 和 actionParams 交由前端渲染。"
    ),
    stateless_http=True,
)


@mcp.tool(name="calculate", description="精确执行两数四则运算。operation 为 ADD、SUBTRACT、MULTIPLY 或 DIVIDE。")
def calculate_tool(operation: str, left: float, right: float) -> dict:
    return calculate(operation, left, right)


@mcp.tool(name="locateEquipment", description="按设备名称、OID 或设备ID定位线路、变电站等设备；多结果时先确认候选。")
def locate_equipment_tool(keyword: str) -> dict:
    return locate_equipment(keyword)


@mcp.tool(name="viewHostedLayer", description="按应用名称与图层名称查找托管图层；多结果时先确认候选。")
def view_hosted_layer_tool(applicationName: str, layerName: str) -> dict:
    return view_hosted_layer(applicationName, layerName)


@mcp.tool(name="drawGeometryRegion", description="绘制组织范围（距离为0）或设备缓冲范围（距离为米）。")
def draw_geometry_region_tool(target: str, bufferDistanceMeters: float) -> dict:
    return draw_geometry_region(target, bufferDistanceMeters)


@mcp.tool(name="browseConstructionProject", description="按工程名称或ID查询工程和模型；多结果时先确认候选。")
def browse_construction_project_tool(projectNameOrId: str) -> dict:
    return browse_construction_project(projectNameOrId)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
