from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from poc_etax import PlaywrightTimeoutError, PocBlocked, attached_context, chrome_executable, current_phase, enter_dpp_invoice_form, exact_buyer_match, fetch_job, live_tax_page, login_gateway_error, navigate_to_invoice_entry, open_invoice_page, unique_visible, validate_job


def payload(**changes):
    value = {"id": 1, "status": "PENDING", "buyer_name": "Buyer", "invoice_type": "SPECIAL", "requested_total_amount": "3.30", "remark": None, "line_items": [{"line_no": 1, "item_name": "Service", "quantity": "2", "amount": "3.30"}]}
    return {**value, **changes}


def test_decimal_total_and_exact_buyer_match():
    job = validate_job(payload(line_items=[{"line_no": 1, "item_name": "A", "quantity": "1", "amount": "1.10"}, {"line_no": 2, "item_name": "B", "quantity": "2", "amount": "2.20"}]))
    assert job.requested_total_amount == Decimal("3.30")
    assert job.line_items[0].line_no == 1
    assert exact_buyer_match("Buyer", ["Other", "Buyer"]) == "Buyer"


@pytest.mark.parametrize("invoice_type", ["SPECIAL", "NORMAL"])
def test_canonical_invoice_types_are_accepted(invoice_type):
    assert validate_job(payload(invoice_type=invoice_type)).invoice_type == invoice_type


@pytest.mark.parametrize("data, code", [
    (payload(buyer_name=""), "BUYER_MATCH_REQUIRED"),
    (payload(invoice_type="普通票"), "UNSUPPORTED_INVOICE_TYPE"),
    (payload(line_items=[]), "MISSING_REQUIRED_LINE_ITEM_DATA"),
    (payload(requested_total_amount="3.31"), "AMOUNT_MISMATCH"),
])
def test_invalid_jobs_fail_closed(data, code):
    with pytest.raises(PocBlocked, match=code):
        validate_job(data)


def test_buyer_matching_rejects_missing_or_ambiguous_matches():
    for candidates in ([], ["Buyer", "Buyer"]):
        with pytest.raises(PocBlocked, match="BUYER_MATCH_REQUIRED"):
            exact_buyer_match("Buyer", candidates)


def test_backend_line_items_reach_canonical_validation(monkeypatch):
    response = {"id": 123, "status": "PENDING", "buyer_name": "测试买方", "invoice_type": "SPECIAL", "requested_total_amount": "100.00", "remark": None, "line_items": [{"line_no": 1, "item_name": "测试服务", "quantity": "1.0000", "amount": "100.00"}]}

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    monkeypatch.setattr("poc_etax.urlopen", lambda *_args, **_kwargs: FakeResponse(__import__("json").dumps(response).encode()))
    job = fetch_job(123)
    assert len(job.line_items) == 1
    assert job.line_items[0].line_no == 1
    assert job.line_items[0].quantity == Decimal("1.0000")
    assert job.line_items[0].amount == Decimal("100.00")


def test_post_login_marker_must_be_unique():
    class Locator:
        first = None

        def __init__(self, count):
            self.first = self
            self._count = count

        def wait_for(self, **_kwargs):
            pass

        def count(self):
            return self._count

        def all(self):
            return [self] * self._count

        def is_visible(self):
            return True

    assert unique_visible(Locator(1), "MARKER_NOT_UNIQUE")
    with pytest.raises(PocBlocked, match="NAVIGATION_SELECTOR_NOT_UNIQUE"):
        unique_visible(Locator(2), "MARKER_NOT_UNIQUE")


def test_explicit_chrome_path_must_exist(monkeypatch, tmp_path):
    chrome = tmp_path / "chrome.exe"
    chrome.touch()
    monkeypatch.setenv("ETAX_CHROME_PATH", str(chrome))
    assert chrome_executable() == chrome


def test_login_phase_and_gateway_error_classification():
    page = type("Page", (), {"url": "https://etax.shanghai.chinatax.gov.cn:8443/loginb/"})()
    assert current_phase(page) == "WAITING_FOR_MANUAL_LOGIN"
    assert login_gateway_error(["GET tpass.shanghai.chinatax.gov.cn:8443/api/v1.0/auth/oauth2/login -> 504"])


def test_attach_mode_reuses_existing_cdp_context(monkeypatch):
    context = object()
    browser = type("Browser", (), {"contexts": [context]})()
    chromium = type("Chromium", (), {"connect_over_cdp": lambda self, url: browser})()
    playwright = type("Playwright", (), {"chromium": chromium})()
    monkeypatch.setenv("ETAX_CDP_URL", "http://127.0.0.1:9222")
    assert attached_context(playwright) is context


def test_existing_logged_in_and_dpp_pages_are_reused():
    home = FakePage("Home")
    home.url = "https://etax.shanghai.chinatax.gov.cn:8443/home"
    assert live_tax_page(FakeContext([home]), "发票业务") == (home, "ETAX_HOME")
    dpp = FakePage("Invoice", has_blue_invoice=True)
    dpp.url = "https://dppt.shanghai.chinatax.gov.cn/invoice-business"
    assert live_tax_page(FakeContext([dpp]), "发票业务") == (dpp, "DPP")


def test_invoice_business_stage_does_not_require_home():
    page = FakePage("Invoice Business", has_blue_invoice=True)
    page.url = "https://etax.shanghai.chinatax.gov.cn:8443/invoice-business"
    assert live_tax_page(FakeContext([page]), "发票业务") == (page, "INVOICE_BUSINESS")


