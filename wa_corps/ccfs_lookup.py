#!/usr/bin/env python3
"""
ccfs_lookup.py – Washington CCFS business details scraper
"""

import csv
import time
from pathlib import Path
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from driver_session import start_driver

# Paths
BASE_DIR = Path(__file__).parent
CONSTANTS_DIR = BASE_DIR / "constants"
UBI_FILE = CONSTANTS_DIR / "Business Search Result.csv"
OUTPUT_FILE = BASE_DIR / "Business Details.csv"
CAPTURE_DIR = BASE_DIR / "html_captures"

# Helpers
def save_html(driver, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    return str(path)

def parse_business_detail(html_path):
    """Extract fields from saved detail page HTML."""
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    data = {}
    def text_after(label):
        el = soup.find(string=lambda s: s and label in s)
        if el:
            nxt = el.find_next("strong")
            if nxt:
                return nxt.get_text(strip=True)
        return ""

    data["Business Name"] = text_after("Business Name:")
    data["UBI"] = text_after("UBI Number:")
    data["Business Type"] = text_after("Business Type:")
    data["Status"] = text_after("Business Status:")
    data["Principal Office"] = text_after("Principal Office Street Address:")
    data["Mailing Address"] = text_after("Principal Office Mailing Address:")
    data["Nature of Business"] = text_after("Nature of Business:")

    # Registered Agent (inside its section)
    agent_section = soup.find("div", class_="div_header", string=lambda s: s and "Registered Agent Information" in s)
    if agent_section:
        agent_block = agent_section.find_parent("div", class_="row-margin")
        if agent_block:
            name_el = agent_block.find("b")
            addr_el = agent_block.find("strong")
            data["Registered Agent"] = (name_el.get_text(strip=True) if name_el else "")
            # optionally capture address
            if addr_el:
                data["Registered Agent Address"] = addr_el.get_text(strip=True)

    # Governors (table rows)
    governors_section = soup.find("div", class_="div_header", string=lambda s: s and "Governors" in s)
    governors = []
    if governors_section:
        table = governors_section.find_next("table")
        if table:
            for tr in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if cells:
                    governors.append(" | ".join(cells))
    data["Governors"] = "; ".join(governors)

    return data

def process_ubi(driver, ubi, writer, seen):
    print(f"[INFO] Processing UBI {ubi}...")

    # Search
    driver.get("https://ccfs.sos.wa.gov/#/BusinessSearch")
    box = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "businessSearchCriteria")))
    box.clear()
    box.send_keys(ubi)
    box.submit()

    # Wait for list
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
    list_path = CAPTURE_DIR / ubi.replace(" ", "") / "list.html"
    save_html(driver, list_path)
    print(f"[DEBUG] Saved list HTML to {list_path}")

    rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
    for i, row in enumerate(rows, start=1):
        try:
            link = row.find_element(By.CSS_SELECTOR, "td a")
        except NoSuchElementException:
            continue

        name = link.text.strip()
        print(f"[INFO] Clicking row {i}: {name}")
        link.click()

        # Wait for detail page
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "divBusinessInformation")))
        detail_path = CAPTURE_DIR / ubi.replace(" ", "") / f"detail_row{i}.html"
        save_html(driver, detail_path)
        print(f"[DEBUG] Saved detail HTML to {detail_path}")

        # Parse
        record = parse_business_detail(detail_path)
        record.update({
            "list_capture_path": str(list_path),
            "detail_capture_path": str(detail_path),
            "debug_path": str(detail_path)
        })
        writer.writerow(record)
        seen.add(ubi)

        # Return to list if more rows
        if i < len(rows):
            try:
                back_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "btnReturnToSearch"))
                )
                back_btn.click()
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
                rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
            except TimeoutException:
                print("[WARN] Could not return to search list")

    print(f"[INFO] Wrote {len(rows)} records for UBI {ubi}")

def main():
    # Load UBIs from Business Search Result.csv
    with open(UBI_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ubis = [row["UBI#"].strip() for row in reader if row.get("UBI#")]

    seen = set()
    fieldnames = [
        "UBI","Business Name","Business Type","Status",
        "Registered Agent","Registered Agent Address",
        "Principal Office","Mailing Address","Nature of Business","Governors",
        "list_capture_path","detail_capture_path","debug_path"
    ]
    write_header = not OUTPUT_FILE.exists()

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as outcsv:
        writer = csv.DictWriter(outcsv, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        with start_driver() as driver:
            for ubi in ubis:
                if ubi in seen:
                    print(f"[INFO] Already processed {ubi}.")
                    continue
                try:
                    process_ubi(driver, ubi, writer, seen)
                except Exception as e:
                    print(f"[ERROR] Failed {ubi}: {e}")

if __name__ == "__main__":
    main()
