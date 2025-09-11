import os
import re
import csv
import time
import random
import requests
import logging
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# -----------------------
# Logging setup
# -----------------------
LOG_FILE = "uhc_pdf_grabber.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# -----------------------
# Helpers
# -----------------------
def format_plan_id(plan_id: str) -> str:
    """
    Convert CMS-style plan IDs (Hxxxx-yyy-z) into UHC 11-digit format.
    Examples:
        H2001-088-1 -> H2001088001
        H5253-141-0 -> H5253141000
        H2802-041-0 -> H2802041000
    """
    parts = plan_id.split("-")
    if len(parts) != 3:
        raise ValueError(f"Unexpected plan_id format: {plan_id}")
    
    contract, plan_num, segment = parts
    plan_num = plan_num.zfill(3)   # ensure 3 digits
    segment = segment.zfill(2)     # ensure 2 digits
    raw = f"{contract}{plan_num}{segment}"
    
    # ensure length = 11, pad with trailing zeros if needed
    return raw.ljust(11, "0")


def extract_uhc_state_fips(link: str) -> str:
    """Extract the last 3 digits of fips from Medicare.gov link_to_plan_page."""
    qs = parse_qs(urlparse(link).query)
    fips_val = qs.get("fips", [""])[0]  # e.g. "01003"
    return fips_val[-3:].zfill(3)       # e.g. "003"


def build_uhc_url(plan: dict, plan_id_fmt: str) -> str:
    zip_code = str(plan["zip"])
    state_fips = extract_uhc_state_fips(str(plan["link_to_plan_page"]))
    year = "2025"
    return f"https://www.uhc.com/medicare/health-plans/details.html/{zip_code}/{state_fips}/{plan_id_fmt}/{year}"


# -----------------------
# Core logic
# -----------------------
def fetch_pdfs(plan, plan_id_fmt, session):
    """Scrape all PDF links from UHC plan page."""
    url = build_uhc_url(plan, plan_id_fmt)
    logger.info(f"🌐 Fetching {url}")

    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        time.sleep(random.uniform(1, 3))  # politeness
    except Exception as e:
        logger.error(f"❌ Failed to fetch {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            text = a.get_text(strip=True)
            pdf_links.append((text, href))
    return pdf_links

def download_pdf(name, url, plan_id_fmt, plan_folder, session):
    """Download one PDF, skip if already exists."""
    try:
        safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', name)
        fname = f"{safe_name}.pdf"
        fpath = os.path.join(plan_folder, fname)

        if os.path.exists(fpath):
            logger.info(f"⏩ Skipping {fname}, already exists.")
            return False

        r = session.get(url, stream=True, timeout=20)
        r.raise_for_status()
        with open(fpath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        logger.info(f"✅ Saved {fpath}")
        time.sleep(random.uniform(1, 3))  # politeness
        return True
    except Exception as e:
        logger.error(f"❌ Failed {url}: {e}")
        return False

def download_plan_pdfs(csv_path, out_dir="uhc_plan_pdfs"):
    os.makedirs(out_dir, exist_ok=True)
    session = requests.Session()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        total = len(reader)

        for idx, plan in enumerate(reader, start=1):
            plan_id_fmt = format_plan_id(plan["plan_id"])
            plan_folder = os.path.join(out_dir, plan["plan_id"])
            os.makedirs(plan_folder, exist_ok=True)

            pdfs = fetch_pdfs(plan, plan_id_fmt, session)
            for text, link in pdfs:
                # categorize document type
                if any(key in text.lower() for key in ["summary of benefits", "sob"]):
                    doc_type = "Summary_of_Benefits"
                elif any(key in text.lower() for key in ["evidence of coverage", "eoc"]):
                    doc_type = "Evidence_of_Coverage"
                elif any(key in text.lower() for key in ["formulary", "drug list"]):
                    doc_type = "Drug_Formulary"
                else:
                    doc_type = "Other"

                success = download_pdf(doc_type, link, plan_id_fmt, plan_folder, session)
                if success:
                    logger.info(f"Downloaded {doc_type} for plan {plan['plan_id']}")
                    print(f"Downloaded {doc_type} for plan {plan['plan_id']}, uhc_plan_links.csv row {idx} / {total}")

if __name__ == "__main__":
    download_plan_pdfs("medicare/uhc_plan_links.csv")