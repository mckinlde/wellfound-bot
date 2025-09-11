import os
import re
import csv
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin

from utils.driver_session import start_driver, get_soup_from_url

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
def build_uhc_url_from_medicare_link(link: str) -> str:
    """
    Construct the UHC plan details URL from a Medicare.gov plan link.
    """
    parsed = urlparse(link)
    frag = parsed.fragment or ""
    frag_path, frag_query = (frag.split("?", 1) + [""])[:2] if "?" in frag else (frag, "")
    q_frag = parse_qs(frag_query)
    q_main = parse_qs(parsed.query)

    def get_param(name, default=None):
        if name in q_frag and q_frag[name]:
            return q_frag[name][0]
        if name in q_main and q_main[name]:
            return q_main[name][0]
        return default

    zip_code = get_param("zip")
    fips_full = get_param("fips")
    year_param = get_param("year")

    m = re.search(r"plan-details/(\d{4})-([A-Z]\d{4})-(\d{3})-(\d{1,2})", frag_path, re.I)
    if not m:
        m = re.search(r"(\d{4})-([A-Z]\d{4})-(\d{3})-(\d{1,2})", link, re.I)
    if not m:
        raise ValueError(f"Could not parse plan identifier from link: {link}")

    year_from_path, contract, plan3, segment = m.groups()
    year = year_param or year_from_path
    if not zip_code or not fips_full or not year:
        raise ValueError(f"Missing zip/fips/year in link: {link}")

    fips3 = str(fips_full)[-3:].zfill(3)
    plan3 = plan3.zfill(3)
    seg3  = str(segment).zfill(3)
    plan_code11 = f"{contract.upper()}{plan3}{seg3}"

    return f"https://www.uhc.com/medicare/health-plans/details.html/{zip_code}/{fips3}/{plan_code11}/{year}"


def make_requests_session_from_driver(driver):
    s = requests.Session()
    # copy cookies from Selenium into requests
    for c in driver.get_cookies():
        s.cookies.set(c['name'], c['value'])
    # match browser headers
    s.headers.update({
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Referer": "https://www.uhc.com/medicare/health-plans",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def categorize_pdf(text):
    txt = text.lower()
    if "summary of benefits" in txt:
        return "Summary_of_Benefits"
    elif "evidence of coverage" in txt:
        return "Evidence_of_Coverage"
    elif "formulary" in txt or "drug list" in txt:
        return "Drug_Formulary"
    else:
        return "Other"

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

    # Prefer structured divs with metadata
    for div in soup.find_all("div", class_="document-link"):
        pdf_name = div.get("data-pdf-name", "").strip().lower()
        a = div.find("a", href=True)
        if not a:
            continue
        href = a["href"]

        if href.lower().endswith(".pdf") or "/medicare/" in href:
            # UHC sometimes gives relative links
            if href.startswith("/"):
                href = "https://www.uhc.com" + href

            pdf_links.append((pdf_name, href))

    # fallback: generic <a> ending with .pdf
    if not pdf_links:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf"):
                pdf_links.append((a.get_text(strip=True), href))

    return pdf_links

def download_pdf(doc_type, url, plan_folder, req_sess):
    safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', doc_type) or "document"
    fname = f"{safe_name}.pdf"
    fpath = os.path.join(plan_folder, fname)

    counter = 1
    base, ext = os.path.splitext(fpath)
    while os.path.exists(fpath):
        fname = f"{safe_name}_{counter}.pdf"
        fpath = os.path.join(plan_folder, fname)
        counter += 1

    try:
        r = req_sess.get(url, stream=True, timeout=20)
        r.raise_for_status()
        with open(fpath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        logger.info(f"✅ Saved {fpath}")
        time.sleep(random.uniform(1, 3))
        return True
    except Exception as e:
        logger.error(f"❌ Failed {url}: {e}")
        return False

def download_plan_pdfs(csv_path, out_dir="uhc_plan_pdfs"):
    os.makedirs(out_dir, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        total = len(reader)

        with start_driver(headless=True) as driver:
            for idx, plan in enumerate(reader, start=1):
                plan_folder = os.path.join(out_dir, plan["plan_id"])
                os.makedirs(plan_folder, exist_ok=True)

                # build the 11-char plan id
                plan_id_fmt = build_uhc_url_from_medicare_link(plan["link_to_plan_page"]).split("/")[-2]

                # create a requests.Session with Selenium’s cookies
                req_sess = make_requests_session_from_driver(driver)

                # fetch PDFs using the requests session
                pdfs = fetch_pdfs(plan, plan_id_fmt, req_sess)

                for text, link in pdfs:
                    doc_type = categorize_pdf(text)
                    success = download_pdf(doc_type, link, plan_folder, req_sess)
                    if success:
                        logger.info(f"Downloaded {doc_type} for plan {plan['plan_id']}")
                        print(f"Downloaded {doc_type} for plan {plan['plan_id']}, uhc_plan_links.csv row {idx} / {total}")

if __name__ == "__main__":
    download_plan_pdfs("medicare/uhc_plan_links.csv")
