from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from typing import Any


def _candidate(oid: str, type_id: str, device_id: str, name: str, kind: str) -> dict[str, Any]:
    return {"oid": oid, "typeId": type_id, "deviceId": device_id, "name": name, "geometryKind": kind}


EQUIPMENT = [
    (_candidate("1516289", "102000", "LINE-1516289", "中闽线", "LINE"), "10kV",
     {"type": "LineString", "coordinates": [[118.128, 24.72], [118.139, 24.726], [118.151, 24.731]]}),
    (_candidate("1612457", "102000", "LINE-1612457", "春山线", "LINE"), "10kV",
     {"type": "LineString", "coordinates": [[118.09, 24.65], [118.103, 24.659]]}),
    (_candidate("1612999", "102000", "LINE-1612999", "春山线备用支线", "LINE"), "10kV",
     {"type": "LineString", "coordinates": [[118.102, 24.659], [118.111, 24.665]]}),
    (_candidate("16841", "301000", "STATION-16841", "110kV同安变电站", "POINT"), "110kV",
     {"type": "Point", "coordinates": [118.151, 24.731]}),
    (_candidate("310001", "301000", "STATION-310001", "110kV莲前变电站", "POINT"), "110kV",
     {"type": "Point", "coordinates": [118.149, 24.476]}),
]

LAYERS = [
    {"layerId": 92, "appKey": "4bb6185c64ec451db9a6fe46c84d7273", "appName": "配网运检应用",
     "layerAlias": "设备缺陷图层", "state": 0},
    {"layerId": 108, "appKey": "4bb6185c64ec451db9a6fe46c84d7273", "appName": "配网运检应用",
     "layerAlias": "抢修资源图层", "state": 0},
    {"layerId": 205, "appKey": "8f8502d7347c4bc1a5ad30f669b66f56", "appName": "基建管理应用",
     "layerAlias": "在建工程图层", "state": 0},
    {"layerId": 206, "appKey": "8f8502d7347c4bc1a5ad30f669b66f56", "appName": "基建管理应用",
     "layerAlias": "工程红线图层", "state": 0},
]

ORGANIZATIONS = [
    ("ORG-XM", "厦门市供电公司", (117.88, 24.42, 118.32, 24.83)),
    ("ORG-TA", "同安区供电中心", (118.02, 24.61, 118.25, 24.82)),
]

PROJECTS = [
    {"projectId": "BUILD-2026-001", "projectName": "厦门同安输变电工程", "status": "CONSTRUCTION",
     "region": "同安区", "models": [
         {"modelId": "MODEL-001-A", "modelName": "变电站主体模型", "modelType": "3DTILES",
          "serviceUrl": "/models/build-2026-001/station/tileset.json"},
         {"modelId": "MODEL-001-B", "modelName": "线路走廊模型", "modelType": "3DTILES",
          "serviceUrl": "/models/build-2026-001/line/tileset.json"}]},
    {"projectId": "BUILD-2026-002", "projectName": "厦门翔安变电站扩建工程", "status": "PLANNING",
     "region": "翔安区", "models": [
         {"modelId": "MODEL-002-A", "modelName": "扩建区模型", "modelType": "3DTILES",
          "serviceUrl": "/models/build-2026-002/tileset.json"}]},
    {"projectId": "BUILD-2025-018", "projectName": "同安配网改造工程", "status": "COMPLETED",
     "region": "同安区", "models": [
         {"modelId": "MODEL-018-A", "modelName": "配网改造模型", "modelType": "BIM",
          "serviceUrl": "/models/build-2025-018/model.json"}]},
]


def calculate(operation: str, left: str | float, right: str | float) -> dict[str, Any]:
    operations = {"ADD": ("+", lambda a, b: a + b), "SUBTRACT": ("-", lambda a, b: a - b),
                  "MULTIPLY": ("*", lambda a, b: a * b)}
    try:
        a, b = Decimal(str(left)), Decimal(str(right))
        if operation == "DIVIDE":
            if b == 0:
                raise ValueError("除数不能为零")
            with localcontext() as context:
                context.prec = 34
                value = a / b
            symbol = "/"
        elif operation in operations:
            symbol, fn = operations[operation]
            value = fn(a, b)
        else:
            raise ValueError("operation 只能是 ADD、SUBTRACT、MULTIPLY 或 DIVIDE")
    except (InvalidOperation, DivisionByZero) as exc:
        raise ValueError("操作数必须是有效数字") from exc
    value = value.normalize() if value else Decimal(0)
    return {"operation": operation, "left": a, "right": b,
            "expression": f"{a} {symbol} {b}", "result": value}


