from etax_projects import PROJECT_ALLOWLIST, PROJECT_ALIASES, resolve_project
from etax.browser import EtaxBlocked


INVOICE_TYPE_LABELS = {
    "SPECIAL": "增值税专用发票",
    "专票": "增值税专用发票",
    "NORMAL": "普通发票",
    "普票": "普通发票",
}
SELLER_PHONE = "021-65152517"


def resolve_invoice_type(value: str) -> str:
    try:
        return INVOICE_TYPE_LABELS[value]
    except KeyError as error:
        raise EtaxBlocked("UNSUPPORTED_INVOICE_TYPE") from error


__all__ = ["INVOICE_TYPE_LABELS", "PROJECT_ALIASES", "PROJECT_ALLOWLIST", "SELLER_PHONE", "resolve_invoice_type", "resolve_project"]
