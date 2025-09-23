-------------------------------------------------------------------------------

I'm trying to adapt aetna_pdf_grabber.py to work for humana, and have written the following ~/medicare/humana/humana_pdf_grabber.py so far:
```
# https://plans.humana.com/

#!/usr/bin/env python3
"""
humana_pdf_grabber.py

Reads plan IDs from humana_plan_links.csv, visits the humana plan page, and downloads
key documents (SB, EOC, Formulary, ANOC in EN/ES).

Features:
- Progress indication using global 1-based index: [(i/total)] PLAN_ID
- Resume by progress index: --start-n and --stop-n (1-based, inclusive)
- Skips already-downloaded PDFs
- Polite delays; downloads via requests Session cloned from Selenium driver
"""

import os
import re
import argparse
from time import sleep
from urllib.parse import urljoin

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# if you want to keep relative imports
# If you always run the script directly (python medicare/humana/humana_pdf_grabber.py from the project root), you can instead do:
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# That forces Python to see the project root, no matter where you launch from.
from utils.driver_session import start_driver
from utils.SPA_utils import make_requests_session_from_driver
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

BASE_ORIGIN = "https://plans.humana.com/"
BASE_URL = f"{BASE_ORIGIN}"
OUTPUT_DIR = "humana_PDFs"

DOC_LABELS = [
    "Summary of Benefits",
    "Evidence of Coverage",
    "CMS plan ratings",
]


def load_plan_ids(csv_path="medicare/humana/humana_plan_links.csv"):
    """Keep the CSV order, drop duplicates."""
    df = pd.read_csv(csv_path, dtype=str)
    plan_ids = df["plan_id"].drop_duplicates().tolist()
    return plan_ids



def load_plan_details(csv_path="medicare/humana/humana_plan_links.csv"):
    """Keep the CSV order, drop duplicates."""
    df = pd.read_csv(csv_path, dtype=str)
    plans = df["zip","plan_name","plan_id"].drop_duplicates().tolist()
    return plans


def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


def scrape_plan_pdfs(driver, zip: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)

    ### Resume work here: fill in zip code, submit form, wait for page load
    # Note: the page uses a lot of dynamic loading; we need to wait for elements to appear
    sleep(2.0)  # initial wait for page to load
    # <input data-v-37ca5262="" data-maska="#####" data-mask-input="" id="ZIP code" type="text" pattern="[0-9]{5}" required="" autocomplete="postal-code" autocapitalize="none" spellcheck="false" autocorrect="off" inputmode="numeric" aria-invalid="false" mptid="INPUT;mptid:0;0">
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[id="ZIP code"]', action="send_keys", keys=zip, timeout=10)
    sleep(0.5)
    # <button data-v-997824cf="" class="nb-btn nb-btn--primary is-small zcf-btn" type="submit" data-search-button=""><span data-v-997824cf="">Get Started</span><!----></button>
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-search-button]', action="click", timeout=10)
    sleep(3.0)  # wait for page to load
    # if it appears, click the type of medicare plan
    # <nucleus-radio-button data-v-cae155e3="" class="coverage-detail is-selection-card selection-card coverage-type-answer nucleus-radio-selection-card" data-medicare-advantage="" name="medicareAdvantage" value="medicareAdvantage" style="padding: 0.5rem;"><div data-v-cae155e3="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-cae155e3="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-cae155e3="" class="coverage-detail-title">Medicare Advantage <span data-v-cae155e3="" class="caption $nt-color-font-heading nu-d-block">(Part C)</span></div><p data-v-cae155e3="" slot:description="" class="nu-d-none md:nu-d-flex">Includes all the benefits of Original Medicare Part A and Part B, and many include coverage for prescription drugs and routine dental, vision and hearing care</p></nucleus-radio-button>
    try:
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="medicareAdvantage"]', action="click", timeout=5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then click the none applied checkbox
        # <nucleus-checkbox data-v-f4c10c2c="" class="inline-flex" name="noneApplies"> None of these apply to me </nucleus-checkbox>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-checkbox[name="noneApplies"]', action="click", timeout=5)
        sleep(0.5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then select open to all plans radio dial
        # <nucleus-radio-button data-v-3603efc7="" data-open-to-all-plans="" class="coverage-detail is-selection-card selection-card plan-network-answer nucleus-radio-selection-card" name="openToAllPlans" value="true" style="padding: 0.5rem;"><div data-v-3603efc7="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-3603efc7="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-3603efc7="" class="coverage-detail-title">I am open to all plan networks</div><p data-v-3603efc7="" slot:description="" class="nu-d-none md:nu-d-inline">We’ll show you recommended plans regardless of provider network. If you are open to seeing an in-network doctor, we can recommend plans that may have lower out-of-pocket costs.</p></nucleus-radio-button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="true"]', action="click", timeout=5)
        sleep(0.5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then click skip this step
        # <button data-v-024a7d79="" class="link" data-skip=""> Skip <span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">this step</span></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(0.5)
        # and the next skip this step
        # <button data-v-024a7d79="" class="link" data-skip=""> Skip <span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">this step</span></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(3.0)  # wait for page to load
    except Exception:
        pass  # if it doesn't appear, continue  
    # Now we should be at the plan list page
    # After pageload, scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # Then find the div with matching plan_id
    # <div class="plan ma" id="" data-mfe-plancard="" data-plan-id="H5216-428-001-2025" data-list-medicare-plans="" idvpage="">
    plan_div = None
    try:
        plan_div = driver.find_element(By.CSS_SELECTOR, f'div[data-plan-id="{plan_id}"]')
    except Exception:
        print("    [ERROR] Could not find plan div on plan list page")
        return {}
    # and click it's "View plan details" link
    # <button data-v-9ee06d52="" class="link" style="font-size: 19px;" data-plan-link="">View plan details</button>
    # (/div/div/div[2]/div/div[3]/div[3]/div/div[2]/div/button)
    try:
        view_button = plan_div.find_element(By.CSS_SELECTOR, 'button[data-plan-link]')
        _safe_click_element(driver, view_button)
        sleep(3.0)  # wait for page to load
    except Exception:
        print("    [ERROR] Could not find or click 'View plan details' button")
        return {}
    
    # then we should be at the plan details page
    # scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # then look for the "Plan Documents" section and click to expand if needed
    # <div data-v-f27cb03a="" data-v-a6b3722d="" class="plan-summary-accordion nu-w-100" id="plan-documents"><div data-v-f27cb03a="" class="accordion-header"><button data-v-f27cb03a="" class="nu-d-flex nu-items-center nu-justify-between nu-w-100" data-toggle=""><div data-v-f27cb03a="" class="btn-info"><nucleus-icon data-v-f27cb03a="" class="title-icon nu-mr-4"></nucleus-icon><span data-v-f27cb03a="">Plan Documents</span><div data-v-f27cb03a="" class="footer-row"> ( Plan documents were updated <span data-v-f27cb03a="" data-plan-updated-date="">10/01/2024 </span> unless otherwise noted. ) </div></div><div data-v-f27cb03a="" style="display: flex; gap: 2px;"><!----><div data-v-f27cb03a="" class="btn-state"><span data-v-f27cb03a="">Open</span><nucleus-icon data-v-f27cb03a="" class="state-icon nu-ml-1"></nucleus-icon></div></div></button><!----></div><div data-v-f27cb03a="" class="accordion-content" style="display: none;"><div data-v-a6b3722d=""><div data-v-a6b3722d=""><div data-v-96181c9f="" data-v-a6b3722d="" data-plan-documents-content=""><div data-v-96181c9f="" class="table plan-documents"><div data-v-96181c9f="" class="section" data-documents=""><div data-v-96181c9f="" class="header-row"><div data-v-96181c9f="" class="title">Documents</div></div><div data-v-96181c9f="" class="data-row" data-sob-documents=""><div data-v-96181c9f="" class="title">Summary of Benefits</div><div data-v-96181c9f="" class="in-network">View deductibles, copays and more.</div><div data-v-96181c9f="" class="out-of-network"><span data-v-e9a96f92="" data-v-96181c9f="" aria-label="English Benefit PDF"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216428001SB25.pdf" target="_blank" rel="noopener">English <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span><span data-v-e9a96f92="" data-v-96181c9f="" aria-label="Spanish Benefit PDF"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216428001SBSP25.pdf" target="_blank" rel="noopener">Spanish <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span></div></div><div data-v-96181c9f="" class="data-row" data-prov-dir-docments=""><div data-v-96181c9f="" class="title">Provider directory</div><div data-v-96181c9f="" class="in-network">Search the directory on Humana's non-Medicare website.</div><div data-v-96181c9f="" class="out-of-network"><span data-v-68b4aabb="" data-v-96181c9f="" aria-label="List of Providers"><a data-v-68b4aabb="" href="https://finder.humana.com/finder/medical?customerId=1" target="_blank" rel="noopener">List of providers <nucleus-icon data-v-68b4aabb=""></nucleus-icon></a></span></div></div><div data-v-96181c9f="" class="data-row" data-pharm-dir-documents=""><div data-v-96181c9f="" class="title">Pharmacy directory</div><div data-v-96181c9f="" class="in-network">Search the directory on Humana's non-Medicare website.</div><div data-v-96181c9f="" class="out-of-network"><span data-v-68b4aabb="" data-v-96181c9f="" aria-label="List of Pharmacies"><a data-v-68b4aabb="" href="https://finder.humana.com/finder/pharmacy" target="_blank" rel="noopener">List of pharmacies <nucleus-icon data-v-68b4aabb=""></nucleus-icon></a></span></div></div><div data-v-96181c9f="" class="data-row" data-printable-drugs-documents=""><div data-v-96181c9f="" class="title">Printable prescription drug list</div><div data-v-96181c9f="" class="in-network">Visit Humana's non-Medicare website to see prescription drug tiers.</div><div data-v-96181c9f="" class="out-of-network"><span data-v-68b4aabb="" data-v-96181c9f="" aria-label="List of prescription drugs"><a data-v-68b4aabb="" href="http://www.humana.com/drug-list/medicare" target="_blank" rel="noopener">List of prescription drugs <nucleus-icon data-v-68b4aabb=""></nucleus-icon></a></span></div></div><div data-v-96181c9f="" class="data-row" data-eoc-documents=""><div data-v-96181c9f="" class="title">Evidence of Coverage (Updated 11/19/2024)</div><div data-v-96181c9f="" class="in-network">See what's covered, and what you pay as a member of this plan.</div><div data-v-96181c9f="" class="out-of-network"><span data-v-e9a96f92="" data-v-96181c9f="" aria-label="English Evidence of Coverage"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216428001EOC25.pdf" target="_blank" rel="noopener">English <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span><span data-v-e9a96f92="" data-v-96181c9f="" aria-label="Spanish Evidence of Coverage"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216428001EOCSP25.pdf" target="_blank" rel="noopener">Spanish <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span></div></div><div data-v-96181c9f="" class="data-row" data-stars-documents=""><div data-v-96181c9f="" class="title">CMS plan ratings</div><div data-v-96181c9f="" class="in-network">Check how Medicare rates this plan's quality and performance.</div><div data-v-96181c9f="" class="out-of-network"><span data-v-e9a96f92="" data-v-96181c9f="" aria-label="English CMS Plan Rating PDF"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216GHA09ECHH25.pdf" target="_blank" rel="noopener">English <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span><span data-v-e9a96f92="" data-v-96181c9f="" aria-label="Spanish CMS Plan Rating PDF"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216GHA09ECHH25RS.pdf" target="_blank" rel="noopener">Spanish <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span></div></div><!----></div></div></div></div></div></div></div>
    try:
        accordion_header = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]')
        # check if it's already open by looking at the accordion content div's style
        accordion_content = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content')
        # Open:
        # <div data-v-f27cb03a="" class="accordion-header open-shadow"><button data-v-f27cb03a="" class="nu-d-flex nu-items-center nu-justify-between nu-w-100" data-toggle=""><div data-v-f27cb03a="" class="btn-info"><nucleus-icon data-v-f27cb03a="" class="title-icon nu-mr-4"></nucleus-icon><span data-v-f27cb03a="">Plan Documents</span><div data-v-f27cb03a="" class="footer-row"> ( Plan documents were updated <span data-v-f27cb03a="" data-plan-updated-date="">10/01/2024 </span> unless otherwise noted. ) </div></div><div data-v-f27cb03a="" style="display: flex; gap: 2px;"><!----><div data-v-f27cb03a="" class="btn-state"><span data-v-f27cb03a="">Close</span><nucleus-icon data-v-f27cb03a="" class="state-icon nu-ml-1"></nucleus-icon></div></div></button><!----></div>
        # Closed:
        # <div data-v-f27cb03a="" class="accordion-header"><button data-v-f27cb03a="" class="nu-d-flex nu-items-center nu-justify-between nu-w-100" data-toggle=""><div data-v-f27cb03a="" class="btn-info"><nucleus-icon data-v-f27cb03a="" class="title-icon nu-mr-4"></nucleus-icon><span data-v-f27cb03a="">Plan Documents</span><div data-v-f27cb03a="" class="footer-row"> ( Plan documents were updated <span data-v-f27cb03a="" data-plan-updated-date="">10/01/2024 </span> unless otherwise noted. ) </div></div><div data-v-f27cb03a="" style="display: flex; gap: 2px;"><!----><div data-v-f27cb03a="" class="btn-state"><span data-v-f27cb03a="">Open</span><nucleus-icon data-v-f27cb03a="" class="state-icon nu-ml-1"></nucleus-icon></div></div></button><!----></div>
        if "open-shadow" not in accordion_content.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)  # wait for content to expand 

        
        pdfs = {}   
        # Then look for document links and return them for downloading in main()
        # Example links:
        # SoB: <span data-v-e9a96f92="" data-v-96181c9f="" aria-label="English Benefit PDF"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216428001SB25.pdf" target="_blank" rel="noopener">English <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span>
        # EoC: <span data-v-e9a96f92="" data-v-96181c9f="" aria-label="English Evidence of Coverage"><a data-v-e9a96f92="" href="https://www.humana-medicare.com/BenefitSummary/2025PDFs/H5216428001EOC25.pdf" target="_blank" rel="noopener">English <nucleus-icon data-v-e9a96f92=""></nucleus-icon></a></span>
        # Search in <div class"table plan-documents">

        # For a <div data-v-96181c9f="" class="data-row" data-sob-documents="">
        # and in that row, find the span with aria-label="English Benefit PDF" and add its href to the dict

        # Then search for a <div data-v-96181c9f="" class="data-row" data-eoc-documents="">
        # and in that row, find the span with aria-label="English Evidence of Coverage" and add its href to the dict

        # finally, return the dict of found PDFs



    except Exception:
        print("    [ERROR] Could not find or click 'Plan Documents' accordion")
        return {}



    except Exception:
        # If nothing shows up, probably a CAPTCHA
        input("[ACTION] No document links found (possibly CAPTCHA). Solve it in the browser, then press Enter...")
        # After manual solve, try again
        try:
            elements = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.type__link__digitaldownload"))
            )
        except Exception:
            print("    [ERROR] Still no links after waiting, skipping plan.")
            return pdfs

    # Collect PDFs
    for el in elements:
        try:
            label = (el.get_attribute("data-analytics-name") or "").strip()
            href = (el.get_attribute("href") or "").strip()
            if label in DOC_LABELS and href.lower().endswith(".pdf"):
                pdfs[label] = urljoin(BASE_ORIGIN, href)
        except Exception:
            continue

    return pdfs


def download_pdf(session, url: str, out_path: str):
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"    [OK] {os.path.basename(out_path)}")
    except Exception as e:
        print(f"    [ERROR] {url}: {e}")


def main(start_n: int, stop_n: int | None):
    plan_ids = load_plan_ids()
    total = len(plan_ids)
    if total == 0:
        print("[ERROR] No plan_ids found in humana_plan_links.csv")
        return

    # Normalize 1-based indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    # Convert to 0-based slice; stop_n is inclusive in CLI
    start_idx = start_n - 1
    stop_idx = stop_n  # slice end is exclusive

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        # Enumerate with global 1-based counter
        for i in range(start_idx, stop_idx):
            plan_id = plan_ids[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id}")

            # Gather links
            pdfs = scrape_plan_pdfs(driver, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                # Pause a bit before next plan
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            # Download each desired PDF; skip if exists
            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)  # polite per-file delay

            sleep(2.5)  # polite per-plan delay


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download humana Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
```

