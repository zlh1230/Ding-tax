from decimal import Decimal
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from etax.browser import AttachedEtaxBrowser, EtaxBlocked
from etax.mappings import PROJECT_ALIASES, PROJECT_ALLOWLIST, resolve_invoice_type, resolve_project
from etax.pages.invoice_form import InvoiceForm
from etax.pages.blue_invoice_home import BlueInvoiceHome
from etax.pages.invoice_type_dialog import InvoiceTypeDialog
from etax.pages.project_dialog import ProjectDialog
from etax.workflow import WorkflowResult


def test_snapshot_markers_cover_all_recorded_states():
    snapshots = Path(__file__).parents[1] / "debug_snapshots"
    markers = {
        "home.html": ("invoice-entrance invoice-home__block", "invoice-entrance-choose"),
    "invoice-type.html": ("t-dialog--default", "t-form-item__fppzDm", "t-select-input"),
        "form.html": ("t-form-item__gmfmc", "t-form-item__xsfdz", "t-form-item__xsfkhh", "xmmc_handle", "amount-tax-form"),
        "project-dialog.html": ("invoice-project__drawer", "t-drawer--open", "t-table__th-xmmc"),
    }
    for filename, required in markers.items():
        source = (snapshots / filename).read_text(encoding="utf-8")
        assert all(marker in source for marker in required)


def test_home_snapshot_has_one_card_and_one_clickable_invoice_action():
    class Node:
        def __init__(self, tag, attrs, parent):
            self.tag, self.attrs, self.parent, self.children, self.text = tag, dict(attrs), parent, [], []
            if parent: parent.children.append(self)
        def content(self):
            return "".join(self.text + [child.content() for child in self.children])
        def walk(self):
            for child in self.children:
                yield child
                yield from child.walk()

    class Tree(HTMLParser):
        def __init__(self):
            super().__init__(); self.root = Node("root", {}, None); self.current = self.root
        def handle_starttag(self, tag, attrs):
            node = Node(tag, attrs, self.current)
            if tag not in {"input", "img", "meta", "link", "br", "path", "svg"}: self.current = node
        def handle_endtag(self, tag):
            node = self.current
            while node.parent and node.tag != tag: node = node.parent
            if node.parent: self.current = node.parent
        def handle_data(self, data): self.current.text.append(data)

    tree = Tree()
    tree.feed((Path(__file__).parents[1] / "debug_snapshots" / "home.html").read_text(encoding="utf-8"))
    nodes = list(tree.root.walk())
    cards = [node for node in nodes if "invoice-entrance" in node.attrs.get("class", "") and "invoice-home__block" in node.attrs.get("class", "")]
    actions = [node for node in nodes if "invoice-entrance-choose" in node.attrs.get("class", "") and "invoice-entrance-choose__content" not in node.attrs.get("class", "") and "立即开票" in "".join(node.content().split())]
    assert BlueInvoiceHome.HOME_CARD
    assert BlueInvoiceHome.INVOICE_ACTION
    assert len(cards) == 1  # HOME_CARD_MATCH_COUNT
    assert len(actions) == 1  # IMMEDIATE_INVOICE_CLICKABLE_MATCH_COUNT


@pytest.mark.parametrize(("source", "target"), [
    ("SPECIAL", "增值税专用发票"),
    ("专票", "增值税专用发票"),
    ("NORMAL", "普通发票"),
    ("普票", "普通发票"),
])
def test_invoice_type_mapping_is_exact(source, target):
    assert resolve_invoice_type(source) == target


def test_unknown_invoice_type_fails_closed():
    with pytest.raises(EtaxBlocked, match="UNSUPPORTED_INVOICE_TYPE"):
        resolve_invoice_type("unknown")


