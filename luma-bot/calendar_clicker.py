from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

# Optional: if you have helper utilities, we’ll use them when present
try:
    from utils.SPA_utils import wait_for, scroll_into_view
except Exception:
    wait_for = None
    scroll_into_view = None


CONFIG_PATH = Path("luma-bot/calendars.json")

DEFAULT_WAIT = 20
LONG_WAIT = 45


def _read_config():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    account_email = cfg.get("account_email", "").strip()
    city_map = cfg.get("city_calendar_map", {})
    return account_email, city_map


def _safe_click(driver, element):
    try:
        element.click()
        return
    except (ElementClickInterceptedException, StaleElementReferenceException):
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        driver.execute_script("arguments[0].click();", element)


def _click_text_like(driver, texts: list[str], wait_s=DEFAULT_WAIT) -> bool:
    """Click the first element that contains any of the provided texts (case-insensitive)."""
    end = time.time() + wait_s
    lowered = [t.lower() for t in texts]
    while time.time() < end:
        # Try buttons
        candidates = driver.find_elements(By.XPATH, "//button|//a|//div|//span")
        for el in candidates:
            try:
                txt = (el.text or "").strip().lower()
                if not txt:
                    continue
                if any(t in txt for t in lowered):
                    _safe_click(driver, el)
                    return True
            except StaleElementReferenceException:
                continue
        time.sleep(0.25)
    return False


def _wait_for_new_tab(driver, old_handles, wait_s=LONG_WAIT) -> Optional[str]:
    end = time.time() + wait_s
    while time.time() < end:
        handles = driver.window_handles
        if len(handles) > len(old_handles):
            # Return the newest handle
            new_handle = next(h for h in handles if h not in old_handles)
            return new_handle
        time.sleep(0.2)
    return None


def _switch_to(driver, handle):
    driver.switch_to.window(handle)


def _choose_google_calendar_on_luma(driver) -> bool:
    """
    On a Luma event confirmation page (or event page with the widget open),
    click "Add to Calendar" -> "Google Calendar".
    """
    # 1) Click "Add to Calendar"
    if not _click_text_like(driver, ["add to calendar", "add to my calendar", "calendar"]):
        # Some events hide it behind a chevron or an overflow; try common buttons
        # Try any button with a calendar icon role
        try:
            icon_btns = driver.find_elements(By.CSS_SELECTOR, "button, a")
            clicked = False
            for el in icon_btns:
                arialabel = (el.get_attribute("aria-label") or "").lower()
                if "calendar" in arialabel:
                    _safe_click(driver, el)
                    clicked = True
                    break
            if not clicked:
                return False
        except Exception:
            return False

    # 2) Click "Google Calendar"
    # Often appears as a list option or button in the popover
    if not _click_text_like(driver, ["google calendar", "google"]):
        return False

    return True


def _maybe_pick_google_account(driver, account_email: str) -> None:
    """
    If Google account chooser appears, click the right account.
    If no chooser, silently return.
    """
    if not account_email:
        return

    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Choose an account') or contains(text(), 'Use another account')]"))
        )
    except TimeoutException:
        return  # No chooser

    # Try to click the account with matching email text
    try:
        # Buttons often contain a span with the email text
        account_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[@role='button' or @role='link']//span[normalize-space()='{account_email}']/ancestor::*[@role='button' or @role='link'][1]")
            )
        )
        _safe_click(driver, account_btn)
        return
    except TimeoutException:
        pass

    # Fallback: look for an input to type an email (rare on gcal add flow)
    try:
        email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
        email_input.clear()
        email_input.send_keys(account_email)
        next_btn = driver.find_element(By.XPATH, "//span[text()='Next']/ancestor::button")
        _safe_click(driver, next_btn)
    except NoSuchElementException:
        # Give up silently; maybe user is already signed in
        return


def _open_calendar_dropdown(driver):
    """
    Open the calendar selector on Google Calendar 'Add event' page.
    Works for both classic and newer UIs. We try multiple selectors.
    """
    # Newer UI: combobox with aria-label Calendar
    selectors = [
        (By.CSS_SELECTOR, "[aria-label='Calendar'][role='combobox']"),
        (By.XPATH, "//div[@role='combobox' and (@aria-label='Calendar' or .//span[text()='Calendar'])]"),
        # Older UI: 'Calendar' field as a button or dropdown
        (By.XPATH, "//*[text()='Calendar']/following::div[@role='button'][1]"),
    ]
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, DEFAULT_WAIT).until(EC.element_to_be_clickable((by, sel)))
            _safe_click(driver, el)
            return True
        except TimeoutException:
            continue
    return False


