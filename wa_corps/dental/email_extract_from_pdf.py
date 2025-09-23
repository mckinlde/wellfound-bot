import pdfplumber
import re
from pathlib import Path
import csv

PDF_DIR = Path("wa_corps/dental/business_pdf")
OUTPUT_FILE = Path("wa_corps/dental/emails_from_pdfs2.csv")

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

emails = []

for pdf_path in PDF_DIR.rglob("*.pdf"):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            found = EMAIL_REGEX.findall(text)
            for email in found:
                emails.append(email)
    except Exception as e:
        print(f"[WARN] Failed to read {pdf_path}: {e}")

# Deduplicate
unique_emails = sorted(set(emails))

# Save to CSV
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["email"])
    for email in unique_emails:
        writer.writerow([email])

print(f"[INFO] Extracted {len(unique_emails)} unique emails → {OUTPUT_FILE}")
