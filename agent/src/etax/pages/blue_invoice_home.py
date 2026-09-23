from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from etax.browser import EtaxBlocked, HOME_TIMEOUT_SECONDS, xpath_literal


class BlueInvoiceHome:
    QUICK_ENTRANCE = ".quick-entrance"
    HOME_CARD = ".quick-entrance .invoice-entrance.invoice-home__block"
    INVOICE_ACTION = ".invoice-entrance-content .invoice-entrance-choose"

    def __init__(self, driver):
        self.driver = driver

    def is_current(self) -> bool:
        try:
            self.home_card()
            return True
        except EtaxBlocked:
            return False

    def home_card(self):
        matches = [element for element in self.driver.find_elements(By.CSS_SELECTOR, self.HOME_CARD) if element.is_displayed()]
        if not matches:
            raise EtaxBlocked("HOME_CARD_NOT_FOUND")
        if len(matches) > 1:
            raise EtaxBlocked("HOME_CARD_NOT_UNIQUE")
        return matches[0]

    def immediate_invoice(self):
        def actionable(_driver):
            candidates = []
            for action in self.home_card().find_elements(By.CSS_SELECTOR, self.INVOICE_ACTION):
                if not action.is_displayed() or not action.is_enabled():
                    continue
                labels = action.find_elements(By.XPATH, f".//*[normalize-space()={xpath_literal('立即开票')}]")
                if labels:
                    candidates.append(action)
            if len(candidates) > 1:
                raise EtaxBlocked("IMMEDIATE_INVOICE_NOT_UNIQUE")
            return candidates[0] if candidates else False

        try:
            return WebDriverWait(self.driver, HOME_TIMEOUT_SECONDS).until(actionable)
        except TimeoutException as error:
            raise EtaxBlocked("IMMEDIATE_INVOICE_NOT_FOUND") from error

    def ensure_ready(self) -> None:
        self.immediate_invoice()

    def open_invoice(self) -> None:
        self.immediate_invoice().click()

    def start_invoice(self) -> None:
        self.open_invoice()