def _select_calendar_by_name(driver, calendar_name: str) -> bool:
    """
    With the calendar dropdown open, pick the entry that matches calendar_name.
    """
    if not calendar_name:
        return False

    # Try common list patterns in the opened menu
    options_xpaths = [
        f"//div[@role='listbox']//span[normalize-space()='{calendar_name}']",
        f"//div[@role='menu']//span[normalize-space()='{calendar_name}']",
        f"//div[@role='listbox']//div[normalize-space()='{calendar_name}']",
        f"//div[@role='menu']//div[normalize-space()='{calendar_name}']",
    ]
    end = time.time() + DEFAULT_WAIT
    while time.time() < end:
        for xp in options_xpaths:
            els = driver.find_elements(By.XPATH, xp)
            if els:
                _safe_click(driver, els[0])
                return True
        time.sleep(0.2)
    return False


def _click_save(driver) -> bool:
    """
    Click the Save button in the Google Calendar event editor.
    Handles text and aria-label variants.
    """
    # Try variants in order
    candidates = [
        "//span[text()='Save']/ancestor::button[not(@disabled)]",
        "//div[@role='button' and .//span[text()='Save']]",
        "//button[@aria-label='Save']",
    ]
    for xp in candidates:
        try:
            btn = WebDriverWait(driver, DEFAULT_WAIT).until(EC.element_to_be_clickable((By.XPATH, xp)))
            _safe_click(driver, btn)
            # Wait for confirmation (toast)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Event created') or contains(text(), 'Saved')]"))
                )
            except TimeoutException:
                # Not all UIs show a toast; a short wait to let the POST complete
                time.sleep(2)
            return True
        except TimeoutException:
            continue
    return False


def _close_current_tab_and_return(driver, original_handle: str):
    # Close and switch back
    driver.close()
    _switch_to(driver, original_handle)


def add_to_google_calendar_for_city(driver, city_slug: str) -> tuple[bool, str]:
    """
    From a Luma event page or post-registration confirmation:
      - Click "Add to Calendar" -> "Google Calendar"
      - Switch to Google tab
      - (If shown) choose correct Google account
      - Select the configured calendar for `city_slug`
      - Click Save
    Returns (success, message)
    """
    account_email, city_map = _read_config()
    calendar_name = city_map.get(city_slug.lower(), "").strip()
    if not calendar_name:
        return False, f"No calendar configured for city '{city_slug}'."

    # Click the flow on Luma
    if not _choose_google_calendar_on_luma(driver):
        return False, "Could not open Google Calendar from Luma UI."

    # Switch to the new tab
    old_handles = driver.window_handles[:]
    new_handle = _wait_for_new_tab(driver, old_handles)
    if not new_handle:
        return False, "Google Calendar tab did not open."
    current_handle = driver.current_window_handle
    _switch_to(driver, new_handle)

    try:
        # If needed, pick account
        _maybe_pick_google_account(driver, account_email)

        # Wait for Google Calendar add-event UI
        # Common URL patterns: calendar.google.com/calendar/u/0/r/eventedit?...
        try:
            WebDriverWait(driver, LONG_WAIT).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//*[text()='Save']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='Calendar']")),
                )
            )
        except TimeoutException:
            _close_current_tab_and_return(driver, current_handle)
            return False, "Google Calendar editor did not load."

        # Open calendar dropdown
        if not _open_calendar_dropdown(driver):
            # Some templates land with calendar preselected; try to save anyway
            if not _click_save(driver):
                _close_current_tab_and_return(driver, current_handle)
                return False, "Could not open calendar dropdown or click Save."
            _close_current_tab_and_return(driver, current_handle)
            return True, "Saved to default calendar (dropdown not found)."

        # Choose the right calendar
        if not _select_calendar_by_name(driver, calendar_name):
            _close_current_tab_and_return(driver, current_handle)
            return False, f"Calendar '{calendar_name}' not found in dropdown."

        # Click Save
        if not _click_save(driver):
            _close_current_tab_and_return(driver, current_handle)
            return False, "Failed to click Save in Google Calendar."

        # Close the tab and go back
        _close_current_tab_and_return(driver, current_handle)
        return True, f"Event added to '{calendar_name}'."

    except Exception as e:
        # Best-effort cleanup
        try:
            _close_current_tab_and_return(driver, current_handle)
        except Exception:
            pass
        return False, f"GCal flow error: {e!r}"
