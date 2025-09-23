#!/usr/bin/env python3
"""
PDF grabber using Google Custom Search JSON API.

Stages:
1) Load plan_ids from CSV
2) For each plan, run a broad API query for PDFs
3) If missing doc types, run targeted API queries
4) Download PDFs, log results into CSV
5) (Optional --debug) Save raw JSON responses for offline analysis
"""

import os
import csv
import json
import time
import random
import argparse
import logging
import requests

from urllib.parse import urlparse

# ---------------------------
# Setup
# ---------------------------

LOG_FILE = "medicare/google_them/google_pdf_grabber.log"
logger = logging.getLogger("pdf_grabber")

DOC_TYPES = {
    "Summary_of_Benefits": "summary of benefits",
    "Evidence_of_Coverage": "evidence of coverage",
    "Drug_Formulary": "formulary drug list",
}

CSV_FIELD_MAP = {
    "Summary_of_Benefits": ("SOB_pdf_link", "SOB_pdf_filepath"),
    "Evidence_of_Coverage": ("EoC_pdf_link", "EoC_pdf_filepath"),
    "Drug_Formulary": ("formulary_pdf_link", "formulary_pdf_filepath"),
}

# ---------------------------
# Config
# ---------------------------

BASE_DIR = os.path.dirname(__file__)
env_path = os.path.join(BASE_DIR, "env.json")
with open(env_path, "r") as f:
    env = json.load(f)

API_KEY = env["Custom Search Api"]["key"]
CX_ID = env["Programmable Search Engine"]["id"]

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# ---------------------------
# Utilities
# ---------------------------

def polite_sleep():
    time.sleep(random.uniform(0.5, 1.5))

def is_pdf_url(u: str) -> bool:
    return ".pdf" in u.lower()

def categorize_link(url: str, text: str):
    """
    Categorize based on URL + snippet/title text.
    """
    t = f"{url} {text}".lower()

    if ("summary of benefits" in t) or (" sob" in t) or ("-sb" in t):
        return "Summary_of_Benefits"
    if ("evidence of coverage" in t) or (" eoc" in t) or ("-eoc" in t):
        return "Evidence_of_Coverage"
    if (
        "formulary" in t
        or "drug list" in t
        or "comprehensive drug list" in t
        or "part d" in t
        or "mapd" in t
    ):
        return "Drug_Formulary"
    return None

def run_search(query, max_results=10, start_index=1):
    params = {
        "key": API_KEY,
        "cx": CX_ID,
        "q": query,
        "num": min(max_results, 10),
        "start": start_index,
    }
    r = requests.get(SEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def api_search_and_categorize(plan_id, plan_name, label="broad", pages=3, debug_dir=None):
    """
    Use API search to return dict of doc_label → url.
    Saves raw JSON to debug_dir if provided.
    """
    if label == "broad":
        query = f"{plan_id} {plan_name} filetype:pdf"
    else:
        query = f"{plan_id} {plan_name} {DOC_TYPES[label]} filetype:pdf"

    found = {}
    for page in range(pages):
        start_index = page * 10 + 1
        data = run_search(query, max_results=10, start_index=start_index)

        # Save debug JSON if enabled
        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"{plan_id}_{label}_page{page+1}.json")
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"[DEBUG] Saved raw JSON → {debug_file}")

        items = []
        for item in data.get("items", []):
            items.append((item.get("link", ""), item.get("title", ""), item.get("snippet", "")))

        logger.debug(f"[DEBUG] {plan_id} {label} page {page+1}: {len(items)} results")
        for url, title, snippet in items:
            logger.debug(f"[DEBUG] Candidate link: {url} | title={title!r} | snippet={snippet!r}")
            if not is_pdf_url(url):
                continue
            doc_label = categorize_link(url, f"{title} {snippet}")
            if doc_label:
                logger.debug(f"[DEBUG] Categorized {url} as {doc_label}")
            if doc_label and doc_label not in found:
                found[doc_label] = url
            if len(found) == 3:
                break
        polite_sleep()
    logger.info(f"[API SEARCH] {plan_id} {label} → {len(found)} categorized")
    return found

