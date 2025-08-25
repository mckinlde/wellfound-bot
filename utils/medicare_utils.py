import re
import os
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

"""
Usage: (after your existing ZIP → plan type → Find Plans steps):

fill_zip_and_click_continue(driver, "98101")
select_plan_type_and_continue(driver, "mapd")
select_none_and_continue(driver)
select_exclude_and_next(driver)

after all that is done I get led to a new page that shows all the plans available in the zip code selected, with url format: 
https://www.medicare.gov/plan-compare/#/search-results?fips=53005&plan_type=PLAN_TYPE_MAPD&zip=99352&year=2025&lang=en&page=1
"""


# -----------------------------------------------------
# Core hardened interaction helper
# -----------------------------------------------------
def wait_scroll_interact(driver, by, selector, action="click", keys=None, timeout=10, settle_delay=1):
    """
    Wait for an element, scroll into view, and interact safely.

    Args:
        driver: Selenium WebDriver instance
        by: locator type, e.g., By.CSS_SELECTOR
        selector: element selector string
        action: "click" (default) or "send_keys"
        keys: text to send if action="send_keys"
        timeout: max seconds to wait for element
        settle_delay: pause after scrolling (for animations)

    Returns:
        element: the WebElement found and interacted with
    """
    wait = WebDriverWait(driver, timeout)

    element = wait.until(EC.element_to_be_clickable((by, selector)))

    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    sleep(settle_delay)

    if action == "click":
        try:
            element.click()
        except Exception:
            driver.execute_script("arguments[0].click();", element)

    elif action == "send_keys":
        if keys is None:
            raise ValueError("Must provide `keys` when using action='send_keys'")
        try:
            element.clear()
            element.send_keys(keys)
        except Exception:
            driver.execute_script("arguments[0].value = arguments[1];", element, keys)

    else:
        raise ValueError(f"Unsupported action: {action}")

    return element


# A safe click that can accept an element instead of requiring a by && selector
def _safe_click_element(driver, element, settle_delay=1):
    """Scroll a concrete WebElement into view and click it (JS fallback)."""
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    sleep(settle_delay)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)

        
# -----------------------------------------------------
# Medicare.gov scraping steps
# -----------------------------------------------------
def fill_zip_and_click_continue(driver, zipcode, timeout=10):
    """Fill ZIP code field and click the Continue button."""
    wait_scroll_interact(driver, By.CSS_SELECTOR, '[data-testid="coverage-selector-zipcode"]',
                         action="send_keys", keys=zipcode, timeout=timeout)
    wait_scroll_interact(driver, By.CSS_SELECTOR, '[data-testid="continue-button"]',
                         action="click", timeout=timeout)


def select_plan_type_and_continue(driver, plan_type, timeout=10):
    """Select a coverage plan type radio button and click 'Find Plans'."""
    plan_ids = {
        "mapd": "what-coverage-mapd",
        "pdp": "what-coverage-pdp",
        "medigap": "what-coverage-medigap",
    }
    if plan_type not in plan_ids:
        raise ValueError(f"Invalid plan_type '{plan_type}'. Must be one of: {list(plan_ids.keys())}")

    wait_scroll_interact(driver, By.ID, plan_ids[plan_type], action="click", timeout=timeout)
    wait_scroll_interact(driver, By.CSS_SELECTOR, '[data-testid="start-button"]',
                         action="click", timeout=timeout)


def select_none_and_continue(driver, timeout=10):
    """On the LIS helpType page: select 'None' option and click Continue."""
    wait_scroll_interact(driver, By.CSS_SELECTOR, '[data-testid="none-option"]',
                         action="click", timeout=timeout)
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button.ds-c-button.ds-c-button--solid.ds-u-margin-top--3',
                         action="click", timeout=timeout)


def select_exclude_and_next(driver, timeout=10):
    """On the drug costs page: select 'Exclude' option and click Next."""
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'input[name="drugCosts"][value="exclude"]',
                         action="click", timeout=timeout)
    wait_scroll_interact(driver, By.CSS_SELECTOR, 'button.e2e-drug-search-pref--continue',
                         action="click", timeout=timeout)


