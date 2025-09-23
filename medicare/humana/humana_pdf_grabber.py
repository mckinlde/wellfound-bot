# https://plans.humana.com/

#!/usr/bin/env python3
"""
humana_pdf_grabber.py

Reads plan IDs from humana_plan_links.csv, visits the humana plan page, and downloads
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

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# if you want to keep relative imports
# If you always run the script directly (python medicare/humana/humana_pdf_grabber.py from the project root), you can instead do:
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# That forces Python to see the project root, no matter where you launch from.
from utils.driver_session import start_driver
from utils.SPA_utils import make_requests_session_from_driver
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

BASE_ORIGIN = "https://plans.humana.com/"
BASE_URL = f"{BASE_ORIGIN}"
OUTPUT_DIR = "humana_PDFs"

DOC_LABELS = [
    "Summary of Benefits",
    "Evidence of Coverage",
    "CMS plan ratings",
]


def load_plan_details(csv_path="medicare/humana/humana_plan_links.csv"):
    """Return list of (zip, plan_name, plan_id) tuples, deduplicated, CSV order preserved."""
    df = pd.read_csv(csv_path, dtype=str)

    # normalize column names in case there's a mismatch
    df = df.rename(columns={"zip": "zip_code"})

    df = df.drop_duplicates(subset=["zip_code", "plan_name", "plan_id"])
    plans = list(df[["zip_code", "plan_name", "plan_id"]].itertuples(index=False, name=None))
    return plans


def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


def scrape_plan_pdfs(driver, zip_code: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)

    ### Resume work here: fill in zip_code, submit form, wait for page load
    # Note: the page uses a lot of dynamic loading; we need to wait for elements to appear
    sleep(2.0)  # initial wait for page to load
    # <input data-v-37ca5262="" data-maska="#####" data-mask-input="" id="ZIP code" type="text" pattern="[0-9]{5}" required="" autocomplete="postal-code" autocapitalize="none" spellcheck="false" autocorrect="off" inputmode="numeric" aria-invalid="false" mptid="INPUT;mptid:0;0">
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[id="ZIP code"]', action="send_keys", keys=zip_code, timeout=10)
    sleep(0.5)
    # <button data-v-997824cf="" class="nb-btn nb-btn--primary is-small zcf-btn" type="submit" data-search-button=""><span data-v-997824cf="">Get Started</span><!----></button>
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-search-button]', action="click", timeout=10)
    sleep(3.0)  # wait for page to load
    # if it appears, click the type of medicare plan
    # <nucleus-radio-button data-v-cae155e3="" class="coverage-detail is-selection-card selection-card coverage-type-answer nucleus-radio-selection-card" data-medicare-advantage="" name="medicareAdvantage" value="medicareAdvantage" style="padding: 0.5rem;"><div data-v-cae155e3="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-cae155e3="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-cae155e3="" class="coverage-detail-title">Medicare Advantage <span data-v-cae155e3="" class="caption $nt-color-font-heading nu-d-block">(Part C)</span></div><p data-v-cae155e3="" slot:description="" class="nu-d-none md:nu-d-flex">Includes all the benefits of Original Medicare Part A and Part B, and many include coverage for prescription drugs and routine dental, vision and hearing care</p></nucleus-radio-button>
    try:
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="medicareAdvantage"]', action="click", timeout=5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # input("Enter to continue 1...")
        # then click the none applied checkbox
        # <nucleus-checkbox data-v-f4c10c2c="" class="inline-flex" name="noneApplies"> None of these apply to me </nucleus-checkbox>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-checkbox[name="noneApplies"]', action="click", timeout=5)
        sleep(0.5)
        # input("Enter to continue 2...")
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # input("Enter to continue 3...")
        # then skip selecting a plan type
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(0.5)
        # input("Enter to continue 4...")
        # then skip adding doctors
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(0.5)
        # input("Enter to continue 5...")
        # and skip adding prescriptions
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(3.0)  # wait for page to load
    except Exception:
        pass  # if it doesn't appear, continue  
    
    # Switch to "All plans" tab if present
    try:
        all_plans_tab = driver.find_element(By.CSS_SELECTOR, "nucleus-tab[data-skip-to-plans]")
        _safe_click_element(driver, all_plans_tab)
        sleep(2.0)  # wait for content to refresh
    except Exception:
        pass  # if already in All plans or element missing

    # After pageload, scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    input("Enter to continue plan_list_page...")
    # Then find the div with matching plan_id
    # <div class="plan ma" id="" data-mfe-plancard="" data-plan-id="H5216-428-001-2025" data-list-medicare-plans="" idvpage="">
    plan_div = None
    try:
        plan_div = driver.find_element(By.CSS_SELECTOR, f'div[data-plan-id="{plan_id}"]')
    except Exception:
        print("    [ERROR] Could not find plan div on plan list page")
        return {}
    # and click it's "View plan details" link
    # <button data-v-9ee06d52="" class="link" style="font-size: 19px;" data-plan-link="">View plan details</button>
    # (/div/div/div[2]/div/div[3]/div[3]/div/div[2]/div/button)
    try:
        view_button = plan_div.find_element(By.CSS_SELECTOR, 'button[data-plan-link]')
        _safe_click_element(driver, view_button)
        sleep(3.0)  # wait for page to load
    except Exception:
        print("    [ERROR] Could not find or click 'View plan details' button")
        return {}
    
    # then we should be at the plan details page
    # scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # then look for the "Plan Documents" section and click to expand if needed
    # <div data-v-f27cb03a="" data-v-a6b3722d="" class="plan-summary-accordion nu-w-100" id="plan-documents"><div data-v-f27cb03a="" class="accordion-header">
    try:
        accordion_header = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]')
        accordion_content = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content')

        if "open-shadow" not in accordion_header.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)

        pdfs = {}

        def collect_links():
            rows = driver.find_elements(
                By.CSS_SELECTOR, 'div#plan-documents div.accordion-content div.data-row'
            )
            tmp = {}
            for row in rows:
                try:
                    title = row.find_element(By.CSS_SELECTOR, ".title").text.strip()
                except Exception:
                    continue
                if not any(lbl.lower() in title.lower() for lbl in DOC_LABELS):
                    continue
                links = row.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
                for link in links:
                    href = link.get_attribute("href")
                    lang = (link.text or "").strip() or "PDF"
                    key = f"{title} ({lang})"
                    tmp[key] = href
            return tmp

        pdfs = collect_links()

        # Retry-on-CAPTCHA: if nothing found, pause for manual solve and retry once
        if not pdfs:
            input("[ACTION] No PDFs found (possibly CAPTCHA). Solve it in the browser, then press Enter...")
            sleep(1.0)
            pdfs = collect_links()

        return pdfs

    except Exception:
        print("    [ERROR] Could not expand or parse 'Plan Documents' accordion")
        return {}




def download_pdf(session, url: str, out_path: str):
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"    [OK] {os.path.basename(out_path)}")
    except Exception as e:
        print(f"    [ERROR] {url}: {e}")


def main(start_n: int, stop_n: int | None):
    plans = load_plan_details()
    total = len(plans)
    if total == 0:
        print("[ERROR] No plans found in humana_plan_links.csv")
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

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for i in range(start_idx, stop_idx):
            zip_code, plan_name, plan_id = plans[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id} {plan_name} ({zip_code})")

            pdfs = scrape_plan_pdfs(driver, zip_code, plan_name, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)

            sleep(2.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download humana Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
