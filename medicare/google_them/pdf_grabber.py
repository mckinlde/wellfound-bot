# A script to google medicare advantage [plan id, plan name]s and grab the pdf links
# for the plan documents (summary of benefits, proof of coverage, drug formulary)
# from the search results.


# Inputs:
# - A CSV file with columns "plan_id", "plan_name", "company"
#   (e.g. medicare/plan_links.csv)
# Outputs:
# - A CSV file with columns "plan_id", "plan_name", "company", "source_url", "EoC_pdf_link", "EoC_pdf_filepath", "SOB_pdf_link", "SOB_pdf_filepath", "formulary_pdf_link", "formulary_pdf_filepath"
#   (e.g. medicare/google_them/plan_docs.csv)
# - PDF files downloaded to medicare/google_them/<plan_id>_<document_type>.pdf
#   (e.g. medicare/google_them/H0104-012-0_EoC.pdf)
#   (e.g. medicare/google_them/H0104-012-0_SOB.pdf)
#   (e.g. medicare/google_them/H0104-012-0_formulary.pdf)
# Special notes:
# - Uses Google search, so be mindful of rate limits and CAPTCHAs.
# - Save html of search results for debugging to medicare/google_them/html/
# - This is a best-effort scraper; not all plans will have all documents available.
# - If no documents are found for a plan, save "error: not found" in the respective fields.
# - Show progress with format X/Y where X is current index and Y is len(plan_ids).
# - Use a ../../utils/driver_session.py start_driver() to create a Firefox driver with a custom profile.
# - Use a requests.Session() for downloading PDFs to reuse connections and share cookies from driver.
# - Use a polite delay (e.g. 1-2 seconds) between requests to avoid being blocked.
# - Log errors and exceptions to the console for visibility.
# - Use BeautifulSoup to parse HTML and extract links.
