#!/usr/bin/env python3
# ccfs_lookup.py

import csv
import os
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- imports: be flexible about package layout ---
try:
    from utils.driver_session import start_driver  # preferred if available
except ImportError:
    from driver_session import start_driver

try:
    from utils.SPA_utils import wait_scroll_interact, _safe_click_element
except ImportError:
    from SPA_utils import wait_scroll_interact, _safe_click_element


# ---------- Constants & Paths ----------
BASE_DIR = Path(__file__).parent
CONSTANTS_DIR = BASE_DIR / "constants"

CSV_PATH = CONSTANTS_DIR / "Business Search Result.csv"
OUTPUT_PATH = CONSTANTS_DIR / "Business Details.csv"

CAPTURE_ROOT = BASE_DIR / "html_captures"  # per UBI subfolders live here
CAPTURE_ROOT.mkdir(exist_ok=True, parents=True)

URL_HOME = "https://ccfs.sos.wa.gov/#/Home"
URL_DETAIL_FMT = "https://ccfs.sos.wa.gov/#/BusinessSearch/BusinessInformation/{business_id}"

# Optional slow-mo for watch-and-debug (seconds)
WATCH_SLEEP = float(os.getenv("WATCH_SLEEP", "0"))

FIELDNAMES = [
    "UBI",
    "Business ID",
    "Business Name",
    "Business Type",
    "Status",
    "Registered Agent",
    "Registered Agent Address",
    "Principal Office",
    "Mailing Address",
    "Nature of Business",
    "Governors",
    "Filing History",           # left blank; separate nav
    "Detail URL",
    "list_capture_path",
    "detail_capture_path",
    "debug_path",
]


# ---------- Small helpers ----------
def dbg_sleep():
    if WATCH_SLEEP > 0:
        time.sleep(WATCH_SLEEP)


def ubi_key(ubi: str) -> str:
    return re.sub(r"\s+", "", ubi.strip())


def ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def save_html_source(driver, path: Path) -> str:
    ensure_dir(path)
    path.write_text(driver.page_source, encoding="utf-8")
    return str(path)


def read_ubi_numbers():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            v = (row.get("UBI#") or "").strip()
            if v:
                yield v


def get_already_processed():
    """
    Consider a UBI processed if 'Governors' column is non-empty in OUTPUT_PATH.
    """
    if not OUTPUT_PATH.exists():
        return set()
    done = set()
    with open(OUTPUT_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            u = (r.get("UBI") or "").strip()
            if u and (r.get("Governors") or "").strip():
                done.add(u)
    return done


# ---------- Parsing (detail page) ----------
def _text_after_label(soup: BeautifulSoup, label: str) -> str:
    """
    Find textual label like 'Business Name:' and return the nearest following <strong> text.
    """
    el = soup.find(string=lambda s: isinstance(s, str) and label in s)
    if el:
        nxt = el.find_next("strong")
        if nxt:
            return nxt.get_text(strip=True)
    return ""


def parse_detail_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    data["Business Name"] = _text_after_label(soup, "Business Name:")
    data["UBI"] = _text_after_label(soup, "UBI Number:")
    data["Business Type"] = _text_after_label(soup, "Business Type:")
    data["Status"] = _text_after_label(soup, "Business Status:")
    data["Principal Office"] = _text_after_label(soup, "Principal Office Street Address:")
    data["Mailing Address"] = _text_after_label(soup, "Principal Office Mailing Address:")
    data["Nature of Business"] = _text_after_label(soup, "Nature of Business:")

    # Registered Agent section
    agent_header = soup.find("div", class_="div_header", string=lambda s: isinstance(s, str) and "Registered Agent Information" in s)
    if agent_header:
        # The section content sits in a nearby row-margin container
        section = agent_header.find_parent("div", class_="row-margin")
        if section:
            # Name appears in <b>, addresses in <strong>
            name_el = section.find("b")
            data["Registered Agent"] = name_el.get_text(strip=True) if name_el else ""
            # collect first two strongs under the section as addresses (street + mailing)
            strongs = section.find_all("strong")
            agent_addr = ""
            if strongs:
                # Try to prefer the 'Street Address' strong by scanning the label next to it
                # but a simple fallback to the first strong is usually correct here
                agent_addr = strongs[0].get_text(strip=True)
            data["Registered Agent Address"] = agent_addr

    # Governors table
    governors = []
    gov_header = soup.find("div", class_="div_header", string=lambda s: isinstance(s, str) and "Governors" in s)
    if gov_header:
        table = gov_header.find_next("table")
        if table:
            for tr in table.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if tds:
                    # typical order: Title | Type | Entity Name | First | Last
                    governors.append(", ".join(tds))
    data["Governors"] = "; ".join(governors)

    # Filing History lives behind another button; leave blank for now
    data["Filing History"] = ""

    return data


# ---------- Navigation (SPA) ----------
def run_ubi_search_from_home(driver, ubi: str):
    """
    Open Home, type UBI, click Search, wait for result rows.
    """
    driver.get(URL_HOME)
    dbg_sleep()

    # Home search box + search button as used originally
    wait_scroll_interact(driver, by=By.CSS_SELECTOR, selector="input#UBINumber",
                         action="send_keys", keys=ubi, timeout=30, settle_delay=0.6)
    wait_scroll_interact(driver, by=By.CSS_SELECTOR, selector="button.btn-search",
                         action="click", timeout=30, settle_delay=0.6)

    # Wait until at least one row is present
    WebDriverWait(driver, 30).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    dbg_sleep()


def back_to_list_or_home_and_restore(driver, ubi: str):
    """
    After parsing a detail page, return to list. If we bounce to Home,
    re-run the search for this UBI.
    """
    # Prefer explicit "Return to Business Search" button
    try:
        wait_scroll_interact(driver, by=By.CSS_SELECTOR, selector="#btnReturnToSearch",
                             action="click", timeout=6, settle_delay=0.4)
    except Exception:
        # Fallback: there's also a 'Back' button on the page
        try:
            wait_scroll_interact(driver, by=By.CSS_SELECTOR, selector=".btn-back",
                                 action="click", timeout=3, settle_delay=0.4)
        except Exception:
            pass

    # Either we land back on BusinessSearch (list) or Home
    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        dbg_sleep()
        return
    except TimeoutException:
        # If no table rows, maybe we're on Home → rerun the search quickly
        try:
            WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#UBINumber"))
            )
            # Home: search again for this ubi
            run_ubi_search_from_home(driver, ubi)
        except TimeoutException:
            # Last resort: just go Home and search again
            run_ubi_search_from_home(driver, ubi)


