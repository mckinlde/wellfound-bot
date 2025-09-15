#!/usr/bin/env python3
"""
ccfs_lookup.py — scrape WA CCFS by UBI.

Input  : wa_corps/constants/Business Search Result.csv (column "UBI#")
Output : for each UBI
  - wa_corps/html_captures/{UBI}/list.html
  - wa_corps/html_captures/{UBI}/detail.html
  - wa_corps/business_json/{UBI}.json
  - wa_corps/business_pdf/{UBI}/annual_report.pdf # we'll get contact info from here in postprocessing

CLI slicing for parallel runs:
  --start_n N (1-based, inclusive)
  --stop_n  M (inclusive)
"""

import argparse
import csv
import json
import time
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import logging
from logging.handlers import RotatingFileHandler

# --- repo path setup (import start_driver) ---
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from utils.driver_session import start_driver  # noqa
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

# --- paths ---
INPUT_CSV        = ROOT / "wa_corps" / "constants" / "Business Search Result.csv"

HTML_CAPTURE_DIR = ROOT / "wa_corps" / "html_captures"
HTML_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

JSON_OUTPUT_DIR  = ROOT / "wa_corps" / "business_json"
JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BUSINESS_PDF_DIR = ROOT / "wa_corps" / "business_pdf"
BUSINESS_PDF_DIR.mkdir(parents=True, exist_ok=True)


# --- config ---
BASE_URL  = "https://ccfs.sos.wa.gov/"
WAIT_TIME = 25  # generous; Angular SPA needs time

# --- logging setup ---
LOG_DIR = ROOT / "wa_corps" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "ccfs_lookup.log"

# Configure logger
logger = logging.getLogger("ccfs")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


# -------------------- logging & progress tracking helpers --------------------

# helper for logging to both console and file
def dual_log(message: str, level: str = "info"):
    """Print to console and log to file at the same time."""
    print(message)
    if level == "info":
        logger.info(message)
    elif level == "warn":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "debug":
        logger.debug(message)
    else:
        logger.info(message)

# progress tracking globals
def log_progress(ubi: str, index: int, total: int, status: str):
    global success_count, fail_count, block_detected

    now = time.time()
    elapsed = now - start_time
    elapsed_str = str(timedelta(seconds=int(elapsed)))

    if status == "success":
        success_count += 1
    elif status.startswith("fail"):
        fail_count += 1
    elif status == "blocked":
        block_detected = True

    msg = (f"[LOG] {datetime.now().isoformat()} | "
           f"UBI {index}/{total}: {ubi} | "
           f"Status: {status} | "
           f"Elapsed: {elapsed_str} | "
           f"Success: {success_count} | Fail: {fail_count}")
    dual_log(msg)

# log summary helper
def summarize_log(log_path: Path = LOG_FILE):
    """
    Parse the ccfs_lookup.log file and summarize performance.
    """
    if not log_path.exists():
        print(f"[ERROR] No logfile found at {log_path}")
        return

    successes, fails, blocks = 0, 0, 0
    first_block_idx, first_block_time = None, None

    with log_path.open(encoding="utf-8") as f:
        for line in f:
            if "Status:" not in line:
                continue
            parts = line.strip().split("|")
            if len(parts) < 4:
                continue
            status = parts[3].split(":")[-1].strip().lower()

            if "success" in status:
                successes += 1
            elif "fail" in status:
                fails += 1
            elif "blocked" in status:
                blocks += 1
                if first_block_idx is None:
                    first_block_idx = successes + fails
                    first_block_time = parts[0]

    dual_log("==== SUMMARY ====", "info")
    dual_log(f"Total successes: {successes}", "info")
    dual_log(f"Total fails: {fails}", "info")
    dual_log(f"Total blocked: {blocks}", "info")
    if first_block_idx:
        dual_log(f"First block after {first_block_idx} requests at {first_block_time}", "warn")
    dual_log("=================", "info")

# ----------------------- HTML parsing helpers -----------------------

