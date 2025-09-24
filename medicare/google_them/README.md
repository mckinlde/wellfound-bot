erfect — let’s simplify your workflow into a “Google → direct PDF only” scraper that:

Runs separate Google searches for each document type (SoB, EoC, Formulary).

Iterates across multiple pages of results until it finds a suitable PDF (or gives up).

Downloads PDFs immediately (skips landing pages entirely).

Saves one CSV row per plan with filepaths and source links.

Implementation Plan
1. Query Strategy

For each plan row:

Build queries like:

"H0524-059-0 Kaiser Permanente Senior Advantage Basic Alameda (HMO)" "Summary of Benefits" filetype:pdf

"H0524-059-0 Kaiser Permanente Senior Advantage Basic Alameda (HMO)" "Evidence of Coverage" filetype:pdf

"H0524-059-0 Kaiser Permanente Senior Advantage Basic Alameda (HMO)" "Formulary" filetype:pdf

Each query focuses on one document type.

2. Google Results Pagination

Use Selenium to fetch &start=0, &start=10, &start=20, …

Extract links from each page until a match is found for the current doc type.

3. Categorization

Since each query is doc-specific, you don’t need heavy categorization logic.

If a PDF is found, assign it to that document type.

Fallback to "not found" if nothing matched after N pages.

4. Outputs

PDFs saved as:
```
medicare/google_them/<plan_id>_SOB.pdf
medicare/google_them/<plan_id>_EoC.pdf
medicare/google_them/<plan_id>_formulary.pdf
```

CSV with:
```
plan_id, plan_name, company, SOB_pdf_link, SOB_pdf_filepath, EoC_pdf_link, EoC_pdf_filepath, formulary_pdf_link, formulary_pdf_filepath
```

Changes to Add
1. Make a dedicated html/ directory inside your --outdir

So each query’s HTML goes to:
```
medicare/google_them/html/H0524-059-0_Summary_of_Benefits_page1.html
medicare/google_them/html/H0524-059-0_Summary_of_Benefits_page2.html
```

2. Save every Google results page

Update google_search_for_pdf() to save driver.page_source for each page.

3. Label them clearly

File naming convention:
```
<plan_id>_<doc_label>_page{N}.html
```

-------------------- Much Goofing ----------------------

Here’s a full updated version of pdf_grabber.py that implements what we discussed:

One broad search first (plan_id + plan_name filetype:pdf, no quotes).

Categorize all PDF results into SoB, EoC, and Formulary if possible.

If some docs are still missing, fall back to specific searches (summary of benefits filetype:pdf, etc.).

Captcha handling with input() so you can solve it manually.

Saves all result pages for debugging.


----------- Switch to 3-stage pipeline ----------
