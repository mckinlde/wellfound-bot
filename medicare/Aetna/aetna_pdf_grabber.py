#!/usr/bin/env python3
"""
aetna_pdf_grabber.py

Reads Aetna plan IDs from aetna_plan_links.csv,
visits the Aetna plan page, and downloads
important documents (SB, EOC, Formulary, ANOC, English/Spanish).
"""

import os
import csv
import time
import requests
import pandas as pd
from urllib.parse import urljoin
from driver_session import start_driver  # your custom session manager
from SPA_utils import save_page_html     # assuming you already have this


BASE_URL = "https://www.aetna.com/medicare/"
OUTPUT_DIR = "Aetna_PDFs"

# Which documents we want
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
    """Read plan IDs from the CSV and return a unique set of plan codes."""
    df = pd.read_csv(csv_path)
    return df["plan_id"].unique()


def build_plan_url(plan_id):
    """
    Convert 'H5521-475-0' -> 'https://www.aetna.com/medicare/plan.H5521.475.html'
    """
    prefix, suffix, _ = plan_id.split("-")
    return f"{BASE_URL}plan.{prefix}.{suffix}.html"


def scrape_plan_pdfs(driver, plan_id):
    """Visit Aetna plan page and collect PDF links."""
    url = build_plan_url(plan_id)
    print(f"[INFO] Visiting {url}")
    driver.get(url)
    time.sleep(2)  # let page settle

    links = driver.find_elements("css selector", "a.type__link__digitaldownload")
    pdfs = {}

    for link in links:
        try:
            label = link.get_attribute("data-analytics-name").strip()
            href = link.get_attribute("href")
            if label in DOC_LABELS and href.endswith(".pdf"):
                pdfs[label] = href
        except Exception as e:
            print(f"[WARN] Skipping link: {e}")

    return pdfs


def download_pdf(url, out_path):
    """Download a PDF from url to out_path."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(f"[OK] Saved {out_path}")
    except Exception as e:
        print(f"[ERROR] Failed {url}: {e}")


def main():
    plan_ids = load_plan_ids()
    print(f"[INFO] Loaded {len(plan_ids)} plan IDs")

    with start_driver() as driver:
        for plan_id in plan_ids:
            pdfs = scrape_plan_pdfs(driver, plan_id)

            if not pdfs:
                print(f"[WARN] No PDFs found for {plan_id}")
                continue

            for label, href in pdfs.items():
                filename = f"{plan_id}_{label.replace(' ', '_').replace('/', '-')}.pdf"
                out_path = os.path.join(OUTPUT_DIR, plan_id, filename)
                download_pdf(href, out_path)


if __name__ == "__main__":
    main()
