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

{state}/members/medicare-plans-2025/{plan_name_spaces_to_hyphens}-{plan_id[1]}

https://www.wellcare.com/en/washington/members/medicare-plans-2025/wellcare-mutual-of-omaha-premium-enhanced-open-ppo-007

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
import csv
import re
import json

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

LOG_DIR = "testrun/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = "testrun/centene_pdf_grabber.log"
logger = logging.getLogger("centene_pdf_grabber")

def save_metadata(metadata: dict, out_dir: str, success_count=0, fail_count=0,
                  plans_succeeded=None, plans_failed=None):
    """Save metadata dict to JSON and CSV, with success/failure stats."""
    os.makedirs(out_dir, exist_ok=True)

    summary = {
        "total_plans": len(metadata),
        "success_count": success_count,
        "fail_count": fail_count,
        "plans_succeeded": plans_succeeded or [],
        "plans_failed": plans_failed or [],
        "files": metadata
    }

    # JSON
    json_path = os.path.join(out_dir, "centene_metadata.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(summary, jf, indent=2, ensure_ascii=False)
    print(f"[INFO] Metadata saved to {json_path}")

    # CSV
    csv_path = os.path.join(out_dir, "centene_metadata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        writer = csv.writer(cf)
        writer.writerow(["plan_id", "status", "label", "url"])
        for plan_id, files in metadata.items():
            status = "success" if plan_id in (plans_succeeded or []) else "failed"
            for label, url in files.items():
                writer.writerow([plan_id, label, url, status])
    print(f"[INFO] Metadata saved to {csv_path}")


state_options = {
    "AL":"Alabama",
    "AK":"Alaska",
    "AZ":"Arizona",
    "AR":"Arkansas",
    "CA":"California",
    "CO":"Colorado",
    "CT":"Connecticut",
    "DE":"Delaware",
    "DC":"District of Columbia",
    "FL":"Florida",
    "GA":"Georgia",
    "HI":"Hawaii",
    "ID":"Idaho",
    "IL":"Illinois",
    "IN":"Indiana",
    "IA":"Iowa",
    "KS":"Kansas",
    "KY":"Kentucky",
    "LA":"Louisiana",
    "ME":"Maine",
    "MD":"Maryland",
    "MA":"Massachusetts",
    "MI":"Michigan",
    "MN":"Minnesota",
    "MS":"Mississippi",
    "MO":"Missouri",
    "MT":"Montana",
    "NE":"Nebraska",
    "NV":"Nevada",
    "NH":"New Hampshire",
    "NJ":"New Jersey",
    "NM":"New Mexico",
    "NY":"New York",
    "NC":"North Carolina",
    "ND":"North Dakota",
    "OH":"Ohio",
    "OK":"Oklahoma",
    "OR":"Oregon",
    "PA":"Pennsylvania",
    "RI":"Rhode Island",
    "SC":"South Carolina",
    "SD":"South Dakota",
    "TN":"Tennessee",
    "TX":"Texas",
    "UT":"Utah",
    "VT":"Vermont",
    "VA":"Virginia",
    "WA":"Washington",
    "WV":"West Virginia",
    "WI":"Wisconsin",
    "WY":"Wyoming",
}

# # unused, implemented directly in load_plan_details
# def format_plan_links(csv_path):
#     output = []
#     with open(csv_path, newline="", encoding="utf-8") as f:
#         reader = csv.reader(f)
#         for row in reader:
#             state, county, fips, zip_code, company, plan_name, plan_type, plan_id, url = row

#             # Convert state code → full state name (lowercase, spaces removed)
#             state_full = state_options.get(state, state).lower().replace(" ", "-")

#             # Normalize plan name
#             name = plan_name.lower()
#             name = re.sub(r"[()]", "", name)       # remove parentheses
#             name = re.sub(r"\s+", "-", name)       # spaces → hyphen
#             name = re.sub(r"-+", "-", name)        # collapse multiple hyphens

#             # Get 2nd segment of plan_id
#             segments = plan_id.split("-")
#             suffix = segments[1] if len(segments) > 1 else ""

#             formatted = f"{state_full}/members/medicare-plans-2025/{name}-{suffix}"
#             output.append(formatted)
#     return output

# # Example usage
# csv_file = "centene_plan_links.csv"
# for link in format_plan_links(csv_file):
#     print(link)
# input("stop")

DOC_LABELS = [
    "Summary of Benefits",
    "Evidence of Coverage",
    "Provider directory",
]


def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


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


def get_enrollment_pdfs(driver, timeout=15, scroll_pause=1.0):
    """
    Scrapes the current plan details page for ALL enrollment-related PDFs.
    Returns dict of {label: url}, with language suffixes when available.
    """
    wait = WebDriverWait(driver, timeout)
    pdfs = {}

    # Step 1: Wait for at least one container with links
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".mod-item-container")))

    # Step 2: Scroll to bottom for lazy loading
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(scroll_pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Step 3: Collect containers
    containers = driver.find_elements(By.CSS_SELECTOR, ".mod-item-container")
    for container in containers:
        try:
            # Get descriptive label text
            try:
                label = container.find_element(By.CSS_SELECTOR, ".document-title").text.strip()
            except Exception:
                label = "plan_file"

            # Normalize the label
            label = re.sub(r"\s+", "_", label)
            label = re.sub(r"[^A-Za-z0-9_]+", "", label)

            # Collect all <a> links in this container
            anchors = container.find_elements(By.TAG_NAME, "a")
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                if not (href.lower().endswith(".pdf") or href.lower().endswith(".ashx")):
                    continue

                # Detect language hints
                lang = None
                href_lower = href.lower()
                if "spanish" in href_lower or "es_" in href_lower or "/es/" in href_lower:
                    lang = "es"
                elif "english" in href_lower or "en_" in href_lower or "/en/" in href_lower:
                    lang = "en"
                if lang:
                    label_lang = f"{label}_{lang}"
                else:
                    label_lang = label

                # Handle duplicates safely
                final_label = label_lang
                counter = 2
                while final_label in pdfs:
                    final_label = f"{label_lang}_{counter}"
                    counter += 1

                # Ensure absolute URL
                if href.startswith("/"):
                    href = "https://www.wellcare.com" + href

                pdfs[final_label] = href

        except Exception as e:
            print(f"    [WARN] error parsing container: {e}")
            continue

    return pdfs


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



def load_plan_details(csv_path="centene_plan_links.csv"):
    """
    Load plan details from CSV.
    Returns a list of tuples: (zip_code, plan_name, plan_id, fragment)
    """
    plans = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            state, county, fips, zip_code, company, plan_name, plan_type, plan_id, url = row

            # State code → full name (lowercase, spaces → hyphens)
            state_full = state_options.get(state, state).lower().replace(" ", "-")

            # Normalize plan name
            name = plan_name.lower()
            name = re.sub(r"[()]", "", name)      # remove parentheses
            name = re.sub(r"\s+", "-", name)      # spaces → hyphen
            name = re.sub(r"-+", "-", name)       # collapse multiple hyphens

            # Use 2nd segment of plan_id
            segments = plan_id.split("-")
            suffix = segments[1] if len(segments) > 1 else ""

            fragment = f"{state_full}/members/medicare-plans-2025/{name}-{suffix}"
            plans.append((zip_code, plan_name, plan_id, fragment))
    return plans


def main(start_n: int, stop_n: int | None, csv_path="centene_plan_links.csv"):
    all_metadata = {}
    success_count = 0
    fail_count = 0
    plans_succeeded = []
    plans_failed = []

    plans = load_plan_details(csv_path)
    total = len(plans)
    if total == 0:
        print("[ERROR] No plans found in centene_plan_links.csv")
        logger.error("[ERROR] No plans found in centene_plan_links.csv")
        return

    # Normalize indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    start_idx = start_n - 1
    stop_idx = stop_n

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")
    logger.info(f"[INFO] Total plans: {total}")
    logger.info(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for i in range(start_idx, stop_idx):
            zip_code, plan_name, plan_id, fragment = plans[i]
            url = f"https://www.wellcare.com/en/{fragment}"

            print(f"[INFO] ({i+1}/{total}) {plan_id} {url}")
            logger.info(f"[INFO] ({i+1}/{total}) {plan_id} {url}")

            try:
                driver.get(url)
                sleep(2.0)
                pdfs = get_enrollment_pdfs(driver)
                all_metadata[plan_id] = pdfs

                if not pdfs:
                    print("    [WARN] No PDFs found")
                    logger.info("    [WARN] No PDFs found")
                    fail_count += 1
                    plans_failed.append(plan_id)
                else:
                    success_count += 1
                    plans_succeeded.append(plan_id)

                    out_dir = os.path.join(OUTPUT_DIR, plan_id)
                    os.makedirs(out_dir, exist_ok=True)

                    print(f"    [FOUND {len(pdfs)} PDFs]")
                    for label, href in pdfs.items():
                        filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                        out_path = os.path.join(out_dir, filename)

                        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                            print(f"    [SKIP] {filename} (exists)")
                            continue

                        download_pdf(session, href, out_path)
                        sleep(1.2)
            except Exception as e:
                print(f"    [ERROR] navigation failed for {plan_id} {url}: {e}")
                logger.error(f"    [ERROR] navigation failed for {plan_id} {url}: {e}")
                fail_count += 1
                plans_failed.append(plan_id)

            # ✅ Save after each plan
            save_metadata(
                all_metadata,
                LOG_DIR,
                success_count=success_count,
                fail_count=fail_count,
                plans_succeeded=plans_succeeded,
                plans_failed=plans_failed
            )

            sleep(2.5)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download centene Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