As you'll notice, I'm in the final stretch of implementing the scrape_plan_pdfs() function, and once that's done it should all work.

Please finish that function, being careful not to break the existing long and brittle chain of SPA navigation calls.

-------------------------------------------------------------------------------


Got it — thanks for laying this out so clearly. You’re right, you’re just missing the tail end of `scrape_plan_pdfs()`: once you’ve expanded the **Plan Documents** accordion, you need to collect the document links and map them into a dictionary that `main()` can use.

Here’s a drop-in completion for the function that won’t disturb your existing brittle navigation chain:

```python
def scrape_plan_pdfs(driver, zip: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)
    sleep(2.0)

    # --- (unchanged SPA navigation chain you wrote above) ---
    # ... ZIP entry, submit, skip, click plan, open details ...
    # ... ends with accordion open attempt ...

    try:
        accordion_header = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]')
        accordion_content = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content')

        if "open-shadow" not in accordion_content.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)

        pdfs = {}

        # Find all document rows inside the accordion
        rows = driver.find_elements(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content div.data-row')
        for row in rows:
            try:
                title = row.find_element(By.CSS_SELECTOR, ".title").text.strip()
            except Exception:
                continue

            # Only care about known labels
            if not any(lbl.lower() in title.lower() for lbl in DOC_LABELS):
                continue

            # Collect links in this row (English / Spanish)
            links = row.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
            for link in links:
                href = link.get_attribute("href")
                lang = (link.text or "").strip() or "PDF"
                key = f"{title} ({lang})"
                pdfs[key] = href
        return pdfs

    except Exception:
        print("    [ERROR] Could not expand or parse 'Plan Documents' accordion")
        return {}
```

