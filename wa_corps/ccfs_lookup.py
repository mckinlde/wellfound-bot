# ccfs_lookup.py

import csv
import time
from pathlib import Path
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.driver_session import start_driver, save_page_html, write_html_to_file
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
CAPTURE_DIR = BASE_DIR / "html_captures"

CSV_PATH = BASE_DIR / "constants/Business Search Result.csv"
OUTPUT_PATH = BASE_DIR / "constants/Business Details.csv"

URL = "https://ccfs.sos.wa.gov/#/Home"
DEBUG_SLEEP = 3

FIELDNAMES = [
    "UBI", "Business Name", "Business Type", "Status",
    "Registered Agent", "Principal Office", "Mailing Address",
    "Nature of Business", "Governors", "Filing History",
    "list_capture_path", "detail_capture_path", "debug_path"
]

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def ubi_capture_dir(ubi: str) -> Path:
    d = CAPTURE_DIR / ubi.replace(" ", "")
    d.mkdir(parents=True, exist_ok=True)
    return d


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
        "Business Name": safe_text("div#divBusinessInformation strong[data-ng-bind='businessInfo.BusinessName']") or safe_text("div.businessDetail h3"),
        "Status": safe_text("div#divBusinessInformation strong[data-ng-bind*='BusinessStatus']"),
        "Registered Agent": safe_text("div#divBusinessInformation b.ng-binding"),
        "Principal Office": safe_text("div#divBusinessInformation strong[data-ng-bind*='PrincipalOffice.PrincipalStreetAddress']"),
        "Mailing Address": safe_text("div#divBusinessInformation strong[data-ng-bind*='PrincipalOffice.PrincipalMailingAddress']"),
        "Nature of Business": safe_text("div#divBusinessInformation strong[ng-bind*='BINAICSCodeDesc']"),
        "Governors": [[td.get_text(strip=True) for td in row.select("td")]
                      for row in soup.select("div#divBusinessInformation table tbody tr")],
        "Filing History": []  # not present in this capture but stubbed
    }
    return details


# -------------------------------------------------------------------
# Core Scraper
# -------------------------------------------------------------------
def process_ubi(ubi):
    results = []
    with start_driver() as driver:
        capdir = ubi_capture_dir(ubi)

        # Navigate to homepage
        driver.get(URL)
        if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

        # Enter UBI and search
        wait_scroll_interact(driver, By.CSS_SELECTOR, "input#UBINumber",
                             action="send_keys", keys=ubi)
        wait_scroll_interact(driver, By.CSS_SELECTOR, "button.btn-search", action="click")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

        # Save the list page
        list_html = driver.page_source
        list_path = write_html_to_file(list_html, capdir / "list.html")
        print(f"[DEBUG] Saved list HTML to {list_path}")

        # Iterate over result rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for idx in range(len(rows)):
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                link_el = rows[idx].find_element(By.CSS_SELECTOR, "td a")
                business_name = link_el.text.strip()
                print(f"[INFO] Clicking row {idx+1}: {business_name}")

                driver.execute_script("arguments[0].click();", link_el)
                if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

                # Wait for detail page
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.ID, "divBusinessInformation"))
                )
                if DEBUG_SLEEP: time.sleep(DEBUG_SLEEP)

                # Save detail HTML
                detail_html = driver.page_source
                detail_file = capdir / f"detail_row{idx+1}.html"
                detail_path = write_html_to_file(detail_html, detail_file)
                print(f"[DEBUG] Saved detail HTML to {detail_path}")

                details = parse_business_detail(detail_html)
                details.update({
                    "UBI": ubi,
                    "list_capture_path": str(list_path),
                    "detail_capture_path": str(detail_path),
                    "debug_path": str(detail_path),  # reuse for now
                })
                results.append(details)

                # Try to return
                try:
                    back_btn = driver.find_element(By.ID, "btnReturnToSearch")
                    _safe_click_element(driver, back_btn)
                except Exception:
                    print("[WARN] btnReturnToSearch not found, using driver.back()")
                    driver.back()

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
            writer.writeheade
