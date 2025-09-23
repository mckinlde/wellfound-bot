#!/usr/bin/env python3
"""
PDF validator: classify downloaded plan PDFs into SoB / EoC / Formulary
and validate they belong to the correct plan_id and plan_name.

Confidence scoring:
- Doc type keywords: 20
- Page count sanity: 10
- Plan ID match: 25
- Plan name match: 25
- Year match: 10
- Company match: 10
"""

import os
import re
import csv
import argparse
from PyPDF2 import PdfReader

# Regex helpers
SOB_PATTERNS = [r"summary of benefits", r"\bSoB\b"]
EOC_PATTERNS = [r"evidence of coverage", r"\bEoC\b"]
FORMULARY_PATTERNS = [r"formulary", r"drug list", r"part d"]

def extract_text(path, max_pages=5):
    """Return concatenated text from first max_pages of a PDF, plus page count."""
    try:
        reader = PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages[:max_pages]):
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(pages), len(reader.pages)
    except Exception as e:
        print(f"[ERROR] Could not read {path}: {e}")
        return "", 0

def score_pdf(text, page_count, plan_id, plan_name, company):
    """Return (label, confidence, reasons)."""
    t = text.lower()
    reasons = []
    score = 0
    detected = "Unknown"

    # --- Doc-type detection (20 pts total) ---
    sob = any(re.search(p, t) for p in SOB_PATTERNS)
    eoc = any(re.search(p, t) for p in EOC_PATTERNS)
    form = any(re.search(p, t) for p in FORMULARY_PATTERNS)

    if sob:
        detected = "Summary_of_Benefits"
        score += 20; reasons.append("SoB keyword")
    if eoc:
        detected = "Evidence_of_Coverage"
        score += 20; reasons.append("EoC keyword")
    if form:
        detected = "Drug_Formulary"
        score += 20; reasons.append("Formulary keyword")

    # --- Page count heuristics (10 pts) ---
    if detected == "Evidence_of_Coverage" and page_count >= 100:
        score += 10; reasons.append("EoC pagecount")
    elif detected == "Summary_of_Benefits" and page_count < 80:
        score += 10; reasons.append("SoB short doc")
    elif detected == "Drug_Formulary" and 20 <= page_count <= 400:
        score += 10; reasons.append("Formulary plausible size")

    # --- Plan ID check (25 pts) ---
    pid_plain = plan_id.replace("-", "").lower()
    if plan_id.lower() in t or pid_plain in t:
        score += 25; reasons.append("Plan ID match")
    else:
        reasons.append("Plan ID missing")

    # --- Plan name check (25 pts) ---
    if plan_name and plan_name.lower() in t:
        score += 25; reasons.append("Plan name match")
    else:
        reasons.append("Plan name missing")

    # --- Year check (10 pts) ---
    if "2025" in t:
        score += 10; reasons.append("Year 2025 found")
    else:
        reasons.append("Year missing")

    # --- Company check (10 pts) ---
    if company and company.lower() in t:
        score += 10; reasons.append("Company match")

    # Clamp score
    score = min(score, 100)

    return detected, score, "; ".join(reasons)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV output from pdf_grabber.py")
    ap.add_argument("--output", required=True, help="CSV with validation results")
    args = ap.parse_args()

    rows = []
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            plan_id = row["plan_id"]
            plan_name = row["plan_name"]
            company = row["company"]
            for label in ["SOB_pdf_filepath", "EoC_pdf_filepath", "formulary_pdf_filepath"]:
                pdf_path = row[label]
                if pdf_path and os.path.exists(pdf_path):
                    text, pages = extract_text(pdf_path, max_pages=5)
                    detected, score, reasons = score_pdf(text, pages, plan_id, plan_name, company)
                    row[f"{label}_detected"] = detected
                    row[f"{label}_score"] = score
                    row[f"{label}_pages"] = pages
                    row[f"{label}_reasons"] = reasons
                else:
                    row[f"{label}_detected"] = "MISSING"
                    row[f"{label}_score"] = 0
                    row[f"{label}_pages"] = 0
                    row[f"{label}_reasons"] = "File missing"
            rows.append(row)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[DONE] Validation results written to {args.output}")

if __name__ == "__main__":
    main()