### Notes

* Keeps your whole **zip → plan list → plan detail → expand accordion** chain untouched.
* Searches inside `div#plan-documents div.accordion-content div.data-row`.
* Matches `DOC_LABELS` against the title text (case-insensitive).
* Returns a dictionary like:

  ```python
  {
      "Summary of Benefits (English)": "https://…SB25.pdf",
      "Summary of Benefits (Spanish)": "https://…SBSP25.pdf",
      "Evidence of Coverage (English)": "https://…EOC25.pdf",
      "CMS plan ratings (English)": "https://…ECHH25.pdf",
      # etc
  }
  ```

That should dovetail with your existing `main()` loop, since it just expects a `{label: href}` mapping.

Do you want me to also patch your `main()` to accept the `plans = zip, plan_name, plan_id` tuples (instead of just plan\_id), so you can pass `zip` and `plan_name` through? Right now `scrape_plan_pdfs()` signature expects three args but `main()` only gives one.

-------------------------------------------------------------------------------

Yes

-------------------------------------------------------------------------------

Perfect — then let’s make the wiring consistent. Right now you’ve got two CSV readers:

* `load_plan_ids()` → returns just `plan_id`s.
* `load_plan_details()` → **intended** to return `(zip, plan_name, plan_id)` but it’s coded incorrectly (`df["zip","plan_name","plan_id"]` will throw).