def save_html(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def parse_detail_html(html: str, ubi: str) -> dict:
    """Parse detail HTML into structured JSON with both fields and tables."""
    soup = BeautifulSoup(html, "html.parser")
    data = {"UBI": ubi, "sections": {}}

    page_header = soup.select_one("header.page-header h2")
    if page_header:
        data["meta"] = {"page_header": page_header.get_text(strip=True)}

    for header in soup.select("div.div_header"):
        section_name = header.get_text(strip=True)
        section = {}

        # ---------- Try tables ----------
        table = header.find_next("table")
        if table and header.find_next(string=True) in table.strings:
            # Parse table
            cols = [th.get_text(strip=True) for th in table.select("thead th")]
            rows = []
            for tr in table.select("tbody tr"):
                row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if row:
                    rows.append(row)
            if cols or rows:
                section["columns"] = cols
                section["rows"] = rows

        # ---------- Try fields ----------
        fields = {}
        for row in header.find_all_next("div", class_="row"):
            cols = row.find_all("div", class_=["col-md-3", "col-md-5", "col-md-7", "col-md-8"])
            if len(cols) >= 2:
                label = cols[0].get_text(strip=True).rstrip(":")
                value = cols[1].get_text(strip=True)
                if label:
                    fields[label] = value
            else:
                # Stop once we hit unrelated layout
                if fields:
                    break
        if fields:
            section["fields"] = fields

        if section:
            data["sections"][section_name] = section

    return data


def save_latest_annual_report(driver, ubi: str, ubi_dir: Path, json_data: dict):
    """
    From the business detail page, navigate to Filing History, open most recent Annual Report,
    and download the PDF if available. Moves it into wa_corps/business_pdf/{UBI}/annual_report.pdf
    and records the path in json_data["capture_paths"].
    """
    try:
        # Click Filing History
        _safe_click_element(driver, driver.find_element(By.ID, "btnFilingHistory"), settle_delay=2)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.table-responsive"))
        )
        time.sleep(1.5)

        # Find all rows containing "ANNUAL REPORT"
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table.table-responsive tbody tr")
        annual_report_rows = [r for r in rows if "ANNUAL REPORT" in r.text.upper()]
        if not annual_report_rows:
            print(f"[WARN] No Annual Report rows found for {ubi}")
            return

        # The first row is the most recent
        most_recent_row = annual_report_rows[0]
        view_docs_link = most_recent_row.find_element(By.LINK_TEXT, "View Documents")
        _safe_click_element(driver, view_docs_link, settle_delay=2)

        # Wait for modal with transaction documents
        modal = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal-dialog"))
        )
        time.sleep(1.0)

        # Look for fulfilled Annual Reports in modal
        doc_rows = modal.find_elements(By.CSS_SELECTOR, "tbody tr")
        fulfilled = [r for r in doc_rows if "ANNUAL REPORT - FULFILLED" in r.text.upper()]
        if not fulfilled:
            print(f"[WARN] No fulfilled Annual Report found in modal for {ubi}")
            return

        # Most recent = first row
        download_icon = fulfilled[0].find_element(By.CSS_SELECTOR, "i.fa-file-text-o")

        # mark a threshold BEFORE clicking
        threshold = time.time()
        print(f"[DEBUG] Threshold time before download click: {threshold}")
        # Click to trigger download
        try:
            _safe_click_element(driver, download_icon, settle_delay=2)
            print(f"[INFO] Clicked download icon for Annual Report for {ubi}")
        except TimeoutException:
            print("[WARN] First click attempt blocked, retrying after clearing overlays...")
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal-backdrop"))
            )
            driver.execute_script("arguments[0].click();", download_icon)
            time.sleep(2.0)

        # Wait for Download to finish (generally <1sec, so we're waiting a static 5 sec to keep it simple)
        time.sleep(5)
        print(f"[INFO] Waited 5 sec for download to finish for {ubi}")

        # Prepare output dir
        ubi_pdf_dir = BUSINESS_PDF_DIR / ubi.replace(" ", "")
        ubi_pdf_dir.mkdir(parents=True, exist_ok=True)
        target = ubi_pdf_dir / "annual_report.pdf"

        # Poll for PDF in the ephemeral profile's ~/Downloads folder
        # query the ephemeral profile for it's downloads folder
        profile_dir = Path(driver.capabilities['moz:profile'])
        downloads_dir = profile_dir / "downloads"
        
        # We could set Firefox profile so the PDF goes straight 
        # into wa_corps/business_pdf/{UBI} without ever touching ~/Downloads,
        # which would avoid this whole polling loop.
        # but for now we want to keep using ephemeral profiles so we don't have to manage cleanup.
        # so we query the ephemeral profile's downloads folder and use that
        downloads = downloads_dir
        end_time = time.time() + 60

        # Just always grab the newest PDF
        while time.time() < end_time:
            # look for any PDF newer than threshold
            pdfs = [p for p in downloads.glob("*.pdf") if p.stat().st_mtime > threshold]
            # Instead of trying to track filenames, we just say:
            # “anything written to ~/Downloads after the click is ours.”
            # This works whether the browser overwrote an old filename or created …(1).pdf.
            # The 5-second buffer gives Firefox/Chrome time to finish renaming .part → .pdf.
            if pdfs:
                newest = max(pdfs, key=lambda p: p.stat().st_mtime)
                newest.replace(target)
                json_data.setdefault("capture_paths", {})["annual_report_pdf"] = str(target)
                print(f"[INFO] Saved annual report PDF → {target}")
                return
            time.sleep(1)

        print(f"[WARN] Timed out waiting for annual report PDF for {ubi}")

    except Exception as e:
        print(f"[ERROR] Failed to save annual report for {ubi}: {e}")


