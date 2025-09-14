# ccfs_lookup.py
"""
Scraper for WA Secretary of State CCFS (Corporations & Charities Filing System).

Workflow:
- Reads UBI numbers from input CSV.
- For each UBI:
    * Searches CCFS
    * Saves the list page HTML for debugging
    * Iterates through all result rows
    * Clicks into each detail page, saves HTML, parses details
    * Returns to the list and continues until all rows scraped
- Writes structured results to output CSV
- Skips UBIs already processed (Governors populated)

Every list and detail page is saved so you can debug DOM transitions.
"""

import csv
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.driver_session import start_driver, save_page_html
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
CSV_PATH = Path("constants/Business Search Result.csv")
OUTPUT_PATH = Path("constants/Business Details.csv")

URL = "https://ccfs.sos.wa.gov/#/Home"
DEBUG_SLEEP = 3  # seconds between navigation steps for visibility

FIELDNAMES = [
    "UBI", "Business Name", "Business Type", "Status",
    "Registered Agent", "Principal Office", "Mailing Address",
    "Nature of Business", "Governors", "Filing History",
    "list_capture_path", "detail_capture_path", "debug_path"
]

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def read_ubi_numbers():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ubi = row.get("UBI#", "").strip()
            if ubi:
                yield ubi


def get_already_processed():
    if not OUTPUT_PATH.exists():
        return set()
    processed = set()
    with open(OUTPUT_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("UBI") and row.get("Governors", "").strip():
                processed.add(row["UBI"])
    return processed


def parse_business_detail(html: str):
    soup = BeautifulSoup(html, "html.parser")
    safe_text = lambda sel: (soup.select_one(sel).get_text(strip=True)
                             if soup.select_one(sel) else None)

    details = {
        "Business Name": safe_text("div.businessDetail h3"),
        "Status": safe_text("div.businessDetail span.status"),
        "Registered Agent": safe_text("div#registeredAgent span.ng-binding"),
        "Principal Office": safe_text("div#principalOffice"),
        "Mailing Address": safe_text("div#mailingAddress"),
        "Nature of Business": safe_text("div#natureOfBusiness"),
        "Governors": [[td.get_text(strip=True) for td in row.select("td")]
                      for row in soup.select("table#governors tbody tr")],
        "Filing History": [[td.get_text(strip=True) for td in row.select("td")]
                           for row in soup.select("table#filingHistory tbody tr")]
    }
    return details


# -------------------------------------------------------------------
# Core Scraper
# -------------------------------------------------------------------
def process_ubi(ubi):
    results = []
    with start_driver() as driver:
        # Navigate to homepage
        driver.get(URL)
        if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

        # Enter UBI and search
        wait_scroll_interact(driver, By.CSS_SELECTOR, "input#UBINumber",
                             action="send_keys", keys=ubi)
        wait_scroll_interact(driver, By.CSS_SELECTOR, "button.btn-search",
                             action="click")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

        # Save the list page
        list_result = save_page_html(driver, driver.current_url,
                                     timeout=20, extra_settle_seconds=2)
        list_capture_path = str(list_result["capture_path"])
        print(f"[DEBUG] Saved list HTML to {list_capture_path}")

        # Iterate over result rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for idx in range(len(rows)):
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                link_el = rows[idx].find_element(By.CSS_SELECTOR, "td a")
                business_name = link_el.text.strip()
                print(f"[INFO] Clicking row {idx+1}: {business_name}")

                # Force Angular click
                driver.execute_script("arguments[0].click();", link_el)
                if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

                # Always save the page after clicking, even if wait fails
                detail_result = None
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.businessDetail"))
                    )
                    if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)
                finally:
                    detail_result = save_page_html(driver, driver.current_url,
                                                   timeout=30, extra_settle_seconds=2)
                    print(f"[DEBUG] Saved detail HTML to {detail_result['capture_path']}")

                if detail_result and detail_result["soup"]:
                    details = parse_business_detail(str(detail_result["soup"]))
                    details.update({
                        "UBI": ubi,
                        "list_capture_path": list_capture_path,
                        "detail_capture_path": str(detail_result["capture_path"]),
                        "debug_path": str(detail_result["debug_path"]),
                    })
                    results.append(details)

                # Click Back to return
                back_btn = driver.find_element(By.ID, "btnReturnToSearch")
                _safe_click_element(driver, back_btn)
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
                )
                if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

            except Exception as e:
                print(f"[ERROR] Failed row {idx+1} for {ubi}: {e}")
                continue
    return results


def write_results(results):
    file_exists = OUTPUT_PATH.exists()
    with open(OUTPUT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow({
                **r,
                "Governors": "; ".join([", ".join(g) for g in r.get("Governors", [])]),
                "Filing History": "; ".join([", ".join(f) for f in r.get("Filing History", [])]),
            })


# -------------------------------------------------------------------
# Entrypoint
# -------------------------------------------------------------------
def main():
    processed = get_already_processed()
    print(f"[INFO] Already processed {len(processed)} UBIs.")

    for ubi in read_ubi_numbers():
        if ubi in processed:
            print(f"[SKIP] UBI {ubi} already processed.")
            continue

        print(f"[INFO] Processing UBI {ubi}...")
        try:
            results = process_ubi(ubi)
            if results:
                write_results(results)
                print(f"[INFO] Wrote {len(results)} records for UBI {ubi}")
            else:
                print(f"[WARN] No results captured for {ubi}")
        except Exception as e:
            print(f"[ERROR] Failed for {ubi}: {e}")


if __name__ == "__main__":
    main()