We’ll fix `load_plan_details()` and switch `main()` to use it, then adjust the enumeration to unpack the tuple.

Here are the drop-in patches:

```python
def load_plan_details(csv_path="medicare/humana/humana_plan_links.csv"):
    """Return list of (zip, plan_name, plan_id) tuples, deduplicated, CSV order preserved."""
    df = pd.read_csv(csv_path, dtype=str)

    # Drop exact duplicate rows across these three cols
    df = df.drop_duplicates(subset=["zip", "plan_name", "plan_id"])

    plans = list(df[["zip", "plan_name", "plan_id"]].itertuples(index=False, name=None))
    return plans
```

And then in `main()`:

```python
def main(start_n: int, stop_n: int | None):
    plans = load_plan_details()
    total = len(plans)
    if total == 0:
        print("[ERROR] No plans found in humana_plan_links.csv")
        return

    # Normalize 1-based indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    start_idx = start_n - 1
    stop_idx = stop_n  # slice end is exclusive

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for i in range(start_idx, stop_idx):
            zip_code, plan_name, plan_id = plans[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id} {plan_name} ({zip_code})")

            pdfs = scrape_plan_pdfs(driver, zip_code, plan_name, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)

            sleep(2.5)
```

---

✅ Now:

* Each iteration passes `zip_code`, `plan_name`, and `plan_id` down to `scrape_plan_pdfs()`.
* `scrape_plan_pdfs()` signature matches.
* Output filenames still use `plan_id` + document label (safe).
* Console logs also show the ZIP and plan name so you can debug navigation issues.

---

Do you also want me to make the **Spanish PDFs optional** (e.g. only download EN unless a `--spanish` flag is passed), or should we always fetch both when available?

-------------------------------------------------------------------------------