# ----------------------- Selenium helpers -----------------------

def wait_clickable(driver, locator, timeout=WAIT_TIME):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))


def wait_present(driver, locator, timeout=WAIT_TIME):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))


def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)


def ensure_home_search_box(driver):
    """
    Make sure we're on the HOME page and can see the global search input
    with placeholder containing 'UBI'. If we're on a results page, click Back.
    """
    # Quick path: try to find the input where we are
    for _ in range(2):
        try:
            box = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder,'UBI')]"))
            )
            return box
        except TimeoutException:
            pass
        # If we didn't find the box, try a 'Back' button (results page shows Back)
        try:
            back_btn = driver.find_element(By.XPATH, "//input[@value='Back' or @id='btnReturnToSearch']")
            try:
                js_click(driver, back_btn)
            except Exception:
                back_btn.click()
            time.sleep(1.5)
        except NoSuchElementException:
            break

    # Force-load HOME and wait for the box
    driver.get(BASE_URL)
    return wait_clickable(driver, (By.XPATH, "//input[contains(@placeholder,'UBI')]"))


def submit_search_from_home(driver, ubi: str):
    """
    On HOME page: type UBI into the big search box and submit.
    Prefer clicking the Search button; fall back to ENTER.
    """
    search_input = ensure_home_search_box(driver)
    search_input.clear()
    search_input.send_keys(ubi)

    # Try to click a Search button near it (or any visible Search button)
    buttons = driver.find_elements(By.XPATH, "//button[normalize-space()='Search'] | //input[@type='button' and @value='Search']")
    clicked = False
    for b in buttons:
        try:
            if b.is_displayed() and b.is_enabled():
                try:
                    js_click(driver, b)
                except Exception:
                    b.click()
                clicked = True
                break
        except StaleElementReferenceException:
            continue

    if not clicked:
        search_input.send_keys(Keys.ENTER)

    # Wait for at least the results table to appear (even if empty first)
    wait_present(driver, (By.XPATH, "//table[contains(@class,'table')]"))
    # Give Angular a moment to render rows
    time.sleep(1.5)


def ensure_results_have_rows_or_retry(driver, ubi: str):
    """
    If results show 0 rows, try to go Back and re-run search once.
    Return True if we have >= 1 row after possible retry, else False.
    """
    def row_count():
        return len(driver.find_elements(By.XPATH, "//table[contains(@class,'table')]//tbody/tr"))

    if row_count() > 0:
        return True

    # Try one retry path: click Back → home → submit again
    try:
        back_btn = driver.find_element(By.XPATH, "//input[@value='Back' or @id='btnReturnToSearch']")
        try:
            js_click(driver, back_btn)
        except Exception:
            back_btn.click()
        time.sleep(1.0)
    except NoSuchElementException:
        # If no Back, force home
        driver.get(BASE_URL)

    # Re-submit
    submit_search_from_home(driver, ubi)
    time.sleep(1.0)
    return row_count() > 0


