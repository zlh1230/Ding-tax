"""Save a read-only DOM snapshot from the manually authenticated DPP tab."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.service import Service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMEDRIVER = PROJECT_ROOT / "agent" / "tools" / "chromedriver" / "153.0.8010.52" / "chromedriver-win64" / "chromedriver.exe"
SNAPSHOT_DIR = PROJECT_ROOT / "agent" / "debug_snapshots"
STAGES = ("home", "invoice-type", "form", "project-dialog")


def attached_dpp_driver():
    if not CHROMEDRIVER.is_file():
        raise RuntimeError("CHROMEDRIVER_NOT_FOUND")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(service=Service(executable_path=str(CHROMEDRIVER)), options=options)
    matches = []
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if urlsplit(driver.current_url).hostname == "dppt.shanghai.chinatax.gov.cn":
            matches.append(handle)
    if not matches:
        raise RuntimeError("DPP_WINDOW_NOT_FOUND")
    if len(matches) != 1:
        raise RuntimeError("DPP_WINDOW_NOT_UNIQUE")
    driver.switch_to.window(matches[0])
    return driver


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only DOM snapshot from an attached ETax DPP page")
    parser.add_argument("--stage", required=True, choices=STAGES)
    args = parser.parse_args()
    driver = attached_dpp_driver()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / f"{args.stage}.html").write_text(driver.page_source, encoding="utf-8")
    print(f"SNAPSHOT_SAVED = {args.stage}")


if __name__ == "__main__":
    main()
