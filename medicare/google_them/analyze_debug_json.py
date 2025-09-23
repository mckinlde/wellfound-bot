#!/usr/bin/env python3
"""
Analyze saved Google Custom Search JSON debug dumps.

Usage:
    python analyze_debug_json.py --debug-dir medicare/google_them/testrun/debug_json --output analysis.csv
"""

import os
import re
import csv
import json
import argparse
from collections import defaultdict

DOC_TYPES = {
    "Summary_of_Benefits": "summary of benefits",
    "Evidence_of_Coverage": "evidence of coverage",
    "Drug_Formulary": "formulary drug list",
}

def is_pdf_url(u: str) -> bool:
    return ".pdf" in u.lower()

def categorize_link(url: str, text: str):
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

def analyze_debug_json(debug_dir, output_file):
    # Data collections
    per_plan = defaultdict(lambda: {
        "candidates": 0,
        "categorized": defaultdict(int),
        "all_links": []
    })
    totals = defaultdict(int)

    for fname in os.listdir(debug_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(debug_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract plan_id and label from filename
        # e.g. H4513-045-0_broad_page1.json
        base = os.path.splitext(fname)[0]
        parts = base.split("_")
        plan_id = parts[0]
        label = "_".join(parts[1:])  # not super important here

        for item in data.get("items", []):
            url = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            combined = f"{title} {snippet}"

            if not url:
                continue

            per_plan[plan_id]["candidates"] += 1
            per_plan[plan_id]["all_links"].append((url, title, snippet))

            if is_pdf_url(url):
                doc_label = categorize_link(url, combined)
                if doc_label:
                    per_plan[plan_id]["categorized"][doc_label] += 1
                    totals[doc_label] += 1

    # Write candidate CSV for manual review
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["plan_id", "url", "title", "snippet", "doc_label"])
        for plan_id, stats in per_plan.items():
            for url, title, snippet in stats["all_links"]:
                doc_label = categorize_link(url, f"{title} {snippet}") if is_pdf_url(url) else ""
                writer.writerow([plan_id, url, title, snippet, doc_label or ""])

    # Print summary
    print("===== Categorization Totals =====")
    for doc_label, count in totals.items():
        print(f"{doc_label}: {count} matches")

    print("\n===== Per-plan Summary (first 10) =====")
    for i, (plan_id, stats) in enumerate(per_plan.items()):
        if i >= 10:
            break
        cats = ", ".join(f"{k}={v}" for k,v in stats["categorized"].items())
        print(f"{plan_id}: candidates={stats['candidates']} | {cats or 'no matches'}")

    print(f"\n[INFO] Wrote candidate CSV → {output_file}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug-dir", required=True, help="Directory with saved JSONs from pdf_grabber.py --debug")
    ap.add_argument("--output", required=True, help="CSV file to save candidate links with categorization attempts")
    args = ap.parse_args()

    analyze_debug_json(args.debug_dir, args.output)

if __name__ == "__main__":
    main()
