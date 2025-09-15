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


# ----------------------- helpers -----------------------

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
    and download the PDF if available.
    """
    try:
        # Click Filing History
        _safe_click_element(driver, driver.find_element(By.ID, "btnFilingHistory"), settle_delay=2)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.table-responsive"))
        )
        time.sleep(1.5)

        # Find all rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table.table-responsive tbody tr")
        annual_report_rows = [
            r for r in rows if "ANNUAL REPORT" in r.text.upper()
        ]
        if not annual_report_rows:
            print(f"[INFO] No Annual Report rows found for {ubi}")
            return

        # The first row is the most recent
        most_recent_row = annual_report_rows[0]
        view_docs_link = most_recent_row.find_element(By.LINK_TEXT, "View Documents")
        _safe_click_element(driver, view_docs_link, settle_delay=2)

        # Wait for modal
        modal = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal-dialog"))
        )
        time.sleep(1.0)

        # Find fulfilled report rows in modal
        doc_rows = modal.find_elements(By.CSS_SELECTOR, "tbody tr")
        fulfilled = [
            r for r in doc_rows if "ANNUAL REPORT - FULFILLED" in r.text.upper()
        ]
        if not fulfilled:
            print(f"[INFO] No fulfilled Annual Report found in modal for {ubi}")
            return

        # First fulfilled entry = most recent
        download_icon = fulfilled[0].find_element(By.CSS_SELECTOR, "i.fa-file-text-o")
        _safe_click_element(driver, download_icon, settle_delay=2)

        # Handle download (depends on browser profile)
        # If using Firefox auto-download, file goes to default Downloads dir.
        # Move it to wa_corps/business_pdf/{UBI}/annual_report.pdf
        ubi_pdf_dir = BUSINESS_PDF_DIR / ubi.replace(" ", "")
        ubi_pdf_dir.mkdir(parents=True, exist_ok=True)

        # Poll for new PDF in Downloads
        downloads = Path.home() / "Downloads"
        for _ in range(30):  # wait up to ~30s
            pdfs = sorted(downloads.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                newest = pdfs[0]
                target = ubi_pdf_dir / "annual_report.pdf"
                newest.replace(target)
                json_data.setdefault("capture_paths", {})["annual_report_pdf"] = str(target)
                print(f"[INFO] Saved annual report PDF → {target}")
                return
            time.sleep(1.0)

        print(f"[WARN] Timed out waiting for PDF download for {ubi}")

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

        # Click "Filing History" button: <input type="button" id="btnFilingHistory" class="btn btn-success" value="Filing History" ng-click="navBusinessFilings()">
        # Args:
        #     driver: Selenium WebDriver instance
        #     by: locator type, e.g., By.CSS_SELECTOR
        #     selector: element selector string
        #     action: "click" (default) or "send_keys"
        #     keys: text to send if action="send_keys"
        #     timeout: max seconds to wait for element
        #     settle_delay: pause after scrolling (for animations)
        _safe_click_element(driver, driver.find_element(By.ID, "btnFilingHistory"), settle_delay=2)
        time.sleep(2.0)  # let Angular finish

        # Scan the business filing table: 
        # #divBusinessInformation > div:nth-child(4) > div.row-margin > div > div > table > tbody:nth-child(3)
        # 
        # for the first "Annual Report" rowand click the "View Documents" link in that row to open the modal: 
        # <tr ng-repeat="filing in businessFilings| orderBy:propertyName:reverse" class="ng-scope" style="">
        #     <td class="ng-binding">0021617353</td>
        #     <td class="ng-binding">02/01/2025 07:27:41 AM</td>

        #     <td class="ng-binding">02/01/2025</td>
        #     <!--<td>{{filing.ProcessedBy | uppercase}}</td>-->
        #     <td ng-bind="filing.FilingTypeName" class="ng-binding">ANNUAL REPORT</td>
        #     <!--<td ng-if="filing.DocumentId > 0">
        #         <i class="fa fa-file-text-o fa-lg" style="cursor:pointer" filename="filing.FileName" params="filing" url="Common/DownloadFileByNumber?filingNo={{filing.FilingNumber}}" title="Download" download-file ng-bind="filing.FilingTypeName">
        #             <span ng-bind="filing.FilingTypeName"></span>
        #         </i>
        #     </td>-->
        #     <td>
        #         <a class="btn-link" style="cursor:pointer" ng-click="getTransactionDocumentsList(filing.FilingNumber,filing.Transactionid,filing.FilingTypeName)">View Documents</a>
        #     </td>
        #     <!--<td ng-if="filing.DocumentId == 0"></td>-->
        # </tr>
        # 
        #
        # Then, in the modal, find the PDF link for the "ANNUAL REPORT - FULFILLED" and download it
        # Modal with table inside of it: 
        # 
        # <div class="modal-dialog" style="width:80%;">
        #     <div class="modal-content">
        #         <div class="modal-header">
        #             ...
        #         </div>
        #         <div class="searchresult modal-body" style="max-height:600px;overflow-y:auto;">
        #             <div class="row table-responsive table-striped">
        #                 <table style="width:100%" border="0" cellpadding="4" cellspacing="0" class="table table-responsive table-striped">
        #                     <thead>
        #                         <tr align="center" class="bg-primary text-center">
        #                             <!--<th>File Name</th>-->
        #                             <th>Document Type</th>
        #                             <!--<th>Created By</th>-->
        #                             <th>Created Date</th>
        #                             <th>Action</th>
        #                         </tr>
        #                     </thead>
        #                     <!-- ngRepeat: document in transactionDocumentsList --><!-- ngIf: document.DocumentTypeID!=2 --><tbody data-ng-repeat="document in transactionDocumentsList" data-ng-if="document.DocumentTypeID!=2" class="ng-scope" style="">
        #                         <tr align="left" class="bgwhite">
        #                             <!--<td><span data-ng-bind="document.CorrespondenceFileName"></span></td>-->
        #                             <td><span data-ng-bind="document.DocumentTypeName" class="ng-binding">ANNUAL REPORT - FULFILLED</span></td>
        #                             <!--<td><span data-ng-bind="document.UserName"></span></td>-->
        #                             <td><span data-ng-bind="document.FilingDateTime | date:'MM/dd/yyyy'" class="ng-binding">02/01/2025</span></td>
        #                             <td>
        #                                 <i class="fa fa-file-text-o fa-lg ng-binding ng-isolate-scope ng-scope" style="cursor:pointer" filename="document.CorrespondenceFileName" params="document" url="Common/DownloadOnlineFilesByNumber?fileName=&amp;CorrespondenceFileName=&amp;DocumentTypeId=" title="Download/Print" download-file="" ng-bind="document.CorrespondenceFileName" ng-click="downloadPdf()"></i>
        #                             </td>
        #                         </tr>
        #                     ...
        #                     <tbody data-ng-hide="transactionDocumentsList.length&gt;0" class="ng-hide" style="">
        #                         <tr><td colspan="5" ng-bind="messages.RegisteredAgent.emptyRecordsMsg" class="ng-binding">No Value Found.</td></tr>
        #                     </tbody>
        #                 </table>
        #             </div>
        #         </div>
        #     </div>
        # </div>
        #
        # table row of interest:
        # <tr align="left" class="bgwhite">
        #     <!--<td><span data-ng-bind="document.CorrespondenceFileName"></span></td>-->
        #     <td><span data-ng-bind="document.DocumentTypeName" class="ng-binding">ANNUAL REPORT - FULFILLED</span></td>
        #     <!--<td><span data-ng-bind="document.UserName"></span></td>-->
        #     <td><span data-ng-bind="document.FilingDateTime | date:'MM/dd/yyyy'" class="ng-binding">02/01/2025</span></td>
        #     <td>
        #         <i class="fa fa-file-text-o fa-lg ng-binding ng-isolate-scope ng-scope" style="cursor:pointer" filename="document.CorrespondenceFileName" params="document" url="Common/DownloadOnlineFilesByNumber?fileName=&amp;CorrespondenceFileName=&amp;DocumentTypeId=" title="Download/Print" download-file="" ng-bind="document.CorrespondenceFileName" ng-click="downloadPdf()"></i>
        #     </td>
        # </tr>
        #
        # download button: <i class="fa fa-file-text-o fa-lg ng-binding ng-isolate-scope ng-scope" style="cursor:pointer" filename="document.CorrespondenceFileName" params="document" url="Common/DownloadOnlineFilesByNumber?fileName=&amp;CorrespondenceFileName=&amp;DocumentTypeId=" title="Download/Print" download-file="" ng-bind="document.CorrespondenceFileName" ng-click="downloadPdf()"></i>
        # save the PDF to wa_corps/business_pdf/{UBI}/annual_report.pdf
        # and record the path in the JSON output under "capture_paths.annual_report_pdf"
        # Note: there may be multiple "ANNUAL REPORT - FULFILLED" entries; we want the most recent one (top of table)
        # Note: there may be no "ANNUAL REPORT - FULFILLED" entry at all
        # Finally, navigate back to the home page for the next UBI
        # (we could also try to click a "Back" button, but this is more robust)
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
