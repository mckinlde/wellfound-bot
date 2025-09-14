#!/usr/bin/env python3
"""
ccfs_lookup.py — Scraper for WA CCFS by UBI

Workflow:
1. Reads UBIs from constants/Business Search Result.csv
2. For each UBI:
   - Opens CCFS search
   - Saves list.html (search results)
   - Clicks the *first row only* (one detail page per UBI)
   - Saves detail_row1.html
   - Parses into structured JSON (expandable)
   - Writes {UBI}.json into business_json/
   - Appends flattened row into Business Details.csv
   
📌 Key Goals
Don’t lose data — If there’s a field we’ve never seen before, capture it anyway.
Stay expandable — As CCFS evolves, we can adapt without rewriting all the scraping/parsing logic.
Process at scale — Thousands of UBIs means we need consistency and resilience.

🔑 Improvements
No more row 2 bug → only the first row is clicked (one detail per UBI).
Expandable JSON → every section/field/table captured dynamically.
CSV stays stable → known fields flattened, extras still preserved in JSON.
Resilient SPA navigation → explicit waits + small pauses to let Angular render.
Three artifacts per UBI:
Raw HTML (list/detail)
{UBI}.json
CSV row (flattened)
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

from utils.driver_session import start_driver

# Constants
BASE_URL = "https://ccfs.sos.wa.gov/#/BusinessSearch"
INPUT_CSV = Path("wa_corps/constants/Business Search Result.csv")
OUTPUT_CSV = Path("wa_corps/Business Details.csv")
HTML_CAPTURE_DIR = Path("wa_corps/html_captures")
JSON_OUTPUT_DIR = Path("wa_corps/business_json")
WAIT_TIME = 15

HTML_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_html(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def parse_detail_html(html: str, ubi: str) -> dict:
    """Parse the detail page HTML into a structured JSON dict."""
    soup = BeautifulSoup(html, "html.parser")
    data = {"UBI": ubi, "sections": {}}

    # Identify all section headers
    for header in soup.select("div.div_header"):
        section_name = header.get_text(strip=True)
        section = {}

        # Capture all rows under this section
        rows = header.find_next("div", class_="row-margin")
        if not rows:
            continue

        # If the section has a table (like Governors)
        table = rows.find("table")
        if table:
            section_rows = []
            for tr in table.select("tbody tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    section_rows.append(cells)
            section["rows"] = section_rows

        else:
            # Otherwise, assume simple label:value pairs
            labels = rows.find_all("div", class_="col-md-3")
            values = rows.find_all("div", class_="col-md-3")
            pairs = {}
            for i in range(0, len(values), 2):
                label = values[i].get_text(strip=True).rstrip(":")
                value = values[i + 1].get_text(strip=True) if i + 1 < len(values) else ""
                pairs[label] = value
            if pairs:
                section["fields"] = pairs

        data["sections"][section_name] = section

    return data


def flatten_for_csv(json_data: dict) -> dict:
    """Flatten the JSON into stable CSV columns."""
    sections = json_data.get("sections", {})
    business_info = sections.get("Business Information", {}).get("fields", {})
    principal_office = sections.get("Business Information", {}).get("fields", {})
    registered_agent = sections.get("Registered Agent Information", {}).get("fields", {})
    governors = sections.get("Governors", {}).get("rows", [])

    return {
        "UBI": json_data.get("UBI", ""),
        "Business Name": business_info.get("Business Name", ""),
        "Business Type": business_info.get("Business Type", ""),
        "Status": business_info.get("Business Status", ""),
        "Registered Agent": registered_agent.get("Registered Agent Name", ""),
        "Principal Office": business_info.get("Principal Office Street Address", ""),
        "Mailing Address": business_info.get("Principal Office Mailing Address", ""),
        "Nature of Business": business_info.get("Nature of Business", ""),
        "Governors": "; ".join([", ".join(row) for row in governors]) if governors else "",
    }


def process_ubi(driver, ubi: str):
    ubi_clean = ubi.replace(" ", "")
    ubi_dir = HTML_CAPTURE_DIR / ubi_clean

    print(f"[INFO] Processing UBI {ubi}...")
    driver.get(BASE_URL)

    try:
        # Wait for UBI input
        search_input = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='UBI, Business Name, or Registered Agent']"))
        )
        search_input.clear()
        search_input.send_keys(ubi)

        # Click search
        search_btn = driver.find_element(By.XPATH, "//button[contains(., 'Search')]")
        search_btn.click()

        # Wait for results table
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table"))
        )
        time.sleep(2)  # extra pause for SPA rendering

        # Save list HTML
        list_html = driver.page_source
        list_path = save_html(ubi_dir / "list.html", list_html)
        print(f"[DEBUG] Saved list HTML → {list_path}")

        # Click first result only
        try:
            first_link = driver.find_element(By.CSS_SELECTOR, "table.table tbody tr td a.btn-link")
            business_name = first_link.text.strip()
            print(f"[INFO] Clicking first row: {business_name}")
            first_link.click()
        except NoSuchElementException:
            print(f"[WARN] No results found for UBI {ubi}")
            return None, None

        # Wait for detail view
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#divBusinessInformation"))
        )
        time.sleep(2)  # allow SPA load

        # Save detail HTML
        detail_html = driver.page_source
        detail_path = save_html(ubi_dir / "detail_row1.html", detail_html)
        print(f"[DEBUG] Saved detail HTML → {detail_path}")

        # Parse detail page
        json_data = parse_detail_html(detail_html, ubi)
        json_data["capture_paths"] = {
            "list_html": str(list_path),
            "detail_html": str(detail_path),
        }

        # Write JSON file
        json_out = JSON_OUTPUT_DIR / f"{ubi_clean}.json"
        json_out.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
        print(f"[INFO] Wrote JSON → {json_out}")

        # Flatten for CSV
        row = flatten_for_csv(json_data)
        row["list_capture_path"] = str(list_path)
        row["detail_capture_path"] = str(detail_path)

        return row, json_data

    except TimeoutException:
        print(f"[ERROR] Timeout while processing UBI {ubi}")
        return None, None


def main():
    # Load UBIs from input CSV
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ubis = [row["UBI"].strip() for row in reader if row.get("UBI")]

    # Open CSV for append
    csv_file = OUTPUT_CSV.open("a", newline="", encoding="utf-8")
    writer = None

    with start_driver() as driver:
        for ubi in ubis:
            row, _ = process_ubi(driver, ubi)
            if row:
                if writer is None:
                    writer = csv.DictWriter(csv_file, fieldnames=row.keys())
                    if OUTPUT_CSV.stat().st_size == 0:
                        writer.writeheader()
                writer.writerow(row)
                csv_file.flush()

    csv_file.close()


if __name__ == "__main__":
    main()
