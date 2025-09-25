#!/usr/bin/env python3
"""
PDF grabber using Google Custom Search JSON API.

Stage 1 collector: gather candidate URLs for each plan and doc type.
- Runs queries with both raw plan_id and normalized plan_id.
- Cross-categorizes results: any query can yield any doc type.
- Writes candidates.csv with all candidates for later filtering/downloading.
- Logs detailed performance metrics.
"""

import os
import re
import csv
import json
import time
import random
import argparse
import logging
import requests
from collections import Counter, defaultdict

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

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# ---------------------------
# Config
# ---------------------------

BASE_DIR = os.path.dirname(__file__)
env_path = os.path.join(BASE_DIR, "env.json")
with open(env_path, "r") as f:
    env = json.load(f)

API_KEY = env["Custom Search Api"]["key"]
CX_ID = env["Programmable Search Engine"]["id"]

# ---------------------------
# Global stats
# ---------------------------

stats = {
    "api_calls": 0,
    "candidates": 0,
    "plans_processed": 0,
    "plans_with_sob": 0,
    "plans_with_eoc": 0,
    "plans_with_formulary": 0,
    "plans_complete": 0,  # SoB + EoC
}
doc_counter = Counter()  # counts total candidates per doc type

# ---------------------------
# Utilities
# ---------------------------

def polite_sleep():
    time.sleep(random.uniform(0.5, 1.5))

def is_pdf_url(u: str) -> bool:
    return ".pdf" in u.lower()

def categorize_link(url: str, text: str):
    """Categorize based on fuzzy keywords in URL/title/snippet."""
    t = f"{url} {text}".lower()

    sob_patterns = [
        r"summary\s+of\s+benefits",
        r"\bbenefit\s+summary\b",
        r"\bsob\b",
        r"\bsum\s+benefits\b",
        r"sb\d{2,4}",
    ]
    for pat in sob_patterns:
        if re.search(pat, t):
            return "Summary_of_Benefits"

    eoc_patterns = [
        r"evidence\s+of\s+coverage",
        r"\beoc\b",
        r"\bcoverage\s+evidence\b",
        r"\beoc\d{2,4}",
    ]
    for pat in eoc_patterns:
        if re.search(pat, t):
            return "Evidence_of_Coverage"

    formulary_patterns = [
        r"\bformulary\b",
        r"drug\s+list",
        r"prescription\s+drug\s+list",
        r"\brx\s+list\b",
        r"comprehensive\s+drug\s+list",
        r"\bpart\s+d\b",
        r"\bmapd\b",
    ]
    for pat in formulary_patterns:
        if re.search(pat, t):
            return "Drug_Formulary"

    return None

def run_search(query, max_results=10, start_index=1):
    stats["api_calls"] += 1
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

def normalize_plan_id(plan_id: str) -> str:
    """Convert 'H5216-318-1' → 'H5216318001' (Humana style)."""
    parts = plan_id.replace(" ", "").split("-")
    if len(parts) != 3:
        return plan_id
    prefix, mid, suffix = parts
    suffix_padded = suffix.zfill(3)
    return f"{prefix}{mid}{suffix_padded}"

def api_collect_candidates(plan_id, plan_name, label="broad", pages=3, debug_dir=None):
    """Run search queries and return all categorized candidates."""
    if label == "broad":
        q_base = f"{plan_id} {plan_name} filetype:pdf"
    else:
        q_base = f"{plan_id} {plan_name} {DOC_TYPES[label]} filetype:pdf"

    candidates = []

    for page in range(pages):
        start_index = page * 10 + 1
        data = run_search(q_base, max_results=10, start_index=start_index)

        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"{plan_id}_{label}_page{page+1}.json")
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        for item in data.get("items", []):
            url = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if not is_pdf_url(url):
                continue
            doc_label = categorize_link(url, f"{title} {snippet}")
            if not doc_label:
                continue
            candidates.append({
                "plan_id": plan_id,
                "plan_name": plan_name,
                "doc_label": doc_label,
                "query_label": label,
                "url": url,
                "title": title,
                "snippet": snippet,
            })
            stats["candidates"] += 1
            doc_counter[doc_label] += 1
        polite_sleep()

    logger.info(f"[API SEARCH] {plan_id} {label} → {len(candidates)} categorized")
    return candidates

# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True, help="CSV of all candidates")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--stop", type=int, default=None)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

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

    debug_dir = None
    if args.debug:
        debug_dir = os.path.join(os.path.dirname(args.output), "debug_json")
        os.makedirs(debug_dir, exist_ok=True)

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    total = len(reader)

    start_idx = max(args.start, 1)
    stop_idx = args.stop if args.stop is not None else total

    out_exists = os.path.exists(args.output)
    out_fh = open(args.output, "a", newline="", encoding="utf-8")
    out_writer = csv.DictWriter(
        out_fh,
        fieldnames=["plan_id","plan_name","doc_label","query_label","url","title","snippet"],
    )
    if not out_exists:
        out_writer.writeheader()

    # per-plan candidate counters
    per_plan_counts = defaultdict(lambda: Counter())

    for idx, plan in enumerate(reader, start=1):
        if idx < start_idx or idx > stop_idx:
            continue

        plan_id = (plan.get("plan_id") or "").strip()
        plan_name = (plan.get("plan_name") or "").strip()
        norm_id = normalize_plan_id(plan_id)

        logger.info(f"[INFO] ({idx}/{total}) Collecting candidates for {plan_id} {plan_name}")
        request_count = 0
        candidates = {d: [] for d in DOC_TYPES}  # SoB, EoC, Formulary

        # --- Stage 1: Broad search raw ID (2 pages)
        broad_raw = api_collect_candidates(plan_id, plan_name, label="broad", pages=2, debug_dir=debug_dir)
        request_count += 2
        for row in broad_raw:
            candidates[row["doc_label"]].append(row)
            out_writer.writerow(row)
        out_fh.flush()

        # --- Stage 2: Targeted search raw ID (1 page each, only if missing)
        for doc_label in DOC_TYPES:
            if not candidates[doc_label]:  # only if missing
                res = api_collect_candidates(plan_id, plan_name, label=doc_label, pages=1, debug_dir=debug_dir)
                request_count += 1
                for row in res:
                    candidates[row["doc_label"]].append(row)
                    out_writer.writerow(row)
                out_fh.flush()

        # --- Stage 3: Broad search normalized ID (2 pages, only if still missing required docs)
        if (not candidates["Summary_of_Benefits"]) or (not candidates["Evidence_of_Coverage"]):
            broad_norm = api_collect_candidates(norm_id, plan_name, label="broad", pages=2, debug_dir=debug_dir)
            request_count += 2
            for row in broad_norm:
                candidates[row["doc_label"]].append(row)
                out_writer.writerow(row)
            out_fh.flush()

        # --- Stage 4: Targeted search normalized ID (1 page each, only if still missing)
        for doc_label in DOC_TYPES:
            if not candidates[doc_label]:  # only if missing
                res = api_collect_candidates(norm_id, plan_name, label=doc_label, pages=1, debug_dir=debug_dir)
                request_count += 1
                for row in res:
                    candidates[row["doc_label"]].append(row)
                    out_writer.writerow(row)
                out_fh.flush()

        # --- Log summary
        summary_bits = [f"{d}={len(candidates[d])}" for d in DOC_TYPES]
        logger.info(f"[SUMMARY] ({idx}/{total}) {plan_id} → {', '.join(summary_bits)} | requests={request_count}")

    out_fh.close()

    # Final run summary
    logger.info("===== Run Summary =====")
    for k,v in stats.items():
        logger.info(f"{k}: {v}")
    logger.info(f"Doc type candidate counts: {dict(doc_counter)}")

    # Derived metrics
    if stats["plans_processed"] > 0:
        avg_calls_per_plan = stats["api_calls"] / stats["plans_processed"]
        logger.info(f"Avg API calls per processed plan: {avg_calls_per_plan:.2f}")
    if stats["plans_complete"] > 0:
        avg_calls_per_complete_plan = stats["api_calls"] / stats["plans_complete"]
        logger.info(f"Avg API calls per COMPLETE plan (SoB+EoC): {avg_calls_per_complete_plan:.2f}")
    logger.info("=======================")

if __name__ == "__main__":
    main()
