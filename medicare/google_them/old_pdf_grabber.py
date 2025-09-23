# Time to get smart.  Left some ToDo's, the final system is gonna be 3 stages.

# 1) get the plan_links.csv updated using medicare.gov (~4,000 unique plan_ids in first run)
# 2) use a google search api (and maybe custom search engines) to get a broad list of candidate PDFs (~$20 for 4000 queries, ~$80 for specialized queries)
# 3) do postprocessing on PDF content to identify which of gathered files are correct. (unknown)

# ToDo: there are only 4089 unique plan_ids in the full 12k+ list.  We should dedupe before processing.
# Total unique plan_id count: 4089
# Total unique plan_name count: 2316

# ToDo: use a search API: https://programmablesearchengine.google.com/controlpanel/create

"""
Yes — you don’t have to rely on Selenium/WebDriver scraping just to get search results. Google offers a couple of official APIs for programmatic search:

### 1. **Google Custom Search JSON API**

* Lets you run Google searches (including restricting to PDFs or certain sites) and returns structured JSON.
* You need to:

  1. Create a [Custom Search Engine (CSE)](https://programmablesearchengine.google.com/).
  2. Enable the **Custom Search JSON API** in Google Cloud Console.
  3. Get an API key and CSE ID.
* Example query:

  ```http
  https://www.googleapis.com/customsearch/v1?q=H4513-077-3+site:aetna.com+filetype:pdf&key=API_KEY&cx=CSE_ID
  ```
* Response is JSON with titles, snippets, and links. You can easily filter for `.pdf` links.

⚠️ Limitation: free tier allows 100 queries/day, after that you pay per 1000 queries.

---

### 2. **Google Programmable Search Engine (PSE)**

* Same engine behind the JSON API but focused on embedding search boxes into websites. Usually paired with the JSON API above.

---

### 3. **Alternative APIs**

* **SerpAPI**, **Zenserp**, **Oxylabs**, etc. — third-party services that provide full Google results in JSON. They tend to cost money but remove quotas and captcha headaches.
* Advantage: they support Google Scholar, Images, News, and advanced filters that Custom Search JSON API doesn’t always expose.

---

### 4. **Validation Layer**

Since your use case is finding the *right PDF* (formularies, evidence of coverage, etc.):

* Run a query via the API (e.g., `"H4513-077-3" filetype:pdf site:aetna.com`).
* Collect the **top N candidates**.
* Download each PDF and programmatically check:

  * File text contains expected keywords (e.g. “Drug Formulary”).
  * Plan ID appears in the PDF metadata or body.
* Keep the first passing candidate, discard the rest.

That way, you combine broad recall with automatic validation, instead of relying solely on scraping or trusting the filename.

---

👉 Do you want me to sketch a small Python script that uses the Google Custom Search JSON API to pull candidate PDF URLs and then auto-validate them by text-searching for the plan ID?

It’s **\$5 per 1,000 queries** for Google’s Custom Search JSON API. ([Google for Developers][1])

Here are a few more details / caveats:

* You get **100 free queries per day** before the charges kick in. ([Google for Developers][1])
* There is a limit of **10,000 queries/day** under some configurations. ([Google for Developers][1])
* There is also a “Site Restricted JSON API” version (for up to 10 sites) which costs the same (\$5 / 1,000) but with **no daily query limit** under that restriction. ([Google for Developers][2])

If you tell me your approximate query volume I can estimate your monthly cost.

[1]: https://developers.google.com/custom-search/v1/overview?utm_source=chatgpt.com "Custom Search JSON API | Programmable Search Engine"
[2]: https://developers.google.com/custom-search/v1/site_restricted_api?utm_source=chatgpt.com "Custom Search Site Restricted JSON API"

Short answer: there’s **no public, official bulk repo of plan PDFs (EOC/SB/Formulary) from CMS**. CMS publishes **templates/model documents** and a lot of **data files/APIs** (e.g., Part D formularies), but **plan-specific PDFs are distributed by each insurer via their own plan finders/portals**.

What exists (useful, but not PDFs):

* **CMS model materials** (templates for ANOC/EOC/Provider Directory), not plan-specific PDFs. ([CMS][1])
* **Part D Formulary files** (monthly/quarterly ZIPs & API on data.cms.gov / catalog.data.gov), gives drug coverage tables, not the PDF books. ([CMS][2])
* **MA/Part D contract/enrollment datasets** (plans, service areas, contacts), again not PDFs. ([CMS][3])

What insurers provide:

* Each carrier hosts plan document finders (EOC/SB/Formulary) behind search flows; there’s **no bulk download** published. Examples: UHC and Aetna member/plan document pages. ([UnitedHealthcare][4])

### Practical path forward

1. Use **CMS datasets** to enumerate contracts/plans and map plan IDs → carrier/site. ([CMS][3])
2. For discovery, hit a **search API** (Google Custom Search, Bing Web Search, or a SERP provider) with constrained queries like:
   `"<H####-###-#>" site:carrier.com filetype:pdf ("Evidence of Coverage" OR "Summary of Benefits" OR formulary)`
   Then **auto-validate** by downloading candidates and checking text for the plan ID + expected keywords.
3. Add **insurer-specific scrapers** for their document finders (where allowed) to reduce reliance on general search.

If you want, I can sketch a small pipeline that: (a) pulls the plan list from CMS, (b) queries a search API per plan, (c) downloads top N PDFs, and (d) validates/labels the correct one.

[1]: https://www.cms.gov/medicare/health-drug-plans/managed-care-marketing/models-standard-documents-educational-materials?utm_source=chatgpt.com "Marketing Models, Standard Documents, and Educational ..."
[2]: https://www.cms.gov/research-statistics-data-and-systems/files-for-order/nonidentifiabledatafiles/prescriptiondrugplanformularypharmacynetworkandpricinginformationfiles?utm_source=chatgpt.com "Prescription Drug Plan Formulary, Pharmacy Network, and ..."
[3]: https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data?utm_source=chatgpt.com "Medicare Advantage/Part D Contract and Enrollment Data"
[4]: https://www.uhc.com/medicare/resources.html?utm_source=chatgpt.com "Member resources for Medicare plans | UnitedHealthcare"

"""

