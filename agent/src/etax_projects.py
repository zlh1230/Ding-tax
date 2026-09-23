"""Explicit DingTalk invoice-content to ETax project mapping."""


PROJECT_ALLOWLIST = frozenset({
    "审核费", "证书费", "*鉴证咨询服务*证书工本费", "证书工本费", "56005评价费",
    "创新管理体系认证费", "创新管理体系年度确认费", "认证服务费", "认证费", "监督审核费",
})

PROJECT_ALIASES = {
    "审核": "审核费", "审核费": "审核费",
    "监督审核": "监督审核费", "监督审核费": "监督审核费",
    "证书": "证书费", "证书费": "证书费", "证书工本费": "证书工本费",
    "认证服务费": "认证服务费", "认证费": "认证费", "56005评价费": "56005评价费",
}


def resolve_project(item_name: str) -> str:
    try:
        return PROJECT_ALIASES[item_name]
    except KeyError as error:
        raise ValueError("UNSUPPORTED_INVOICE_PROJECT") from error