def test_invoice_type_snapshot_has_one_semantic_dialog_select_and_confirm():
    class Node:
        def __init__(self, tag, attrs, parent):
            self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
            if parent:
                parent.children.append(self)
        def walk(self):
            for child in self.children:
                yield child
                yield from child.walk()

    class Tree(HTMLParser):
        def __init__(self):
            super().__init__(); self.root = Node("root", {}, None); self.current = self.root
        def handle_starttag(self, tag, attrs):
            node = Node(tag, attrs, self.current)
            if tag not in {"input", "img", "meta", "link", "br", "path", "svg"}:
                self.current = node
        def handle_endtag(self, tag):
            node = self.current
            while node.parent and node.tag != tag:
                node = node.parent
            if node.parent:
                self.current = node.parent

    tree = Tree()
    tree.feed((Path(__file__).parents[1] / "debug_snapshots" / "invoice-type.html").read_text(encoding="utf-8"))
    fields = [node for node in tree.root.walk() if "t-form-item__fppzDm" in node.attrs.get("class", "")]
    assert len(fields) == 1
    dialog = fields[0].parent
    while dialog and "t-dialog" not in dialog.attrs.get("class", "").split():
        dialog = dialog.parent
    assert dialog is not None  # INVOICE_TYPE_DIALOG_SELECTOR count
    assert len([node for node in fields[0].walk() if {"t-select-input", "t-select"}.issubset(node.attrs.get("class", "").split())]) == 1
    assert len([node for node in dialog.walk() if "t-dialog__confirm" in node.attrs.get("class", "").split()]) == 1
    assert InvoiceTypeDialog.TICKET_FIELD
    assert InvoiceTypeDialog.TICKET_SELECT
    assert InvoiceTypeDialog.CONFIRM


def test_login_state_detection_is_conservative():
    assert AttachedEtaxBrowser.is_authenticated_tax_url("https://dppt.shanghai.chinatax.gov.cn:8443/blue-invoice-makeout")
    assert AttachedEtaxBrowser.is_authenticated_tax_url("https://etax.shanghai.chinatax.gov.cn:8443/home")
    assert not AttachedEtaxBrowser.is_authenticated_tax_url("https://etax.shanghai.chinatax.gov.cn:8443/loginb/")
    assert not AttachedEtaxBrowser.is_authenticated_tax_url("https://tpass.shanghai.chinatax.gov.cn:8443/login")


def test_home_snapshot_structure_count_is_stable():
    source = (Path(__file__).parents[1] / "debug_snapshots" / "home.html").read_text(encoding="utf-8")
    assert AttachedEtaxBrowser._class_count(source, "quick-entrance") >= 1
    assert AttachedEtaxBrowser._class_count(source, "invoice-home__block") >= 1


def test_buyer_normalization_is_exact_not_fuzzy():
    assert InvoiceForm.normalized(" A  B ") == "AB"
    assert InvoiceForm.normalized("AB") == "AB"
    assert InvoiceForm.normalized("AC") != InvoiceForm.normalized("AB")


def test_buyer_exact_match_requires_exactly_one_visible_company_name():
    class Candidate:
        def __init__(self, text, tag_name="div", visible=True, content=None): self.text, self.tag_name, self.visible, self.content = text, tag_name, visible, content or text
        def get_attribute(self, name): return self.content if name == "textContent" else ""

    target = Candidate("测试公司")
    assert InvoiceForm.exact_buyer_match([Candidate("其他公司"), target], "测试公司") is target
    assert InvoiceForm.exact_buyer_match([Candidate("测试公司", "li")], "测试公司").tag_name == "li"
    assert InvoiceForm.exact_buyer_match([Candidate("", "div", False, "测试公司")], "测试公司")
    with pytest.raises(EtaxBlocked, match="BUYER_EXACT_MATCH_NOT_FOUND"):
        InvoiceForm.exact_buyer_match([Candidate("其他公司")], "测试公司")
    with pytest.raises(EtaxBlocked, match="BUYER_EXACT_MATCH_NOT_UNIQUE"):
        InvoiceForm.exact_buyer_match([target, Candidate("测试公司")], "测试公司")
    assert InvoiceForm.BUYER_POPUP == ".t-popup"
    assert InvoiceForm.BUYER_DATA_READY == ".t-popup .auto-complete__list .auto-complete__item"
    assert InvoiceForm.BUYER_OPTION == ".auto-complete__item"
    assert InvoiceForm.BUYER_TAX_ID == ".t-form-item__gmfnsrsbh input.t-input__inner"


def test_buyer_popup_is_selected_by_its_exact_company_option_not_global_popup_count():
    class Candidate:
        def __init__(self, text): self.text = text

    unrelated, buyer_popup = object(), object()
    candidate = Candidate("测试公司")
    assert InvoiceForm.buyer_popup_with_exact_match(
        [(unrelated, [Candidate("其他公司")]), (buyer_popup, [candidate])], "测试公司"
    ) == (buyer_popup, candidate)
    with pytest.raises(EtaxBlocked, match="BUYER_POPUP_AMBIGUOUS"):
        InvoiceForm.buyer_popup_with_exact_match(
            [(object(), [Candidate("测试公司")]), (object(), [Candidate("测试公司")])], "测试公司"
        )


