from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from etax.browser import EtaxBlocked


class InvoiceTypeDialog:
    """The visible `立即开票` dialog, identified by its unique ticket-type field."""

    TICKET_FIELD = ".t-form-item__fppzDm"
    TICKET_SELECT = ".t-select-input.t-select"
    DROPDOWN = ".t-select__dropdown"
    CONFIRM = "button.t-dialog__confirm"
    FORM_MARKER = ".t-form-item__gmfmc"
    TIMEOUT_SECONDS = 20

    def __init__(self, driver):
        self.driver = driver

    @staticmethod
    def _visible(elements):
        return [element for element in elements if element.is_displayed()]

    def _visible_dialogs(self):
        dialogs = []
        for field in self._visible(self.driver.find_elements(By.CSS_SELECTOR, self.TICKET_FIELD)):
            dialog = field.find_element(
                By.XPATH,
                "ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' t-dialog ')][1]",
            )
            if dialog.is_displayed() and dialog.id not in {item.id for item in dialogs}:
                dialogs.append(dialog)
        return dialogs

    def root(self):
        def one_dialog(_):
            dialogs = self._visible_dialogs()
            if len(dialogs) > 1:
                raise EtaxBlocked("INVOICE_TYPE_DIALOG_NOT_UNIQUE")
            return dialogs[0] if dialogs else False

        try:
            return WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(one_dialog)
        except TimeoutException as error:
            raise EtaxBlocked("INVOICE_TYPE_DIALOG_NOT_FOUND") from error

    def _one_visible(self, root, selector, failure):
        def one_element(_):
            elements = self._visible(root.find_elements(By.CSS_SELECTOR, selector))
            if len(elements) > 1:
                raise EtaxBlocked(failure)
            return elements[0] if elements else False

        try:
            return WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(one_element)
        except TimeoutException as error:
            raise EtaxBlocked(failure) from error

    def choose(self, invoice_type: str) -> None:
        root = self.root()
        ticket_select = self._one_visible(root, self.TICKET_FIELD + " " + self.TICKET_SELECT, "INVOICE_TYPE_SELECT_NOT_FOUND")
        ticket_select.click()
        dropdown = self._one_visible(self.driver, self.DROPDOWN, "INVOICE_TYPE_DROPDOWN_NOT_FOUND")
        option = self._one_visible(
            dropdown,
            f'.t-select-option[title="{invoice_type}"]',
            "INVOICE_TYPE_OPTION_NOT_FOUND",
        )
        option.click()
        self._one_visible(root, self.CONFIRM, "INVOICE_TYPE_CONFIRM_NOT_FOUND").click()
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(lambda _: not self._visible_dialogs())
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda driver: bool(self._visible(driver.find_elements(By.CSS_SELECTOR, self.FORM_MARKER)))
            )
        except TimeoutException as error:
            raise EtaxBlocked("INVOICE_FORM_NOT_REACHED") from error
