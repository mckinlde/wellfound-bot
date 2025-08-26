#!/usr/bin/env python3
"""
medicare_scraper.py (Medicare.gov scraper)

Usage:
  nix develop
  python3 medicare_scraper.py
"""

import pathlib
import csv
import sys
import time
from utils.driver_session import start_driver
from utils.medicare_utils import (
    fill_zip_and_click_continue,
    select_plan_type_and_continue,
    select_none_and_continue,
    select_exclude_and_next,
    scrape_all_plan_details,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------------
# CONFIG
# -------------------------
ZIPCODES_FILE = "constants/single_county_zips_final_fixed.csv"  # has cols: state,county,state_fips,zip_code
PLAN_CHOICES = ["mapd"]  # for now just medicare advantage
PLAN_LINKS_CSV = "plan_links.csv"


def save_plan_link(zip_info, company, plan_name, plan_type, plan_id, link_to_plan_page):
    """Append plan website info to a CSV, including county metadata."""
    file_exists = pathlib.Path(PLAN_LINKS_CSV).is_file()
    with open(PLAN_LINKS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "state", "county", "state_fips", "zip",
                "company", "plan_name", "plan_type", "plan_id", "link_to_plan_page"
            ])
        writer.writerow([
            zip_info.get("state", ""),
            zip_info.get("county", ""),
            zip_info.get("state_fips", ""),
            zip_info.get("zip_code", ""),
            company, plan_name, plan_type, plan_id, link_to_plan_page
        ])


def run_zipcode_plan(driver, zip_info, plan_type, progress_str, cumulative_plans):
    """Run full workflow for a single ZIP + plan type. Returns number of plans found."""
    zipcode = zip_info["zip_code"]
    print(f"\n[INFO] {progress_str} | ZIP={zipcode}, plan={plan_type}")
    sys.stdout.flush()

    start_time = time.time()

    # Load landing page fresh for each ZIP/plan
    driver.get("https://www.medicare.gov/plan-compare/#/?year=2025&lang=en")
    # Wait up to 15s for the ZIP code input to appear
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input#zipCode"))
    )

    # Step 1: ZIP → Continue
    fill_zip_and_click_continue(driver, zipcode)

    # Step 2: Select plan type → Continue
    select_plan_type_and_continue(driver, plan_type)

    # Step 3: Select LIS None → Continue
    select_none_and_continue(driver)

    # Step 4: Select drug exclude → Next
    select_exclude_and_next(driver)

    # Step 5: Scrape all plan detail pages (returns dicts including company + link)
    results = scrape_all_plan_details(driver, zipcode=zipcode)

    # Step 6: Save plan website links
    for plan in results:
        save_plan_link(
            zip_info,
            plan.get("company", ""),
            plan.get("plan_name", ""),
            plan.get("plan_type", ""),
            plan.get("plan_id", ""),
            plan.get("link_to_plan_page", ""),
        )

    elapsed = time.time() - start_time
    cumulative_plans += len(results)

    print(f"[DONE] {progress_str} | ZIP={zipcode}, plan={plan_type}, "
          f"{len(results)} plans saved, took {elapsed:.1f}s | "
          f"Cumulative plans so far: {cumulative_plans}")
    sys.stdout.flush()

    return cumulative_plans

def main():
    # Load ZIP codes with full row dicts
    with open(ZIPCODES_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        zip_infos = [row for row in reader if row.get("zip_code")]

    total_tasks = len(zip_infos) * len(PLAN_CHOICES)
    completed = 0
    cumulative_plans = 0
    print(f"[START] Processing {len(zip_infos)} ZIPs × {len(PLAN_CHOICES)} plans = {total_tasks} tasks")
    sys.stdout.flush()

    for zi, zip_info in enumerate(zip_infos, 1):
        for pi, plan_type in enumerate(PLAN_CHOICES, 1):
            completed += 1
            progress_str = f"Task {completed}/{total_tasks} (ZIP {zi}/{len(zip_infos)}, Plan {pi}/{len(PLAN_CHOICES)})"

            try:
                with start_driver() as driver:
                    cumulative_plans = run_zipcode_plan(driver, zip_info, plan_type, progress_str, cumulative_plans)
            except Exception as e:
                print(f"[ERROR] {progress_str} | ZIP={zip_info['zip_code']}, plan={plan_type}: {e}")
                sys.stdout.flush()
                continue

    print(f"[COMPLETE] All {total_tasks} tasks finished. Total plans saved: {cumulative_plans}")


if __name__ == "__main__":
    main()
