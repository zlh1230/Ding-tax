from app.integrations.dingtalk.inspector import aggregate_inspections, inspect_approval


def test_inspector_keeps_values_out_of_report():
    detail = {"result": {"status": "COMPLETED", "result": "agree", "formComponentValues": [{"name": "抬头类型", "componentType": "DDSelectField", "value": "企业"}, {"name": "抬头名称", "componentType": "TextField", "value": "private-name"}, {"name": "开票内容明细", "componentType": "TableField", "value": '[{"rowNumber":"1","rowValue":[{"label":"开票内容","value":"private-item"},{"label":"数量","value":"2"},{"label":"金额（元）","value":"1.20"}]}]'}]}}
    report = inspect_approval("abcdefghi", detail)
    assert report["process_instance_id"] == "abc***ghi"
    assert "private-name" not in str(report)
    assert "private-item" not in str(report)
    aggregate = aggregate_inspections([report])
    assert aggregate["table"] == {"min_rows": 1, "max_rows": 1, "columns": ["开票内容", "数量", "金额（元）"], "amount_decimal_safe": True, "quantity_types": ["decimal"], "valid": True}
