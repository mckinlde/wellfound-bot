https://api.centene.com/SOB/2024/
https://api.centene.com/EOC/2024/

https://api.centene.com/SOB/Medicare/2024/00MB27.pdf

^^Those are tempting, but nonsensical

https://www.wellcare.com/en/medicare/access-plan-information-and-documents

https://www.wellcare.com/en/medicare
^^ This is where it begins

https://www.wellcare.com/en/washington/find-my-plan
^^ maybe just every state, but this takes ZIPs

and gives list of plan details pages:
https://www.wellcare.com/en/washington/members/medicare-plans-2025/wellcare-mutual-of-omaha-premium-enhanced-open-ppo-007

Ta-da, all the links on there

corresponding row:
WA,Asotin,53,99401,Wellcare,Wellcare Mutual of Omaha Premium Enhanced Open (PPO),Medicare Advantage with drug coverage,H5965-007-0,https://www.medicare.gov/plan-compare/#/plan-details/2025-H5965-007-0?fips=53003&plan_type=PLAN_TYPE_MAPD&zip=99401&year=2025&lang=en&page=1

{state}/members/medicare-plans-2025/{plan_name_spaces_to_hyphens}+{plan_id[20++]}




The crucial prompt:

-----
We're still not finding all of the pdfs.  Here's the html file for https://www.wellcare.com/en/arkansas/members/medicare-plans-2025/wellcare-patriot-giveback-hmo-pos-058, I can see the following pdfs on the page, and I'm expecting downloads for all of them:


Plan Specific Documents
pdf iconAnnual Notice of Change
Download

    English
    Last Updated
    October 01, 2024

pdf iconSummary of Benefits
Download

    English
    Last Updated
    October 01, 2024

pdf iconEvidence of Coverage
Download

    English
    Last Updated
    October 01, 2024

pdf iconDental Benefit Details
Download

    English
    Last Updated
    December 12, 2024

pdf iconPlan Enrollment Form
Download

    English
    Last Updated
    October 16, 2024

pdf iconStar Ratings
Download

    English
    Last Updated
    October 30, 2024

Related Materials
pdf iconNotice of Availability of Language Assistance Services and Auxiliary Aids and Services
Download

    Multi Language

pdf iconMulti-Language Interpreter Services and Phone Contact Information
Download

    Multi Language

pdf iconElectronic Funds Transfer Request Form
Download

    English
    Spanish

pdf iconMedical Direct Member Reimbursement Form
Download

    English
    Spanish

pdf iconPrescription Drug Claim Form
Download

    English
    Spanish

pdf iconAppointment of Representative Form
Download

    English
    Spanish

pdf iconMember Disenrollment Form
Download

    English
    Spanish

pdf iconLate Enrollment Penalty (LEP) Reconsideration Form
Download

    English

pdf iconPrimary Care Provider (PCP) Change Request Form
Download

    English

pdf iconMedicare Step Therapy Part B Drugs
Download

    English

pdf iconPreventive Health Screenings by Age
Download

    English

pdf iconMedicare Parts A & B Premiums and Deductibles
Download 
-----
I checked the uploaded HTML (`Wellcare Patriot Giveback (HMO-POS)`), and you’re right — there are **many more PDFs than just one**. They’re grouped under two main headings:

---

### 📑 Plan Specific Documents (6 PDFs)

1. **Annual Notice of Change** → `/medicare-2025/anoc/h1416_058_2025_ar_anoc_hmao_154857e_r.ashx`
2. **Summary of Benefits** → `/medicare-2025/sb/h1416_2025_ar_sb_hmao_155626e_r.ashx`
3. **Evidence of Coverage** → `/medicare-2025/eoc/h1416_058_2025_ar_eoc_hmao_155378e_r.ashx`
4. **Dental Benefit Details** → `/medicare-2025/dbd/na_dental_benefit_details_silver_161834e_r.ashx`
5. **Plan Enrollment Form** → `/medicare-2025/app/na_mapd_2025_enrollment_application_151574e_r.ashx`
6. **Star Ratings** → `/medicare-2025/stars/na_h1416_star_rating_165572e_2025_r.ashx`

---

### 📑 Related Materials (13+ PDFs)

