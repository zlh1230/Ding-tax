from dataclasses import dataclass

from etax.browser import AttachedEtaxBrowser, EtaxBlocked
from etax.mappings import resolve_invoice_type
from etax.pages.blue_invoice_home import BlueInvoiceHome
from etax.pages.invoice_form import InvoiceForm
from etax.pages.invoice_type_dialog import InvoiceTypeDialog


@dataclass(frozen=True)
class WorkflowResult:
    stopped_before_issue: bool = True


class EtaxInvoiceWorkflow:
    """Deterministic ETax entry workflow; it has no issuance operation."""

    def __init__(self, browser: AttachedEtaxBrowser):
        self.browser = browser

    def run(self, job) -> WorkflowResult:
        if len(job.line_items) != 1:
            raise EtaxBlocked("UNSUPPORTED_LINE_ITEM_COUNT")
        driver = self.browser.normalize_start_state()
        form = InvoiceForm(driver)
        BlueInvoiceHome(driver).open_invoice()
        InvoiceTypeDialog(driver).choose(resolve_invoice_type(job.invoice_type))
        form.root()
        line = job.line_items[0]
        form.fill_buyer(job.buyer_name)
        form.configure_seller()
        form.select_project(line.item_name)
        form.fill_amount(job.requested_total_amount)
        form.validate(job.requested_total_amount)
        return WorkflowResult()