def test_seller_phone_option_must_be_the_one_exact_fixed_number():
    class Option:
        def __init__(self, text): self.text = text

    target = Option("021-65152517")
    assert InvoiceForm.exact_seller_phone_option([Option("other"), target]) is target
    with pytest.raises(EtaxBlocked, match="SELLER_PHONE_OPTION_NOT_FOUND"):
        InvoiceForm.exact_seller_phone_option([Option("other")])
    with pytest.raises(EtaxBlocked, match="SELLER_PHONE_OPTION_NOT_UNIQUE"):
        InvoiceForm.exact_seller_phone_option([target, Option("021-65152517")])


def test_buyer_autocomplete_contract_uses_data_before_popup_visibility():
    source = __import__("inspect").getsource(InvoiceForm.fill_buyer)
    assert "BUYER_DATA_READY" in source
    assert "ActionChains(self.driver).move_to_element(control).click().perform()" in source
    assert "BUYER_AUTOCOMPLETE_DATA_TIMEOUT" in source
    assert "buyer_popup_with_exact_match" in source


def test_project_mapping_and_decimal_amount_are_exact():
    assert resolve_project("审核") == "审核费"
    assert format(Decimal("100.00"), "f") == "100.00"
    with pytest.raises(ValueError, match="UNSUPPORTED_INVOICE_PROJECT"):
        resolve_project("unmapped")


def test_all_snapshot_derived_form_and_project_controls_are_unique():
    snapshots = Path(__file__).parents[1] / "debug_snapshots"
    form = (snapshots / "form.html").read_text(encoding="utf-8")
    project = (snapshots / "project-dialog.html").read_text(encoding="utf-8")
    for marker in (
        "t-form-item__gmfmc", "t-form-item__xsflxdh", "t-form-item__xsfdz",
        "t-form-item__xsfkhh", "xmmc_handle",
    ):
        assert form.count(marker) == 1
    assert 'class="blue-invoice"' in form
    assert 'class="amount-tax-form"' in form
    assert 'class="total-amount"' in form
    assert project.count("invoice-project__drawer") == 1
    assert project.count("t-table__th-xmmc") == 1


def test_all_project_aliases_target_the_confirmed_allowlist():
    assert len(PROJECT_ALLOWLIST) == 10
    assert set(PROJECT_ALIASES.values()) <= PROJECT_ALLOWLIST
    assert all(resolve_project(alias) == target for alias, target in PROJECT_ALIASES.items())
    snapshot = (Path(__file__).parents[1] / "debug_snapshots" / "project-dialog.html").read_text(encoding="utf-8")
    assert all(project in snapshot for project in PROJECT_ALLOWLIST)


def test_checkbox_preserves_checked_and_checks_unchecked():
    class Label:
        def __init__(self, checked): self.checked, self.clicks = checked, 0
        def get_attribute(self, name): return "t-checkbox t-is-checked" if name == "class" and self.checked else "t-checkbox"
        def click(self): self.clicks += 1; self.checked = True

    checked, unchecked = Label(True), Label(False)
    form = InvoiceForm(None)
    form.ensure_checked(checked, "ADDRESS")
    form.ensure_checked(unchecked, "BANK")
    assert checked.clicks == 0
    assert unchecked.clicks == 1
    assert form.is_checked(checked) and form.is_checked(unchecked)


def test_exact_project_row_rejects_zero_or_multiple_rows():
    class Cell:
        def __init__(self, text): self.text = text
        def get_attribute(self, name): return self.text if name == "textContent" else ""

    class Row:
        def __init__(self, project): self.cells = [Cell("1"), Cell(project)]
        def find_elements(self, *_): return self.cells

    row = Row("审核费")
    assert ProjectDialog.exact_row([row], "审核费") is row
    with pytest.raises(EtaxBlocked, match="PROJECT_ROW_NOT_FOUND"):
        ProjectDialog.exact_row([], "审核费")
    with pytest.raises(EtaxBlocked, match="PROJECT_ROW_NOT_UNIQUE"):
        ProjectDialog.exact_row([row, Row("审核费")], "审核费")