* **Notice of Availability of Language Assistance Services** → `/na/corporate/noa/na_care_notice_of_availability_2026_r.ashx`
* **Multi-Language Interpreter Services** → `/na/corporate/mli/na_ccp_multi_language_interpreter_services.ashx`
* **Electronic Funds Transfer Request Form** → English + Spanish
* **Medical Direct Member Reimbursement Form** → English + Spanish
* **Prescription Drug Claim Form** → English + Spanish
* **Appointment of Representative Form** → CMS links (English + Spanish)
* **Member Disenrollment Form** → English + Spanish
* **Late Enrollment Penalty Reconsideration Form** → English
* **Primary Care Provider (PCP) Change Request Form** → English
* **Medicare Step Therapy Part B Drugs** → English
* **Preventive Health Screenings by Age** → English
* **Medicare Parts A & B Premiums and Deductibles** → English

---

✅ That means **~19–20 PDFs in total** are discoverable on that single plan page.
Your current `get_enrollment_pdfs()` is likely only grabbing the **first link per `.mod-item-container`**, but each has its own `<ul><li><a ...>` structure. To catch all, the scraper should:

1. **Iterate through every `.mod-item-container`** under both `Plan Specific Documents` and `Related Materials`.
2. For each, collect **all `<a>` inside its `<ul>`** (some have multiple, e.g. English/Spanish).
3. Build full URLs (`https://www.wellcare.com` + href) before download.

---

Would you like me to **rewrite your `get_enrollment_pdfs()`** so it:

* scrolls for lazy-load,
* waits for `.mod-item-container` blocks to appear,
* and extracts **all `<a>` PDF links** (not just the first)?
-----
yes
-----
Perfect 👍 — let’s make `get_enrollment_pdfs()` scrape **all PDFs in both “Plan Specific Documents” and “Related Materials”**, instead of just the first one.

Here’s a rewritten version you can drop into your script:

```python
def get_enrollment_pdfs(driver, timeout=15, scroll_pause=1.0):
    """
    Scrapes the current plan details page for ALL enrollment-related PDFs.
    Returns dict of {label: url}, with language suffixes when available.
    """
    wait = WebDriverWait(driver, timeout)
    pdfs = {}

    # Step 1: Wait for at least one PDF link
    wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '.pdf') or contains(@href, '.ashx')]")))

    # Step 2: Scroll to bottom for lazy loading
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(scroll_pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Step 3: Collect ALL anchors under .mod-item-container (both Plan Specific Docs + Related Materials)
    containers = driver.find_elements(By.CSS_SELECTOR, ".mod-item-container")
    for container in containers:
        anchors = container.find_elements(By.TAG_NAME, "a")
        for a in anchors:
            try:
                href = a.get_attribute("href")
                if not href:
                    continue
                if not (href.lower().endswith(".pdf") or href.lower().endswith(".ashx")):
                    continue

                # Try to build a useful label
                label = (a.text or "").strip()
                if not label:
                    label = a.get_attribute("aria-label") or a.get_attribute("title") or os.path.basename(href)

                # Normalize label
                label = re.sub(r"\s+", "_", label)
                label = re.sub(r"[^A-Za-z0-9_]+", "", label)

                # Detect language hints
                lang = None
                href_lower = href.lower()
                if "spanish" in href_lower or "es_" in href_lower or "/es/" in href_lower:
                    lang = "es"
                elif "english" in href_lower or "en_" in href_lower or "/en/" in href_lower:
                    lang = "en"
                if lang:
                    label = f"{label}_{lang}"

                # Avoid collisions
                if label in pdfs:
                    counter = 2
                    new_label = f"{label}_{counter}"
                    while new_label in pdfs:
                        counter += 1
                        new_label = f"{label}_{counter}"
                    label = new_label

                # Ensure full URL
                if href.startswith("/"):
                    href = "https://www.wellcare.com" + href

                pdfs[label] = href
            except Exception as e:
                print(f"    [WARN] error parsing anchor: {e}")
                continue

    return pdfs
```

### 🔑 What changed

1. Looks for **`.pdf` or `.ashx`** links (Wellcare serves PDFs via `.ashx`).
2. Scrolls to bottom for lazy-loaded Related Materials.
3. Iterates through **all `.mod-item-container` blocks**, not just one.
4. Collects **multiple anchors per container** (e.g. English + Spanish).
5. Labels normalized and suffixed with `_en` / `_es` if language is detected.
6. Auto-prepends domain when href starts with `/`.

---

👉 This should give you all **19+ documents** for the Patriot Giveback page you uploaded.

Do you want me to also **log the count per section** (Plan Specific vs Related Materials), so you can confirm you’re getting the right sets for each plan?