That's okay, here's the update, please give it a final bug check:
```
# https://plans.humana.com/

#!/usr/bin/env python3
"""
humana_pdf_grabber.py

Reads plan IDs from humana_plan_links.csv, visits the humana plan page, and downloads
key documents (SB, EOC, Formulary, ANOC in EN/ES).

Features:
- Progress indication using global 1-based index: [(i/total)] PLAN_ID
- Resume by progress index: --start-n and --stop-n (1-based, inclusive)
- Skips already-downloaded PDFs
- Polite delays; downloads via requests Session cloned from Selenium driver
"""

import os
import re
import argparse
from time import sleep
from urllib.parse import urljoin

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# if you want to keep relative imports
# If you always run the script directly (python medicare/humana/humana_pdf_grabber.py from the project root), you can instead do:
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# That forces Python to see the project root, no matter where you launch from.
from utils.driver_session import start_driver
from utils.SPA_utils import make_requests_session_from_driver
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

BASE_ORIGIN = "https://plans.humana.com/"
BASE_URL = f"{BASE_ORIGIN}"
OUTPUT_DIR = "humana_PDFs"

DOC_LABELS = [
    "Summary of Benefits",
    "Evidence of Coverage",
    "CMS plan ratings",
]


def load_plan_details(csv_path="medicare/humana/humana_plan_links.csv"):
    """Return list of (zip, plan_name, plan_id) tuples, deduplicated, CSV order preserved."""
    df = pd.read_csv(csv_path, dtype=str)

    # Drop exact duplicate rows across these three cols
    df = df.drop_duplicates(subset=["zip", "plan_name", "plan_id"])

    plans = list(df[["zip", "plan_name", "plan_id"]].itertuples(index=False, name=None))
    return plans


def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


def scrape_plan_pdfs(driver, zip: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)

    ### Resume work here: fill in zip code, submit form, wait for page load
    # Note: the page uses a lot of dynamic loading; we need to wait for elements to appear
    sleep(2.0)  # initial wait for page to load
    # <input data-v-37ca5262="" data-maska="#####" data-mask-input="" id="ZIP code" type="text" pattern="[0-9]{5}" required="" autocomplete="postal-code" autocapitalize="none" spellcheck="false" autocorrect="off" inputmode="numeric" aria-invalid="false" mptid="INPUT;mptid:0;0">
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[id="ZIP code"]', action="send_keys", keys=zip, timeout=10)
    sleep(0.5)
    # <button data-v-997824cf="" class="nb-btn nb-btn--primary is-small zcf-btn" type="submit" data-search-button=""><span data-v-997824cf="">Get Started</span><!----></button>
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-search-button]', action="click", timeout=10)
    sleep(3.0)  # wait for page to load
    # if it appears, click the type of medicare plan
    # <nucleus-radio-button data-v-cae155e3="" class="coverage-detail is-selection-card selection-card coverage-type-answer nucleus-radio-selection-card" data-medicare-advantage="" name="medicareAdvantage" value="medicareAdvantage" style="padding: 0.5rem;"><div data-v-cae155e3="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-cae155e3="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-cae155e3="" class="coverage-detail-title">Medicare Advantage <span data-v-cae155e3="" class="caption $nt-color-font-heading nu-d-block">(Part C)</span></div><p data-v-cae155e3="" slot:description="" class="nu-d-none md:nu-d-flex">Includes all the benefits of Original Medicare Part A and Part B, and many include coverage for prescription drugs and routine dental, vision and hearing care</p></nucleus-radio-button>
    try:
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="medicareAdvantage"]', action="click", timeout=5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then click the none applied checkbox
        # <nucleus-checkbox data-v-f4c10c2c="" class="inline-flex" name="noneApplies"> None of these apply to me </nucleus-checkbox>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-checkbox[name="noneApplies"]', action="click", timeout=5)
        sleep(0.5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then select open to all plans radio dial
        # <nucleus-radio-button data-v-3603efc7="" data-open-to-all-plans="" class="coverage-detail is-selection-card selection-card plan-network-answer nucleus-radio-selection-card" name="openToAllPlans" value="true" style="padding: 0.5rem;"><div data-v-3603efc7="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-3603efc7="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-3603efc7="" class="coverage-detail-title">I am open to all plan networks</div><p data-v-3603efc7="" slot:description="" class="nu-d-none md:nu-d-inline">We’ll show you recommended plans regardless of provider network. If you are open to seeing an in-network doctor, we can recommend plans that may have lower out-of-pocket costs.</p></nucleus-radio-button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="true"]', action="click", timeout=5)
        sleep(0.5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then click skip this step
        # <button data-v-024a7d79="" class="link" data-skip=""> Skip <span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">this step</span></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(0.5)
        # and the next skip this step
        # <button data-v-024a7d79="" class="link" data-skip=""> Skip <span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">this step</span></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(3.0)  # wait for page to load
    except Exception:
        pass  # if it doesn't appear, continue  
    # Now we should be at the plan list page
    # After pageload, scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # Then find the div with matching plan_id
    # <div class="plan ma" id="" data-mfe-plancard="" data-plan-id="H5216-428-001-2025" data-list-medicare-plans="" idvpage="">
    plan_div = None
    try:
        plan_div = driver.find_element(By.CSS_SELECTOR, f'div[data-plan-id="{plan_id}"]')
    except Exception:
        print("    [ERROR] Could not find plan div on plan list page")
        return {}
    # and click it's "View plan details" link
    # <button data-v-9ee06d52="" class="link" style="font-size: 19px;" data-plan-link="">View plan details</button>
    # (/div/div/div[2]/div/div[3]/div[3]/div/div[2]/div/button)
    try:
        view_button = plan_div.find_element(By.CSS_SELECTOR, 'button[data-plan-link]')
        _safe_click_element(driver, view_button)
        sleep(3.0)  # wait for page to load
    except Exception:
        print("    [ERROR] Could not find or click 'View plan details' button")
        return {}
    
    # then we should be at the plan details page
    # scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # then look for the "Plan Documents" section and click to expand if needed
    # <div data-v-f27cb03a="" data-v-a6b3722d="" class="plan-summary-accordion nu-w-100" id="plan-documents"><div data-v-f27cb03a="" class="accordion-header">
    try:
        accordion_header = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]')
        accordion_content = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content')

        if "open-shadow" not in accordion_content.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)

        pdfs = {}

        # Find all document rows inside the accordion
        rows = driver.find_elements(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content div.data-row')
        for row in rows:
            try:
                title = row.find_element(By.CSS_SELECTOR, ".title").text.strip()
            except Exception:
                continue

            # Only care about known labels
            if not any(lbl.lower() in title.lower() for lbl in DOC_LABELS):
                continue

            # Collect links in this row (English / Spanish)
            links = row.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
            for link in links:
                href = link.get_attribute("href")
                lang = (link.text or "").strip() or "PDF"
                key = f"{title} ({lang})"
                pdfs[key] = href
        return pdfs

    except Exception:
        print("    [ERROR] Could not expand or parse 'Plan Documents' accordion")
        return {}



def download_pdf(session, url: str, out_path: str):
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"    [OK] {os.path.basename(out_path)}")
    except Exception as e:
        print(f"    [ERROR] {url}: {e}")


def main(start_n: int, stop_n: int | None):
    plans = load_plan_details()
    total = len(plans)
    if total == 0:
        print("[ERROR] No plans found in humana_plan_links.csv")
        return

    # Normalize 1-based indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    start_idx = start_n - 1
    stop_idx = stop_n  # slice end is exclusive

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for i in range(start_idx, stop_idx):
            zip_code, plan_name, plan_id = plans[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id} {plan_name} ({zip_code})")

            pdfs = scrape_plan_pdfs(driver, zip_code, plan_name, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)

            sleep(2.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download humana Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)
```

-------------------------------------------------------------------------------

Nice work — this is very close. I’ve gone through your latest version line by line. Here are the bug/robustness points I spotted:

---

### ✅ Good / Correct

* `load_plan_details()` fixed with proper `itertuples`.
* `scrape_plan_pdfs()` now returns `{label: href}` cleanly.
* `main()` loops over `(zip, plan_name, plan_id)` correctly.
* Safe filenames with `safe_name()`.
* Polite delays and skip-if-exists implemented.

---

### ⚠️ Issues to Patch