def test_project_row_selection_is_exact_and_row_scoped():
    class Cell:
        def __init__(self, text): self.text = text
        def get_attribute(self, name): return self.text if name == "textContent" else ""

    class Row:
        def __init__(self, project): self.cells = [Cell("1"), Cell(project)]
        def find_elements(self, *_): return self.cells

    class Action:
        def __init__(self, text): self.text = text

    row = ProjectDialog.exact_row([Row("其他费"), Row("审核费")], "审核费")
    action = Action("选择")
    assert ProjectDialog.project_name(row) == "审核费"
    assert ProjectDialog.exact_select_action([action]) is action
    with pytest.raises(EtaxBlocked, match="PROJECT_SELECT_NOT_FOUND"):
        ProjectDialog.exact_select_action([Action("选择"), Action("选择")])
    assert ProjectDialog.normalized("*生产生活服务*审核费").endswith(ProjectDialog.normalized("审核费"))


def test_project_selection_uses_same_row_span_and_safe_click_fallback():
    import inspect

    source = inspect.getsource(ProjectDialog.select_exact)
    assert ProjectDialog.ROW == "tbody tr"
    assert "project-table__container" not in source
    assert "t-table__empty-row" in source
    assert 'self.SELECT_ACTION' in source
    assert 'row.find_elements' in source
    assert 'action.click()' in source
    assert 'ActionChains(self.driver).move_to_element(action).click().perform()' in source
    assert all(message in source for message in (
        "PROJECT_TARGET_ROW_FOUND",
        "PROJECT_SELECT_SPAN_FOUND",
        "PROJECT_SELECT_CLICKED",
        "PROJECT_DRAWER_CLOSED",
        "PROJECT_AUTOFILL_VALUE",
        "PROJECT_AUTOFILL_CONFIRMED",
    ))


def test_last_known_good_project_flow_uses_all_drawer_rows_without_container_dependency():
    project_names = [
        "审核费", "证书费", "*鉴证咨询服务*证书工本费", "证书工本费", "56005评价费",
        "创新管理体系认证费", "创新管理体系年度确认费", "认证服务费", "认证费", "监督审核费",
    ]

    class Cell:
        def __init__(self, text): self.text = text

    class Action:
        def __init__(self): self.text = "选择"

    class Row:
        def __init__(self, index, project): self.cells = [Cell(str(index)), Cell(project)]
        def find_elements(self, _by, selector):
            if selector == "td":
                return self.cells
            if selector == ProjectDialog.SELECT_ACTION:
                return [Action()]
            return []

    rows = [Row(index, name) for index, name in enumerate(project_names, start=1)]
    target = resolve_project("监督审核")
    matched = ProjectDialog.exact_row(rows, target)
    assert len(rows) == 10
    assert ProjectDialog.project_name(matched) == "监督审核费"
    assert ProjectDialog.exact_select_action(matched.find_elements(By.CSS_SELECTOR, ProjectDialog.SELECT_ACTION)).text == "选择"


def test_project_snapshot_maps_supervision_review_to_tenth_exact_second_cell_row():
    source = (Path(__file__).parents[1] / "debug_snapshots" / "project-dialog.html").read_text(encoding="utf-8")

    def text(markup):
        return ProjectDialog.normalized(unescape(re.sub(r"<[^>]+>", "", markup)))

    rows = [
        row for row in re.findall(r"<tr[^>]*>(.*?)</tr>", source, flags=re.DOTALL)
        if len(re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL)) >= 2
        and "button-text primary-button__text" in row
    ]
    names = [text(re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL)[1]) for row in rows]
    target = resolve_project("监督审核")
    assert target == "监督审核费"
    assert len(rows) == 10
    assert names[9] == target
    assert names.count(target) == 1
    assert text(re.findall(r"<span[^>]*button-text primary-button__text[^>]*>(.*?)</span>", rows[9], flags=re.DOTALL)[0]) == "选择"


def test_total_validation_uses_decimal():
    assert InvoiceForm.parse_total("100.00") == Decimal("100.00")
    assert InvoiceForm.parse_total("￥5,775.00") == Decimal("5775.00")
    assert InvoiceForm.parse_total(" ¥ 5,775.00 ") == Decimal("5775.00")
    with pytest.raises(EtaxBlocked, match="TOTAL_NOT_READABLE"):
        InvoiceForm.parse_total("not-a-total")
    InvoiceForm.assert_total_matches("￥5,775.00", Decimal("5775.00"))
    with pytest.raises(EtaxBlocked, match="TOTAL_MISMATCH"):
        InvoiceForm.assert_total_matches("5774.99", Decimal("5775.00"))


