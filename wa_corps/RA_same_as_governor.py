# ccfs_lookup.py
"""
Scraper for WA Secretary of State CCFS (Corporations & Charities Filing System).
- Reads UBI numbers from input CSV.
- For each UBI, caches business search results and scrapes detail pages.
- Outputs results into a CSV with governors, filing history, etc.

Dependencies:
- Selenium
- BeautifulSoup4
- utils.driver_session.start_driver
- utils.SPA_utils.wait_scroll_interact
"""

import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.driver_session import start_driver
from utils.SPA_utils import wait_scroll_interact

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
CSV_PATH = Path("constants/Business Search Result.csv")
OUTPUT_PATH = Path("constants/Business Details.csv")

URL = "https://ccfs.sos.wa.gov/#/Home"

FIELDNAMES = [
    "UBI", "Business ID", "Business Name", "Business Type", "Status",
    "Registered Agent", "Principal Office", "Mailing Address",
    "Nature of Business", "Governors", "Filing History", "Detail URL"
]

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def read_ubi_numbers():
    """Yield UBI numbers from the input CSV."""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ubi = row.get("UBI#", "").strip()
            if ubi:
                yield ubi


def get_already_processed():
    """Return set of UBIs already scraped (Governors column populated)."""
    if not OUTPUT_PATH.exists():
        return set()

    processed = set()
    with open(OUTPUT_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ubi = row.get("UBI")
            if ubi and row.get("Governors", "").strip():
                processed.add(ubi)
    return processed


def cache_business_links(driver, ubi):
    """Perform search by UBI and return list of result rows (with detail URLs)."""
    driver.get(URL)

    wait_scroll_interact(driver, By.CSS_SELECTOR, "input#UBINumber", action="send_keys", keys=ubi)
    wait_scroll_interact(driver, By.CSS_SELECTOR, "button.btn-search", action="click")

    WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
    )

    links = []
    for row in driver.find_elements(By.CSS_SELECTOR, "table tbody tr"):
        link = row.find_element(By.CSS_SELECTOR, "td a")
        business_name = link.text.strip()
        cells = [td.text.strip() for td in row.find_elements(By.CSS_SELECTOR, "td")]

        # Extract BusinessID and Type from ng-click
        ng_click = link.get_attribute("ng-click")
        match = re.search(r"showBusineInfo\((\d+),\s*'([^']+)'\)", ng_click)
        if not match:
            continue
        business_id, business_type = match.groups()

        detail_url = f"https://ccfs.sos.wa.gov/#/BusinessSearch/BusinessInformation/{business_id}"
        links.append({
            "UBI": ubi,
            "Business Name": business_name,
            "Business Type": business_type,
            "Business ID": business_id,
            "Detail URL": detail_url,
            "Status": cells[-1] if cells else None,
        })
    return links


def parse_business_detail(html):
    """Extract structured business details from detail page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    safe_text = lambda sel: (soup.select_one(sel).get_text(strip=True) if soup.select_one(sel) else None)

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


def process_ubi(ubi):
    """Scrape all business detail records for a given UBI."""
    # First: collect business search result links
    with start_driver() as driver:
        links = cache_business_links(driver, ubi)

    # Then: open each detail page in a new session
    results = []
    with start_driver() as driver:
        for link in links:
            print(f"[INFO] Fetching {link['Business Name']} at {link['Detail URL']}")
            driver.get(link["Detail URL"])
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.businessDetail"))
            )
            details = parse_business_detail(driver.page_source)
            details.update(link)  # merge with search row data
            results.append(details)
    return results


def write_results(results):
    """Append scraped results to CSV."""
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
            write_results(results)
            print(f"[INFO] Wrote {len(results)} records for UBI {ubi}")
        except Exception as e:
            print(f"[ERROR] Failed for {ubi}: {e}")


if __name__ == "__main__":
    main()
