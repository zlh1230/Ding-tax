"""Local, headed ETax entry POC. It deliberately has no submit action."""

import argparse
import json
import os
import re
import time
from urllib.parse import urlsplit
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


class PocBlocked(RuntimeError):
    pass


def chrome_executable() -> Path:
    configured = os.getenv("ETAX_CHROME_PATH", "").strip()
    candidates = [Path(configured)] if configured else [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise PocBlocked("GOOGLE_CHROME_EXECUTABLE_NOT_FOUND")


def attached_context(playwright):
    browser = playwright.chromium.connect_over_cdp(os.getenv("ETAX_CDP_URL", "http://127.0.0.1:9222"))
    if not browser.contexts:
        raise PocBlocked("ETAX_LOGIN_REQUIRED")
    return browser.contexts[0]


def live_tax_page(context, marker: str):
    dpp_pages = [page for page in context.pages if urlsplit(page.url).hostname == "dppt.shanghai.chinatax.gov.cn"]
    if len(dpp_pages) == 1:
        return dpp_pages[0], "DPP"
    invoice_pages = [page for page in context.pages if urlsplit(page.url).hostname == "etax.shanghai.chinatax.gov.cn" and _visible_text(page, "蓝字发票开具")]
    if len(invoice_pages) == 1:
        return invoice_pages[0], "INVOICE_BUSINESS"
    homes = [page for page in context.pages if urlsplit(page.url).hostname == "etax.shanghai.chinatax.gov.cn" and _visible_text(page, marker)]
    if len(homes) == 1:
        return homes[0], "ETAX_HOME"
    login_pages = [page for page in context.pages if current_phase(page) == "WAITING_FOR_MANUAL_LOGIN"]
    if len(login_pages) == len(context.pages):
        raise PocBlocked("ETAX_LOGIN_REQUIRED")
    raise PocBlocked("ETAX_STAGE_NOT_RECOGNIZED")


@dataclass(frozen=True)
class LineItem:
    line_no: int
    item_name: str
    quantity: Decimal
    amount: Decimal


@dataclass(frozen=True)
class InvoiceJob:
    job_id: int
    buyer_name: str
    invoice_type: str
    requested_total_amount: Decimal
    line_items: list[LineItem]
    remark: str | None


def _load_local_env() -> None:
    root = Path(__file__).resolve().parents[1]
    for filename in (".env", ".env.local"):
        path = root / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key and not key.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise PocBlocked(f"MISSING_REQUIRED_LINE_ITEM_DATA: {field}") from error


def validate_job(payload: dict) -> InvoiceJob:
    if payload.get("status") != "PENDING":
        raise PocBlocked("JOB_NOT_PENDING")
    if payload.get("invoice_type") not in {"SPECIAL", "NORMAL"}:
        raise PocBlocked("UNSUPPORTED_INVOICE_TYPE")
    buyer_name = str(payload.get("buyer_name") or "").strip()
    if not buyer_name:
        raise PocBlocked("BUYER_MATCH_REQUIRED")
    raw_lines = payload.get("line_items")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise PocBlocked("MISSING_REQUIRED_LINE_ITEM_DATA: line_items")
    lines = []
    for raw in raw_lines:
        try:
            line_no = int(raw.get("line_no"))
        except (TypeError, ValueError) as error:
            raise PocBlocked("MISSING_REQUIRED_LINE_ITEM_DATA: line_no") from error
        item_name = str(raw.get("item_name") or "").strip()
        quantity = _decimal(raw.get("quantity"), "quantity")
        amount = _decimal(raw.get("amount"), "amount")
        if not item_name:
            raise PocBlocked("MISSING_REQUIRED_LINE_ITEM_DATA: item_name")
        lines.append(LineItem(line_no=line_no, item_name=item_name, quantity=quantity, amount=amount))
    total = sum((line.amount for line in lines), Decimal("0"))
    expected = _decimal(payload.get("requested_total_amount"), "requested_total_amount")
    if total != expected:
        raise PocBlocked("AMOUNT_MISMATCH")
    return InvoiceJob(job_id=int(payload["id"]), buyer_name=buyer_name, invoice_type=str(payload["invoice_type"]), requested_total_amount=expected, line_items=lines, remark=str(payload["remark"]).strip() if payload.get("remark") else None)


def exact_buyer_match(buyer_name: str, candidates: list[str]) -> str:
    matches = [candidate for candidate in candidates if candidate.strip() == buyer_name]
    if len(matches) != 1:
        raise PocBlocked("BUYER_MATCH_REQUIRED")
    return matches[0]


def fetch_job(job_id: int) -> InvoiceJob:
    base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8010").rstrip("/")
    request = Request(f"{base_url}/api/invoice-jobs/{job_id}")
    with urlopen(request, timeout=20) as response:
        return validate_job(json.load(response))


def unique_visible(locator, blocker: str, timeout: int = 30_000, diagnostic_label: str | None = None):
    deadline = time.monotonic() + timeout / 1_000
    while True:
        matches = locator.all()
        visible = [candidate for candidate in matches if candidate.is_visible()]
        if diagnostic_label:
            print(f"{diagnostic_label}_MATCH_COUNT = {len(matches)}")
            print(f"{diagnostic_label}_VISIBLE_COUNT = {len(visible)}")
        if len(visible) == 1:
            return visible[0]
        if len(visible) > 1:
            raise PocBlocked("NAVIGATION_SELECTOR_NOT_UNIQUE")
        if time.monotonic() >= deadline:
            raise PlaywrightTimeoutError(f"No visible locator for {blocker}")
        time.sleep(0.1)


def _visible_text(page, text: str) -> bool:
    try:
        locator = page.get_by_text(text, exact=True)
        return locator.count() == 1 and locator.first.is_visible()
    except Exception:
        return False


def navigate_to_invoice_entry(page) -> str:
    for label in ("蓝字发票开具", "立即开票"):
        unique_visible(page.get_by_text(label, exact=True), f"NAVIGATION_SELECTOR_NOT_UNIQUE: {label}").click()
        page.wait_for_load_state("domcontentloaded")
    return page.title()


def enter_dpp_invoice_form(page) -> str:
    unique_visible(page.get_by_text("蓝字发票开具", exact=True), "BLUE_INVOICE_ENTRY_SELECTOR_NOT_UNIQUE", diagnostic_label="BLUE_INVOICE").click()
    page.wait_for_load_state("domcontentloaded")
    unique_visible(page.get_by_text("立即开票", exact=True), "IMMEDIATE_INVOICE_SELECTOR_NOT_UNIQUE", diagnostic_label="IMMEDIATE_INVOICE").click()
    page.wait_for_load_state("domcontentloaded")
    return page.title()


def blue_invoice_visible(page) -> bool:
    try:
        locator = page.get_by_text("蓝字发票开具", exact=True)
        return len([candidate for candidate in locator.all() if candidate.is_visible()]) == 1
    except Exception:
        return False


def page_diagnostics(context, current_page, original_url: str) -> None:
    pages = context.pages
    print(f"PAGE_COUNT = {len(pages)}")
    print(f"CURRENT_PAGE_CHANGED = {'YES' if current_page.url != original_url else 'NO'}")
    for index, candidate in enumerate(pages, start=1):
        parsed = urlsplit(candidate.url)
        title = " ".join(candidate.title().split())[:80] or "(empty)"
        print(f"PAGE_{index}: TITLE={title}; URL={parsed.netloc}{parsed.path}; BLUE_INVOICE_VISIBLE={'YES' if blue_invoice_visible(candidate) else 'NO'}")


def safe_url(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.netloc}{parsed.path}"


def current_phase(page) -> str:
    parsed = urlsplit(page.url)
    if parsed.hostname == "tpass.shanghai.chinatax.gov.cn" or (parsed.hostname == "etax.shanghai.chinatax.gov.cn" and parsed.path.startswith("/loginb/")):
        return "WAITING_FOR_MANUAL_LOGIN"
    return "UNKNOWN"


def login_gateway_error(failures: list[str]) -> bool:
    return any("tpass.shanghai.chinatax.gov.cn:8443/api/v1.0/auth/oauth2/login -> 5" in item for item in failures)


def wait_for_logged_in_home(page, failures: list[str], marker: str) -> None:
    print(f"PHASE = {current_phase(page)}")
    while True:
        if login_gateway_error(failures):
            raise PocBlocked("LOGIN_GATEWAY_ERROR")
        try:
            unique_visible(page.get_by_text(marker, exact=True), "POST_LOGIN_SELECTOR_NOT_UNIQUE", timeout=1_000)
            return
        except PlaywrightTimeoutError:
            continue


def attach_blue_invoice_diagnostics(context):
    failures, console, page_errors = [], [], []

    def on_response(response):
        if response.status >= 400:
            failures.append(f"{response.request.method} {safe_url(response.url)} -> {response.status}")

    def on_request_failed(request):
        failures.append(f"{request.method} {safe_url(request.url)} -> {request.failure or 'failed'}")

    def attach_console(page):
        def on_console(message):
            if message.type in {"error", "warning"}:
                text = re.sub(r"https?://[^\s?]+\?[^\s]+", "<url-redacted>", message.text)
                console.append(f"{message.type}: {text[:200]}")
        page.on("console", on_console)
        page.on("pageerror", lambda error: page_errors.append(re.sub(r"https?://[^\s?]+\?[^\s]+", "<url-redacted>", str(error))[:200]))

    context.on("response", on_response)
    context.on("requestfailed", on_request_failed)
    context.on("page", attach_console)
    for page in context.pages:
        attach_console(page)
    return failures, console, page_errors


def blue_invoice_diagnostics(context, page, original_host: str, failures, console, page_errors) -> None:
    parsed = urlsplit(page.url)
    print(f"CHROME_EXECUTABLE = {chrome_executable()}")
    print(f"PAGE_COUNT = {len(context.pages)}")
    print(f"ACTIVE_PAGE_TITLE = {' '.join(page.title().split())[:80] or '(empty)'}")
    print(f"CURRENT_HOST_PATH = {safe_url(page.url)}")
    print(f"FRAME_COUNT = {len(page.frames)}")
    ready_state = page.evaluate("document.readyState")
    print(f"READY_STATE = {ready_state}")
    print(f"PAGE_STILL_NAVIGATING = {'YES' if ready_state != 'complete' else 'NO'}")
    print(f"CROSS_DOMAIN_NAVIGATION = {'YES' if parsed.netloc != original_host else 'NO'}")
    for item in failures:
        print(f"FAILED_REQUEST = {item}")
    for item in console:
        print(f"CONSOLE = {item}")
    for item in page_errors:
        print(f"PAGE_ERROR = {item}")
    print("BLUE_INVOICE_DIAGNOSTIC_COMPLETE")


def wait_for_dpp_initialization(context) -> None:
    dpp_page = next((page for page in context.pages if urlsplit(page.url).hostname == "dppt.shanghai.chinatax.gov.cn"), None)
    if not dpp_page:
        print("DPP_PAGE_DETECTED = NO")
        return
    print("DPP_PAGE_DETECTED = YES")
    print(f"DPP_PATH = {urlsplit(dpp_page.url).path}")
    print(f"DPP_READY_STATE = {dpp_page.evaluate('document.readyState')}")
    print(f"DPP_PAGE_TITLE = {' '.join(dpp_page.title().split())[:80] or '(empty)'}")
    print(f"DPP_PAGE_COUNT = {len(context.pages)}")
    dpp_page.wait_for_timeout(20_000)


def open_invoice_page(context, homepage, post_login_marker: str):
    pages_before = list(context.pages)
    try:
        with context.expect_page(timeout=5_000) as page_info:
            unique_visible(homepage.get_by_text(post_login_marker, exact=True), "POST_LOGIN_SELECTOR_NOT_UNIQUE", timeout=0).click()
        page_info.value.wait_for_load_state("domcontentloaded")
        return page_info.value
    except PlaywrightTimeoutError:
        pages_after = list(context.pages)
        new_pages = [page for page in pages_after if page not in pages_before]
        candidates = [page for page in new_pages if blue_invoice_visible(page)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise PocBlocked("ETAX_INVOICE_BUSINESS_PAGE_NOT_RESOLVED")
        candidates = [page for page in pages_after if page is not homepage and blue_invoice_visible(page)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) == 0 and blue_invoice_visible(homepage):
            return homepage
        raise PocBlocked("ETAX_INVOICE_BUSINESS_PAGE_NOT_RESOLVED")


def run(job_id: int) -> None:
    _load_local_env()
    job = fetch_job(job_id)
    print("status: job validated")
    start_url = os.getenv("ETAX_START_URL", "").strip()
    post_login_marker = os.getenv("ETAX_POST_LOGIN_SELECTOR", "").strip()
    if not start_url:
        raise PocBlocked("ETAX_START_URL is required before launching the real tax site")
    if os.getenv("ETAX_BROWSER", "chrome").strip().lower() != "chrome":
        raise PocBlocked("ETAX_BROWSER must be chrome")
    attach_mode = os.getenv("ETAX_BROWSER_MODE", "launch").strip().lower() == "attach"
    chrome_path = chrome_executable()
    profile_dir = Path(os.getenv("ETAX_PROFILE_DIR", str(Path(__file__).resolve().parents[1] / "browser-profile-chrome"))).resolve()
    with sync_playwright() as playwright:
        if attach_mode:
            context = attached_context(playwright)
            failures, console, page_errors = attach_blue_invoice_diagnostics(context)
            try:
                page, state = live_tax_page(context, post_login_marker)
            except PocBlocked:
                print("请在开票专用 Chrome 中完成 U盾登录和人员身份选择，然后重新执行/继续。")
                raise
            original_host = urlsplit(page.url).netloc
            print(f"CURRENT_ETAX_STAGE = {state}")
            if state == "DPP":
                page_title = enter_dpp_invoice_form(page)
                print(f"Invoice entry page reached. title: {page_title}")
                blue_invoice_diagnostics(context, page, original_host, failures, console, page_errors)
                return
            invoice_page = page if state == "INVOICE_BUSINESS" else open_invoice_page(context, page, post_login_marker)
            page_title = navigate_to_invoice_entry(invoice_page)
            print(f"Invoice entry page reached. title: {page_title}")
            wait_for_dpp_initialization(context)
            blue_invoice_diagnostics(context, invoice_page, original_host, failures, console, page_errors)
            return
        context = playwright.chromium.launch_persistent_context(str(profile_dir), executable_path=str(chrome_path), headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        failures, console, page_errors = attach_blue_invoice_diagnostics(context)
        page.goto(start_url, wait_until="domcontentloaded")
        if not post_login_marker:
            raise PocBlocked("ETAX_POST_LOGIN_SELECTOR is required; no tax-page marker was guessed")
        print("Waiting for manual U-shield login and personnel identity selection...")
        original_url = page.url
        original_host = urlsplit(original_url).netloc
        try:
            wait_for_logged_in_home(page, failures, post_login_marker)
            invoice_page = open_invoice_page(context, page, post_login_marker)
            page_title = navigate_to_invoice_entry(invoice_page)
        except PlaywrightTimeoutError as error:
            page_diagnostics(context, page, original_url)
            blue_invoice_diagnostics(context, page, original_host, failures, console, page_errors)
            input("Navigation blocked. Browser remains open for inspection; press Enter to exit: ")
            raise PocBlocked("ETAX_NAVIGATION_TIMEOUT") from error
        except PocBlocked:
            page_diagnostics(context, page, original_url)
            blue_invoice_diagnostics(context, page, original_host, failures, console, page_errors)
            input("Navigation blocked. Browser remains open for inspection; press Enter to exit: ")
            raise
        print(f"Invoice entry page reached. title: {page_title}")
        wait_for_dpp_initialization(context)
        blue_invoice_diagnostics(context, invoice_page, original_host, failures, console, page_errors)
        input("No invoice fields were filled. Browser remains open for inspection; press Enter to exit: ")


def main() -> None:
    parser = argparse.ArgumentParser(description="ETax POC that stops before final invoice submission")
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()
    try:
        run(args.job_id)
    except PocBlocked as error:
        print(f"status: blocked ({error})")


if __name__ == "__main__":
    main()
