from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from etax.browser import EtaxBlocked, visible_unique
from etax_projects import resolve_project


class ProjectDialog:
    ROOT = ".invoice-project__drawer.t-drawer--open"
    ROW = "tbody tr"
    SELECT_ACTION = "span.button-text.primary-button__text"
    PROJECT_FIELD = ".blue-invoice .xmmc_handle input.hwhyslwfwmc_0"
    TIMEOUT_SECONDS = 20

    def __init__(self, driver):
        self.driver = driver

    def root(self):
        return visible_unique(self.driver, By.CSS_SELECTOR, self.ROOT, "PROJECT_DIALOG_NOT_FOUND")

    @staticmethod
    def normalized(value: str) -> str:
        return "".join(value.split())

    @classmethod
    def project_name(cls, row) -> str:
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        if len(cells) < 2:
            return ""
        return cls.normalized(cells[1].text)

    @classmethod
    def exact_row(cls, rows, project_name: str):
        matches = [row for row in rows if cls.project_name(row) == cls.normalized(project_name)]
        if not matches:
            raise EtaxBlocked("PROJECT_ROW_NOT_FOUND")
        if len(matches) > 1:
            raise EtaxBlocked("PROJECT_ROW_NOT_UNIQUE")
        return matches[0]

    @classmethod
    def exact_select_action(cls, actions):
        matches = [action for action in actions if cls.normalized(action.text) == "选择"]
        if not matches:
            raise EtaxBlocked("PROJECT_SELECT_NOT_FOUND")
        if len(matches) > 1:
            raise EtaxBlocked("PROJECT_SELECT_NOT_FOUND")
        return matches[0]

    def select_item(self, raw_project_name: str) -> str:
        try:
            project_name = resolve_project(raw_project_name)
        except ValueError as error:
            raise EtaxBlocked("PROJECT_MAPPING_FAILED") from error
        print(f"PROJECT_RAW_NAME = {raw_project_name}", flush=True)
        print(f"PROJECT_MAPPED_NAME = {project_name}", flush=True)
        self.select_exact(project_name)
        return project_name

    def select_exact(self, project_name: str) -> None:
        root = self.root()
        def project_rows(_):
            return [
                row for row in root.find_elements(By.CSS_SELECTOR, self.ROW)
                if row.is_displayed()
                and "t-table__empty-row" not in (row.get_attribute("class") or "").split()
                and len(row.find_elements(By.CSS_SELECTOR, "td")) >= 2
            ] or False

        try:
            rows = WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(project_rows)
        except TimeoutException as error:
            raise EtaxBlocked("PROJECT_TABLE_NOT_FOUND")
        names = [self.project_name(row) for row in rows]
        print(f"PROJECT_ROW_COUNT = {len(rows)}", flush=True)
        print(f"PROJECT_VISIBLE_NAMES = {', '.join(names)}", flush=True)
        row = self.exact_row(rows, project_name)
        print("PROJECT_TARGET_ROW_FOUND", flush=True)

        def select_span_ready(_):
            actions = [
                action
                for action in row.find_elements(By.CSS_SELECTOR, self.SELECT_ACTION)
                if action.is_displayed() and action.is_enabled()
            ]
            if not actions:
                return False
            return self.exact_select_action(actions)

        try:
            action = WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(select_span_ready)
        except TimeoutException as error:
            raise EtaxBlocked("PROJECT_SELECT_NOT_FOUND") from error
        print("PROJECT_SELECT_SPAN_FOUND", flush=True)
        try:
            action.click()
        except ElementClickInterceptedException:
            ActionChains(self.driver).move_to_element(action).click().perform()
        print("PROJECT_SELECT_CLICKED", flush=True)
        try:
            WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(
                lambda driver: not any(element.is_displayed() for element in driver.find_elements(By.CSS_SELECTOR, self.ROOT))
            )
            print("PROJECT_DRAWER_CLOSED", flush=True)

            def project_field_populated(driver):
                fields = [field for field in driver.find_elements(By.CSS_SELECTOR, self.PROJECT_FIELD) if field.is_displayed()]
                if len(fields) > 1:
                    raise EtaxBlocked("PROJECT_FIELD_NOT_UNIQUE")
                if not fields:
                    return False
                value = fields[0].get_attribute("value") or ""
                return value if self.normalized(value).endswith(self.normalized(project_name)) else False

            project_value = WebDriverWait(self.driver, self.TIMEOUT_SECONDS).until(project_field_populated)
            print(f"PROJECT_AUTOFILL_VALUE = {project_value}", flush=True)
            print("PROJECT_AUTOFILL_CONFIRMED", flush=True)
        except TimeoutException as error:
            raise EtaxBlocked("PROJECT_FIELD_NOT_POPULATED") from error