1. **Accordion “open” detection**

   ```python
   if "open-shadow" not in accordion_content.get_attribute("class"):
   ```

   The `accordion_content` div never contains `"open-shadow"` — that’s on the header wrapper.
   → Use the header’s `class` instead:

   ```python
   if "open-shadow" not in accordion_header.get_attribute("class"):
       _safe_click_element(driver, accordion_header)
       sleep(1.0)
   ```

2. **Double `import os`**

   ```python
   import os
   import re
   ...
   import sys, os
   ```

   Harmless but redundant. Drop the second `, os`.

3. **Variable shadowing `zip`**
   You use `zip` as a parameter name in `scrape_plan_pdfs`. That shadows Python’s built-in `zip()`. Won’t break here, but best practice: rename to `zip_code`.

   ```python
   def scrape_plan_pdfs(driver, zip_code: str, plan_name: str, plan_id: str) -> dict:
       ...
       wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[id="ZIP code"]',
                            action="send_keys", keys=zip_code, timeout=10)
   ```

4. **DOC\_LABELS strictness**
   Right now you match labels like `"CMS plan ratings"`, but the site text can include updates (e.g., `"Evidence of Coverage (Updated 11/19/2024)"`).
   Your `any(lbl.lower() in title.lower() for lbl in DOC_LABELS)` handles this, so ✅. Just know you might want to add `"Summary of Benefits"` variants like `"Benefit Summary"` if Humana changes wording.

---

### ✨ Suggested Fix Patch

Here’s the minimal clean diff you should apply:

```python
def scrape_plan_pdfs(driver, zip_code: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)
    sleep(2.0)

    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[id="ZIP code"]',
                         action="send_keys", keys=zip_code, timeout=10)
    ...
    try:
        accordion_header = driver.find_element(
            By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]'
        )
        accordion_content = driver.find_element(
            By.CSS_SELECTOR, 'div#plan-documents div.accordion-content'
        )

        if "open-shadow" not in accordion_header.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)

        pdfs = {}
        rows = driver.find_elements(
            By.CSS_SELECTOR, 'div#plan-documents div.accordion-content div.data-row'
        )
        ...
```

---

With these tweaks, you should be able to run a real test without silent failures in the accordion step.

Want me to also add a **retry-on-CAPTCHA hook** like you had in Aetna (pause with `[ACTION]` and let you solve it, then resume), so you don’t lose progress on a blocked run?

-------------------------------------------------------------------------------

