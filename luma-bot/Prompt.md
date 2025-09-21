I want to build a bot that opens luma.com for a given city (luma.com/{city}), scrolls down all the way to the bottom of the page, registers for every free event, and then adds it to a google calendar that I've made for that city.

The registration form is going to be different for each event, so we'll need a way to detect what fields need to be filled and fill them sucessfully.

I have some existing utilities for navigating SPA's in utils/SPA_utils.py, and a utility for managing a webdriver lifecycle in utils/driver_session.py

-------------------------------------------------------------------------------

Got it — you want a full pipeline bot for **Luma event scraping + auto-registering + Google Calendar integration**. Let’s break it down into components so it fits cleanly with your existing `utils` modules:

---

## 1. High-level Workflow

1. **Start driver session** (use your `utils/driver_session.py`).
2. **Open** `https://luma.com/{city}`.
3. **Scroll to bottom** (handle lazy loading).
4. **Extract event links** for all free events.
5. **Iterate through events**:

   * Open event page.
   * Detect “Register” button, click.
   * Parse the form dynamically:

     * Identify required inputs (`<input>`, `<select>`, `<textarea>`).
     * Fill them from a **profile config** (name, email, phone, etc.).
   * Submit registration.
   * Capture confirmation page → extract event details (title, time, location).
6. **Write event to Google Calendar** (via the Google Calendar API).
7. Repeat until all events are registered.

---

## 2. Event Form Detection & Filling

Because each form differs:

* Use Selenium to grab all visible `<input>` / `<select>` / `<textarea>` inside the registration form.
* Inspect `aria-label`, `placeholder`, `name`, `id`, or `<label for=…>` to guess field purpose.
* Maintain a **mapping dictionary**, e.g.:

```python
FIELD_MAP = {
    "name": ["name", "full name", "your name"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "mobile"],
}
PROFILE = {
    "name": "Douglas McKinley",
    "email": "doug@example.com",
    "phone": "555-555-5555",
}
```

* For each detected field, fuzzy-match its label/placeholder to `FIELD_MAP` keys, then fill with the `PROFILE` value.

Fallback: if no mapping → fill with `"N/A"` or skip.

---

## 3. Calendar Integration