# ToDo: postprocess to determine which PDFs are which (SoB, EoC, Formulary) based on text content.

"""
I dug through the log you pasted and the control flow in your script. Here’s what’s going on:

---

### What the log shows

* **Broad search** runs for up to 3 pages. Any PDF links found here are immediately downloaded (`download_pdf()` is called right inside the broad loop).
* **Targeted search** runs if something is still missing. But notice in the log:

  ```
  [SEARCH] H0154-016-0 Summary_of_Benefits, page 1 → ...
  [PARSE] Summary_of_Benefits page 1: 9 PDF links scanned, 0 categorized
  ...
  [WARN] Targeted search for Summary_of_Benefits failed
  ```

  Then the script just moves on without a `[DOWNLOAD]` line.

---

### Why it happens

The difference is in the return values:

* **Broad search** calls `parse_and_categorize()`, which returns a dict of *all* categories it found. You then loop over those and call `download_pdf()` immediately.

* **Targeted search** calls `parse_and_categorize()` and only checks if `doc_label` is present in the returned dict. If yes, it returns the URL to the caller.
  But **the caller (`main()`) is the only place that calls `download_pdf()`** after targeted search succeeds.

So the logic *is* supposed to download targeted finds — but only if the `categorize_link()` matched the PDF.

---

### The bug

Your `categorize_link()` is strict. In the broad search, you get some “false positives” because many PDFs mention “summary of benefits” etc. But in targeted searches, you already add the keyword (`summary of benefits`, `evidence of coverage`, `formulary drug list`) to the Google query. The actual PDF links might not repeat those words in the filename or anchor text, so `categorize_link()` never matches them → dict is empty → `main()` never sees a URL to download.

That’s why your log shows `9 PDF links scanned, 0 categorized` even though it clearly scanned PDFs. The categorization filter is too tight.

---

### How to fix

Option 1: **Always return raw PDFs in targeted search**
Instead of relying on `categorize_link()` again, accept the first `.pdf` you see in a targeted search:

```python
def targeted_search(driver, plan_id, plan_name, html_dir, doc_label, max_pages=3):
    query = f"{plan_id} {plan_name} {DOC_TYPES[doc_label]} filetype:pdf"
    for page in range(1, max_pages + 1):
        found = parse_and_categorize(driver, plan_id, query, html_dir, label=doc_label, page=page)
        # if categorized, use it
        if doc_label in found:
            print(f"[INFO] Targeted search for {doc_label} succeeded")
            return found[doc_label]

        # fallback: grab the first PDF on page
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for real_url, _ in extract_google_links_with_text(soup):
            if is_pdf_url(real_url):
                print(f"[FALLBACK] Using first PDF for {doc_label}: {real_url}")
                return real_url
    print(f"[WARN] Targeted search for {doc_label} failed")
    return ""
```

Option 2: **Loosen categorization**
Expand `categorize_link()` to allow matches like “benefits”, “coverage”, “eoc”, etc. But this still risks missing PDFs when filenames are opaque (like `doc12345.pdf`).

---

### Answer to your question

* **No, it’s not skipping downloads intentionally.**
* It’s just that **targeted search results rarely match your categorization keywords**, so they never pass the filter → nothing to download.
* Broad search works because some links happen to include the right phrases.

---

👉 Do you want me to patch your `targeted_search()` with the fallback logic (Option 1), or widen `categorize_link()` to be fuzzier (Option 2)?

Love the way you’re thinking about this. Here’s a battle-tested approach that gets you **high recall with low false positives** while staying resilient to Google’s markup churn.

# 1) Split the job into two passes

**Pass A — Harvest candidates (cheap & broad):**

* Run both **broad** and **targeted** queries.
* Collect the top N results across P pages (e.g., N=12 per page, P=3) for each plan.
* Save a **candidate row** for every PDF-ish link (and a few non-.pdf links that return `Content-Type: application/pdf` on HEAD).
* Store: `plan_id, plan_name, company, query_label (broad|SoB|EoC|Formulary), page, rank, url, domain, anchor_text, around_text(optional), html_snapshot_path`.

**Pass B — Validate & select (smart & picky):**

* For each plan × doc\_type, **score** all candidates, **download the top K** (e.g., K=3), **classify by content**, then select the winner with a confidence score.
* Emit:

  * `plan_pdfs.csv` (final choices),
  * `plan_pdfs_ambiguous.csv` (human review queue with reasons),
  * a per-plan mini-report (optional) summarizing why a candidate was chosen.

This keeps scraping lightweight and pushes the expensive logic (downloads, parsing, classification) into a deterministic validator that you can rerun.

---

# 2) Harvest smarter (min false positives up front)

**Query shaping**

* Always include `filetype:pdf`, the **plan\_id**, and the **target year** (e.g., `2025`).
* Use doc-type synonyms:

  * SoB: `"summary of benefits" OR sob`
  * EoC: `"evidence of coverage" OR eoc`
  * Formulary: `formulary OR "drug list" OR "Part D" OR MAPD`
* Add **company** and **state/region** cues from your CSV when available.
* Prefer known **host patterns** with `site:` when you can (big quality boost):

  * Cigna: `site:cigna.com` or `site:static.www-cigna-com`
  * Humana: `site:content.medicareadvantage.com` or `site:humana.com`
  * UHC: `site:uhc.com` or `site:content.uhc.com`
  * Aetna: `site:aetna.com` or `site:content.medicareadvantage.com`
  * BCBS affiliates: use each plan’s affiliate domain map (maintainable JSON)
* Add a **negative keyword blocklist** to the query for common garbage (or post-filtering):

  * `-reimbursement -“mail order” -employer -Medicaid -Medicare Supplement -Part B -claim`
  * You already hit a false positive: `my.healthmart.com/...MedD_Reimbursement...` → blocklist that domain.

**Candidate extraction**

* Keep your flexible anchor extraction (direct `href` or `/url?`).
* Treat as a candidate if:

  * URL has `.pdf`, **or**
  * `HEAD`/`GET` returns `Content-Type: application/pdf`.
    (Do a 3-second HEAD with redirects; if inconclusive, defer to Pass B.)

**De-dupe & normalize**

* Normalize URLs (strip tracking params, lowercase host, collapse duplicate slashes).
* Keep first-seen rank; later duplicates just add provenance.

---

# 3) Robust content-aware validation (the secret sauce)

Once you download up to K candidates per doc type, classify by **what the PDF says**, not how the URL looks.

**Extract**

* Use `pdfminer.six` (or `pypdf` for page count + `pdfminer` for text) to grab:

  * **Page count**
  * **First \~3 pages of text** (SoB/EoC titles are usually there)
  * **Random mid-page snippet** (some docs bury plan codes in headers/footers)
  * **XMP/Info metadata** if present (title/subject often helpful)

**Signals & rules (give each a weight)**

* **Doc-type phrases** (heavy):

  * SoB: `\bSummary of Benefits\b`, `\bSB\b` near title
  * EoC: `\bEvidence of Coverage\b`, `\bEOC\b`
  * Formulary: `\bFormulary\b`, `\bDrug List\b`, `\bPart D\b`
* **Plan ID presence** (very heavy if SoB/EoC; optional for Formulary):

  * Regex like: `\b[HRS]\d{4}-\d{3}-\d\b` and fuzzy variant without dashes
* **Year** (heavy):

  * Prefer **exact target year**; allow previous year at a penalty; reject old.
  * Extract year from **text first**, then fallback to URL segments.
* **Company/brand strings** (medium):

  * `\bCigna\b`, `\bHumana\b`, `\bUnitedHealthcare\b`, affiliate names
* **Product type words** (bonus):

  * HMO/PPO/RPPO/LPPO/DSNP
* **Domain whitelist / blacklist** (heavy boost/penalty)
* **Page count sanity** (medium):

  * EoC: usually **150–350+** pages
  * SoB: typically **10–60**
  * Formularies: **50–300** (but often generic & shared)
* **Anchor/snippet text** from SERP (light but helpful)

Compute a **score per (candidate, doc\_type)**. Pick the highest-scoring, above a threshold; else mark ambiguous (keep two) or “missing”.

**Why this works**

* It **corrects mislabels** from URLs (e.g., file named “…EOC…” that’s actually a SoB).
* It **keeps good PDFs from targeted searches** even when filenames are opaque—content wins.
* It handles **generic formularies** (no plan\_id in text): strong Formulary terms + company + year + domain + page count typically suffice.

---

# 4) Multiple candidates? Yes—store top-K and decide later

* Save to: `.../candidates/{plan_id}/{doc_type}/rank_{k}.pdf`
* Write a `candidates.csv` with:

  * all the signals, the final **score**, and **why** (top 5 contributing features)
* The selector writes `plan_pdfs.csv` with the chosen file + confidence.
* Keep a small **human-review queue** for edge cases (low confidence / ties).

---

# 5) Make targeted searches “can’t miss”

* Don’t require categorization at harvest time; **record every plausible PDF**.
* Let Pass B’s classifier decide doc type from content.
* Targeted queries still help surface the right file sooner (higher rank), but you’re no longer at the mercy of the filename.

---

# 6) Concrete implementation notes

* **Dataclass** for candidates:

  ```python
  @dataclass
  class PdfCandidate:
      plan_id: str
      company: str
      plan_name: str
      query_label: str   # broad | Summary_of_Benefits | Evidence_of_Coverage | Drug_Formulary
      page: int
      rank: int
      url: str
      domain: str
      anchor_text: str
  ```
* **Scoring**:

  ```python
  SCORE = (
      6*has_doc_phrase +
      6*has_plan_id +
      5*year_score +
      4*company_match +
      3*product_match +
      4*domain_whitelist -
      6*domain_blacklist +
      3*pagecount_reasonable
  )
  ```

  Keep weights in a YAML so you can tune without code changes.
* **Heuristics**:

  * If **EoC** and pagecount < 80 → strong penalty.
  * If **SoB** and pagecount > 120 → penalty (could be EoC).
  * If **Formulary** and doc has “Tier”/“Drug” tables on early pages → bonus.
* **False-positive guardrails**:

  * Hard-block domains like `my.healthmart.com` (reimbursement PDFs).
  * Penalize “claim”, “reimbursement”, “employer”, “mail order” in URL/text.
* **Performance**:

  * Stream PDFs; if file > \~80 MB and doc type ≠ EoC, abort candidate (very likely wrong).
  * Extract only first 3 pages + page count unless needed.

---

# 7) Reporting & self-audit

* Output a **QA CSV** per run: `qa_summary.csv` with columns:

  ```
  plan_id, company, doc_type, chosen_url, confidence, page_count,
  found_year, expected_year, plan_id_in_text (y/n), notes
  ```
* Spot anomalies at a glance:

  * Wrong year but high confidence? (maybe your expected year is off)
  * No plan\_id found in SoB? Flag for review.
  * Formularies from a state DOI site vs carrier—acceptable but note it.

---

# 8) Incremental polish (optional but high ROI)

* Maintain a tiny **carrier host map** (JSON) for per-company `site:` hints & known CDNs.
* Cache **HEAD** results so reruns don’t hit the network for triage.
* Add a `--harvest-only` and `--validate-only` mode.
* If CAPTCHAs bite, try **Bing** fallback for the same query (similar results, fewer roadblocks).

---

### TL;DR

* **Harvest broadly**, don’t over-filter early.
* **Validate by PDF content**, not filenames.
* **Score & choose** using weighted signals (doc phrases, plan\_id, year, domain, page count).
* **Keep top-K** and a **human-review lane** for low-confidence cases.

If you want, I can sketch the validator module (candidate schema, pdf text extractor, scorer, and selector) as drop-in files you can call after your current scraper.

"""


