#!/usr/bin/env python3
"""
Analyze candidates.csv from pdf_grabber stage.

Outputs:
- Console summaries (counts, duplicates, domains)
- CSV with per-plan stats
"""

import os
import csv
import argparse
from collections import defaultdict, Counter
from urllib.parse import urlparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="candidates.csv from pdf_grabber")
    ap.add_argument("--output", required=True, help="summary CSV to write")
    args = ap.parse_args()

    # Load candidates
    rows = []
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Counters
    per_plan = defaultdict(lambda: defaultdict(list))
    domain_counter = Counter()
    dup_counter = 0
    seen_urls = set()

    for row in rows:
        plan_id = row["plan_id"]
        doc_label = row["doc_label"]
        url = row["url"]
        per_plan[plan_id][doc_label].append(url)

        domain = urlparse(url).netloc
        if domain:
            domain_counter[domain] += 1

        if url in seen_urls:
            dup_counter += 1
        else:
            seen_urls.add(url)

    # Console report
    print("===== Overall Totals =====")
    print(f"Total rows in CSV: {len(rows)}")
    print(f"Unique URLs: {len(seen_urls)}")
    print(f"Duplicate URLs: {dup_counter}")
    print()

    print("===== Domain Distribution (top 20) =====")
    for domain, count in domain_counter.most_common(20):
        print(f"{domain:40s} {count}")
    print()

    print("===== Per-plan sample (first 10) =====")
    for i, (plan_id, d) in enumerate(per_plan.items()):
        sob = len(d.get("Summary_of_Benefits", []))
        eoc = len(d.get("Evidence_of_Coverage", []))
        form = len(d.get("Drug_Formulary", []))
        total = sob + eoc + form
        print(f"{plan_id}: total={total} | SoB={sob}, EoC={eoc}, Formulary={form}")
        if i >= 9:
            break

    # Write summary CSV
    out_fields = ["plan_id", "SoB_count", "EoC_count", "Formulary_count", "Total_count"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for plan_id, d in per_plan.items():
            sob = len(d.get("Summary_of_Benefits", []))
            eoc = len(d.get("Evidence_of_Coverage", []))
            form = len(d.get("Drug_Formulary", []))
            total = sob + eoc + form
            writer.writerow({
                "plan_id": plan_id,
                "SoB_count": sob,
                "EoC_count": eoc,
                "Formulary_count": form,
                "Total_count": total
            })

    print()
    print(f"[INFO] Wrote per-plan summary CSV → {args.output}")

if __name__ == "__main__":
    main()

# Usage:
# python medicare/google_them/analyze_candidates_csv.py `
#   --input medicare/google_them/testrun/candidates.csv `
#   --output medicare/google_them/candidates_summary.csv