Yes please.  Here's my update from your feedback, please add a retry-on-CAPTCHA hook and bug check everything:
```
# https://plans.humana.com/

#!/usr/bin/env python3
"""
humana_pdf_grabber.py

Reads plan IDs from humana_plan_links.csv, visits the humana plan page, and downloads
key documents (SB, EOC, Formulary, ANOC in EN/ES).

Features:
- Progress indication using global 1-based index: [(i/total)] PLAN_ID
- Resume by progress index: --start-n and --stop-n (1-based, inclusive)
- Skips already-downloaded PDFs
- Polite delays; downloads via requests Session cloned from Selenium driver
"""

import sys, re, os
import argparse
from time import sleep
from urllib.parse import urljoin

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# if you want to keep relative imports
# If you always run the script directly (python medicare/humana/humana_pdf_grabber.py from the project root), you can instead do:
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# That forces Python to see the project root, no matter where you launch from.
from utils.driver_session import start_driver
from utils.SPA_utils import make_requests_session_from_driver
from utils.SPA_utils import wait_scroll_interact, _safe_click_element

BASE_ORIGIN = "https://plans.humana.com/"
BASE_URL = f"{BASE_ORIGIN}"
OUTPUT_DIR = "humana_PDFs"

DOC_LABELS = [
    "Summary of Benefits",
    "Evidence of Coverage",
    "CMS plan ratings",
]


def load_plan_details(csv_path="medicare/humana/humana_plan_links.csv"):
    """Return list of (zip_code, plan_name, plan_id) tuples, deduplicated, CSV order preserved."""
    df = pd.read_csv(csv_path, dtype=str)

    # Drop exact duplicate rows across these three cols
    df = df.drop_duplicates(subset=["zip_code", "plan_name", "plan_id"])

    plans = list(df[["zip_code", "plan_name", "plan_id"]].itertuples(index=False, name=None))
    return plans


def safe_name(s: str) -> str:
    """Filesystem-safe name (Windows-friendly)."""
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", s)


def scrape_plan_pdfs(driver, zip_code: str, plan_name: str, plan_id: str) -> dict:
    driver.get(BASE_URL)

    ### Resume work here: fill in zip_code, submit form, wait for page load
    # Note: the page uses a lot of dynamic loading; we need to wait for elements to appear
    sleep(2.0)  # initial wait for page to load
    # <input data-v-37ca5262="" data-maska="#####" data-mask-input="" id="ZIP code" type="text" pattern="[0-9]{5}" required="" autocomplete="postal-code" autocapitalize="none" spellcheck="false" autocorrect="off" inputmode="numeric" aria-invalid="false" mptid="INPUT;mptid:0;0">
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[id="ZIP code"]', action="send_keys", keys=zip_code, timeout=10)
    sleep(0.5)
    # <button data-v-997824cf="" class="nb-btn nb-btn--primary is-small zcf-btn" type="submit" data-search-button=""><span data-v-997824cf="">Get Started</span><!----></button>
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-search-button]', action="click", timeout=10)
    sleep(3.0)  # wait for page to load
    # if it appears, click the type of medicare plan
    # <nucleus-radio-button data-v-cae155e3="" class="coverage-detail is-selection-card selection-card coverage-type-answer nucleus-radio-selection-card" data-medicare-advantage="" name="medicareAdvantage" value="medicareAdvantage" style="padding: 0.5rem;"><div data-v-cae155e3="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-cae155e3="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-cae155e3="" class="coverage-detail-title">Medicare Advantage <span data-v-cae155e3="" class="caption $nt-color-font-heading nu-d-block">(Part C)</span></div><p data-v-cae155e3="" slot:description="" class="nu-d-none md:nu-d-flex">Includes all the benefits of Original Medicare Part A and Part B, and many include coverage for prescription drugs and routine dental, vision and hearing care</p></nucleus-radio-button>
    try:
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="medicareAdvantage"]', action="click", timeout=5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then click the none applied checkbox
        # <nucleus-checkbox data-v-f4c10c2c="" class="inline-flex" name="noneApplies"> None of these apply to me </nucleus-checkbox>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-checkbox[name="noneApplies"]', action="click", timeout=5)
        sleep(0.5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then select open to all plans radio dial
        # <nucleus-radio-button data-v-3603efc7="" data-open-to-all-plans="" class="coverage-detail is-selection-card selection-card plan-network-answer nucleus-radio-selection-card" name="openToAllPlans" value="true" style="padding: 0.5rem;"><div data-v-3603efc7="" class="medicine-center mb-3 w-100 nu-d-none md:nu-d-flex"><nucleus-icon data-v-3603efc7="" class="icon-large medicine-center"></nucleus-icon></div><div data-v-3603efc7="" class="coverage-detail-title">I am open to all plan networks</div><p data-v-3603efc7="" slot:description="" class="nu-d-none md:nu-d-inline">We’ll show you recommended plans regardless of provider network. If you are open to seeing an in-network doctor, we can recommend plans that may have lower out-of-pocket costs.</p></nucleus-radio-button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'nucleus-radio-button[value="true"]', action="click", timeout=5)
        sleep(0.5)
        # then click next
        # <button data-v-024a7d79="" class="nb-btn nb-btn--primary next" type="submit" data-next=""><span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">Next</span><span data-v-024a7d79="" class="nu-d-flex md:nu-d-none">Next</span><!----><!----></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[type="submit"][data-next]', action="click", timeout=5)
        sleep(0.5)
        # then click skip this step
        # <button data-v-024a7d79="" class="link" data-skip=""> Skip <span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">this step</span></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(0.5)
        # and the next skip this step
        # <button data-v-024a7d79="" class="link" data-skip=""> Skip <span data-v-024a7d79="" class="nu-d-none md:nu-d-inline">this step</span></button>
        wait_scroll_interact(driver, By.CSS_SELECTOR, 'button[data-skip]', action="click", timeout=5)
        sleep(3.0)  # wait for page to load
    except Exception:
        pass  # if it doesn't appear, continue  
    # Now we should be at the plan list page
    # After pageload, scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # Then find the div with matching plan_id
    # <div class="plan ma" id="" data-mfe-plancard="" data-plan-id="H5216-428-001-2025" data-list-medicare-plans="" idvpage="">
    plan_div = None
    try:
        plan_div = driver.find_element(By.CSS_SELECTOR, f'div[data-plan-id="{plan_id}"]')
    except Exception:
        print("    [ERROR] Could not find plan div on plan list page")
        return {}
    # and click it's "View plan details" link
    # <button data-v-9ee06d52="" class="link" style="font-size: 19px;" data-plan-link="">View plan details</button>
    # (/div/div/div[2]/div/div[3]/div[3]/div/div[2]/div/button)
    try:
        view_button = plan_div.find_element(By.CSS_SELECTOR, 'button[data-plan-link]')
        _safe_click_element(driver, view_button)
        sleep(3.0)  # wait for page to load
    except Exception:
        print("    [ERROR] Could not find or click 'View plan details' button")
        return {}
    
    # then we should be at the plan details page
    # scroll down to the bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    sleep(2.0)  # wait for lazy load
    # then look for the "Plan Documents" section and click to expand if needed
    # <div data-v-f27cb03a="" data-v-a6b3722d="" class="plan-summary-accordion nu-w-100" id="plan-documents"><div data-v-f27cb03a="" class="accordion-header">
    try:
        accordion_header = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]')
        accordion_content = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content')

        if "open-shadow" not in accordion_header.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)

        pdfs = {}

        # Find all document rows inside the accordion
        rows = driver.find_elements(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content div.data-row')
        for row in rows:
            try:
                title = row.find_element(By.CSS_SELECTOR, ".title").text.strip()
            except Exception:
                continue

            # Only care about known labels
            if not any(lbl.lower() in title.lower() for lbl in DOC_LABELS):
                continue

            # Collect links in this row (English / Spanish)
            links = row.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
            for link in links:
                href = link.get_attribute("href")
                lang = (link.text or "").strip() or "PDF"
                key = f"{title} ({lang})"
                pdfs[key] = href
        return pdfs

    except Exception:
        print("    [ERROR] Could not expand or parse 'Plan Documents' accordion")
        return {}



def download_pdf(session, url: str, out_path: str):
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"    [OK] {os.path.basename(out_path)}")
    except Exception as e:
        print(f"    [ERROR] {url}: {e}")


def main(start_n: int, stop_n: int | None):
    plans = load_plan_details()
    total = len(plans)
    if total == 0:
        print("[ERROR] No plans found in humana_plan_links.csv")
        return

    # Normalize 1-based indices
    if start_n < 1:
        start_n = 1
    if stop_n is None or stop_n > total:
        stop_n = total
    if start_n > stop_n:
        print(f"[ERROR] Invalid range: start_n ({start_n}) > stop_n ({stop_n})")
        return

    start_idx = start_n - 1
    stop_idx = stop_n  # slice end is exclusive

    print(f"[INFO] Total plans: {total}")
    print(f"[INFO] Processing progress range: {start_n}..{stop_n} (inclusive)")

    with start_driver() as driver:
        session = make_requests_session_from_driver(driver)

        for i in range(start_idx, stop_idx):
            zip_code, plan_name, plan_id = plans[i]
            print(f"[INFO] ({i+1}/{total}) {plan_id} {plan_name} ({zip_code})")

            pdfs = scrape_plan_pdfs(driver, zip_code, plan_name, plan_id)
            if not pdfs:
                print("    [WARN] No PDFs found")
                sleep(2.0)
                continue

            out_dir = os.path.join(OUTPUT_DIR, plan_id)
            os.makedirs(out_dir, exist_ok=True)

            for label, href in pdfs.items():
                filename = f"{safe_name(plan_id)}_{safe_name(label)}.pdf"
                out_path = os.path.join(out_dir, filename)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    print(f"    [SKIP] {filename} (exists)")
                    continue
                download_pdf(session, href, out_path)
                sleep(1.2)

            sleep(2.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download humana Medicare Advantage plan PDFs by progress index.")
    parser.add_argument("--start-n", type=int, default=1, help="1-based progress index to start at (default: 1)")
    parser.add_argument("--stop-n", type=int, default=None, help="1-based progress index to stop at (inclusive). Default: end")
    args = parser.parse_args()

    main(start_n=args.start_n, stop_n=args.stop_n)

```