# ---------- Core per-UBI workflow ----------
def process_ubi(driver, ubi: str, writer):
    ukey = ubi_key(ubi)
    cap_dir = CAPTURE_ROOT / ukey
    cap_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Processing UBI {ubi}...")

    # Always start search fresh from Home for this ubi
    run_ubi_search_from_home(driver, ubi)

    # Save list page immediately for debug
    list_path = cap_dir / "list.html"
    save_html_source(driver, list_path)
    print(f"[DEBUG] Saved list HTML to {list_path}")

    # Gather row elements
    rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
    if not rows:
        print(f"[WARN] No rows for {ubi} — see {list_path}")
        return 0

    # Use index-based loop so we can re-query rows after returning from detail
    count_written = 0
    idx = 0
    while idx < len(rows):
        try:
            # Re-fetch rows each iteration to avoid stale element issues
            rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
            if idx >= len(rows):
                break

            row = rows[idx]
            # Link + basic info from the row (BusinessID in ng-click)
            link = row.find_element(By.CSS_SELECTOR, "a.btn-link")
            name = link.text.strip()

            ng_click = link.get_attribute("ng-click") or ""
            m = re.search(r"showBusineInfo\((\d+)", ng_click)
            business_id = m.group(1) if m else ""

            # Table cells (to pick up status/type if desired)
            cells = [td.text.strip() for td in row.find_elements(By.CSS_SELECTOR, "td")]
            list_business_type = cells[2] if len(cells) >= 3 else ""
            list_status = cells[-1] if cells else ""

            print(f"[INFO] Clicking row {idx + 1}: {name}")
            _safe_click_element(driver, link)
            dbg_sleep()

            # Wait for detail page key container
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#divBusinessInformation"))
            )
            dbg_sleep()

            # Save detail page
            detail_path = cap_dir / f"detail_row{idx + 1}.html"
            save_html_source(driver, detail_path)
            print(f"[DEBUG] Saved detail HTML to {detail_path}")

            # Parse detail page
            record = parse_detail_html(Path(detail_path).read_text(encoding="utf-8"))

            # Fill fallbacks from list if detail missed something
            if not record.get("Business Type"):
                record["Business Type"] = list_business_type
            if not record.get("Status"):
                record["Status"] = list_status

            record.update({
                "UBI": ubi,
                "Business ID": business_id,
                "Detail URL": URL_DETAIL_FMT.format(business_id=business_id) if business_id else "",
                "list_capture_path": str(list_path),
                "detail_capture_path": str(detail_path),
                "debug_path": str(detail_path),
            })

            writer.writerow(record)
            count_written += 1

            # If there might be more rows, go back to list (or Home+re-search)
            idx += 1
            if idx < len(rows):
                back_to_list_or_home_and_restore(driver, ubi)
                # (list reloaded; loop will re-fetch rows)
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            print(f"[ERROR] Failed row {idx + 1} for {ubi}: {e}")
            # Attempt to recover back to list/home for next potential row
            try:
                back_to_list_or_home_and_restore(driver, ubi)
            except Exception:
                pass
            idx += 1  # skip this row to avoid infinite loop

    if count_written == 0:
        print(f"[WARN] No results captured for {ubi}")
    else:
        print(f"[INFO] Wrote {count_written} records for UBI {ubi}")
    return count_written


# ---------- Main ----------
def main():
    processed = get_already_processed()
    if processed:
        print(f"[INFO] Already processed {len(processed)} UBIs.")
    else:
        print(f"[INFO] Already processed 0 UBIs.")

    write_header = not OUTPUT_PATH.exists()
    with open(OUTPUT_PATH, "a", newline="", encoding="utf-8") as outf:
        writer = csv.DictWriter(outf, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()

        with start_driver() as driver:
            for ubi in read_ubi_numbers():
                if ubi in processed:
                    print(f"[SKIP] UBI {ubi} already processed.")
                    continue
                try:
                    process_ubi(driver, ubi, writer)
                except Exception as e:
                    print(f"[ERROR] Failed for {ubi}: {e}")


if __name__ == "__main__":
    main()
# End of ccfs_lookup.py