def test_dpp_immediate_invoice_enters_form_without_final_submit():
    page = FakePage("Invoice Entry", has_blue_invoice=True)
    assert enter_dpp_invoice_form(page) == "Invoice Entry"
    assert page.clicked == ["蓝字发票开具", "立即开票"]


def test_login_pages_require_human_login():
    class Locator:
        first = None

        def __init__(self):
            self.first = self

        def count(self):
            return 0

        def is_visible(self):
            return False

    login = type("Login", (), {"url": "https://etax.shanghai.chinatax.gov.cn:8443/loginb/", "get_by_text": lambda *_: Locator()})()
    with pytest.raises(PocBlocked, match="ETAX_LOGIN_REQUIRED"):
        live_tax_page(FakeContext([login]), "发票业务")


class FakeTimeout(Exception):
    pass


class FakeLocator:
    def __init__(self, page, label):
        self.first = self
        self.page = page
        self.label = label

    def wait_for(self, **_kwargs):
        pass

    def count(self):
        return 1

    def all(self):
        return [self]

    def is_visible(self):
        return self.label != "蓝字发票开具" or self.page.has_blue_invoice

    def click(self):
        self.page.clicked.append(self.label)
        if self.label == "发票业务" and self.page.navigate_to_invoice:
            self.page.has_blue_invoice = True


class FakePage:
    def __init__(self, title, *, has_blue_invoice=False, navigate_to_invoice=False):
        self._title = title
        self.url = f"https://example.test/{title.lower().replace(' ', '-') }"
        self.has_blue_invoice = has_blue_invoice
        self.navigate_to_invoice = navigate_to_invoice
        self.clicked = []

    def get_by_text(self, label, exact):
        assert exact is True
        return FakeLocator(self, label)

    def wait_for_load_state(self, state):
        assert state == "domcontentloaded"

    def title(self):
        return self._title


class FakePageEvent:
    def __init__(self, context):
        self.context = context
        self.value = context.new_page

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.context.new_page is None:
            raise FakeTimeout()
        self.context.pages.append(self.context.new_page)
        return False


class FakeContext:
    def __init__(self, pages, new_page=None):
        self.pages = pages
        self.new_page = new_page

    def expect_page(self, timeout):
        assert timeout == 5_000
        return FakePageEvent(self)


def test_invoice_navigation_uses_new_page_after_invoice_business_click(monkeypatch):
    monkeypatch.setattr("poc_etax.PlaywrightTimeoutError", FakeTimeout)
    homepage = FakePage("Home")
    invoice_page = FakePage("Invoice Entry", has_blue_invoice=True)
    captured_page = open_invoice_page(FakeContext([homepage], invoice_page), homepage, "发票业务")
    assert captured_page is invoice_page
    assert homepage.clicked == ["发票业务"]
    assert navigate_to_invoice_entry(captured_page) == "Invoice Entry"
    assert invoice_page.clicked == ["蓝字发票开具", "立即开票"]


def test_invoice_navigation_uses_current_page_when_it_navigates(monkeypatch):
    monkeypatch.setattr("poc_etax.PlaywrightTimeoutError", FakeTimeout)
    homepage = FakePage("Home", navigate_to_invoice=True)
    assert open_invoice_page(FakeContext([homepage]), homepage, "发票业务") is homepage


def test_invoice_navigation_reuses_existing_invoice_page(monkeypatch):
    monkeypatch.setattr("poc_etax.PlaywrightTimeoutError", FakeTimeout)
    homepage = FakePage("Home")
    invoice_page = FakePage("Invoice Business", has_blue_invoice=True)
    assert open_invoice_page(FakeContext([homepage, invoice_page]), homepage, "发票业务") is invoice_page


def test_invoice_navigation_blocks_when_no_page_has_blue_invoice(monkeypatch):
    monkeypatch.setattr("poc_etax.PlaywrightTimeoutError", FakeTimeout)
    homepage = FakePage("Home")
    with pytest.raises(PocBlocked, match="ETAX_INVOICE_BUSINESS_PAGE_NOT_RESOLVED"):
        open_invoice_page(FakeContext([homepage]), homepage, "发票业务")


def test_invoice_navigation_blocks_for_multiple_invoice_pages(monkeypatch):
    monkeypatch.setattr("poc_etax.PlaywrightTimeoutError", FakeTimeout)
    homepage = FakePage("Home")
    first = FakePage("Invoice Business A", has_blue_invoice=True)
    second = FakePage("Invoice Business B", has_blue_invoice=True)
    with pytest.raises(PocBlocked, match="ETAX_INVOICE_BUSINESS_PAGE_NOT_RESOLVED"):
        open_invoice_page(FakeContext([homepage, first, second]), homepage, "发票业务")


def test_unique_visible_selects_one_visible_node_among_49():
    class Node:
        def __init__(self, visible):
            self.visible = visible

        def is_visible(self):
            return self.visible

    class Locator:
        def __init__(self, nodes):
            self.nodes = nodes

        def all(self):
            return self.nodes

    target = Node(True)
    assert unique_visible(Locator([Node(False) for _ in range(48)] + [target]), "TEST", timeout=1) is target


def test_unique_visible_rejects_zero_or_multiple_visible_nodes():
    class Node:
        def __init__(self, visible): self.visible = visible
        def is_visible(self): return self.visible

    class Locator:
        def __init__(self, nodes): self.nodes = nodes
        def all(self): return self.nodes

    with pytest.raises(PlaywrightTimeoutError):
        unique_visible(Locator([Node(False)]), "TEST", timeout=0)
    with pytest.raises(PocBlocked, match="NAVIGATION_SELECTOR_NOT_UNIQUE"):
        unique_visible(Locator([Node(True), Node(True)]), "TEST", timeout=1)