def download_pdf(session, url, dest_path, plan_id, doc_label):
    """Download PDF if not already saved; log destination."""
    if not url:
        return False
    if os.path.exists(dest_path):
        logger.info(f"[SKIP] {doc_label} already exists for {plan_id} → {dest_path}")
        return True
    try:
        r = session.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        logger.info(f"[DOWNLOAD] Saved {doc_label} for {plan_id} → {dest_path}")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Failed {url}: {e}")
        return False

# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--stop", type=int, default=None, help="Inclusive 1-based stop index")
    ap.add_argument("--pages", type=int, default=3, help="Max API pages per query (default: 3)")
    ap.add_argument("--debug", action="store_true", help="Enable debug logging and save raw JSON")
    args = ap.parse_args()

    # Configure logging level
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logger.setLevel(log_level)

    # Debug directory for raw API JSONs
    debug_dir = None
    if args.debug:
        debug_dir = os.path.join(args.outdir, "debug_json")
        os.makedirs(debug_dir, exist_ok=True)

    os.makedirs(args.outdir, exist_ok=True)

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    total = len(reader)

    start_idx = max(args.start, 1)
    stop_idx = args.stop if args.stop is not None else total

    out_exists = os.path.exists(args.output)
    out_fh = open(args.output, "a", newline="", encoding="utf-8")
    out_writer = csv.DictWriter(
        out_fh,
        fieldnames=[
            "plan_id","plan_name","company",
            "SOB_pdf_link","SOB_pdf_filepath",
            "EoC_pdf_link","EoC_pdf_filepath",
            "formulary_pdf_link","formulary_pdf_filepath",
        ],
    )
    if not out_exists:
        out_writer.writeheader()

    session = requests.Session()

    for idx, plan in enumerate(reader, start=1):
        if idx < start_idx or idx > stop_idx:
            continue

        plan_id = (plan.get("plan_id") or "").strip()
        plan_name = (plan.get("plan_name") or "").strip()
        company = (plan.get("company") or "").strip()

        row = {
            "plan_id": plan_id,
            "plan_name": plan_name,
            "company": company,
            "SOB_pdf_link": "",
            "SOB_pdf_filepath": "",
            "EoC_pdf_link": "",
            "EoC_pdf_filepath": "",
            "formulary_pdf_link": "",
            "formulary_pdf_filepath": "",
        }

        logger.info(f"[INFO] ({idx}/{total}) Searching PDFs for {plan_id} {plan_name}")

        # 1) Broad search
        broad_found = api_search_and_categorize(plan_id, plan_name, label="broad", pages=args.pages, debug_dir=debug_dir)
        for doc_label, pdf_url in broad_found.items():
            dest_path = os.path.join(args.outdir, f"{plan_id}_{doc_label}.pdf")
            ok = download_pdf(session, pdf_url, dest_path, plan_id, doc_label)
            if ok:
                link_field, path_field = CSV_FIELD_MAP[doc_label]
                row[link_field] = pdf_url
                row[path_field] = dest_path

        # 2) Targeted search for missing
        missing_labels = [d for d in DOC_TYPES.keys() if d not in broad_found]
        for doc_label in missing_labels:
            res = api_search_and_categorize(plan_id, plan_name, label=doc_label, pages=args.pages, debug_dir=debug_dir)
            pdf_url = res.get(doc_label, "")
            if pdf_url:
                dest_path = os.path.join(args.outdir, f"{plan_id}_{doc_label}.pdf")
                ok = download_pdf(session, pdf_url, dest_path, plan_id, doc_label)
                if ok:
                    link_field, path_field = CSV_FIELD_MAP[doc_label]
                    row[link_field] = pdf_url
                    row[path_field] = dest_path

        # 3) Summary
        summary_bits = [
            "SoB=" + ("FOUND" if row["SOB_pdf_link"] else "NOT FOUND"),
            "EoC=" + ("FOUND" if row["EoC_pdf_link"] else "NOT FOUND"),
            "Formulary=" + ("FOUND" if row["formulary_pdf_link"] else "NOT FOUND"),
        ]
        logger.info(f"[SUMMARY] ({idx}/{total}) {plan_id} → {', '.join(summary_bits)}")

        out_writer.writerow(row)
        out_fh.flush()

    out_fh.close()

if __name__ == "__main__":
    main()
