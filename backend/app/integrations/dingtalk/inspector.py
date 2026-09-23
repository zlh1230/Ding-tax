import json
from decimal import Decimal, InvalidOperation

SAFE_SELECT_LABELS = {"是否第一次开票", "票款情况", "抬头类型", "开票类型"}
SENSITIVE_LABELS = {"收款公司", "抬头名称", "公司税号", "公司开户行", "开户行账号", "公司地址", "公司电话", "备注", "开票项目"}


def _masked(value: str) -> str:
    return f"{value[:3]}***{value[-3:]}" if len(value) > 6 else "***"


def _value_present(component: dict) -> bool:
    return component.get("value") not in (None, "", [], {})


def _safe_select_value(component: dict) -> str | None:
    if component.get("name") not in SAFE_SELECT_LABELS:
        return None
    return component.get("value") if isinstance(component.get("value"), str) else None


def _table_structure(component: dict) -> dict:
    raw = component.get("value")
    try:
        rows = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return {"valid": False, "rows": 0, "columns": [], "amount_decimal_safe": False, "quantity_types": []}
    if not isinstance(rows, list):
        return {"valid": False, "rows": 0, "columns": [], "amount_decimal_safe": False, "quantity_types": []}
    columns, quantity_types, amount_safe = set(), set(), True
    for row in rows:
        values = row.get("rowValue", []) if isinstance(row, dict) else []
        if not isinstance(values, list):
            return {"valid": False, "rows": len(rows), "columns": sorted(columns), "amount_decimal_safe": False, "quantity_types": sorted(quantity_types)}
        for cell in values:
            label = cell.get("label") if isinstance(cell, dict) else None
            if not label:
                continue
            columns.add(label)
            if label.startswith("金额"):
                try:
                    Decimal(str(cell.get("value")))
                except (InvalidOperation, ValueError):
                    amount_safe = False
            if label == "数量":
                value = str(cell.get("value"))
                try:
                    Decimal(value)
                    quantity_types.add("decimal")
                except InvalidOperation:
                    quantity_types.add("text")
    return {"valid": True, "rows": len(rows), "columns": sorted(columns), "amount_decimal_safe": amount_safe, "quantity_types": sorted(quantity_types)}


def inspect_approval(instance_id: str, detail: dict) -> dict:
    result = detail.get("result", {})
    components = result.get("formComponentValues", [])
    fields, table = [], None
    for component in components:
        name = component.get("name", "")
        field = {"label": name, "component_type": component.get("componentType", ""), "present": _value_present(component)}
        safe_value = _safe_select_value(component)
        if safe_value is not None:
            field["safe_select_value"] = safe_value
        fields.append(field)
        if name == "开票内容明细":
            table = _table_structure(component)
    return {"process_instance_id": _masked(instance_id), "status": result.get("status"), "result": result.get("result"), "fields": fields, "table": table}


def aggregate_inspections(inspections: list[dict]) -> dict:
    field_counts, select_values, title_rules = {}, {}, {}
    tables = [item["table"] for item in inspections if item["table"]]
    for item in inspections:
        by_label = {field["label"]: field for field in item["fields"]}
        title_type = by_label.get("抬头类型", {}).get("safe_select_value")
        if title_type:
            rule = title_rules.setdefault(title_type, {"samples": 0, "抬头名称": 0, "公司税号": 0, "公司开户行": 0, "开户行账号": 0, "公司地址": 0, "公司电话": 0})
            rule["samples"] += 1
            for label in tuple(rule)[1:]:
                rule[label] += bool(by_label.get(label, {}).get("present"))
        for field in item["fields"]:
            count = field_counts.setdefault(field["label"], {"component_types": set(), "present": 0, "absent": 0})
            count["component_types"].add(field["component_type"])
            count["present" if field["present"] else "absent"] += 1
            if "safe_select_value" in field:
                select_values.setdefault(field["label"], set()).add(field["safe_select_value"])
    return {"instances": len(inspections), "fields": {label: {"component_types": sorted(value["component_types"]), "present": value["present"], "absent": value["absent"]} for label, value in field_counts.items()}, "safe_select_values": {label: sorted(values) for label, values in select_values.items()}, "buyer_rules": title_rules, "table": {"min_rows": min((item["rows"] for item in tables), default=0), "max_rows": max((item["rows"] for item in tables), default=0), "columns": sorted({column for item in tables for column in item["columns"]}), "amount_decimal_safe": all(item["amount_decimal_safe"] for item in tables), "quantity_types": sorted({kind for item in tables for kind in item["quantity_types"]}), "valid": all(item["valid"] for item in tables)}}
