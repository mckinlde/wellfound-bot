"""
https://www.wellcare.com/en/medicare
^^ This is where it begins

https://www.wellcare.com/en/washington/find-my-plan
^^ maybe just every state, but this takes ZIPs

and gives list of plan details pages:
https://www.wellcare.com/en/washington/members/medicare-plans-2025/wellcare-mutual-of-omaha-premium-enhanced-open-ppo-007

Ta-da, all the links on there

corresponding row:
WA,Asotin,53,99401,Wellcare,Wellcare Mutual of Omaha Premium Enhanced Open (PPO),Medicare Advantage with drug coverage,H5965-007-0,https://www.medicare.gov/plan-compare/#/plan-details/2025-H5965-007-0?fips=53003&plan_type=PLAN_TYPE_MAPD&zip=99401&year=2025&lang=en&page=1

{state}/members/medicare-plans-2025/{plan_name_spaces_to_hyphens}+{plan_id[20++]}
"""

#!/usr/bin/env python3
"""
centene_pdf_grabber.py

Reads plan IDs from centene_plan_links.csv, visits the centene plan page, and downloads
key documents (SB, EOC, Formulary, ANOC in EN/ES).

Features:
- Progress indication using global 1-based index: [(i/total)] PLAN_ID
- Resume by progress index: --start-n and --stop-n (1-based, inclusive)
- Skips already-downloaded PDFs
- Polite delays; downloads via requests Session cloned from Selenium driver
"""

import sys, re, os
import argparse
from time import sleep
from urllib.parse import urljoin
import logging

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# if you want to keep relative imports
# If you always run the script directly (python medicare/centene/centene_pdf_grabber.py from the project root), you can instead do:
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# That forces Python to see the project root, no matter where you launch from.
from utils.driver_session import start_driver
from utils.SPA_utils import make_requests_session_from_driver
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

BASE_ORIGIN = "https://www.wellcare.com/en/medicare"
BASE_URL = f"{BASE_ORIGIN}"
OUTPUT_DIR = "centene_PDFs"

LOG_DIR = "medicare/centene/testrun/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = "medicare/centene/testrun/centene_pdf_grabber.log"
logger = logging.getLogger("centene_pdf_grabber")


DOC_LABELS = [
    "Summary of Benefits",
    "Evidence of Coverage",
    "Provider directory",
]




def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


def get_enrollment_pdfs(driver, timeout=10, base_url="https://healthy.centenepermanente.org"):
    """
    Scrapes the Enrollment Materials tab for Summary of Benefits, 
    Evidence of Coverage, and Drug Formulary PDF links.
    
    Returns a dict of {label: url}
    """
    wait = WebDriverWait(driver, timeout)
    pdfs = {}

    # --- Summary of Benefits ---
    try:
        sob_link = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#benefitSummaryWrapper ul.region-document a")
            )
        )
        pdfs["Summary of Benefits"] = sob_link.get_attribute("href")
    except Exception:
        pdfs["Summary of Benefits"] = None

    # --- Evidence of Coverage ---
    try:
        eoc_link = driver.find_element(By.CSS_SELECTOR, "#evidenceWrapper ul.region-document a")
        pdfs["Evidence of Coverage"] = eoc_link.get_attribute("href")
    except Exception:
        pdfs["Evidence of Coverage"] = None

    # --- Drug Formulary ---
    try:
        formulary_link = driver.find_element(
            By.XPATH, '//a[contains(@href, "/formularies/medicare/2025/")]'
        )
        pdfs["Drug Formulary"] = formulary_link.get_attribute("href")
    except Exception:
        pdfs["Drug Formulary"] = None

    # normalize URLs (if relative paths like "/content/dam/...")
    for key, val in pdfs.items():
        if val and val.startswith("/"):
            pdfs[key] = base_url.rstrip("/") + val

    return pdfs


# ToDo: wire this in to wait_scroll_interact, etc.
def click_when_ready(driver, button_locator, timeout=15):
    wait = WebDriverWait(driver, timeout)

    # Wait for the loading indicator to disappear
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading-indicator")))

    # Wait for the button to be clickable
    button = wait.until(EC.element_to_be_clickable(button_locator))

    button.click()
    """usage:
    click_when_ready(
        driver,
        (By.CSS_SELECTOR, "#plan-details-btn-2")  # or whatever locator you use
    )
    """


def scrape_plan_pdfs(driver, zip_code: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)
    
    # Note: the page uses a lot of dynamic loading; we need to wait for elements to appear
    sleep(10)  # initial wait for page to load
    # After pageload, scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(10)  # wait for lazy load
    
    # Fill Zip code
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[name="zipcodeValue"]', action="send_keys", keys=zip_code, timeout=10)
    # Small pause to let the dropdown populate
    sleep(10)
    # Now select the first suggestion
    select_first_zipcode_suggestion(driver, timeout=8)
    sleep(10) # Wait for pageload
    # And click Explore Plans
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[id="explorePlansBtnText"]', action="click", timeout=10)
    sleep(10)
    # We should now be at plan list page, find the plan Name that matches
    # and click that plan's plan details button
    click_plan_details(driver, plan_name)
    sleep(10)

    # then we should be at the plan details page
    # click into the enrollment materials tab
    click_enrollment_materials_tab(driver)
    sleep(10)

    # and get the PDF links
    pdf_links = get_enrollment_pdfs(driver)
    # print(pdf_links)
    return pdf_links



def download_pdf(session, url: str, out_path: str):
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"    [OK] {os.path.basename(out_path)}")
        logger.info(f"    [OK] {os.path.basename(out_path)}")
    except Exception as e:
        logger.error(f"    [ERROR] {url}: {e}")
        print(f"    [ERROR] {url}: {e}")


def main(start_n: int, stop_n: int | None):
    plans = load_plan_details()
    total = len(plans)
    if total == 0:
        print("[ERROR] No plans found in centene_plan_links.csv")
        logger.error("[ERROR] No plans found in centene_plan_links.csv")
        return

    # Normalize 1-based indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    start_idx = start_n - 1
    stop_idx = stop_n  # slice end is exclusive

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")
    logger.info(f"[INFO] Total plans: {total}")
    logger.info(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for i in range(start_idx, stop_idx):
            zip_code, plan_name, plan_id = plans[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id} {plan_name} ({zip_code})")
            logger.info(f"[INFO] ({i+1}/{total}) {plan_id} {plan_name} ({zip_code})")

            pdfs = scrape_plan_pdfs(driver, zip_code, plan_name, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                logger.info("    [WARN] No PDFs found")
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    logger.info(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)

            sleep(2.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download centene Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