import os
import csv
import time
import random
import argparse
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, quote_plus

from utils.driver_session import start_driver

# Selenium waits to ensure we parse search results (not the captcha page)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------
# Setup
# ---------------------------

LOG_FILE = "google_pdf_grabber.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("google_pdf_grabber")

DOC_TYPES = {
    "Summary_of_Benefits": "summary of benefits",
    "Evidence_of_Coverage": "evidence of coverage",
    "Drug_Formulary": "formulary drug list",
}

CSV_FIELD_MAP = {
    "Summary_of_Benefits": ("SOB_pdf_link", "SOB_pdf_filepath"),
    "Evidence_of_Coverage": ("EoC_pdf_link", "EoC_pdf_filepath"),
    "Drug_Formulary": ("formulary_pdf_link", "formulary_pdf_filepath"),
}

RESULTS_SELECTORS = "div#search, div#rso"  # used to confirm we're on results page

# ToDo: Read search engine ID and API key 
# {
#     "Programmable Search Engine":
#     {
#         "id":
# and
    # "Custom Search Api":
    # {
    #     "key":
# from ~/medicare/google_them/env.json


# ---------------------------
# Utilities
# ---------------------------
def polite_sleep():
    time.sleep(random.uniform(1.0, 2.0))


def wait_for_results_dom(driver, timeout=25):
    """Block until a Google results container appears (after CAPTCHA), then settle briefly."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, RESULTS_SELECTORS))
        )
        time.sleep(1.5)  # settle a bit more
        return True
    except Exception as e:
        print(f"[WARN] Results DOM did not appear after CAPTCHA: {e}")
        logger.warning(f"Results DOM did not appear after CAPTCHA: {e}")
        return False


def save_html(html_dir, plan_id, label, page, html, suffix=""):
    name = f"{plan_id}_{label}_page{page}{suffix}.html"
    path = os.path.join(html_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def extract_google_links_with_text(soup):
    """
    Yield (real_url, anchor_text) pairs from Google result links.
    Handle both /url?q=… wrappers and direct <a href="…"> cases.
    """
    for a in soup.select("a[href]"):
        href = a.get("href", "")

        # Case 1: /url?q=… redirect links
        if href.startswith("/url?"):
            qs = parse_qs(urlparse(href).query)
            real = qs.get("q", [""])[0]
        else:
            # Case 2: direct links (Google sometimes uses them now)
            real = href

        if not real:
            continue

        text = a.get_text(" ", strip=True) or ""
        yield real, text


def is_pdf_url(u: str) -> bool:
    return ".pdf" in u.lower()


def categorize_link(url: str, text: str):
    """
    Categorize based on URL+text. Keep this forgiving and tuned to the Cigna examples you shared:
      - SoB: "summary of benefits", "sob", "sb-"
      - EoC: "evidence of coverage", "eoc"
      - Formulary: "formulary", "drug list", "comprehensive drug list", "part d", "mapd"
    """
    t = f"{url} {text}".lower()

    # Summary of Benefits
    if ("summary of benefits" in t) or (" sob" in t) or ("sob " in t) or (" sb-" in t) or ("-sb" in t):
        return "Summary_of_Benefits"

    # Evidence of Coverage
    if ("evidence of coverage" in t) or (" eoc" in t) or ("eoc " in t) or ("-eoc" in t):
        return "Evidence_of_Coverage"

    # Formulary / Drug list
    if (
        "formulary" in t
        or "drug list" in t
        or "comprehensive drug list" in t
        or "part d" in t
        or "mapd" in t
    ):
        return "Drug_Formulary"

    return None


# ---------------------------
# Search & Parse
# ---------------------------
def parse_and_categorize(driver, plan_id, query, html_dir, label="broad", page=1):
    """
    Run a Google search for one page, save HTML, and return categorized PDF links.
    Critically: if CAPTCHA is present, we pause, then re-parse this SAME page after solve.
    """
    url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en&num=10&start={(page-1)*10}"
    logger.info(f"[SEARCH] {plan_id} {label}, page {page} → {url}")
    print(f"[SEARCH] {plan_id} {label}, page {page} → {url}")

    driver.get(url)
    polite_sleep()

    # Save initial HTML (which might be the captcha page)
    save_html(html_dir, plan_id, label, page, driver.page_source)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # CAPTCHA detection
    if soup.select_one("#recaptcha-anchor") or "recaptcha" in driver.page_source.lower() or "unusual traffic" in driver.page_source.lower():
        input("[ACTION] CAPTCHA detected. Solve it in the browser, then press Enter here to continue...")
        polite_sleep()
        # Ensure Google has swapped in the actual search results on THIS SAME PAGE
        wait_for_results_dom(driver, timeout=30)
        # Re-save and re-parse after solve
        save_html(html_dir, plan_id, label, page, driver.page_source, suffix="__postcaptcha")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        logger.info(f"[DEBUG] Re-parsed {label} page {page} after captcha solve")
        print(f"[DEBUG] Re-parsed {label} page {page} after captcha solve")

    # Parse for PDFs and categorize
    found = {}
    candidates = []
    for real_url, anchor_text in extract_google_links_with_text(soup):
        #print("[DEBUG] link:", real_url, "| text:", anchor_text)
        if not is_pdf_url(real_url):
            continue
        candidates.append((real_url, anchor_text))

        doc_label = categorize_link(real_url, anchor_text)
        if doc_label and doc_label not in found:
            found[doc_label] = real_url
            logger.info(f"[CANDIDATE] {doc_label} → {real_url}")
            print(f"[CANDIDATE] {doc_label} → {real_url}")

        if len(found) == 3:
            break

    logger.info(f"[PARSE] {label} page {page}: {len(candidates)} PDF links scanned, {len(found)} categorized")
    print(f"[PARSE] {label} page {page}: {len(candidates)} PDF links scanned, {len(found)} categorized")
    return found


def broad_search(driver, plan_id, plan_name, html_dir, max_pages=3):
    """Broad search only: return dict of found docs."""
    results = {}
    query = f"{plan_id} {plan_name} filetype:pdf"
    for page in range(1, max_pages + 1):
        found = parse_and_categorize(driver, plan_id, query, html_dir, label="broad", page=page)
        for k, v in found.items():
            results.setdefault(k, v)
        if len(results) == 3:
            break

    found_labels = list(results.keys())
    missing_labels = [d for d in DOC_TYPES.keys() if d not in results]
    human_found = ", ".join(found_labels) if found_labels else "none"
    human_missing = ", ".join(missing_labels) if missing_labels else "none"
    logger.info(f"[INFO] Broad search found {len(found_labels)}/3 docs ({human_found}; missing: {human_missing})")
    print(f"[INFO] Broad search found {len(found_labels)}/3 docs ({human_found}; missing: {human_missing})")

    return results


def targeted_search(driver, plan_id, plan_name, html_dir, doc_label, max_pages=3):
    """Search specifically for one missing doc label."""
    query = f"{plan_id} {plan_name} {DOC_TYPES[doc_label]} filetype:pdf"
    for page in range(1, max_pages + 1):
        found = parse_and_categorize(driver, plan_id, query, html_dir, label=doc_label, page=page)
        if doc_label in found:
            logger.info(f"[INFO] Targeted search for {doc_label} succeeded")
            print(f"[INFO] Targeted search for {doc_label} succeeded")
            return found[doc_label]
    logger.warning(f"[WARN] Targeted search for {doc_label} failed")
    print(f"[WARN] Targeted search for {doc_label} failed")
    return ""


# ---------------------------
# Download
# ---------------------------
def download_pdf(session, url, dest_path, plan_id, doc_label):
    """Download PDF if not already saved; log destination."""
    if not url:
        return False
    if os.path.exists(dest_path):
        logger.info(f"⏩ Skipping existing {dest_path}")
        print(f"[SKIP] {doc_label} already exists for {plan_id} → {dest_path}")
        return True
    try:
        r = session.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        logger.info(f"[DOWNLOAD] Saved {doc_label} for {plan_id} → {dest_path}")
        print(f"[DOWNLOAD] Saved {doc_label} for {plan_id} → {dest_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed {url}: {e}")
        print(f"[ERROR] Failed {url}: {e}")
        return False


# ---------------------------
# Main
# ---------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--stop", type=int, default=None, help="Inclusive 1-based stop index")
    ap.add_argument("--pages", type=int, default=3, help="Max Google pages per query (default: 3)")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    html_dir = os.path.join(args.outdir, "html")
    os.makedirs(html_dir, exist_ok=True)

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    total = len(reader)

    # normalize slice
    start_idx = max(args.start, 1)
    stop_idx = args.stop if args.stop is not None else total

    out_exists = os.path.exists(args.output)
    out_fh = open(args.output, "a", newline="", encoding="utf-8")
    out_writer = csv.DictWriter(
        out_fh,
        fieldnames=[
            "plan_id","plan_name","company",
            "SOB_pdf_link","SOB_pdf_filepath",
            "EoC_pdf_link","EoC_pdf_filepath",
            "formulary_pdf_link","formulary_pdf_filepath",
        ],
    )
    if not out_exists:
        out_writer.writeheader()

    with start_driver(headless=False) as driver:
        session = requests.Session()

        for idx, plan in enumerate(reader, start=1):
            if idx < start_idx or idx > stop_idx:
                continue

            plan_id = (plan.get("plan_id") or "").strip()
            plan_name = (plan.get("plan_name") or "").strip()
            company = (plan.get("company") or "").strip()

            row = {
                "plan_id": plan_id,
                "plan_name": plan_name,
                "company": company,
                "SOB_pdf_link": "",
                "SOB_pdf_filepath": "",
                "EoC_pdf_link": "",
                "EoC_pdf_filepath": "",
                "formulary_pdf_link": "",
                "formulary_pdf_filepath": "",
            }

            logger.info(f"[INFO] ({idx}/{total}) Searching PDFs for {plan_id} {plan_name}")
            print(f"[INFO] ({idx}/{total}) Searching PDFs for {plan_id} {plan_name}")

            # 1) Broad search → download immediately
            broad_found = broad_search(driver, plan_id, plan_name, html_dir, max_pages=args.pages)

            for doc_label, pdf_url in broad_found.items():
                dest_path = os.path.join(args.outdir, f"{plan_id}_{doc_label}.pdf")
                ok = download_pdf(session, pdf_url, dest_path, plan_id, doc_label)
                if ok:
                    link_field, path_field = CSV_FIELD_MAP[doc_label]
                    row[link_field] = pdf_url
                    row[path_field] = dest_path

            # 2) Targeted search for missing → download
            missing_labels = [d for d in DOC_TYPES.keys() if d not in broad_found]
            for doc_label in missing_labels:
                pdf_url = targeted_search(driver, plan_id, plan_name, html_dir, doc_label, max_pages=args.pages)
                if pdf_url:
                    dest_path = os.path.join(args.outdir, f"{plan_id}_{doc_label}.pdf")
                    ok = download_pdf(session, pdf_url, dest_path, plan_id, doc_label)
                    if ok:
                        link_field, path_field = CSV_FIELD_MAP[doc_label]
                        row[link_field] = pdf_url
                        row[path_field] = dest_path

            # 3) Summary
            summary_bits = [
                "SoB=" + ("FOUND" if row["SOB_pdf_link"] else "NOT FOUND"),
                "EoC=" + ("FOUND" if row["EoC_pdf_link"] else "NOT FOUND"),
                "Formulary=" + ("FOUND" if row["formulary_pdf_link"] else "NOT FOUND"),
            ]
            summary = ", ".join(summary_bits)
            logger.info(f"[SUMMARY] ({idx}/{total}) {plan_id} → {summary}")
            print(f"[SUMMARY] ({idx}/{total}) {plan_id} → {summary}")

            out_writer.writerow(row)
            out_fh.flush()

    out_fh.close()


if __name__ == "__main__":
    main()
# Note: It's generally better to solve captchas with user input and script resuming afterwards.  Horizontal scaling probably involves multiplexing to many machines for captcha solving.

# usage, from repo root:

# python medicare/google_them/pdf_grabber.py --input medicare/plan_links.csv --output medicare/google_them/testrun/plan_pdfs.csv --outdir medicare/google_them/testrun --start 1