-------------------------------------------------------------------------------

Great — your update is clean. Let me show you how to integrate a **retry-on-CAPTCHA hook** and also highlight the last few bug checks.

---

### 🔎 Bug Check

* ✅ Fixed `zip_code` shadowing.
* ✅ Accordion open check corrected.
* ✅ Redundant `import os` removed.
* ✅ `load_plan_details` column names consistent (`zip_code`, `plan_name`, `plan_id`).
* ⚠️ Current `scrape_plan_pdfs()` just returns `{}` on failure — with CAPTCHA you’ll want to pause and retry instead of silently skipping.

---

### 🔄 Retry-on-CAPTCHA Hook

We can add a small helper inside `scrape_plan_pdfs` after attempting to parse the Plan Documents accordion. If no rows or links are found, prompt the user to solve the CAPTCHA in the Selenium browser window, then retry once.

Here’s the adjusted section:

```python
    try:
        accordion_header = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-header button[data-toggle]')
        accordion_content = driver.find_element(By.CSS_SELECTOR, 'div#plan-documents div.accordion-content')

        if "open-shadow" not in accordion_header.get_attribute("class"):
            _safe_click_element(driver, accordion_header)
            sleep(1.0)

        pdfs = {}

        def collect_links():
            rows = driver.find_elements(
                By.CSS_SELECTOR, 'div#plan-documents div.accordion-content div.data-row'
            )
            tmp = {}
            for row in rows:
                try:
                    title = row.find_element(By.CSS_SELECTOR, ".title").text.strip()
                except Exception:
                    continue
                if not any(lbl.lower() in title.lower() for lbl in DOC_LABELS):
                    continue
                links = row.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
                for link in links:
                    href = link.get_attribute("href")
                    lang = (link.text or "").strip() or "PDF"
                    key = f"{title} ({lang})"
                    tmp[key] = href
            return tmp

        pdfs = collect_links()

        # Retry-on-CAPTCHA: if nothing found, pause for manual solve and retry once
        if not pdfs:
            input("[ACTION] No PDFs found (possibly CAPTCHA). Solve it in the browser, then press Enter...")
            sleep(1.0)
            pdfs = collect_links()

        return pdfs

    except Exception:
        print("    [ERROR] Could not expand or parse 'Plan Documents' accordion")
        return {}
```

---

### ✅ Final Notes

* The `input("[ACTION] ...")` call pauses execution until you hit **Enter**, so you can manually clear the CAPTCHA in the browser.
* After retry, if still no links, it will just return `{}` and let `main()` skip the plan gracefully.
* This matches your Aetna workflow.

---

Do you want me to also make the **retry hook optional via CLI flag** (e.g. `--no-retry`) in case you want to run unattended and skip blocked plans automatically?

-------------------------------------------------------------------------------


(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> & "C:/Users/mckin/OneDrive/Desktop/syncthing-folder/Git Repos/wellfound-bot/.venv/Scripts/python.exe" "c:/Users/mckin/OneDrive/Desktop/syncthing-folder/Git Repos/wellfound-bot/medicare/humana/humana_pdf_grabber.py"
Could not find platform independent libraries <prefix>
Traceback (most recent call last):
  File "c:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\medicare\humana\humana_pdf_grabber.py", line 252, in <module>
    main(start_n=args.start_n, stop_n=args.stop_n)     
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^     
  File "c:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\medicare\humana\humana_pdf_grabber.py", line 197, in main
    plans = load_plan_details()
  File "c:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\medicare\humana\humana_pdf_grabber.py", line 51, in load_plan_details
    df = df.drop_duplicates(subset=["zip_code", "plan_name", "plan_id"])
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\pandas\core\frame.py", line 6825, in drop_duplicates        
    result = self[-self.duplicated(subset, keep=keep)] 
                   ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^  
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\pandas\core\frame.py", line 6957, in duplicated
    raise KeyError(Index(diff))
KeyError: Index(['zip_code'], dtype='object')

-------------------------------------------------------------------------------
Ah, that traceback is clear:

Your CSV doesn’t have a column named `zip_code`. It probably has `zip` (or something similar), since you started from the Aetna format.

---

### 🔧 Fix

Update `load_plan_details()` to match the real column names in your `humana_plan_links.csv`.
If the CSV looks like:

```
zip,plan_name,plan_id
30301,HumanaChoice, H5216-428-001-2025
...
```

then the function should be:

```python
def load_plan_details(csv_path="medicare/humana/humana_plan_links.csv"):
    """Return list of (zip, plan_name, plan_id) tuples, deduplicated, CSV order preserved."""
    df = pd.read_csv(csv_path, dtype=str)

    # normalize column names in case there's a mismatch
    df = df.rename(columns={"zip": "zip_code"})

    df = df.drop_duplicates(subset=["zip_code", "plan_name", "plan_id"])
    plans = list(df[["zip_code", "plan_name", "plan_id"]].itertuples(index=False, name=None))
    return plans
```

---

### ✅ Why this works

* Renames the column once → all downstream code can consistently expect `zip_code`.
* Still works even if the CSV already uses `zip_code` (the rename is harmless).

---

⚡ Question for you: do you want me to add a **CSV header check** that raises a friendly error if `zip/zip_code`, `plan_name`, or `plan_id` are missing, instead of throwing a pandas `KeyError`? That way you’d immediately know if the input file is malformed.

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
