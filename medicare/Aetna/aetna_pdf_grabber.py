#!/usr/bin/env python3
"""
aetna_pdf_grabber.py

Reads Aetna plan IDs from aetna_plan_links.csv,
visits the Aetna plan page, and downloads
important documents (SB, EOC, Formulary, ANOC, English/Spanish).
"""

import os
import pandas as pd
from time import sleep
from selenium.webdriver.common.by import By
from driver_session import start_driver
from SPA_utils import (
    wait_scroll_interact,
    _safe_click_element,
    make_requests_session_from_driver,
)

BASE_URL = "https://www.aetna.com/medicare/"
OUTPUT_DIR = "Aetna_PDFs"

DOC_LABELS = [
    "Summary of Benefits (SB)",
    "Summary of Benefits (SB) - Español",
    "Evidence of Coverage (EOC)",
    "Evidence of Coverage (EOC) - Español",
    "Formulary (drug list)",
    "Formulary (drug list) - Español",
    "Annual Notice of Change (ANOC)",
    "Annual Notice of Change (ANOC) - Español",
]


def load_plan_ids(csv_path="aetna_plan_links.csv"):
    df = pd.read_csv(csv_path)
    return df["plan_id"].unique()


def build_plan_url(plan_id):
    prefix, suffix, _ = plan_id.split("-")
    return f"{BASE_URL}plan.{prefix}.{suffix}.html"


def scrape_plan_pdfs(driver, session, plan_id):
    url = build_plan_url(plan_id)
    print(f"[INFO] Visiting {url}")
    driver.get(url)

    # politely wait for page to load and scroll
    sleep(2)

    # Grab all document links
    elements = driver.find_elements(By.CSS_SELECTOR, "a.type__link__digitaldownload")
    pdfs = {}

    for el in elements:
        try:
            label = el.get_attribute("data-analytics-name") or ""
            href = el.get_attribute("href")
            if label.strip() in DOC_LABELS and href and href.endswith(".pdf"):
                pdfs[label.strip()] = href
        except Exception as e:
            print(f"[WARN] Skipping element: {e}")

    return pdfs


def download_pdf(session, url, out_path):
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"[OK] Saved {out_path}")
    except Exception as e:
        print(f"[ERROR] Failed to download {url}: {e}")


def main():
    plan_ids = load_plan_ids()
    print(f"[INFO] Loaded {len(plan_ids)} plan IDs")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for plan_id in plan_ids:
            pdfs = scrape_plan_pdfs(driver, session, plan_id)

            if not pdfs:
                print(f"[WARN] No PDFs found for {plan_id}")
                continue

            for label, href in pdfs.items():
                filename = f"{plan_id}_{label.replace(' ', '_').replace('/', '-')}.pdf"
                out_path = os.path.join(OUTPUT_DIR, plan_id, filename)
                download_pdf(session, href, out_path)

                # Be polite: short delay per file
                sleep(1.5)

            # Small extra delay between plans
            sleep(3)


if __name__ == "__main__":
    main()
