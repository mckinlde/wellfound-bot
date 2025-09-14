#!/usr/bin/env python3
"""
ccfs_lookup.py — scrape WA CCFS by UBI.

- Reads UBIs from wa_corps/constants/Business Search Result.csv
- Navigates CCFS SPA
- Saves:
    - list.html
    - detail.html
    - structured JSON
into wa_corps/html_captures and wa_corps/business_json.

No CSV flattening. Shows progress.
"""

import csv
import json
import time
from pathlib import Path
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from driver_session import start_driver

# Paths
INPUT_CSV = Path("wa_corps/constants/Business Search Result.csv")
HTML_CAPTURE_DIR = Path("wa_corps/html_captures")
JSON_OUTPUT_DIR = Path("wa_corps/business_json")
HTML_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Config
BASE_URL = "https://ccfs.sos.wa.gov/#/BusinessSearch"
WAIT_TIME = 20


def save_html(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def parse_detail_html(html: str, ubi: str) -> dict:
    """Parse detail HTML into structured JSON (flexible/expandable)."""
    soup = BeautifulSoup(html, "html.parser")
    data = {"UBI": ubi, "sections": {}}

    for header in soup.select("div.div_header"):
        section_name = header.get_text(strip=True)
        section = {}

        # Look for tables
        table = header.find_next("table")
        if table:
            rows = []
            for tr in table.select("tbody tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                section["rows"] = rows

        # Otherwise look for fields
        else:
            fields = {}
            for row in header.find_all_next("div", class_="row"):
                cols = row.find_all("div", class_="col-md-3")
                if len(cols) == 2:
                    label = cols[0].get_text(strip=True).rstrip(":")
                    value = cols[1].get_text(strip=True)
                    if label:
                        fields[label] = value
                else:
                    break
            if fields:
                section["fields"] = fields

        data["sections"][section_name] = section

    return data


def process_ubi(driver, ubi: str, index: int, total: int):
    ubi_clean = ubi.replace(" ", "")
    ubi_dir = HTML_CAPTURE_DIR / ubi_clean

    print(f"[INFO] Processing UBI {index}/{total}: {ubi}")

    driver.get(BASE_URL)

    try:
        # Wait for search input
        search_input = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[placeholder='UBI, Business Name, or Registered Agent']")
            )
        )
        search_input.clear()
        search_input.send_keys(ubi)

        # Click Search button
        search_btn = driver.find_element(By.XPATH, "//button[contains(., 'Search')]")
        search_btn.click()

        # Wait for results table
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table"))
        )
        time.sleep(2)  # let Angular render fully

        # Save list.html
        list_html = driver.page_source
        save_html(ubi_dir / "list.html", list_html)

        # Click first result link
        try:
            first_link = driver.find_element(By.CSS_SELECTOR, "table.table tbody tr td a.btn-link")
            business_name = first_link.text.strip()
            print(f"[INFO] Clicking: {business_name}")
            first_link.click()
        except NoSuchElementException:
            print(f"[WARN] No search results for UBI {ubi}")
            return

        # Wait for detail view
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#divBusinessInformation"))
        )
        time.sleep(2)

        # Save detail.html
        detail_html = driver.page_source
        save_html(ubi_dir / "detail.html", detail_html)

        # Parse → JSON
        json_data = parse_detail_html(detail_html, ubi)
        json_data["capture_paths"] = {
            "list_html": str(ubi_dir / "list.html"),
            "detail_html": str(ubi_dir / "detail.html"),
        }

        # Save JSON
        json_out = JSON_OUTPUT_DIR / f"{ubi_clean}.json"
        json_out.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

        print(f"[INFO] Saved JSON → {json_out}")

    except TimeoutException:
        print(f"[ERROR] Timeout for UBI {ubi}")


def main():
    # Load UBIs
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ubis = [row["UBI"].strip() for row in reader if row.get("UBI")]

    total = len(ubis)
    if not total:
        print("[ERROR] No UBIs found in input CSV")
        return

    with start_driver() as driver:
        for i, ubi in enumerate(ubis, start=1):
            process_ubi(driver, ubi, i, total)


if __name__ == "__main__":
    main()