def collect_plan_detail_links(driver, timeout=10):
    """Collect all 'Plan Details' links across all paginated search results."""
    wait = WebDriverWait(driver, timeout)
    all_links = []

    while True:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.e2e-plan-details-btn')))
        links = driver.find_elements(By.CSS_SELECTOR, 'a.e2e-plan-details-btn')
        page_links = [link.get_attribute("href") for link in links]
        all_links.extend(page_links)

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, 'button.Pagination__next')
            if not next_button.is_enabled():
                break
            wait_scroll_interact(driver, By.CSS_SELECTOR, 'button.Pagination__next', action="click")
            wait.until(EC.staleness_of(links[0]))
        except:
            break

    return all_links


def scrape_plan_detail_page(driver, zipcode, base_dir=".", timeout=10):
    """Scrape plan detail page and save HTML snapshot."""
    wait = WebDriverWait(driver, timeout)

    header = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.e2e-plan-details-plan-header")))
    company_el = driver.find_element(By.CSS_SELECTOR, "div.PlanDetailsPagePlanInfo__planName h2")
    plan_type_el = driver.find_element(By.CSS_SELECTOR, "span.e2e-plan-details-plan-type")
    plan_id_el = driver.find_element(
        By.XPATH, "//li[span[text()='Plan ID:']]/span[@class='PlanDetailsPagePlanInfo__value']"
    )

    plan_name = header.text.strip()
    company = company_el.text.strip()
    plan_type = plan_type_el.text.strip()
    plan_id = plan_id_el.text.strip()

    expanders = driver.find_elements(By.XPATH, "//span[contains(text(),'more benefits')] | //span[contains(text(),'extra benefits')]")
    for expander in expanders:
        try:
            _safe_click_element(expander)
        except:
            pass

    output_dir = os.path.join(base_dir, "medicare_zncti")
    os.makedirs(output_dir, exist_ok=True)

    safe_plan_name = re.sub(r'\W+', '_', plan_name)
    safe_company = re.sub(r'\W+', '_', company)
    safe_plan_type = re.sub(r'\W+', '_', plan_type)
    safe_plan_id = re.sub(r'\W+', '_', plan_id)
    filename = f"z,{zipcode}_n,{safe_plan_name}_c,{safe_company}_t,{safe_plan_type}_i,{safe_plan_id}.html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    return {
        "plan_name": plan_name,
        "company": company,
        "plan_type": plan_type,
        "plan_id": plan_id,
        "saved_file": filepath,
    }


def scrape_all_plan_details(driver, zipcode, base_dir=".", timeout=10):
    sleep(1)
    """Iterate all result pages; open each plan detail, scrape, go back, continue."""
    wait = WebDriverWait(driver, timeout)
    results = []

    page = 1
    while True:
        # Wait for any plan details buttons to exist on this page
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.e2e-plan-details-btn')))

        # Freeze the count for this page (pagination changes between pages only)
        link_elems = driver.find_elements(By.CSS_SELECTOR, 'a.e2e-plan-details-btn')
        total = len(link_elems)

        for i in range(total):
            sleep(1)
            # Re-find fresh elements each iteration to avoid stale references
            link_elems = driver.find_elements(By.CSS_SELECTOR, 'a.e2e-plan-details-btn')
            if i >= len(link_elems):
                break  # defensive: DOM changed unexpectedly

            link_el = link_elems[i]

            # Click the specific i-th element (not a generic selector)
            _safe_click_element(driver, link_el)

            # Wait for the plan details header to confirm navigation
            try:
                sleep(1)
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.e2e-plan-details-plan-header'))
                )
            except TimeoutException:
                # If navigation failed (e.g., intercepted click), try one more time
                _safe_click_element(driver, link_el)
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.e2e-plan-details-plan-header'))
                )

            # Scrape and record
            details = scrape_plan_detail_page(driver, zipcode=zipcode, base_dir=base_dir, timeout=timeout)
            results.append(details)

            # Go back to the results list and wait for buttons to reappear
            driver.back()
            sleep(1)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.e2e-plan-details-btn')))

        # Try to advance pagination
        try:
            # Keep a handle to detect staleness after clicking Next
            before = driver.find_elements(By.CSS_SELECTOR, 'a.e2e-plan-details-btn')
            first_before = before[0] if before else None

            next_btn = driver.find_element(By.CSS_SELECTOR, 'button.Pagination__next')
            if not next_btn.is_enabled():
                break

            _safe_click_element(driver, next_btn)

            # Wait until the list actually updates
            if first_before:
                sleep(1)
                wait.until(EC.staleness_of(first_before))
            sleep(1)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.e2e-plan-details-btn')))
            page += 1
        except Exception:
            # No next button or navigation failed => last page
            break

    return results