def test_amount_tax_and_total_use_snapshot_header_to_same_row_column_mapping():
    source = (Path(__file__).parents[1] / "debug_snapshots" / "form.html").read_text(encoding="utf-8")
    tables = re.findall(r"<table\b[^>]*>(.*?)</table>", source, flags=re.DOTALL)

    def header_keys(table):
        return re.findall(r'<th\b[^>]*data-colkey="([^"]+)"[^>]*>', table)

    table_keys = [(table, header_keys(table)) for table in tables]
    candidates = [
        (table, keys)
        for table, keys in table_keys
        if all(keys.count(key) == 1 for key in ("je", "slv", "se")) and "<tbody" in table
    ]
    mapped_rows = []
    for table, keys in candidates:
        indices = {key: InvoiceForm.column_index(keys, key) for key in ("je", "slv", "se")}
        tbody = re.search(r"<tbody\b[^>]*>(.*?)</tbody>", table, flags=re.DOTALL)
        if tbody is None:
            continue
        rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", tbody.group(1), flags=re.DOTALL)
        data_rows = [row for row in rows if len(re.findall(r"<td\b", row)) > max(indices.values())]
        if not data_rows:
            continue
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", data_rows[0], flags=re.DOTALL)
        if "blueinvoice-input" in cells[indices["je"]]:
            mapped_rows.append((keys, indices, cells))

    assert len(mapped_rows) == 1  # Only the real data table, never the empty table clone.
    keys, indices, cells = mapped_rows[0]
    assert {keys[index] for index in indices.values()} == {"je", "slv", "se"}
    assert len(set(indices.values())) == 3
    assert "blueinvoice-input" in cells[indices["je"]]
    assert "t-input__inner" in cells[indices["slv"]]
    assert "blueinvoice-input" in cells[indices["se"]]

    import inspect
    column_source = inspect.getsource(InvoiceForm._column_input)
    amount_source = inspect.getsource(InvoiceForm.fill_amount) + inspect.getsource(InvoiceForm._amount_input)
    validation_source = inspect.getsource(InvoiceForm.validate)
    assert 'thead th[data-colkey]' in column_source
    assert 'cells[index]' in column_source
    assert 'execute_script' not in column_source
    assert 'input.t-input.blueinvoice-input' in amount_source
    assert 'Keys.TAB' in amount_source
    assert 'PROJECT_AUTOFILL_NOT_CONFIRMED' in amount_source
    assert 'TAX_RATE_NOT_POPULATED' in validation_source
    assert 'TAX_AMOUNT_NOT_POPULATED' in validation_source
    assert InvoiceForm.TOTAL == ".amount-tax-statistics .amount-tax-form .amount-tax-form__lower"
    assert format(Decimal("5775.00"), "f") == "5775.00"


def test_total_value_uses_the_span_after_the_small_case_total_label_in_snapshot():
    source = (Path(__file__).parents[1] / "debug_snapshots" / "form.html").read_text(encoding="utf-8")
    container = re.search(
        r'<div[^>]*class="amount-tax-form__lower"[^>]*>(.*?)</div>', source, flags=re.DOTALL
    )
    assert container is not None
    span_texts = [
        InvoiceForm.normalized(unescape(text))
        for text in re.findall(r"<span[^>]*>(.*?)</span>", container.group(1), flags=re.DOTALL)
    ]
    assert InvoiceForm.total_value_from_spans(span_texts) == "0.00"
    with pytest.raises(EtaxBlocked, match="TOTAL_NOT_READABLE"):
        InvoiceForm.total_value_from_spans(["价税合计（小写）："])


def test_amount_input_requires_editable_control_and_re_resolves_after_project(monkeypatch):
    class Project:
        def get_attribute(self, name): return "selected" if name == "value" else None
        def get_property(self, name): return "selected" if name == "value" else None

    class Amount:
        def __init__(self): self.keys = []
        def is_displayed(self): return True
        def is_enabled(self): return True
        def get_attribute(self, _name): return None
        def get_property(self, name): return "100.00" if name == "value" else None
        def send_keys(self, *keys): self.keys.append(keys)

    form = InvoiceForm(None)
    amount = Amount()
    form.root = lambda: object()
    project = Project()
    monkeypatch.setattr("etax.pages.invoice_form.visible_unique", lambda *_args: project)
    resolved, keyboard_paths = [], []
    form._amount_input = lambda: (resolved.append(amount) or amount)
    form._send_amount_keys = lambda _control, _project, _text, *, actions: (keyboard_paths.append(actions) or True)

    form.fill_amount(Decimal("100.00"))
    assert resolved == [amount]  # Resolve occurs after project autofill, not before it.
    assert keyboard_paths == [False]
    assert amount.keys == [(Keys.TAB,)]