def click_first_result(driver) -> str:
    """
    Clicks the first result link in the results table.
    Returns the business name text (best-effort) for logging.
    """
    first_link = wait_clickable(
        driver, (By.XPATH, "//table[contains(@class,'table')]//tbody/tr[1]//a")
    )
    name = first_link.text.strip()
    try:
        js_click(driver, first_link)
    except Exception:
        first_link.click()
    return name


# ----------------------- main per-UBI flow -----------------------

def process_ubi(driver, ubi: str, index: int, total: int):
    ubi_clean = ubi.replace(" ", "")
    ubi_dir = HTML_CAPTURE_DIR / ubi_clean
    print(f"[INFO] Processing UBI {index}/{total}: {ubi}")

    try:
        # Always begin from Home and submit the search there (this is the reliable route)
        submit_search_from_home(driver, ubi)

        # If we landed on results but with zero rows, recover via Back → retry once
        if not ensure_results_have_rows_or_retry(driver, ubi):
            # Save the empty list page for forensics, then give up on this UBI
            save_html(ubi_dir / "list.html", driver.page_source)
            print(f"[WARN] No results for UBI {ubi}")
            return

        # Save list.html (with rows)
        save_html(ubi_dir / "list.html", driver.page_source)

        # Click the first (and only one we need)
        try:
            business_name = click_first_result(driver)
            if business_name:
                print(f"[INFO] Clicking: {business_name}")
        except TimeoutException:
            print(f"[ERROR] Could not click first result for UBI {ubi}")
            return

        # Wait for details panel
        wait_present(driver, (By.ID, "divBusinessInformation"))
        time.sleep(1.5)  # let Angular finish

        # Save detail.html
        save_html(ubi_dir / "detail.html", driver.page_source)

        # Parse to JSON
        json_data = parse_detail_html(driver.page_source, ubi)
        json_data["capture_paths"] = {
            "list_html": str(ubi_dir / "list.html"),
            "detail_html": str(ubi_dir / "detail.html"),
        }
        out_path = JSON_OUTPUT_DIR / f"{ubi_clean}.json"
        out_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
        print(f"[INFO] Saved JSON → {out_path}")

        # Try to capture annual report PDF
        save_latest_annual_report(driver, ubi, ubi_dir, json_data)

        # Re-save JSON (now with PDF path if found)
        out_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    except TimeoutException:
        print(f"[ERROR] Timeout for UBI {ubi}")
    except Exception as e:
        print(f"[ERROR] Unexpected error for UBI {ubi}: {e}")


# ----------------------- CLI & runner -----------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_n", type=int, default=1, help="Start index (1-based)")
    parser.add_argument("--stop_n", type=int, default=None, help="Stop index (inclusive)")
    args = parser.parse_args()

    if not INPUT_CSV.exists():
        print(f"[ERROR] Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    # Read all UBIs
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ubis = [row["UBI#"].strip() for row in reader if row.get("UBI#")]

    total = len(ubis)
    if total == 0:
        print("[ERROR] No UBIs found in input CSV")
        sys.exit(1)

    start_n = max(1, args.start_n)
    stop_n = args.stop_n if args.stop_n is not None else total
    if start_n > total:
        print(f"[ERROR] start_n {start_n} > total {total}")
        sys.exit(1)
    stop_n = min(stop_n, total)

    slice_ubis = ubis[start_n - 1: stop_n]
    print(f"[INFO] Loaded {total} UBIs, processing {len(slice_ubis)} (rows {start_n}..{stop_n})")

    # Single stable session
    with start_driver() as driver:
        # Ensure we load home once up-front (also prompts any CF/js to settle)
        driver.get(BASE_URL)
        for i, ubi in enumerate(slice_ubis, start=start_n):
            process_ubi(driver, ubi, i, total)


if __name__ == "__main__":
    main()
    summarize_log()