* Use the [Google Calendar API](https://developers.google.com/calendar/api/quickstart/python).
* Create a dedicated calendar per city (once).
* After registering:

  * Parse event details (title, start, end, location).
  * Insert via API:

```python
event = {
    "summary": title,
    "location": location,
    "start": {"dateTime": start, "timeZone": "America/Los_Angeles"},
    "end": {"dateTime": end, "timeZone": "America/Los_Angeles"},
}
service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
```

---

## 4. Directory Structure

Given you already have:

```
utils/
  ├── driver_session.py   # start_driver context manager
  ├── SPA_utils.py        # scroll, wait_for, click helpers
luma_bot/
  ├── __init__.py
  ├── register_events.py  # main workflow
  ├── form_filler.py      # dynamic form parsing/filling
  ├── calendar_utils.py   # Google Calendar API wrapper
```

---

## 5. Example Skeleton (`register_events.py`)

```python
from utils.driver_session import start_driver
from utils.SPA_utils import scroll_to_bottom, wait_and_click
from luma_bot.form_filler import fill_form
from luma_bot.calendar_utils import add_event_to_calendar

BASE_URL = "https://luma.com/{}"

def register_city_events(city: str):
    with start_driver() as driver:
        driver.get(BASE_URL.format(city))
        scroll_to_bottom(driver)

        events = driver.find_elements("css selector", "a[href*='/events/']")
        links = [e.get_attribute("href") for e in events]

        for link in links:
            driver.get(link)
            try:
                wait_and_click(driver, "button:contains('Register')")
                fill_form(driver)
                # TODO: parse confirmation page for event details
                add_event_to_calendar(title, start, end, location)
            except Exception as e:
                print(f"[WARN] Failed on {link}: {e}")
```

---

## 6. Next Steps / Decisions Needed

1. Do you want the **profile info** (name, email, phone) hardcoded, in `config.json`, or pulled from env vars?
2. Should the bot **stop after first failure** or **continue** with a log of failed events?
3. Do you want the bot to **actually submit registrations**, or should I build a **“dry run” mode** first (fills forms, doesn’t hit submit)?

---

Would you like me to draft the **`form_filler.py`** (dynamic field detection + filling logic) next, or the **Google Calendar wrapper**?

-------------------------------------------------------------------------------

We don't need to use the google calendar API, luma has a button for adding to calendars, and that workflow will be the same every time.

profile info can be in a .json in /luma-bot

I'd like to continue with a log of failed events, particularly failed events due to a form field that cannot be filled because there's nothing to fill it in the .json

I'd like to actually submit registrations.  The only thing I want to avoid is registering for events that cost money, it should only register for free events.

I want to review the high level architecture again and ask any more questions you have.

-------------------------------------------------------------------------------

Perfect — thanks for clarifying. Let’s lock down the **high-level architecture** with your constraints baked in:

---

## 📐 High-Level Architecture

### 1. Driver Lifecycle

* Reuse `utils/driver_session.py` for clean startup/teardown.
* All navigation, waiting, and scrolling helpers come from `utils/SPA_utils.py`.

### 2. Event Discovery

* Go to `https://luma.com/{city}`.
* Scroll until no new content loads (lazy loading).
* Collect event URLs.
* Filter to **only free events**:

  * Look for a "Free" badge or a `$` price indicator.
  * Skip anything not explicitly free.

### 3. Event Registration

* For each free event:

  1. Navigate to event page.
  2. Detect and click **“Register”**.
  3. Inspect registration form:

     * Detect required fields.
     * Map fields → profile values from `profile.json`.
     * If a field is required but unmapped → log it and skip the event.
  4. Submit registration.
  5. Wait for confirmation page.

### 4. Calendar Integration

* On confirmation page, locate **“Add to Calendar”** button.
* Always click through **Google Calendar** option.
* This will open a new tab → auto-submit if possible (since workflow is consistent).
* Return focus to the main driver.

### 5. Logging

* Maintain `logs/failed_events.log` and `logs/successful_events.log`.
* Failed events include:

  * Missing profile field mapping.
  * Unexpected form errors.
  * Paid event detected after starting registration.
* Successful events include:

  * Event URL, title, date/time.

---

## 📂 Project Structure

```
luma-bot/
  profile.json            # name, email, phone, etc.
  register_events.py      # main workflow (city runner)
  form_filler.py          # dynamic field mapping & filling
  calendar_clicker.py     # standardized Google Calendar add-to-calendar handler
  logger.py               # unified success/fail logging
utils/
  driver_session.py
  SPA_utils.py
logs/
  successful_events.log
  failed_events.log
```

---

## 🔑 Design Choices (based on your input)

* **Profile config**: lives in `/luma-bot/profile.json` so it’s easy to edit.
* **Error handling**: continue through all events; log failures instead of crashing.
* **Paid events**: must be excluded early (double check on event page before registering).
* **Registration**: actually submits (no dry run).
* **Calendar integration**: reuse Luma’s own “Add to Google Calendar” workflow — no API needed.

---

## ❓ Remaining Questions for You

1. **Profile fields**
   Should I design the `profile.json` to be flat (just `"name": "Doug", "email": ...`) or grouped (like `{ "contact": {...}, "preferences": {...} }`)?

2. **Google Calendar tab**
   Do you want the bot to:

   * Automatically click “Save” in the Google Calendar pop-up?
   * Or just leave it open for you to manually confirm?

3. **Multi-city execution**
   Should the bot take a **single city argument** (`register_events.py seattle`) or accept a list of cities (`--cities seattle,portland`)?

4. **Run cadence**
   Do you want this to run **once manually**, or should I make it schedulable (e.g. via cron/Windows Task Scheduler) so it refreshes registrations daily?

---

Want me to propose the exact structure of `profile.json` next, or sketch out the `form_filler.py` logic in more detail?

-------------------------------------------------------------------------------

1. However will be easier for us to maintain, expand, and use in the actual automation
2. Automatically select the correct calendar for the city, and click save
3. Yes, multi-city execution; although actual processing can be one city at a time
4. Yes, schedule-able.  We'll run from a .ps1 command for dev/test so that scheduling is integrated from the start

Let's move on to form_filler.py

-------------------------------------------------------------------------------

Great — thanks for clarifying. Let’s dig into **`form_filler.py`** since that’s the trickiest part of the pipeline.

---

## 🎯 Design Goals for `form_filler.py`

1. **Dynamic Detection**: Forms differ across events → must work without hardcoding field names.
2. **Profile-Driven**: Pull values from `profile.json`. Flexible enough to expand later.
3. **Graceful Failure**: If required field cannot be filled → abort registration for that event and log.
4. **Extensible**: Easy to add new field mappings.

---

## 📄 Proposed `profile.json` Structure

We’ll keep it **flat** with semantic keys, so it’s both easy to expand and easy for fuzzy matching:

```json
{
  "full_name": "Douglas McKinley",
  "first_name": "Douglas",
  "last_name": "McKinley",
  "email": "doug@example.com",
  "phone": "555-555-5555",
  "company": "Cadocary",
  "job_title": "Software Engineer",
  "website": "https://douglasmckinley.com",
  "city": "Seattle",
  "state": "WA"
}
```

---

## 🧭 Field Mapping Strategy

We’ll maintain a `FIELD_MAP` dictionary of **keywords → profile keys**:

```python
FIELD_MAP = {
    "name": ["name", "full name", "your name"],
    "first_name": ["first name", "given name"],
    "last_name": ["last name", "surname"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "mobile", "telephone"],
    "company": ["company", "organization", "employer"],
    "job_title": ["job", "role", "title", "occupation"],
    "website": ["website", "url", "portfolio"],
    "city": ["city", "town"],
    "state": ["state", "province"]
}
```

For each `<input>`, `<select>`, or `<textarea>`:

* Extract **label, placeholder, aria-label, name, id**.
* Normalize (lowercase, strip punctuation).
* Fuzzy match against `FIELD_MAP`.
* If a match → fill with value from `profile.json`.
* If no match but field is optional → skip.
* If no match and field is required → log failure and abort this event.

---

## 🧩 Example Implementation: `form_filler.py`

```python
import json
import re
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

# Load profile.json once
PROFILE = json.loads(Path("luma-bot/profile.json").read_text())

FIELD_MAP = {
    "full_name": ["name", "full name", "your name"],
    "first_name": ["first name", "given name"],
    "last_name": ["last name", "surname"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "mobile", "telephone"],
    "company": ["company", "organization", "employer"],
    "job_title": ["job", "role", "title", "occupation"],
    "website": ["website", "url", "portfolio"],
    "city": ["city", "town"],
    "state": ["state", "province"]
}

def normalize(text: str) -> str:
    """Lowercase and strip punctuation for matching."""
    return re.sub(r"[^a-z0-9 ]", "", text.strip().lower())

def map_field(label: str) -> str | None:
    """Map a form field label to a profile key."""
    norm = normalize(label)
    for profile_key, candidates in FIELD_MAP.items():
        for candidate in candidates:
            if candidate in norm:
                return profile_key
    return None

def fill_form(driver):
    """
    Detect and fill the registration form dynamically.
    Returns True if form submitted, False if failed.
    """
    form = driver.find_element(By.CSS_SELECTOR, "form")
    inputs = form.find_elements(By.CSS_SELECTOR, "input, textarea, select")

    for field in inputs:
        try:
            # Extract label info
            label_text = (
                field.get_attribute("aria-label")
                or field.get_attribute("placeholder")
                or field.get_attribute("name")
                or field.get_attribute("id")
                or ""
            )

            profile_key = map_field(label_text)
            if not profile_key:
                # If required, abort and log
                if field.get_attribute("required"):
                    raise ValueError(f"Unmapped required field: {label_text}")
                else:
                    continue

            value = PROFILE.get(profile_key, "")
            if not value:
                raise ValueError(f"No profile value for {profile_key}")

            # Fill based on element type
            tag = field.tag_name.lower()
            if tag == "input":
                field.clear()
                field.send_keys(value)
            elif tag == "textarea":
                field.send_keys(value)
            elif tag == "select":
                Select(field).select_by_visible_text(value)

        except Exception as e:
            print(f"[FAIL] {e}")
            return False

    # Submit
    form.submit()
    return True
```

---

## ✅ Next Steps

* Integrate `fill_form(driver)` inside your `register_events.py` loop.
* If it returns `False`, log failure and move to next event.
* After success, proceed to the “Add to Calendar” flow.

---

Do you want me to now draft the **`calendar_clicker.py`** (to handle clicking through Luma’s “Add to Google Calendar” → selecting the right city calendar → clicking Save automatically)?

-------------------------------------------------------------------------------

Yep, show me calendar_clicker.py

-------------------------------------------------------------------------------

Awesome — here’s a robust, production-ready `calendar_clicker.py` that:

* Clicks **Add to Calendar** on Luma → chooses **Google Calendar**
* Switches to the new Google Calendar tab
* (If needed) selects the correct **Google account**
* Chooses the **right calendar for the city** from a config mapping
* Clicks **Save**, waits for confirmation, then returns to the Luma tab
* Handles common UI variants with resilient selectors and fallbacks
* Logs meaningful reasons for failures (so your main loop can continue)

It expects a small config file at `luma-bot/calendars.json` like:

```json
{
  "account_email": "you@example.com",
  "city_calendar_map": {
    "seattle": "Seattle (Luma)",
    "portland": "Portland (Luma)"
  }
}
```

---

### `luma-bot/calendar_clicker.py`

```python
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
```

---

### How it plugs into your main loop

In your `register_events.py` (or equivalent), after a successful registration:

```python
from luma-bot.calendar_clicker import add_to_google_calendar_for_city

success, msg = add_to_google_calendar_for_city(driver, city_slug)
if success:
    logger.success(f"[CAL] {msg} :: {event_url}")
else:
    logger.fail(f"[CAL FAIL] {msg} :: {event_url}")
```

---

### Notes / assumptions

* **Authentication**: You should be signed into Google in that Selenium profile/session. If you use a fresh profile, `_maybe_pick_google_account` will try its best to select the right account by email.
* **Calendar names**: Must exactly match the dropdown entry (including capitalization). You can alias city slugs to any calendar display name via `calendars.json`.
* **UI resiliency**: The module covers the most common GCal UI variants (aria-labels, role=combobox menus, Save buttons). If Google ships a sudden redesign, you’ll still have the fallbacks (e.g., text contains).
* **Logging**: This returns `(success, message)` so your central logger can write to `logs/successful_events.log` and `logs/failed_events.log` with consistent reasons (including “calendar not found”, “GCal editor didn’t load”, etc.).

If you want, I can wire this into a full `register_events.py` skeleton (with **free-event filtering**, **form\_filler integration**, and a **.ps1** runner scaffold for scheduling).

-------------------------------------------------------------------------------

Yep!

-------------------------------------------------------------------------------

**Edited/Added files**

* `luma-bot/register_events.py`
* `luma-bot/logger.py`
* `luma-bot/profile.json` (example)
* `luma-bot/calendars.json` (example)
* `scripts/run-luma-bot.ps1`

---

# `luma-bot/register_events.py`

```python
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable, List, Set, Tuple
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)

# Your utilities
from utils.driver_session import start_driver

# If you have helpful SPA utilities, we’ll use them; otherwise we’ll fall back locally.
try:
    from utils.SPA_utils import scroll_to_bottom as spa_scroll_to_bottom
except Exception:
    spa_scroll_to_bottom = None

# Bot modules you already have / we defined earlier
from luma_bot.form_filler import fill_form
from luma_bot.calendar_clicker import add_to_google_calendar_for_city

from luma_bot.logger import BotLogger

BASE = "https://luma.com"
CITY_URL = "https://luma.com/{city}"

DATA_DIR = Path("luma-bot/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REGISTERED_DB = DATA_DIR / "registered_events.json"  # simple de-dupe store


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def robust_scroll_to_bottom(driver, quiet_secs: float = 1.25, max_rounds: int = 50):
    """
    Fallback scroll in case SPA_utils isn't present. Scrolls until height stops changing.
    """
    if spa_scroll_to_bottom:
        # Use user’s helper if available
        spa_scroll_to_bottom(driver)
        return

    last_height = -1
    rounds = 0
    while rounds < max_rounds:
        height = driver.execute_script("return document.body.scrollHeight")
        if height == last_height:
            time.sleep(quiet_secs)
            height2 = driver.execute_script("return document.body.scrollHeight")
            if height2 == height:
                break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(quiet_secs)
        last_height = height
        rounds += 1


def collect_city_event_links(driver) -> List[str]:
    """
    Collects candidate event links from a city listing page.
    We intentionally over-collect then de-dupe + validate.
    """
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    links: Set[str] = set()
    for a in anchors:
        try:
            href = a.get_attribute("href") or ""
            if not href:
                continue
            # Accept obvious event-ish links
            # We allow both absolute and site-relative
            if "/event" in href or "/events" in href or "/e/" in href:
                links.add(href)
        except StaleElementReferenceException:
            continue
    # Normalize: ensure absolute URLs to luma.com
    normalized = []
    for href in links:
        parsed = urlparse(href)
        if not parsed.netloc:
            normalized.append(BASE.rstrip("/") + "/" + href.lstrip("/"))
        else:
            normalized.append(href)
    return sorted(set(normalized))


def is_free_event_on_page(driver) -> bool:
    """
    Checks the current event page for FREE (vs price).
    Strategy: look for any price badge containing 'Free' and ensure no '$' price is the *primary* price.
    We purposely re-check on the event detail page, not just the city feed.
    """
    texts = []
    # Common price containers
    candidates = driver.find_elements(By.XPATH, "//*[self::span or self::div or self::p]")
    for el in candidates:
        try:
            t = (el.text or "").strip()
            if not t:
                continue
            if "free" in t.lower():
                texts.append(t)
        except StaleElementReferenceException:
            continue

    if any("free" in t.lower() for t in texts):
        # defensive: ensure we don’t see a clear $price near primary CTA
        try:
            price_cta_region = driver.find_elements(
                By.XPATH,
                "//*[contains(translate(., 'REGISTERJOINRSVPGETTICKETRESERVE', 'registerjoinrsvpgetticketreserve'), 'register') or "
                "contains(translate(., 'REGISTERJOINRSVPGETTICKETRESERVE', 'registerjoinrsvpgetticketreserve'), 'join') or "
                "contains(translate(., 'REGISTERJOINRSVPGETTICKETRESERVE', 'registerjoinrsvpgetticketreserve'), 'rsvp') or "
                "contains(translate(., 'REGISTERJOINRSVPGETTICKETRESERVE', 'registerjoinrsvpgetticketreserve'), 'get ticket') or "
                "contains(translate(., 'REGISTERJOINRSVPGETTICKETRESERVE', 'registerjoinrsvpgetticketreserve'), 'reserve')]"
            )
            around_cta_texts = []
            for cta in price_cta_region:
                try:
                    parent = cta.find_element(By.XPATH, "./..")
                    around_cta_texts.append((parent.text or "").strip())
                except Exception:
                    continue
            # If a nearby explicit $xx.xx exists, assume paid
            if any("$" in t for t in around_cta_texts):
                return False
        except Exception:
            pass
        return True

    # If we saw no 'free' hints and do see clear $price anywhere, consider paid
    # We bias toward safety (skip if unsure)
    try:
        any_price = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
        if any_price:
            return False
    except Exception:
        pass

    return False


def open_register_cta(driver) -> bool:
    """
    Find and click a register-ish CTA on the event page.
    Covers 'Register', 'RSVP', 'Join', 'Get Ticket', 'Reserve', etc.
    """
    cta_texts = ["register", "rsvp", "join", "get ticket", "reserve", "sign up", "attend"]
    end = time.time() + 10
    while time.time() < end:
        try:
            # search buttons/links/spans/divs
            ctables = driver.find_elements(By.XPATH, "//button|//a|//div|//span")
            for el in ctables:
                try:
                    txt = (el.text or "").strip().lower()
                    if not txt:
                        continue
                    if any(t in txt for t in cta_texts):
                        el.click()
                        return True
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
        except Exception:
            pass
        time.sleep(0.25)
    return False


def wait_for_form(driver, timeout=15) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        return True
    except TimeoutException:
        return False


def load_registered_db() -> dict:
    return load_json(REGISTERED_DB, default={"events": []})


def mark_registered(url: str):
    db = load_registered_db()
    if url not in db["events"]:
        db["events"].append(url)
        save_json(REGISTERED_DB, db)


def already_registered(url: str) -> bool:
    db = load_registered_db()
    return url in db["events"]


def handle_one_event(driver, event_url: str, city: str, logger: BotLogger) -> Tuple[bool, str]:
    """
    Returns (success, message)
    """
    # Skip duplicates (idempotency)
    if already_registered(event_url):
        return True, "Already registered (skipped)."

    driver.get(event_url)

    # Confirm it's free
    if not is_free_event_on_page(driver):
        logger.fail(f"[PAID] Skipping non-free event :: {event_url}")
        return False, "Non-free event"

    # Open register modal/page
    if not open_register_cta(driver):
        return False, "Register CTA not found"

    # Wait for form to render
    if not wait_for_form(driver):
        return False, "Form did not appear"

    # Fill + submit
    try:
        ok = fill_form(driver)  # your earlier implementation returns True/False
        if not ok:
            return False, "Form fill failed (likely unmapped required field)"
    except Exception as e:
        return False, f"Form filler error: {e!r}"

    # Confirmation + Add to Calendar (Google), pick calendar based on city
    # Give the page a moment to render the confirmation widgets.
    time.sleep(2.0)
    cal_ok, cal_msg = add_to_google_calendar_for_city(driver, city_slug=city)
    if not cal_ok:
        # Registration succeeded; calendar can fail without aborting
        logger.fail(f"[CAL] {cal_msg} :: {event_url}")
    else:
        logger.success(f"[CAL] {cal_msg} :: {event_url}")

    mark_registered(event_url)
    return True, "Registered"


def process_city(driver, city: str, logger: BotLogger, max_events: int | None = None):
    city = city.strip().lower()
    url = CITY_URL.format(city=city)
    logger.info(f"[CITY] Visiting {url}")
    driver.get(url)

    robust_scroll_to_bottom(driver)
    links = collect_city_event_links(driver)

    logger.info(f"[CITY] Found {len(links)} candidate event links.")

    # Process serially (one city at a time as requested)
    processed = 0
    for link in links:
        if max_events and processed >= max_events:
            break
        try:
            success, msg = handle_one_event(driver, link, city, logger)
            if success:
                logger.success(f"[OK] {msg} :: {link}")
            else:
                logger.fail(f"[FAIL] {msg} :: {link}")
        except Exception as e:
            logger.fail(f"[EXC] {e!r} :: {link}")
        processed += 1

    logger.info(f"[CITY] Done. Processed {processed} events for '{city}'.")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Luma Free Events Auto-Registration Bot"
    )
    p.add_argument(
        "--cities",
        required=True,
        help="Comma-separated city slugs, e.g. 'seattle,portland'",
    )
    p.add_argument(
        "--max-per-city",
        type=int,
        default=None,
        help="Optional cap per city (useful for testing)",
    )
    p.add_argument(
        "--profile-json",
        default=str(Path("luma-bot/profile.json")),
        help="Path to profile.json used by form_filler.py (if it loads dynamically)",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless (if your driver_session supports it)",
    )
    return p.parse_args(list(argv))


def main(argv: Iterable[str] = None):
    args = parse_args(argv or sys.argv[1:])
    cities = [c.strip().lower() for c in args.cities.split(",") if c.strip()]

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True, parents=True)
    logger = BotLogger(
        success_path=logs_dir / "successful_events.log",
        fail_path=logs_dir / "failed_events.log",
        tee_stdout=True,
    )

    # If your form_filler loads profile.json internally, ensure it exists.
    prof = Path(args.profile_json)
    if not prof.exists():
        logger.fail(f"[CONFIG] Missing profile file at: {prof.resolve()}")
        sys.exit(2)

    # Start driver
    # If your start_driver() supports headless config, pass it here; otherwise ignore.
    # Example: with start_driver(headless=args.headless) as driver:
    try:
        with start_driver() as driver:
            for city in cities:
                process_city(driver, city, logger, max_events=args.max_per_city)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as e:
        logger.fail(f"[FATAL] {e!r}")


if __name__ == "__main__":
    main()
```

---

# `luma-bot/logger.py`

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


class BotLogger:
    def __init__(self, success_path: Path, fail_path: Path, tee_stdout: bool = True):
        self.success_path = success_path
        self.fail_path = fail_path
        self.tee = tee_stdout
        self.success_path.parent.mkdir(parents=True, exist_ok=True)
        self.fail_path.parent.mkdir(parents=True, exist_ok=True)

    def _stamp(self) -> str:
        # ISO-like, local time
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, path: Path, line: str):
        path.write_text(
            (path.read_text(encoding="utf-8") if path.exists() else "") + line,
            encoding="utf-8",
        )

    def info(self, msg: str):
        line = f"{self._stamp()} [INFO] {msg}\n"
        if self.tee:
            print(line, end="")
        self._write(self.success_path, line)

    def success(self, msg: str):
        line = f"{self._stamp()} [SUCCESS] {msg}\n"
        if self.tee:
            print(line, end="")
        self._write(self.success_path, line)

    def fail(self, msg: str):
        line = f"{self._stamp()} [FAIL] {msg}\n"
        if self.tee:
            print(line, end="")
        self._write(self.fail_path, line)
