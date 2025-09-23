#!/usr/bin/env python3
"""
humana_pdf_direct.py

Reads plan IDs from humana_plan_links.csv, derives possible Humana PDF URLs
based on ID formatting, and downloads them directly (SB/EOC for 2025 and 2024).
"""

import os
import re
import argparse
from time import sleep

import pandas as pd
import requests


OUTPUT_DIR = "humana_PDFs"
BASE_URL = "https://www.humana-medicare.com/BenefitSummary/{year}PDFs/{plan}{suffix}{year_short}.pdf"

# Document suffixes we want
DOC_SUFFIXES = {
    "SB": "Summary of Benefits",
    "EOC": "Evidence of Coverage",
}
YEARS = [2025, 2024]


def load_plan_ids(csv_path="medicare/humana/humana_plan_links.csv"):
    """Return list of plan IDs from CSV, order preserved, drop duplicates."""
    df = pd.read_csv(csv_path, dtype=str)
    plan_ids = df["plan_id"].drop_duplicates().tolist()
    return plan_ids


def normalize_plan_id(plan_id: str) -> str:
    """
    Convert a CSV-style plan ID like 'H5216-318-1' into Humana's PDF format 'H5216318001'.
    Rules:
    - Strip dashes
    - Last segment must be left-padded to 3 digits
    """
    parts = plan_id.replace(" ", "").split("-")
    if len(parts) != 3:
        raise ValueError(f"Unexpected plan_id format: {plan_id}")
    prefix, mid, suffix = parts
    suffix_padded = suffix.zfill(3)
    return f"{prefix}{mid}{suffix_padded}"


def download_pdf(session: requests.Session, url: str, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 200 and resp.headers.get("content-type", "").lower().startswith("application/pdf"):
            with open(out_path, "wb") as f:
                f.write(resp.content)
            print(f"    [OK] {os.path.basename(out_path)}")
            return True
        else:
            print(f"    [MISS] {url} (status={resp.status_code})")
            return False
    except Exception as e:
        print(f"    [ERROR] {url}: {e}")
        return False


def main(start_n: int, stop_n: int | None):
    plan_ids = load_plan_ids()
    total = len(plan_ids)
    if total == 0:
        print("[ERROR] No plan_ids found in humana_plan_links.csv")
        return

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
    print(f"[INFO] Processing range: {start_n}..{stop_n} (inclusive)")

    session = requests.Session()

    for i in range(start_idx, stop_idx):
        raw_id = plan_ids[i]
        print(f"[INFO] ({i+1}/{total}) {raw_id}")
        try:
            normalized_id = normalize_plan_id(raw_id)
        except ValueError as e:
            print(f"    [SKIP] {e}")
            continue

        out_dir = os.path.join(OUTPUT_DIR, normalized_id)
        os.makedirs(out_dir, exist_ok=True)

        for year in YEARS:
            year_short = str(year)[-2:]
            for suffix, label in DOC_SUFFIXES.items():
                url = BASE_URL.format(year=year, year_short=year_short, plan=normalized_id, suffix=suffix)
                filename = f"{normalized_id}_{label.replace(' ', '')}_{year}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, url, out_path)
                sleep(0.8)  # polite delay


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Humana Medicare PDFs directly by plan_id pattern.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based start index")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based stop index (inclusive)")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
