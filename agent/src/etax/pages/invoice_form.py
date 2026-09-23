from decimal import Decimal, InvalidOperation

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from etax.browser import EtaxBlocked, visible_unique
from etax.mappings import SELLER_PHONE
from etax.pages.project_dialog import ProjectDialog


class InvoiceForm:
    ROOT = ".blue-invoice"
    BUYER = ".t-form-item__gmfmc input.t-input__inner"
    BUYER_POPUP = ".t-popup"
    BUYER_DATA_READY = ".t-popup .auto-complete__list .auto-complete__item"
    BUYER_OPTION = ".auto-complete__item"
    BUYER_TAX_ID = ".t-form-item__gmfnsrsbh input.t-input__inner"
    SELLER_PHONE = ".t-form-item__xsflxdh input.t-input__inner"
    SELLER_PHONE_OPTION = ".t-select-option"
    ADDRESS_PHONE_CHECKBOX = ".t-form-item__xsfdz label.t-checkbox"
    BANK_CHECKBOX = ".t-form-item__xsfkhh label.t-checkbox"
    PROJECT_INPUT = ".xmmc_handle input.hwhyslwfwmc_0"
    PROJECT_BUTTON = ".xmmc_handle button.t-button--shape-square"
    TOTAL = ".amount-tax-statistics .amount-tax-form .amount-tax-form__lower"
    TOTAL_LABEL = "价税合计（小写）："
    TIMEOUT_SECONDS = 20

    def __init__(self, driver):
        self.driver = driver

    def is_current(self) -> bool:
        return len([element for element in self.driver.find_elements(By.CSS_SELECTOR, self.ROOT) if element.is_displayed()]) == 1

    @staticmethod
    def normalized(value: str) -> str:
        return "".join(value.split())

    @staticmethod
    def is_checked(label) -> bool:
        return "t-is-checked" in (label.get_attribute("class") or "").split()

    def ensure_checked(self, label, failure: str) -> None:
        if self.is_checked(label):
            return
        label.click()
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(lambda _: self.is_checked(label))
        except TimeoutException as error:
            raise EtaxBlocked(failure) from error

    @staticmethod
    def parse_total(raw_total: str) -> Decimal:
        try:
            normalized = raw_total.replace(",", "").replace("¥", "").replace("￥", "")
            return Decimal("".join(normalized.split()))
        except (InvalidOperation, ValueError) as error:
            raise EtaxBlocked("TOTAL_NOT_READABLE") from error

    @classmethod
    def assert_total_matches(cls, raw_total: str, expected_total: Decimal) -> None:
        if cls.parse_total(raw_total) != expected_total:
            raise EtaxBlocked("TOTAL_MISMATCH")

    @classmethod
    def total_value_from_spans(cls, span_texts: list[str]) -> str:
        labels = [
            index for index, text in enumerate(span_texts)
            if cls.normalized(text) == cls.normalized(cls.TOTAL_LABEL)
        ]
        if len(labels) != 1 or labels[0] + 1 >= len(span_texts):
            raise EtaxBlocked("TOTAL_NOT_READABLE")
        return span_texts[labels[0] + 1].strip()

    @classmethod
    def exact_buyer_match(cls, candidates, buyer_name: str, candidate_text=None):
        def default_text(candidate):
            text = candidate.text
            if text:
                return text
            try:
                return candidate.get_attribute("textContent") or ""
            except AttributeError:
                return ""

        candidate_text = candidate_text or default_text
        matches = [candidate for candidate in candidates if cls.normalized(candidate_text(candidate)) == cls.normalized(buyer_name)]
        if not matches:
            raise EtaxBlocked("BUYER_EXACT_MATCH_NOT_FOUND")
        if len(matches) > 1:
            raise EtaxBlocked("BUYER_EXACT_MATCH_NOT_UNIQUE")
        return matches[0]

    @classmethod
    def buyer_popup_with_exact_match(cls, popup_options, buyer_name: str):
        matches = []
        for popup, options in popup_options:
            try:
                candidate = cls.exact_buyer_match(options, buyer_name)
            except EtaxBlocked as error:
                if str(error) == "BUYER_EXACT_MATCH_NOT_FOUND":
                    continue
                raise
            matches.append((popup, candidate))
        if not matches:
            raise EtaxBlocked("BUYER_EXACT_MATCH_NOT_FOUND")
        if len(matches) > 1:
            raise EtaxBlocked("BUYER_POPUP_AMBIGUOUS")
        return matches[0]

    @classmethod
    def exact_seller_phone_option(cls, options):
        matches = [option for option in options if cls.normalized(option.text) == cls.normalized(SELLER_PHONE)]
        if not matches:
            raise EtaxBlocked("SELLER_PHONE_OPTION_NOT_FOUND")
        if len(matches) > 1:
            raise EtaxBlocked("SELLER_PHONE_OPTION_NOT_UNIQUE")
        return matches[0]

    def root(self):
        return visible_unique(self.driver, By.CSS_SELECTOR, self.ROOT, "INVOICE_FORM_NOT_FOUND")

    def fill_buyer(self, buyer_name: str) -> None:
        root = self.root()
        control = visible_unique(root, By.CSS_SELECTOR, self.BUYER, "BUYER_INPUT_NOT_FOUND")
        control.click()
        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(buyer_name).perform()

        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda _: control.get_attribute("value") == buyer_name
            )
            data_options = WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda driver: driver.find_elements(By.CSS_SELECTOR, self.BUYER_DATA_READY) or False
            )
        except TimeoutException as error:
            raise EtaxBlocked("BUYER_AUTOCOMPLETE_DATA_TIMEOUT") from error
        self.exact_buyer_match(data_options, buyer_name)
        ActionChains(self.driver).move_to_element(control).click().perform()

        def buyer_popup(_):
            popup_options = []
            for popup in self.driver.find_elements(By.CSS_SELECTOR, self.BUYER_POPUP):
                if popup.is_displayed():
                    options = [element for element in popup.find_elements(By.CSS_SELECTOR, self.BUYER_OPTION) if element.is_displayed()]
                    popup_options.append((popup, options))
            try:
                return self.buyer_popup_with_exact_match(popup_options, buyer_name)
            except EtaxBlocked as error:
                if str(error) == "BUYER_EXACT_MATCH_NOT_FOUND":
                    return False
                raise

        try:
            popup, candidate = WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(buyer_popup)
        except TimeoutException as error:
            raise EtaxBlocked("BUYER_EXACT_MATCH_NOT_FOUND") from error
        candidate.click()
        try:
            def popup_gone(_):
                try:
                    return not popup.is_displayed()
                except StaleElementReferenceException:
                    return True

            def tax_id_populated(_):
                fields = [element for element in self.root().find_elements(By.CSS_SELECTOR, self.BUYER_TAX_ID) if element.is_displayed()]
                if len(fields) > 1:
                    raise EtaxBlocked("BUYER_TAX_ID_NOT_UNIQUE")
                return fields and fields[0].get_attribute("value").strip()

            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(popup_gone)
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(tax_id_populated)
        except TimeoutException as error:
            raise EtaxBlocked("BUYER_TAX_ID_NOT_POPULATED") from error

    def configure_seller(self) -> None:
        root = self.root()
        phone = visible_unique(root, By.CSS_SELECTOR, self.SELLER_PHONE, "SELLER_PHONE_NOT_FOUND")
        phone.click()
        dropdown = visible_unique(self.driver, By.CSS_SELECTOR, ".t-select__dropdown", "SELLER_PHONE_DROPDOWN_NOT_FOUND")
        options = [element for element in dropdown.find_elements(By.CSS_SELECTOR, self.SELLER_PHONE_OPTION) if element.is_displayed()]
        self.exact_seller_phone_option(options).click()
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda _: phone.get_attribute("value") == SELLER_PHONE
            )
        except TimeoutException as error:
            raise EtaxBlocked("SELLER_PHONE_VALUE_NOT_SET") from error
        for selector, failure in (
            (self.ADDRESS_PHONE_CHECKBOX, "SELLER_ADDRESS_PHONE_CHECKBOX_NOT_CHECKED"),
            (self.BANK_CHECKBOX, "SELLER_BANK_ACCOUNT_CHECKBOX_NOT_CHECKED"),
        ):
            label = visible_unique(root, By.CSS_SELECTOR, selector, "SELLER_CHECKBOX_NOT_FOUND")
            self.ensure_checked(label, failure)

    def select_project(self, project_name: str) -> None:
        root = self.root()
        visible_unique(root, By.CSS_SELECTOR, self.PROJECT_INPUT, "PROJECT_INPUT_NOT_FOUND")
        visible_unique(root, By.CSS_SELECTOR, self.PROJECT_BUTTON, "PROJECT_BUTTON_NOT_FOUND").click()
        project_name = ProjectDialog(self.driver).select_item(project_name)
        def project_populated(_):
            inputs = [element for element in self.root().find_elements(By.CSS_SELECTOR, self.PROJECT_INPUT) if element.is_displayed()]
            if len(inputs) > 1:
                raise EtaxBlocked("PROJECT_INPUT_NOT_UNIQUE")
            return inputs and inputs[0].get_attribute("value").strip()

        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(project_populated)
        except TimeoutException as error:
            raise EtaxBlocked("PROJECT_FIELD_NOT_POPULATED") from error

    @staticmethod
    def column_index(header_keys: list[str], column_key: str) -> int:
        matches = [index for index, key in enumerate(header_keys) if key == column_key]
        if len(matches) != 1:
            raise EtaxBlocked(f"{column_key}_HEADER_NOT_UNIQUE")
        return matches[0]

    def _column_input(self, column_key: str, selector: str, failure: str):
        def one_input(_):
            elements = []
            for table in self.root().find_elements(By.CSS_SELECTOR, ".invoice-info.mrt24 table.t-table--layout-fixed"):
                if not table.is_displayed():
                    continue
                headers = [header for header in table.find_elements(By.CSS_SELECTOR, "thead th[data-colkey]") if header.is_displayed()]
                try:
                    index = self.column_index([header.get_attribute("data-colkey") for header in headers], column_key)
                except EtaxBlocked:
                    continue
                rows = [row for row in table.find_elements(By.CSS_SELECTOR, "tbody tr") if row.is_displayed() and row.find_elements(By.CSS_SELECTOR, "td")]
                if not rows:
                    continue
                cells = rows[0].find_elements(By.CSS_SELECTOR, "td")
                if index >= len(cells):
                    continue
                elements.extend(element for element in cells[index].find_elements(By.CSS_SELECTOR, selector) if element.is_displayed())
            if len(elements) > 1:
                raise EtaxBlocked(f"{failure}_NOT_UNIQUE")
            return elements[0] if elements else False

        try:
            return WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(one_input)
        except TimeoutException as error:
            raise EtaxBlocked(failure) from error

    @staticmethod
    def _input_value(control) -> str:
        return (control.get_property("value") or "").strip()

    def _project_input(self):
        return visible_unique(self.root(), By.CSS_SELECTOR, self.PROJECT_INPUT, "PROJECT_AUTOFILL_NOT_CONFIRMED")

    @staticmethod
    def _same_element(first, second) -> bool:
        return first == second

    def _amount_input(self):
        control = self._column_input("je", "input.t-input.blueinvoice-input", "AMOUNT_INPUT_NOT_FOUND")
        displayed = control.is_displayed()
        enabled = control.is_enabled()
        readonly = control.get_attribute("readonly") is not None
        disabled = control.get_attribute("disabled") is not None
        print("AMOUNT_INPUT_FOUND", flush=True)
        print(f"AMOUNT_INPUT_DISPLAYED = {'YES' if displayed else 'NO'}", flush=True)
        print(f"AMOUNT_INPUT_ENABLED = {'YES' if enabled else 'NO'}", flush=True)
        print(f"AMOUNT_INPUT_READONLY = {'YES' if readonly else 'NO'}", flush=True)
        print(f"AMOUNT_INPUT_DISABLED = {'YES' if disabled else 'NO'}", flush=True)
        print(f"AMOUNT_VALUE_BEFORE = {self._input_value(control)}", flush=True)
        if not displayed or not enabled or readonly or disabled:
            raise EtaxBlocked("AMOUNT_FILL_FAILED")
        return control

    def _focus_amount_input(self, control, project) -> None:
        ActionChains(self.driver).move_to_element(control).click().perform()
        active = self.driver.switch_to.active_element
        if self._same_element(active, project):
            print("AMOUNT_FOCUS_CONFIRMED = NO", flush=True)
            raise EtaxBlocked("AMOUNT_FOCUS_WRONG_ELEMENT")
        focused = self._same_element(active, control)
        print(f"AMOUNT_FOCUS_CONFIRMED = {'YES' if focused else 'NO'}", flush=True)
        if not focused:
            raise EtaxBlocked("AMOUNT_FOCUS_FAILED")

    def _send_amount_keys(self, control, project, amount_text: str, *, actions: bool) -> bool:
        self._focus_amount_input(control, project)
        if actions:
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(
                Keys.BACKSPACE
            ).send_keys(amount_text).perform()
        else:
            control.send_keys(Keys.CONTROL, "a")
            control.send_keys(Keys.BACKSPACE)
            control.send_keys(amount_text)
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda _: self._input_value(control) == amount_text
            )
            return True
        except TimeoutException:
            return False

    def fill_amount(self, amount: Decimal) -> None:
        project = self._project_input()
        project_value_before = self._input_value(project)
        if not project_value_before:
            raise EtaxBlocked("PROJECT_AUTOFILL_NOT_CONFIRMED")
        if not isinstance(amount, Decimal):
            raise EtaxBlocked("AMOUNT_FILL_FAILED")
        amount_text = format(amount, "f")
        print(f"PROJECT_VALUE_BEFORE_AMOUNT = {project_value_before}", flush=True)
        print("AMOUNT_COLUMN_KEY = je", flush=True)
        print(f"AMOUNT_TARGET_VALUE = {amount_text}", flush=True)
        for attempt in range(2):
            try:
                # Resolve after project autofill, and again for the single Vue re-render retry.
                project = self._project_input()
                control = self._amount_input()
                is_project_input = self._same_element(control, project)
                print(f"AMOUNT_INPUT_IS_PROJECT_INPUT = {'YES' if is_project_input else 'NO'}", flush=True)
                if is_project_input:
                    raise EtaxBlocked("AMOUNT_RESOLVED_TO_PROJECT_INPUT")
                filled = self._send_amount_keys(control, project, amount_text, actions=attempt == 1)
                value = self._input_value(control)
                if attempt == 0:
                    print(f"AMOUNT_VALUE_AFTER_SEND_KEYS = {value}", flush=True)
                else:
                    print(f"AMOUNT_VALUE_AFTER_RETRY = {value}", flush=True)
                if not filled:
                    continue
                if attempt == 0:
                    print("AMOUNT_VALUE_AFTER_RETRY = NOT_REQUIRED", flush=True)
                project_value_after = self._input_value(self._project_input())
                print(f"PROJECT_VALUE_AFTER_AMOUNT = {project_value_after}", flush=True)
                if project_value_after != project_value_before:
                    raise EtaxBlocked("PROJECT_VALUE_CHANGED_DURING_AMOUNT_FILL")
                control.send_keys(Keys.TAB)
                print("AMOUNT_FILLED", flush=True)
                print("AMOUNT_BLURRED", flush=True)
                return
            except StaleElementReferenceException:
                if attempt == 0:
                    print("AMOUNT_VALUE_AFTER_SEND_KEYS = STALE", flush=True)
                    continue
                print("AMOUNT_VALUE_AFTER_RETRY = STALE", flush=True)
                break
            except WebDriverException as error:
                raise EtaxBlocked("AMOUNT_FILL_FAILED") from error
        raise EtaxBlocked("AMOUNT_FILL_FAILED")

    def quantity_input(self):
        return self._column_input("spsl", "input.t-input.blueinvoice-input", "QUANTITY_INPUT_NOT_FOUND")

    def validate(self, expected_total: Decimal) -> None:
        rate = self._column_input("slv", "input.t-input__inner", "TAX_RATE_NOT_POPULATED")
        tax_amount = self._column_input("se", "input.t-input.blueinvoice-input", "TAX_AMOUNT_NOT_POPULATED")
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda _: rate.get_attribute("value").strip() or False
            )
        except TimeoutException as error:
            raise EtaxBlocked("TAX_RATE_NOT_POPULATED") from error
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda _: tax_amount.get_attribute("value").strip() or False
            )
        except TimeoutException as error:
            raise EtaxBlocked("TAX_AMOUNT_NOT_POPULATED") from error

        print(f"TAX_RATE_VALUE = {self._input_value(rate)}", flush=True)
        print(f"TAX_AMOUNT_VALUE = {self._input_value(tax_amount)}", flush=True)

        root = self.root()

        def total_matches(_):
            try:
                containers = [
                    container for container in root.find_elements(By.CSS_SELECTOR, self.TOTAL)
                    if container.is_displayed()
                ]
                if len(containers) != 1:
                    return False
                spans = [span for span in containers[0].find_elements(By.CSS_SELECTOR, "span") if span.is_displayed()]
                total_text = self.total_value_from_spans([span.text for span in spans])
                self.assert_total_matches(total_text, expected_total)
                return total_text
            except (EtaxBlocked, StaleElementReferenceException):
                return False

        try:
            total_text = WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(total_matches)
        except TimeoutException as error:
            raise EtaxBlocked("TOTAL_MISMATCH") from error
        print(f"TOTAL_VALUE = {total_text}", flush=True)
        print("TOTAL_MATCH", flush=True)
