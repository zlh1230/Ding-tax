"""Read-only Selenium attach probe for the already-open ETax Chrome."""

from datetime import datetime
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service


LABELS = {
    "BUYER_SECTION_VISIBLE": "购买方信息",
    "SELLER_SECTION_VISIBLE": "销售方信息",
    "INVOICE_SECTION_VISIBLE": "开票信息",
    "PROJECT_LABEL_VISIBLE": "项目名称",
    "AMOUNT_LABEL_VISIBLE": "金额（含税）",
    "TAX_RATE_LABEL_VISIBLE": "税率/征收率",
    "TAX_AMOUNT_LABEL_VISIBLE": "税额",
}


def visible_text(driver, text: str) -> bool:
    return any(element.is_displayed() for element in driver.find_elements(By.XPATH, f"//*[normalize-space()={text!r}]"))


def main() -> None:
    print(f"A {datetime.now().isoformat(timespec='seconds')} before ChromeOptions")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    print(f"B {datetime.now().isoformat(timespec='seconds')} before Service / driver resolution")
    driver_path = r"C:\DingInvoiceMVP\agent\tools\chromedriver\153.0.8010.52\chromedriver-win64\chromedriver.exe"
    print(f"C {datetime.now().isoformat(timespec='seconds')} before webdriver.Chrome")
    driver = webdriver.Chrome(service=Service(executable_path=driver_path), options=options)
    print(f"D {datetime.now().isoformat(timespec='seconds')} webdriver.Chrome returned")
    windows = []
    print(f"E {datetime.now().isoformat(timespec='seconds')} window_handles read")
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url = urlsplit(driver.current_url)
        title_kind = "BLUE_INVOICE" if driver.title.startswith("蓝字发票开具") else "OTHER"
        print(f"WINDOW: TITLE_KIND={title_kind}; HOST={url.hostname or ''}; PATH={url.path}")
        windows.append((handle, url.hostname, url.path))

    targets = [window for window in windows if window[1] == "dppt.shanghai.chinatax.gov.cn" and window[2].startswith("/blue-invoice-makeout/")]
    print(f"SELENIUM_ATTACHED={'YES' if windows else 'NO'}")
    print(f"WINDOW_COUNT={len(windows)}")
    print(f"DPP_FORM_WINDOW_FOUND={'YES' if len(targets) == 1 else 'NO'}")
    if len(targets) != 1:
        return

    driver.switch_to.window(targets[0][0])
    print(f"TARGET_HOST={targets[0][1]}")
    print(f"TARGET_PATH={targets[0][2]}")
    for key, label in LABELS.items():
        print(f"{key}={'YES' if visible_text(driver, label) else 'NO'}")


if __name__ == "__main__":
    main()
