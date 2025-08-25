#!/usr/bin/env python3
"""
medicare_scraper.py (Medicare.gov scraper)

Usage:
  nix develop
  python3 medicare_scraper.py
"""

import pathlib
import csv
from utils.driver_session import start_driver
from utils.medicare_utils import (
    fill_zip_and_click_continue,
    select_plan_type_and_continue,
    select_none_and_continue,
    select_exclude_and_next,
    scrape_all_plan_details,
)


# -------------------------
# CONFIG
# -------------------------
ZIPCODES_FILE = "constants/zipcodes.txt"  # one zipcode per line
PLAN_CHOICES = ["mapd"]# for now just medicare advantage, "pdp", "medigap"]
OUTPUT_DIR = "medicare_dot_gov_html"
PLAN_LINKS_CSV = "plan_links.csv"


def save_plan_link(zipcode, plan_type, plan_name, plan_id, plan_url):
    """Append plan website info to a CSV."""
    file_exists = pathlib.Path(PLAN_LINKS_CSV).is_file()
    with open(PLAN_LINKS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["zip", "plan_type", "plan_name", "plan_id", "plan_website"])
        writer.writerow([zipcode, plan_type, plan_name, plan_id, plan_url])


def run_zipcode_plan(driver, zipcode, plan_type):
    """Run full workflow for a single ZIP + plan type."""
    print(f"\n[INFO] ZIP={zipcode}, plan={plan_type}")

    # Load landing page fresh for each ZIP/plan
    driver.get("https://www.medicare.gov/plan-compare/#/?year=2025&lang=en")

    # Step 1: ZIP → Continue
    fill_zip_and_click_continue(driver, zipcode)

    # Step 2: Select plan type → Continue
    select_plan_type_and_continue(driver, plan_type)

    # Step 3: Select LIS None → Continue
    select_none_and_continue(driver)

    # Step 4: Select drug exclude → Next
    select_exclude_and_next(driver)

    # Step 5: Scrape all plan detail pages
    results = scrape_all_plan_details(driver, zipcode=zipcode, base_dir=OUTPUT_DIR)

    # Step 6: Save plan website links
    for plan in results:
        if "plan_website" in plan and plan["plan_website"]:
            save_plan_link(
                zipcode,
                plan_type,
                plan.get("plan_name", ""),
                plan.get("plan_id", ""),
                plan.get("plan_website", ""),
            )

    print(f"[DONE] ZIP={zipcode}, plan={plan_type}, {len(results)} plans saved.")


def main():
    # Load ZIP codes
    with open(ZIPCODES_FILE) as f:
        zipcodes = [line.strip() for line in f if line.strip()]

    with start_driver() as driver:
        for zipcode in zipcodes:
            for plan_type in PLAN_CHOICES:
                try:
                    run_zipcode_plan(driver, zipcode, plan_type)
                except Exception as e:
                    print(f"[ERROR] ZIP={zipcode}, plan={plan_type}: {e}")
                    continue


if __name__ == "__main__":
    main()