```

---

# Example config files

**`luma-bot/profile.json`**

```json
{
  "full_name": "Douglas McKinley",
  "first_name": "Douglas",
  "last_name": "McKinley",
  "email": "doug@example.com",
  "phone": "555-555-5555",
  "company": "Cadocary",
  "job_title": "Software Engineer",
  "website": "https://douglasmckinley.com",
  "city": "Seattle",
  "state": "WA"
}
```

**`luma-bot/calendars.json`**

```json
{
  "account_email": "you@example.com",
  "city_calendar_map": {
    "seattle": "Seattle (Luma)",
    "portland": "Portland (Luma)",
    "san-francisco": "SF (Luma)"
  }
}
```

---

# `scripts/run-luma-bot.ps1`

```powershell
param(
  [Parameter(Mandatory = $true)]
  [string]$Cities,  # e.g. "seattle,portland"
  [string]$RepoRoot = ".",
  [string]$VenvPath = ".\.venv\Scripts\python.exe",
  [string]$ProfileJson = "luma-bot\profile.json",
  [int]$MaxPerCity = 0,   # 0 = unlimited
  [switch]$Headless
)

# Ensure we run from repo root (so relative paths match)
Set-Location -Path $RepoRoot

# Build arg list
$py = $VenvPath
$script = "luma-bot\register_events.py"

