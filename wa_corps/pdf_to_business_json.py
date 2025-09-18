import os
import json
from pypdf import PdfReader

PDF_ROOT = r"wa_corps\business_pdf"
OUTPUT_DIR = r"wa_corps\business_json"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_info(path):
    """Extract structured info from WA SOS PDFs."""
    info = {
        "filename": os.path.basename(path),
        "filing_type": None,
        "date_filed": None,
        "status": None,
        "registered_agent": None,
        "principal_office": None,
        "email": None,
        "phone": None,
        "governors": []
    }

    try:
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("Date Filed:"):
                info["date_filed"] = line.split(":",1)[1].strip()
            elif line.startswith("Business Status:"):
                info["status"] = line.split(":",1)[1].strip()
            elif line.startswith("Email:"):
                info["email"] = line.split(":",1)[1].strip()
            elif line.startswith("Phone:"):
                info["phone"] = line.split(":",1)[1].strip()
            elif "GOVERNOR" in line.upper():
                info["governors"].append(line)

        # Filing type
        if "Annual Report" in text:
            info["filing_type"] = "Annual Report"
        elif "Designation of Agent" in text:
            info["filing_type"] = "Designation of Agent"

        # Registered agent
        if "Registered Agent" in text:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i,l in enumerate(lines):
                if "Registered Agent" in l and i+2 < len(lines):
                    info["registered_agent"] = lines[i+2]
                    break

        # Principal office
        if "Principal Office Street Address:" in text:
            for line in text.splitlines():
                if "Principal Office Street Address:" in line:
                    info["principal_office"] = line.split(":",1)[1].strip()
                    break

    except Exception as e:
        print(f"[ERROR] Failed to parse {path}: {e}")

    return info

def append_to_json(ubi, info):
    path = os.path.join(OUTPUT_DIR, f"{ubi}.json")
    data = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    data.append(info)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[OK] Appended filing to {path}")

def main():
    for ubi in os.listdir(PDF_ROOT):
        ubi_path = os.path.join(PDF_ROOT, ubi)
        if not os.path.isdir(ubi_path):
            continue

        for fname in os.listdir(ubi_path):
            if fname.lower().endswith(".pdf"):
                pdf_path = os.path.join(ubi_path, fname)
                print(f"[STEP] Processing {ubi}/{fname}")
                info = extract_info(pdf_path)
                append_to_json(ubi, info)

if __name__ == "__main__":
    main()