def _result(status: str, action: str | None = None, params: Any = None,
            candidates: list[Any] | None = None, calls: list[Any] | None = None) -> dict[str, Any]:
    messages = {"COMPLETED": "操作已完成", "NOT_FOUND": "未找到匹配结果",
                "NEED_CONFIRMATION": "找到多个候选结果，请先确认目标"}
    return {"status": status, "action": action, "actionParams": params,
            "candidates": candidates or [], "endpointCalls": calls or [], "message": messages[status]}


def locate_equipment(keyword: str) -> dict[str, Any]:
    if not keyword or not keyword.strip():
        raise ValueError("设备关键字不能为空")
    query = keyword.strip().casefold()
    matches = [(item, voltage, geometry) for item, voltage, geometry in EQUIPMENT
               if query in item["name"].casefold() or query in (item["oid"], item["deviceId"].casefold())]
    calls = [{"method": "POST", "endpoint": "/datasearchservice/equipment/search",
              "parameters": {"keyword": keyword.strip(), "keywordType": 4, "pageNum": 1, "pageSize": 20}}]
    if not matches:
        return _result("NOT_FOUND", calls=calls)
    if len(matches) > 1:
        return _result("NEED_CONFIRMATION", candidates=[item for item, _, _ in matches], calls=calls)
    item, voltage, geometry = matches[0]
    calls.append({"method": "GET", "endpoint": f"/queryservice/psrquery/object/{item['typeId']}/{item['oid']}",
                  "parameters": {"iscodetsf": False, "isterminal": False, "versionid": "0",
                                 "cstype": "lonlat", "isGeojsonFormat": True}})
    params = {"equipment": item, "voltageLevel": voltage, "geometry": geometry,
              "icon": "substation" if geometry["type"] == "Point" else "power-line", "highlight": True}
    return _result("COMPLETED", "LOCATE_EQUIPMENT", params, calls=calls)


def view_hosted_layer(application_name: str, layer_name: str) -> dict[str, Any]:
    if not application_name or not application_name.strip():
        raise ValueError("应用名称不能为空")
    if not layer_name or not layer_name.strip():
        raise ValueError("图层名称不能为空")
    app, layer = application_name.strip().casefold(), layer_name.strip().casefold()
    matches = [item for item in LAYERS if app in item["appName"].casefold()
               and layer in item["layerAlias"].casefold()]
    calls = [
        {"method": "GET", "endpoint": "/authorityservice/baseservice/getapps",
         "parameters": {"appName": application_name.strip()}},
        {"method": "POST", "endpoint": "/metadataservice/datatype/list",
         "parameters": {"appName": application_name.strip(), "layerAlias": layer_name.strip(),
                        "queryType": 3, "page": 1, "size": 50}},
    ]
    if not matches:
        return _result("NOT_FOUND", calls=calls)
    if len(matches) > 1:
        return _result("NEED_CONFIRMATION", candidates=matches, calls=calls)
    return _result("COMPLETED", "LOAD_HOSTED_LAYER",
                   {"layer": matches[0], "sceneMode": "3D", "visible": True}, calls=calls)


def _polygon(bounds: tuple[float, float, float, float]) -> dict[str, Any]:
    x1, y1, x2, y2 = bounds
    return {"type": "Polygon", "coordinates": [[[x1, y1], [x2, y1], [x2, y2],
                                                  [x1, y2], [x1, y1]]]}