$argList = @("--cities", $Cities, "--profile-json", $ProfileJson)
if ($MaxPerCity -gt 0) {
  $argList += @("--max-per-city", "$MaxPerCity")
}
if ($Headless) {
  $argList += "--headless"
}

Write-Host "[RUN] $py $script $($argList -join ' ')"
& $py $script @argList
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERROR] Bot exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}
```

> For Windows Task Scheduler, point the action to `powershell.exe` and set **Arguments** to something like:
>
> ```
> -ExecutionPolicy Bypass -File "C:\path\to\repo\scripts\run-luma-bot.ps1" -Cities "seattle,portland" -RepoRoot "C:\path\to\repo" -VenvPath "C:\path\to\repo\.venv\Scripts\python.exe" -Headless
> ```

---

## Notes & integration details

* **De-dupe**: `luma-bot/data/registered_events.json` stores URLs you’ve already registered to avoid repeats on scheduled runs.
* **Free-only**: We re-verify on the event page via `is_free_event_on_page()` right before registering. When in doubt, we **skip** to avoid accidental paid signups.
* **Form failures**: If `fill_form()` returns `False` (e.g., required field unmapped in `profile.json`), we log the failure with the event URL and keep going.
* **Calendar add**: Uses your `calendars.json` mapping to auto-select the city-specific calendar and click **Save**.
* **One city at a time**: The CLI accepts multiple cities (`--cities seattle,portland`) but processes them serially, per your requirement.

If you want, I can also add an **optional summary CSV** (`logs/run_summary.csv`) with columns like `timestamp, city, event_url, status, reason` to make reviews easier.

---

**Conventional Commit**

feat(luma-bot): add end-to-end Luma auto-register pipeline with free-event filtering, dynamic form filling, Google Calendar click-through, de-dupe store, logging, and PowerShell scheduler entrypoint

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

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