def test_amount_input_rejects_noneditable_control_and_focus_requires_active_element(monkeypatch):
    class Control:
        def __init__(self, *, enabled=True, readonly=None, disabled=None):
            self.enabled, self.readonly, self.disabled = enabled, readonly, disabled
        def is_displayed(self): return True
        def is_enabled(self): return self.enabled
        def get_attribute(self, name): return {"readonly": self.readonly, "disabled": self.disabled}.get(name)
        def get_property(self, name): return "" if name == "value" else None

    form = InvoiceForm(None)
    editable = Control()
    form._column_input = lambda *_args: editable
    assert form._amount_input() is editable
    form._column_input = lambda *_args: Control(enabled=False)
    with pytest.raises(EtaxBlocked, match="AMOUNT_FILL_FAILED"):
        form._amount_input()

    class Driver:
        class Switch:
            active_element = None
        switch_to = Switch()

    class FocusChain:
        def __init__(self, driver): self.driver, self.control = driver, None
        def move_to_element(self, control): self.control = control; return self
        def click(self): return self
        def perform(self): self.driver.switch_to.active_element = self.control

    driver = Driver()
    focus_form = InvoiceForm(driver)
    monkeypatch.setattr("etax.pages.invoice_form.ActionChains", FocusChain)
    focus_form._focus_amount_input(editable, Control())
    assert driver.switch_to.active_element is editable

    class NoFocusChain(FocusChain):
        def perform(self): pass

    driver.switch_to.active_element = None
    monkeypatch.setattr("etax.pages.invoice_form.ActionChains", NoFocusChain)
    with pytest.raises(EtaxBlocked, match="AMOUNT_FOCUS_FAILED"):
        focus_form._focus_amount_input(editable, Control())


def test_amount_fill_uses_one_retry_for_stale_or_unchanged_value(monkeypatch):
    from selenium.common.exceptions import StaleElementReferenceException

    class Project:
        def get_attribute(self, name): return "selected" if name == "value" else None
        def get_property(self, name): return "selected" if name == "value" else None

    class Amount:
        def get_property(self, name): return "100.00" if name == "value" else None
        def send_keys(self, *_keys): pass

    form = InvoiceForm(None)
    form.root = lambda: object()
    project = Project()
    monkeypatch.setattr("etax.pages.invoice_form.visible_unique", lambda *_args: project)
    controls = [Amount(), Amount()]
    resolved = []
    form._amount_input = lambda: (resolved.append(controls[len(resolved)]) or resolved[-1])
    calls = []

    def send_once_stale_then_fill(_control, _project, _text, *, actions):
        calls.append(actions)
        if len(calls) == 1:
            raise StaleElementReferenceException()
        return True

    form._send_amount_keys = send_once_stale_then_fill
    form.fill_amount(Decimal("100.00"))
    assert len(resolved) == 2
    assert calls == [False, True]

    failing = InvoiceForm(None)
    failing.root = lambda: object()
    failing_project = Project()
    monkeypatch.setattr("etax.pages.invoice_form.visible_unique", lambda *_args: failing_project)
    failing._amount_input = lambda: Amount()
    failing._send_amount_keys = lambda *_args, **_kwargs: False
    failing._input_value = lambda control: "selected" if control is failing_project else ""
    with pytest.raises(EtaxBlocked, match="AMOUNT_FILL_FAILED"):
        failing.fill_amount(Decimal("100.00"))