def draw_geometry_region(target: str, buffer_distance_meters: float) -> dict[str, Any]:
    if not target or not target.strip():
        raise ValueError("目标名称不能为空")
    if not 0 <= buffer_distance_meters <= 100_000:
        raise ValueError("缓冲距离必须在0到100000米之间")
    target = target.strip()
    if buffer_distance_meters == 0:
        matches = [org for org_id, name, _ in ORGANIZATIONS
                   if target.casefold() in name.casefold() or org_id.casefold() == target.casefold()
                   for org in [(org_id, name)]]
        calls = [{"method": "GET", "endpoint": "/metadataservice/organization/catalog",
                  "parameters": {"keyword": target}}]
        if not matches:
            return _result("NOT_FOUND", calls=calls)
        if len(matches) > 1:
            return _result("NEED_CONFIRMATION", candidates=[
                {"id": org_id, "typeId": "ORGANIZATION", "name": name} for org_id, name in matches], calls=calls)
        org_id, name = matches[0]
        bounds = next(bound for oid, org_name, bound in ORGANIZATIONS if oid == org_id)
        calls.append({"method": "POST", "endpoint": "/metadataservice/organization/jurisdiction",
                      "parameters": {"iscIds": [org_id], "cstype": "lonlat", "isDilution": False}})
        params = {"mode": "ORGANIZATION_BOUNDARY", "name": name, "geometry": _polygon(bounds),
                  "bufferDistanceMeters": 0, "strokeColor": "#2F80ED",
                  "fillColor": "rgba(47,128,237,0.25)"}
        return _result("COMPLETED", "DRAW_REGION", params, calls=calls)

    matches = [(item, voltage, geometry) for item, voltage, geometry in EQUIPMENT
               if target.casefold() in item["name"].casefold() or target.casefold() == item["oid"].casefold()]
    search = {"method": "POST", "endpoint": "/datasearchservice/equipment/search",
              "parameters": {"keyword": target, "keywordType": 4, "pageNum": 1, "pageSize": 20}}
    if not matches:
        return _result("NOT_FOUND", calls=[search])
    if len(matches) > 1:
        return _result("NEED_CONFIRMATION", candidates=[
            {"id": item["oid"], "typeId": item["typeId"], "name": item["name"]}
            for item, _, _ in matches], calls=[search])
    item, _, geometry = matches[0]
    coords = geometry["coordinates"]
    points = [coords] if geometry["type"] == "Point" else coords
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    delta = buffer_distance_meters / 111_000
    buffered = _polygon((min(xs) - delta, min(ys) - delta, max(xs) + delta, max(ys) + delta))
    calls = [search,
             {"method": "GET", "endpoint": f"/queryservice/psrquery/object/{item['typeId']}/{item['oid']}",
              "parameters": {"cstype": "lonlat", "isGeojsonFormat": True}},
             {"method": "POST", "endpoint": "/mapservice/spatial/buffer",
              "parameters": {"geometry": [geometry], "distance": buffer_distance_meters}}]
    params = {"mode": "EQUIPMENT_BUFFER", "name": item["name"], "geometry": buffered,
              "bufferDistanceMeters": buffer_distance_meters, "strokeColor": "#F2994A",
              "fillColor": "rgba(242,153,74,0.25)"}
    return _result("COMPLETED", "DRAW_REGION", params, calls=calls)


def browse_construction_project(project_name_or_id: str) -> dict[str, Any]:
    if not project_name_or_id or not project_name_or_id.strip():
        raise ValueError("工程名称或ID不能为空")
    query = project_name_or_id.strip().casefold()
    matches = [item for item in PROJECTS if item["projectId"].casefold() == query
               or query in item["projectName"].casefold()]
    calls = [{"method": "POST", "endpoint": "/epgis3d/swgis/build/getBuildServiceList",
              "parameters": {"keyword": project_name_or_id.strip(), "pageNum": 1, "pageSize": 20}}]
    candidates = [{key: item[key] for key in ("projectId", "projectName", "status", "region")}
                  for item in matches]
    if not matches:
        return _result("NOT_FOUND", calls=calls)
    if len(matches) > 1:
        return _result("NEED_CONFIRMATION", candidates=candidates, calls=calls)
    item = matches[0]
    params = {"project": candidates[0], "models": item["models"],
              "defaultModel": item["models"][0] if item["models"] else None,
              "autoLoadDefaultModel": True}
    return _result("COMPLETED", "SHOW_CONSTRUCTION_PROJECT", params, calls=calls)
