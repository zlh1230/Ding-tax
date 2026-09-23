"""Thin CLI wrapper for the snapshot-derived ETax workflow."""

import argparse

from etax.browser import AttachedEtaxBrowser, EtaxBlocked
from etax.workflow import EtaxInvoiceWorkflow
from poc_etax import _load_local_env, fetch_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Stops before final invoice issuance")
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--normalize-only", action="store_true")
    args = parser.parse_args()
    try:
        _load_local_env()
        browser = AttachedEtaxBrowser.attach()
        if args.normalize_only:
            browser.normalize_start_state()
            print("NORMALIZE_START_STATE = PASS")
            return
        result = EtaxInvoiceWorkflow(browser).run(fetch_job(args.job_id))
        print(f"STOPPED_BEFORE_ISSUE = {'YES' if result.stopped_before_issue else 'NO'}")
    except EtaxBlocked as error:
        print(f"status: blocked ({error})")


if __name__ == "__main__":
    main()
