#!/usr/bin/env python3
"""
ccfs_lookup.py

Scrape WA Corporations & Charities Filing System (CCFS).
For each UBI in ubis.txt:
  - Run a search
  - Click each business row (if any)
  - Save list + detail HTML under wa_corps/html_captures/<UBI>/
  - Parse key business details into Business Details.csv
"""

import csv
import logging
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from driver_session import start_driver, write_html_to_file

# --- Config ---
BASE_URL = "https://ccfs.sos.wa.gov/#/BusinessSearch"
UBI_FILE = Path(__file__).parent / "ubis.txt"
OUTPUT_CSV = Path(__file__).parent / "Business Details.csv"
CAPTURE_ROOT = Path(__file__).parent / "html_captures"

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def safe_text(soup, selector: str) -> str:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else ""


def parse_business_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    governors = []
    for row in soup.select("#divBusinessInformation table tbody tr"):
        tds = [td.get_text(strip=True) for td in row.select("td")]
        if any(tds):
            governors.append(tds)

    return {
        "Business Name": safe_text(soup, "#divBusinessInformation [data-ng-bind='businessInfo.BusinessName']"),
        "Business Type": safe_text(soup, "#divBusinessInformation [data-ng-bind='businessInfo.BusinessType']"),
        "Status": safe_text(soup, "#divBusinessInformation [data-ng-bind*='BusinessStatus']"),
        "Registered Agent": safe_text(soup, "#divBusinessInformation b.ng-binding"),
        "Principal Office": safe_text(soup, "#divBusinessInformation [data-ng-bind*='PrincipalStreetAddress']"),
        "Mailing Address": safe_text(soup, "#divBusinessInformation [data-ng-bind*='PrincipalMailingAddress']"),
        "Nature of Business": safe_text(soup, "#divBusinessInformation [ng-bind*='BINAICSCodeDesc']"),
        "Governors": governors,
    }


def process_ubi(driver, ubi: str, writer: csv.DictWriter):
    logging.info(f"Processing UBI {ubi}...")
    ubi_dir = CAPTURE_ROOT / ubi.replace(" ", "")
    ensure_dir(ubi_dir)

    # Go to base URL and search for UBI
    driver.get(BASE_URL)
    time.sleep(3)
    try:
        input_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "SearchCriteria"))
        )
        input_box.clear()
        input_box.send_keys(ubi)

        search_btn = driver.find_element(By.ID, "searchButton")
        search_btn.click()
    except Exception as e:
        logging.error(f"Failed to initiate search for {ubi}: {e}")
        return

    # Wait for list
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table tbody tr"))
        )
    except Exception:
        logging.warning(f"No results for {ubi}")
        return

    # Save list HTML
    list_html = driver.page_source
    list_path = write_html_to_file(list_html, ubi_dir / "list.html")
    logging.debug(f"Saved list HTML to {list_path}")

    rows = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
    if not rows:
        logging.warning(f"No rows found for {ubi}")
        return

    for idx, row in enumerate(rows, start=1):
        try:
            name_el = row.find_element(By.CSS_SELECTOR, "td a.btn-link")
            logging.info(f"Clicking row {idx}: {name_el.text.strip()}")
            name_el.click()
        except Exception as e:
            logging.error(f"Failed to click row {idx} for {ubi}: {e}")
            continue

        # Wait for detail page
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "divBusinessInformation"))
            )
        except Exception as e:
            logging.error(f"Detail page never loaded for row {idx} {ubi}: {e}")
            continue

        detail_html = driver.page_source
        detail_path = write_html_to_file(detail_html, ubi_dir / f"detail_row{idx}.html")
        logging.debug(f"Saved detail HTML to {detail_path}")

        # Parse details
        parsed = parse_business_detail(detail_html)
        row_out = {
            "UBI": ubi,
            **parsed,
            "list_capture_path": str(list_path),
            "detail_capture_path": str(detail_path),
        }
        writer.writerow(row_out)

        # Go back (prefer Return button)
        try:
            back_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.ID, "btnReturnToSearch"))
            )
            back_btn.click()
        except Exception:
            driver.back()

        time.sleep(2)  # let Angular reset list view


def main():
    ubis = [line.strip() for line in UBI_FILE.read_text().splitlines() if line.strip()]

    ensure_dir(CAPTURE_ROOT)

    fieldnames = [
        "UBI",
        "Business Name",
        "Business Type",
        "Status",
        "Registered Agent",
        "Principal Office",
        "Mailing Address",
        "Nature of Business",
        "Governors",
        "list_capture_path",
        "detail_capture_path",
    ]

    with start_driver() as driver, OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ubi in ubis:
            process_ubi(driver, ubi, writer)
            logging.info(f"Finished {ubi}")


if __name__ == "__main__":
    main()
