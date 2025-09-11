import re
import os
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

"""
Utility functions for Single Page Application (SPA) interactions using Selenium.
Includes:
- wait_scroll_interact: Wait for an element, scroll into view, and interact safely.
- _safe_click_element: Scroll a concrete WebElement into view and click it (JS fallback).
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

        