def test_project_survives_amount_fill_and_amount_can_never_be_the_project_input(monkeypatch):
    class Input:
        def __init__(self, value): self.value, self.keys = value, []
        def get_attribute(self, name): return self.value if name == "value" else None
        def get_property(self, name): return self.value if name == "value" else None
        def send_keys(self, *keys): self.keys.append(keys)

    project, amount = Input("监督审核费"), Input("100.00")
    form = InvoiceForm(None)
    form.root = lambda: object()
    monkeypatch.setattr("etax.pages.invoice_form.visible_unique", lambda *_args: project)
    form._amount_input = lambda: amount
    sent_to = []
    form._send_amount_keys = lambda control, _project, _text, *, actions: (sent_to.append(control) or True)
    form.fill_amount(Decimal("100.00"))
    assert project.value == "监督审核费"
    assert amount.value == "100.00"
    assert sent_to == [amount]
    assert amount.keys == [(Keys.TAB,)]

    blocked = InvoiceForm(None)
    blocked.root = lambda: object()
    blocked._amount_input = lambda: project
    keyboard_calls = []
    blocked._send_amount_keys = lambda *_args, **_kwargs: keyboard_calls.append(True)
    with pytest.raises(EtaxBlocked, match="AMOUNT_RESOLVED_TO_PROJECT_INPUT"):
        blocked.fill_amount(Decimal("100.00"))
    assert keyboard_calls == []


def test_project_value_change_or_wrong_active_element_fails_before_keyboard_input(monkeypatch):
    class Input:
        def __init__(self, value): self.value, self.keys = value, []
        def get_attribute(self, name): return self.value if name == "value" else None
        def get_property(self, name): return self.value if name == "value" else None
        def send_keys(self, *keys): self.keys.append(keys)

    before, after, amount = Input("项目A"), Input("项目B"), Input("100.00")
    form = InvoiceForm(None)
    form.root = lambda: object()
    projects = iter([before, before, after])
    monkeypatch.setattr("etax.pages.invoice_form.visible_unique", lambda *_args: next(projects))
    form._amount_input = lambda: amount
    form._send_amount_keys = lambda *_args, **_kwargs: True
    with pytest.raises(EtaxBlocked, match="PROJECT_VALUE_CHANGED_DURING_AMOUNT_FILL"):
        form.fill_amount(Decimal("100.00"))
    assert amount.keys == []  # No TAB after a project-integrity failure.

    class Driver:
        class Switch:
            active_element = None
        switch_to = Switch()

    class WrongFocusChain:
        def __init__(self, driver): self.driver = driver
        def move_to_element(self, _control): return self
        def click(self): return self
        def perform(self): self.driver.switch_to.active_element = before

    focus_form = InvoiceForm(Driver())
    monkeypatch.setattr("etax.pages.invoice_form.ActionChains", WrongFocusChain)
    with pytest.raises(EtaxBlocked, match="AMOUNT_FOCUS_WRONG_ELEMENT"):
        focus_form._focus_amount_input(amount, before)


def test_amount_keyboard_contract_requires_focus_and_never_assigns_value_with_javascript():
    import inspect

    source = inspect.getsource(InvoiceForm.fill_amount) + inspect.getsource(InvoiceForm._send_amount_keys)
    assert "for attempt in range(2)" in source
    assert "AMOUNT_FOCUS_FAILED" in inspect.getsource(InvoiceForm._focus_amount_input)
    assert "AMOUNT_FOCUS_WRONG_ELEMENT" in inspect.getsource(InvoiceForm._focus_amount_input)
    assert "AMOUNT_RESOLVED_TO_PROJECT_INPUT" in inspect.getsource(InvoiceForm.fill_amount)
    assert "PROJECT_VALUE_CHANGED_DURING_AMOUNT_FILL" in inspect.getsource(InvoiceForm.fill_amount)
    assert "switch_to.active_element" in inspect.getsource(InvoiceForm._focus_amount_input)
    assert "Keys.CONTROL, \"a\"" in source
    assert "Keys.BACKSPACE" in source
    assert "Keys.TAB" in source
    assert "execute_script" not in source


def test_amount_flow_stops_before_any_final_issue_action():
    workflow_source = __import__("inspect").getsource(__import__("etax.workflow", fromlist=["EtaxInvoiceWorkflow"]).EtaxInvoiceWorkflow.run)
    assert "form.fill_amount(job.requested_total_amount)" in workflow_source
    assert "form.validate(job.requested_total_amount)" in workflow_source
    assert all(forbidden not in workflow_source.lower() for forbidden in ("submit", "issue", "确认开具"))


def test_workflow_result_cannot_indicate_issuance():
    assert WorkflowResult().stopped_before_issue is True
    assert not hasattr(WorkflowResult(), "issued")
