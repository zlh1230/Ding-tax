from __future__ import annotations

import time
import re
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


class EtaxBlocked(RuntimeError):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMEDRIVER = PROJECT_ROOT / "agent" / "tools" / "chromedriver" / "153.0.8010.52" / "chromedriver-win64" / "chromedriver.exe"
DPP_HOST = "dppt.shanghai.chinatax.gov.cn"
ETAX_HOST = "etax.shanghai.chinatax.gov.cn"
START_URL = "https://dppt.shanghai.chinatax.gov.cn:8443/blue-invoice-makeout"
HOME_TIMEOUT_SECONDS = 20


def xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in value.split("'")) + ")"


def visible_unique(root, by, selector: str, code: str, timeout: float = 20):
    def one_visible(_):
        matches = [element for element in root.find_elements(by, selector) if element.is_displayed()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise EtaxBlocked(f"{code}_NOT_UNIQUE")
        return False

    try:
        return WebDriverWait(root, timeout).until(one_visible)
    except TimeoutException as error:
        raise EtaxBlocked(code) from error


class AttachedEtaxBrowser:
    def __init__(self, driver):
        self.driver = driver

    @classmethod
    def attach(cls):
        if not CHROMEDRIVER.is_file():
            raise EtaxBlocked("CHROMEDRIVER_NOT_FOUND")
        options = webdriver.ChromeOptions()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        return cls(webdriver.Chrome(service=Service(executable_path=str(CHROMEDRIVER)), options=options))

    @staticmethod
    def is_authenticated_tax_url(url: str) -> bool:
        page = urlsplit(url)
        return page.hostname == DPP_HOST or (page.hostname == ETAX_HOST and not page.path.startswith("/loginb/"))

    def normalize_start_state(self):
        """Start every job from the DPP home, never from a prior form state."""
        authenticated = []
        current = self.driver.current_window_handle
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if self.is_authenticated_tax_url(self.driver.current_url):
                authenticated.append(handle)
        if not authenticated:
            raise EtaxBlocked("ETAX_LOGIN_REQUIRED")
        if current in authenticated:
            target = current
        elif len(authenticated) == 1:
            target = authenticated[0]
        else:
            raise EtaxBlocked("ETAX_SESSION_NOT_UNIQUE")
        self.driver.switch_to.window(target)
        self.driver.set_page_load_timeout(HOME_TIMEOUT_SECONDS)
        try:
            self.driver.get(START_URL)
        except TimeoutException:
            pass
        if not self._wait_for_complete():
            self._capture_home_timeout()
            raise EtaxBlocked("DPP_HOME_LOAD_TIMEOUT")
        if not self.is_authenticated_tax_url(self.driver.current_url):
            raise EtaxBlocked("ETAX_LOGIN_REQUIRED")
        from etax.pages.blue_invoice_home import BlueInvoiceHome
        if not self._wait_for_visible(BlueInvoiceHome.QUICK_ENTRANCE):
            self._capture_home_timeout()
            raise EtaxBlocked("HOME_QUICK_ENTRANCE_NOT_FOUND")
        if not self._wait_for_visible(BlueInvoiceHome.HOME_CARD):
            self._capture_home_timeout()
            raise EtaxBlocked("HOME_CARD_NOT_FOUND")
        try:
            BlueInvoiceHome(self.driver).ensure_ready()
        except EtaxBlocked:
            self._capture_home_timeout()
            raise
        return self.driver

    def _wait_for_complete(self) -> bool:
        try:
            WebDriverWait(self.driver, HOME_TIMEOUT_SECONDS).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            return False

    def _wait_for_visible(self, selector: str) -> bool:
        try:
            WebDriverWait(self.driver, HOME_TIMEOUT_SECONDS).until(
                lambda driver: any(element.is_displayed() for element in driver.find_elements(By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _class_count(source: str, class_name: str) -> int:
        return len(re.findall(r'class="[^"]*' + re.escape(class_name) + r'[^"]*"', source))

    def _capture_home_timeout(self) -> None:
        snapshot_dir = PROJECT_ROOT / "agent" / "debug_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        source = self.driver.page_source
        (snapshot_dir / "home-live-failure.html").write_text(source, encoding="utf-8")
        current = urlsplit(self.driver.current_url)
        quick_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".quick-entrance"))
        card_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".quick-entrance .invoice-entrance.invoice-home__block"))
        action_count = len(self.driver.find_elements(By.CSS_SELECTOR, ".quick-entrance .invoice-entrance.invoice-home__block .invoice-entrance-content .invoice-entrance-choose"))
        print(f"CURRENT_PATH = {current.path}", flush=True)
        print(f"QUICK_ENTRANCE_COUNT = {quick_count}", flush=True)
        print(f"HOME_CARD_COUNT = {card_count}", flush=True)
        print(f"IMMEDIATE_INVOICE_ACTION_COUNT = {action_count}", flush=True)
