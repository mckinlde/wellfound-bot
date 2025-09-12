#!/usr/bin/env python3
"""
aetna_pdf_grabber.py

Reads plan IDs from aetna_plan_links.csv, visits the Aetna plan page, and downloads
key documents (SB, EOC, Formulary, ANOC in EN/ES).

Features:
- Progress indication using global 1-based index: [(i/total)] PLAN_ID
- Resume by progress index: --start-n and --stop-n (1-based, inclusive)
- Skips already-downloaded PDFs
- Polite delays; downloads via requests Session cloned from Selenium driver
"""

import os
import re
import argparse
from time import sleep
from urllib.parse import urljoin

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# if you want to keep relative imports
# If you always run the script directly (python medicare/Aetna/aetna_pdf_grabber.py from the project root), you can instead do:
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# That forces Python to see the project root, no matter where you launch from.
from utils.driver_session import start_driver
from utils.SPA_utils import make_requests_session_from_driver

BASE_ORIGIN = "https://www.aetna.com"
BASE_URL = f"{BASE_ORIGIN}/medicare/"
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
    """Keep the CSV order, drop duplicates."""
    df = pd.read_csv(csv_path, dtype=str)
    plan_ids = df["plan_id"].drop_duplicates().tolist()
    return plan_ids


def build_plan_url(plan_id: str) -> str:
    """Convert 'H5521-475-0' -> 'https://www.aetna.com/medicare/plan.H5521.475.html'."""
    prefix, suffix, _ = plan_id.split("-")
    return f"{BASE_URL}plan.{prefix}.{suffix}.html"


def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


def scrape_plan_pdfs(driver, plan_id: str) -> dict:
    url = build_plan_url(plan_id)
    print(f"[INFO] Visiting {url}")
    driver.get(url)

    pdfs = {}

    try:
        # Wait up to 10s for at least one document link
        elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.type__link__digitaldownload"))
        )
    except Exception:
        # If nothing shows up, probably a CAPTCHA
        input("[ACTION] No document links found (possibly CAPTCHA). Solve it in the browser, then press Enter...")
        # After manual solve, try again
        try:
            elements = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.type__link__digitaldownload"))
            )
        except Exception:
            print("    [ERROR] Still no links after waiting, skipping plan.")
            return pdfs

    # Collect PDFs
    for el in elements:
        try:
            label = (el.get_attribute("data-analytics-name") or "").strip()
            href = (el.get_attribute("href") or "").strip()
            if label in DOC_LABELS and href.lower().endswith(".pdf"):
                pdfs[label] = urljoin(BASE_ORIGIN, href)
        except Exception:
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


def main(start_n: int, stop_n: int | None):
    plan_ids = load_plan_ids()
    total = len(plan_ids)
    if total == 0:
        print("[ERROR] No plan_ids found in aetna_plan_links.csv")
        return

    # Normalize 1-based indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    # Convert to 0-based slice; stop_n is inclusive in CLI
    start_idx = start_n - 1
    stop_idx = stop_n  # slice end is exclusive

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        # Enumerate with global 1-based counter
        for i in range(start_idx, stop_idx):
            plan_id = plan_ids[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id}")

            # Gather links
            pdfs = scrape_plan_pdfs(driver, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                # Pause a bit before next plan
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            # Download each desired PDF; skip if exists
            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)  # polite per-file delay

            sleep(2.5)  # polite per-plan delay


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Aetna Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
