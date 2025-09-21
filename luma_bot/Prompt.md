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

How do I run it?

-------------------------------------------------------------------------------

Here’s the fastest path to a first run on Windows (PowerShell), plus a “schedule-ready” way to run it.

# One-time setup

1. **Folder names (important):** make sure the Python package folder is `luma_bot` (underscore), not `luma-bot`. Put all these files inside it:

* `luma_bot/register_events.py`
* `luma_bot/form_filler.py`
* `luma_bot/calendar_clicker.py`
* `luma_bot/logger.py`
* `luma_bot/profile.json`
* `luma_bot/calendars.json`

2. **Create venv & install deps**

```powershell
cd C:\path\to\your\repo
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install selenium
```

(Your `utils/driver_session.py` should handle the browser driver; if not, also `pip install webdriver-manager` and use it there.)

3. **Fill configs**

* Edit `luma_bot\profile.json` with your real name/email/phone, etc.
* Edit `luma_bot\calendars.json` with your Google account email and the city→calendar name map.
* First run should be **non-headless** so you can sign into Google once in that Selenium profile.

# Quick test run (non-headless)

From repo root:

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle" --max-per-city 3
```

Tips:

* Use a small `--max-per-city` first.
* Watch it scroll, open events, fill forms, then hit “Add to Google Calendar” and select your mapped calendar.
* Logs: `.\logs\successful_events.log` and `.\logs\failed_events.log`
* De-dupe: `.\luma_bot\data\registered_events.json`

# Multi-city run

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland,san-francisco"
```

# Headless (after you’ve signed into Google once)

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

# Schedule-ready PowerShell wrapper (optional)

If you want a wrapper script, create `scripts\run-luma-bot.ps1` like this:

```powershell
param(
  [Parameter(Mandatory = $true)] [string]$Cities,
  [string]$RepoRoot = ".",
  [string]$VenvPath = ".\.venv\Scripts\python.exe",
  [string]$ProfileJson = "luma_bot\profile.json",
  [int]$MaxPerCity = 0,
  [switch]$Headless
)
Set-Location -Path $RepoRoot
$py = $VenvPath
$script = "luma_bot\register_events.py"
$argList = @("--cities", $Cities, "--profile-json", $ProfileJson)
if ($MaxPerCity -gt 0) { $argList += @("--max-per-city", "$MaxPerCity") }
if ($Headless) { $argList += "--headless" }
& $py $script @argList
exit $LASTEXITCODE
```

Run it like:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-luma-bot.ps1 -Cities "seattle,portland" -RepoRoot "$PWD" -MaxPerCity 5
```

## Common gotchas

* **Google sign-in:** do the first run non-headless and complete sign-in. Keep using the same driver profile your `driver_session.py` sets up.
* **Paid events:** the bot will skip anything not clearly marked **Free**.
* **Unmapped required fields:** these will be logged in `failed_events.log` with the event URL. Add missing keys to `profile.json` and re-run.
* **Hyphen vs underscore:** Python imports require `luma_bot` (underscore). If you had any paths using `luma-bot`, switch them to `luma_bot`.

If you hit an error, paste the exact console output and I’ll pinpoint the fix.

-------------------------------------------------------------------------------

Looks like it failed to find the events:
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> .\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle" --max-per-city 3
>> 
Could not find platform independent libraries <prefix>
2025-09-20 18:16:14 [INFO] [CITY] Visiting https://luma.com/seattle
2025-09-20 18:16:20 [INFO] [CITY] Found 0 candidate event links.
2025-09-20 18:16:20 [INFO] [CITY] Done. Processed 0 events for 'seattle'.

-------------------------------------------------------------------------------

Nice catch — the city page is fine, but my link filter was too strict.
On Luma, **event links are usually short slugs** like `https://luma.com/yu2ccnvr` or `https://lu.ma/tnogkouo` (no `/event` or `/events` in the path), so our collector ignored them and returned 0. You can see this on the Seattle page and a sample event: ([Luma][1])

Here’s a drop-in patch to make `collect_city_event_links()` recognize those short slugs and (if needed) fall back to card links:

---

### Patch `luma_bot/register_events.py`

Add imports near the top:

```python
import re
from urllib.parse import urlparse
```

Replace your current `collect_city_event_links` with this version (it’s tolerant of both luma.com and lu.ma, skips the CDN, and accepts single-segment slugs):

```python
def collect_city_event_links(driver) -> List[str]:
    """
    Collect candidate event links from a city listing page.

    Luma event URLs are usually short slugs like:
      https://luma.com/yu2ccnvr  or  https://lu.ma/tnogkouo
    (no '/event' or '/events' segment). This collector accepts:
      • absolute luma.com / lu.ma single-segment paths
      • '/event/...', '/e/...' (older patterns)
      • relative versions of the above
    """

    def looks_like_event_url(href: str) -> bool:
        if not href or href.startswith(("mailto:", "tel:")):
            return False

        # Absolute short slug or /event|/e/ style
        if re.match(r"^https?://(luma\.com|lu\.ma)/[A-Za-z0-9_-]{4,}$", href):
            return True
        if re.match(r"^https?://(luma\.com|lu\.ma)/(event|e)/.+", href):
            return True

        # Relative versions
        if href.startswith("/"):
            path = href.split("?")[0].strip("/")
            parts = path.split("/")
            blocked = {"discover", "help", "pricing", "host", "login", "signup", "map"}
            if len(parts) == 1 and parts[0] and parts[0] not in blocked and len(parts[0]) >= 4:
                return True
            if parts and parts[0] in {"event", "e"} and len(parts) > 1:
                return True

        return False

    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    matched: List[str] = []

    for a in anchors:
        try:
            href = a.get_attribute("href") or ""
            if looks_like_event_url(href):
                netloc = urlparse(href).netloc
                if "lumacdn.com" in netloc:
                    continue  # skip CDN images
                matched.append(href)
                continue

            # Try relative hrefs
            if href.startswith("/") and looks_like_event_url(BASE.rstrip("/") + href):
                matched.append(BASE.rstrip("/") + href)
        except StaleElementReferenceException:
            continue

    # Fallback: some cards are clickable containers; grab the nearest ancestor with href/data-href
    if not matched:
        cards = driver.find_elements(
            By.XPATH, "//h3/ancestor::*[self::a or @role='link' or @data-href][1]"
        )
        for el in cards:
            try:
                href = el.get_attribute("href") or el.get_attribute("data-href") or ""
                if href and looks_like_event_url(href):
                    if href.startswith("/"):
                        href = BASE.rstrip("/") + href
                    matched.append(href)
            except StaleElementReferenceException:
                continue

    matched = sorted(set(matched))
    print(f"[DEBUG] Anchors: {len(anchors)}, event-like: {len(matched)}")
    return matched
```

Optionally, make the scrolling a bit “stickier” to ensure all cards load:

```python
def robust_scroll_to_bottom(driver, quiet_secs: float = 1.0, max_rounds: int = 60):
    last_height = 0
    rounds_same = 0
    for _ in range(max_rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(quiet_secs)
        height = driver.execute_script("return document.body.scrollHeight")
        if height == last_height:
            rounds_same += 1
            if rounds_same >= 2:
                break
        else:
            rounds_same = 0
        last_height = height

    # Try a 'Load more' if present
    try:
        btns = driver.find_elements(By.XPATH, "//button[contains(., 'Load more') or contains(., 'Show more')]")
        if btns:
            btns[0].click()
            time.sleep(1.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(quiet_secs)
    except Exception:
        pass
```

---

### Re-run (small batch first)

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle" --max-per-city 3
```

You should now see something like:

```
[DEBUG] Anchors: 120, event-like: 24
[CITY] Found 24 candidate event links.
```

If it still returns 0, ping me with the console output and I’ll add a second fallback that literally clicks each visible card (by `<h3>` title) to harvest the canonical event URL before proceeding.

(For reference: Seattle city page exists and lists events; individual event pages use short slugs. That’s why we adjusted the matcher.) ([Luma][1])

[1]: https://luma.com/seattle "Popular events in Seattle · Events Calendar"

-------------------------------------------------------------------------------

It had some false positives on paid events, but the main issue is that I wasn't signed in to Luma in the new session.  Can we implement a quick setup_driver_session.py that will trigger human-guided signins for both Luma and Google before handing off to register_events?


(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> .\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle" --max-per-city 3
Could not find platform independent libraries <prefix>
2025-09-20 18:20:02 [INFO] [CITY] Visiting https://luma.com/seattle
[DEBUG] Anchors: 39, event-like: 18
2025-09-20 18:20:08 [INFO] [CITY] Found 18 candidate event links.
2025-09-20 18:20:13 [FAIL] [PAID] Skipping non-free event :: https://luma.com/46lyzgf8
2025-09-20 18:20:13 [FAIL] [FAIL] Non-free event :: https://luma.com/46lyzgf8
2025-09-20 18:20:18 [FAIL] [PAID] Skipping non-free event :: https://luma.com/4v0m67y2
2025-09-20 18:20:18 [FAIL] [FAIL] Non-free event :: https://luma.com/4v0m67y2
[FAIL] Message: Element <textarea class="lux-naked-input mounted"> is not reachable by keyboard; For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#elementnotinteractableexception
Stacktrace:
RemoteError@chrome://remote/content/shared/RemoteError.sys.mjs:8:8
WebDriverError@chrome://remote/content/shared/webdriver/Errors.sys.mjs:199:5
ElementNotInteractableError@chrome://remote/content/shared/webdriver/Errors.sys.mjs:368:5
webdriverSendKeysToElement@chrome://remote/content/marionette/interaction.sys.mjs:667:13
interaction.sendKeysToElement@chrome://remote/content/marionette/interaction.sys.mjs:639:11
sendKeysToElement@chrome://remote/content/marionette/actors/MarionetteCommandsChild.sys.mjs:609:29
receiveMessage@chrome://remote/content/marionette/actors/MarionetteCommandsChild.sys.mjs:269:31

2025-09-20 18:20:25 [FAIL] [FAIL] Form fill failed (likely unmapped required field) :: https://luma.com/create
2025-09-20 18:20:25 [INFO] [CITY] Done. Processed 3 events for 'seattle'.

-------------------------------------------------------------------------------

Got it. Here’s a **drop-in, human-guided sign-in launcher** that:

* opens Luma login and waits for you to finish signing in,
* opens Google Calendar and waits for you to finish,
* closes that browser,
* then **hands off to your existing** `register_events.py` with the same args.

It assumes your `utils/driver_session.start_driver()` uses a **persistent browser profile** (e.g., Chrome user-data-dir) so the sign-ins stick for subsequent runs.

---

# `luma_bot/setup_driver_session.py`

```python
from __future__ import annotations

import argparse
import sys
import time
from typing import Iterable

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Your driver context manager
from utils.driver_session import start_driver

# Reuse your runner after sign-in
from luma_bot import register_events


def _prompt(msg: str):
    print(msg)
    input("Press Enter when you're done… ")


def _wait_any(driver, xpaths: list[str], timeout: int = 10) -> bool:
    """Return True if any of the xpaths appears within timeout."""
    end = time.time() + timeout
    while time.time() < end:
        for xp in xpaths:
            try:
                WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, xp)))
                return True
            except TimeoutException:
                continue
    return False


def _signin_luma(driver) -> bool:
    """
    Open Luma login and wait for user to complete sign-in.
    Works for luma.com or lu.ma (they redirect freely).
    """
    driver.get("https://luma.com/login")
    time.sleep(1.0)
    _prompt(
        "\n[Action] Sign in to Luma in the opened browser.\n"
        " - If redirected to lu.ma, complete the login there.\n"
        " - Make sure you end up logged in (avatar/menu visible).\n"
        "When finished,"
    )
    # Best-effort verification (works for common nav variants)
    ok = _wait_any(
        driver,
        xpaths=[
            "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'log out')]",
            "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign out')]",
            "//*[@aria-label='Account' or @aria-label='Profile']",
            "//a[contains(@href, '/logout') or contains(@href, '/signout')]",
        ],
        timeout=8,
    )
    print(f"[LUMA] Login check: {'OK' if ok else 'Not verified (continuing anyway)'}")
    return ok


def _signin_google_calendar(driver) -> bool:
    """
    Open Google Calendar and wait for user sign-in;
    we check for Create button or left sidebar as a success signal.
    """
    driver.get("https://calendar.google.com/calendar/u/0/r")
    time.sleep(1.0)
    _prompt(
        "\n[Action] Sign in to your Google account (the one in calendars.json),\n"
        "then ensure Google Calendar loads fully.\n"
        "When the calendar UI is visible,"
    )
    ok = _wait_any(
        driver,
        xpaths=[
            "//*[@aria-label='Create']",
            "//div[@role='button' and .//span[text()='Create']]",
            "//*[@aria-label='Main menu']",
        ],
        timeout=12,
    )
    print(f"[GCAL] Calendar UI check: {'OK' if ok else 'Not verified (continuing anyway)'}")
    return ok


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="One-time interactive sign-in for Luma & Google Calendar, then run register_events."
    )
    p.add_argument("--cities", required=True, help="Comma-separated city slugs, e.g. 'seattle,portland'")
    p.add_argument("--max-per-city", type=int, default=None, help="Optional cap per city")
    p.add_argument("--headless", action="store_true", help="Run register_events headless AFTER sign-in")
    p.add_argument("--profile-json", default="luma_bot/profile.json", help="Path to profile.json (sanity check)")
    return p.parse_args(list(argv))


def main(argv: Iterable[str] = None):
    args = parse_args(argv or sys.argv[1:])

    # 1) Open a NON-headless browser so you can sign in
    with start_driver() as driver:
        print("[SETUP] Starting interactive sign-in…")
        _signin_luma(driver)
        _signin_google_calendar(driver)
        print("[SETUP] Sign-in steps done. Closing this browser…")

    # 2) Hand off to your normal runner (with whatever mode you want)
    print("[HANDOFF] Launching register_events with your args…\n")
    handoff_args = []
    handoff_args += ["--cities", args.cities]
    if args.max_per_city is not None:
        handoff_args += ["--max-per-city", str(args.max_per_city)]
    handoff_args += ["--profile-json", args.profile_json]
    if args.headless:
        handoff_args += ["--headless"]

    # Call register_events.main() directly to keep it simple
    register_events.main(handoff_args)


if __name__ == "__main__":
    main()
```

---

## How to use it

1. Make sure `start_driver()` uses a **persistent profile** (e.g., Chrome `--user-data-dir` pointing to a fixed folder). If it’s ephemeral, sign-ins won’t be remembered.

2. First run (interactive sign-ins, then handoff):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 3
```

* Sign into **Luma** when prompted.
* Sign into **Google Calendar** when prompted.
* The script closes that window and immediately calls your **normal** runner using the saved session.

3. Subsequent runs (no setup needed):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

---

## Optional quick patches (based on your logs)

### 1) Reduce paid false-positives

Replace `is_free_event_on_page()` with this stricter version in `register_events.py`:

```python
def is_free_event_on_page(driver) -> bool:
    """
    Declare FREE only if:
      - A visible element says 'Free' (badge/price),
      - AND no visible '$' price is in the primary price/CTA region.
    Otherwise return False (skip).
    """
    # Look for explicit 'Free'
    try:
        free_badges = driver.find_elements(By.XPATH, "//*[self::span or self::div or self::p][contains(translate(.,'FREE','free'),'free')]")
        has_free = any((el.is_displayed() and 'free' in (el.text or '').lower()) for el in free_badges)
    except Exception:
        has_free = False

    # Look near CTAs for $price
    try:
        price_near_cta = driver.find_elements(
            By.XPATH,
            "//*[self::button or self::a][contains(translate(.,'REGISTERJOINRSVPGETTICKETRESERVE','registerjoinrsvpgetticketreserve'),'register') "
            "or contains(translate(.,'REGISTERJOINRSVPGETTICKETRESERVE','registerjoinrsvpgetticketreserve'),'rsvp') "
            "or contains(translate(.,'REGISTERJOINRSVPGETTICKETRESERVE','registerjoinrsvpgetticketreserve'),'join') "
            "or contains(translate(.,'REGISTERJOINRSVPGETTICKETRESERVE','registerjoinrsvpgetticketreserve'),'get ticket') "
            "or contains(translate(.,'REGISTERJOINRSVPGETTICKETRESERVE','registerjoinrsvpgetticketreserve'),'reserve')]"
        )
        any_dollar = False
        for cta in price_near_cta:
            try:
                region = cta.find_element(By.XPATH, "./ancestor::*[self::section or self::div][1]")
                if "$" in (region.text or ""):
                    any_dollar = True
                    break
            except Exception:
                continue
    except Exception:
        any_dollar = False

    return bool(has_free and not any_dollar)
```

### 2) Fix “not reachable by keyboard” on `<textarea>`

In `form_filler.py`, before sending keys, ensure visibility and fall back to JS:

```python
from selenium.webdriver.support import expected_conditions as EC

def _send_keys_safe(driver, el, value: str):
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable(el))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.clear()
        el.send_keys(value)
        return
    except Exception:
        # Fallback: set value via JS + dispatch events (helps with masked/overlayed inputs)
        driver.execute_script("""
            const el = arguments[0], val = arguments[1];
            const setVal = (e,v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); };
            if (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && el.type !== 'checkbox' && el.type !== 'radio')) {
                setVal(el, val);
            } else if (el.hasAttribute('contenteditable')) {
                el.innerText = val;
                el.dispatchEvent(new Event('input', {bubbles:true}));
            }
        """, el, value)
```

…and use `_send_keys_safe(driver, field, value)` wherever you previously called `send_keys`.

---

If your `start_driver()` doesn’t currently persist a profile, I can give you a crisp snippet to add to it for Chrome/Edge that writes to, e.g., `.selenium-profile/luma_bot`, so these sign-ins stick between runs.

-------------------------------------------------------------------------------

Here's utils/driver_session.py, make whatever changes you need, but keep interoperability in mind--this file is used across many scrapers.

<driver_session.py>

-------------------------------------------------------------------------------

Awesome—let’s make sign-ins stick.

Below is a **drop-in replacement** for `utils/driver_session.py` that adds **optional persistent Firefox profiles** while keeping the old, throwaway-per-run default. Then I show tiny patches so your `setup_driver_session.py` signs in once using a persistent profile and your `register_events.py` reuses it (or you can just set two env vars and avoid touching other code).

---

# ✅ What changes you get

* **New optional args/env vars** for persistent sessions:

  * `persist_profile: bool = None`
  * `profile_name: str | None = None` (stored under `.selenium-profiles/<name>`)
  * `profile_dir: str | Path | None = None` (absolute path you choose)
* **Backwards-compatible default**: still creates a temporary throwaway profile and deletes it on exit.
* **Env overrides** (so you don’t have to change other scrapers):

  * `FIREFOX_PROFILE_PERSIST=1`
  * `FIREFOX_PROFILE_NAME=luma_bot`
  * `FIREFOX_PROFILE_BASE_DIR=.selenium-profiles` (default)
  * `FIREFOX_PROFILE_DIR=<absolute path>` (beats the above two)
* Download prefs still set; only the temp profile folder cleanup changes (persistent profiles are **not** deleted).

---

# 🔧 Updated `utils/driver_session.py` (copy–paste)

```python
# driver_session.py
"""
driver_session abstracts Selenium WebDriver state from the rest of the app.
- Provides a context-managed Firefox driver with sane defaults.
- Works whether or not FIREFOX_BIN / GECKODRIVER_PATH are set (falls back to Selenium Manager).
- DEFAULT: Creates a throwaway Firefox profile per run and cleans it up deterministically.
- OPTIONAL: Can reuse a persistent Firefox profile across runs (for saved logins).

Env (optional):
  FIREFOX_BIN              -> path to firefox.exe (overrides system default)
  GECKODRIVER_PATH         -> path to geckodriver.exe (overrides Selenium Manager)
  FIREFOX_HEADLESS         -> "1" to run headless (default: windowed)

  # Persistent profile controls (optional; all backwards-compatible):
  FIREFOX_PROFILE_PERSIST  -> "1" to reuse a persistent profile (default: temp throwaway)
  FIREFOX_PROFILE_NAME     -> logical name under FIREFOX_PROFILE_BASE_DIR (e.g., "luma_bot")
  FIREFOX_PROFILE_BASE_DIR -> base dir for named profiles (default: ".selenium-profiles")
  FIREFOX_PROFILE_DIR      -> absolute path to a specific profile dir (overrides NAME+BASE)

"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import logging
import time
import random
from pathlib import Path
from contextlib import contextmanager

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ---------- Configuration ----------
_DEFAULT_TIMEOUT = 30  # seconds
_HTML_DIR = Path("html_captures")
_LOG_DEBUG_DIR = Path("logs/debug")

_FIREFOX_BIN = os.getenv("FIREFOX_BIN") or None
_GECKO_PATH = os.getenv("GECKODRIVER_PATH") or None
_HEADLESS = (os.getenv("FIREFOX_HEADLESS") == "1")

# Persistent profile envs
_ENV_PERSIST = (os.getenv("FIREFOX_PROFILE_PERSIST") == "1")
_ENV_PROFILE_DIR = os.getenv("FIREFOX_PROFILE_DIR") or None
_ENV_PROFILE_NAME = os.getenv("FIREFOX_PROFILE_NAME") or None
_ENV_PROFILE_BASE = Path(os.getenv("FIREFOX_PROFILE_BASE_DIR") or ".selenium-profiles")


SEED_URLS = [
    "https://www.wikipedia.org/",
    "https://www.bbc.com/news",
    "https://www.nytimes.com/",
    "https://www.reddit.com/",
    "https://weather.com/",
]

# ---------- Filesystem helpers ----------
def _ensure_dirs() -> None:
    _HTML_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_for_filename(s: str, maxlen: int = 128) -> str:
    """Conservative filename sanitizer."""
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"[\/\?\:\&\=\#\%\\\*\|\<\>\"]+", "_", s)
    s = s.strip(" ._")
    return s[:maxlen] if len(s) > maxlen else s


def write_html_to_file(html: str, file_name: str) -> Path:
    """Write raw HTML to html_captures, return Path."""
    _ensure_dirs()
    out = _HTML_DIR / file_name
    out.write_text(html, encoding="utf-8")
    return out


def write_soup_to_file(soup: BeautifulSoup, file_name: str) -> Path:
    """Write pretty HTML to html_captures, return Path."""
    return write_html_to_file(soup.prettify(), file_name)


# ---------- Internal profile resolver ----------
def _resolve_profile(
    persist_profile: bool | None,
    profile_name: str | None,
    profile_dir: str | Path | None,
) -> tuple[Path, bool, bool]:
    """
    Decide which profile directory to use.

    Returns:
      (profile_path, is_persistent, is_temporary)
    """
    # Explicit args take precedence; otherwise env; otherwise temp.
    arg_persist = bool(persist_profile) if persist_profile is not None else None

    # 1) If a specific directory is given/ENVed, use it and mark persistent
    chosen_dir: Path | None = None
    if profile_dir:
        chosen_dir = Path(profile_dir)
        is_persistent = True
    elif _ENV_PROFILE_DIR:
        chosen_dir = Path(_ENV_PROFILE_DIR)
        is_persistent = True
    else:
        # 2) If a name is given/ENVed, build under base and mark persistent
        name = profile_name or _ENV_PROFILE_NAME
        if name:
            chosen_dir = _ENV_PROFILE_BASE / name
            is_persistent = True
        else:
            # 3) Otherwise, temp throwaway
            tmp = tempfile.mkdtemp(prefix="ff-profile-")
            chosen_dir = Path(tmp)
            is_persistent = False

    # arg_persist can force persistent behavior (but never force-delete a named/explicit dir)
    if arg_persist is not None:
        if arg_persist:
            is_persistent = True
        else:
            # Only allow forcing non-persistent if we were going to temp anyway
            if is_persistent and (profile_dir or profile_name or _ENV_PROFILE_DIR or _ENV_PROFILE_NAME or _ENV_PERSIST):
                # Ignore the force-off in this scenario to avoid deleting user dirs.
                pass

    # ENV_PERSIST can flip a temp into persistent (by simply not deleting later)
    if _ENV_PERSIST:
        is_persistent = True

    chosen_dir.mkdir(parents=True, exist_ok=True)
    is_temporary = not is_persistent and chosen_dir.name.startswith("ff-profile-")
    return chosen_dir, is_persistent, is_temporary


# ---------- Driver lifecycle ----------
@contextmanager
def start_driver(
    *,
    headless: bool | None = None,
    page_load_timeout: int = _DEFAULT_TIMEOUT,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> webdriver.Firefox:
    """
    Start a Firefox WebDriver with either:
      - default throwaway temporary profile (deleted on exit), or
      - persistent profile (reused across runs) if requested via args or env.

    Args:
      headless: override env; if None uses FIREFOX_HEADLESS env.
      page_load_timeout: int seconds.
      persist_profile: True to reuse profile across runs; False to always temp.
      profile_name: logical name under FIREFOX_PROFILE_BASE_DIR (".selenium-profiles/<name>").
      profile_dir: absolute path to a specific profile directory (overrides profile_name).
    """
    _ensure_dirs()

    profile_path, is_persistent, is_temporary = _resolve_profile(
        persist_profile=persist_profile, profile_name=profile_name, profile_dir=profile_dir
    )
    logging.info("Firefox profile: %s (%s)", profile_path, "persistent" if is_persistent else "temporary")

    # Options
    opts = FirefoxOptions()
    if headless if headless is not None else _HEADLESS:
        opts.add_argument("-headless")

    # Optional custom Firefox binary
    if _FIREFOX_BIN:
        opts.binary_location = _FIREFOX_BIN

    # Use our profile dir explicitly
    opts.add_argument("-profile")
    opts.add_argument(str(profile_path))

    # Preferences (downloads, noisiness)
    downloads_dir = str(Path(profile_path, "downloads"))
    os.makedirs(downloads_dir, exist_ok=True)
    opts.set_preference("browser.download.folderList", 2)
    opts.set_preference("browser.download.dir", downloads_dir)
    opts.set_preference("browser.download.useDownloadDir", True)
    opts.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/octet-stream,application/pdf,text/plain")
    opts.set_preference("pdfjs.disabled", True)
    opts.set_preference("dom.webnotifications.enabled", False)
    opts.set_preference("general.useragent.updates.enabled", False)
    opts.set_preference("datareporting.healthreport.uploadEnabled", False)

    # Service: prefer explicit geckodriver path if provided; else Selenium Manager
    service = FirefoxService(executable_path=_GECKO_PATH) if _GECKO_PATH else FirefoxService()

    driver = None
    try:
        driver = webdriver.Firefox(options=opts, service=service)
        # Attach a hint so callers can introspect which profile was used (optional)
        try:
            setattr(driver, "_profile_dir", str(profile_path))
            setattr(driver, "_profile_persistent", bool(is_persistent))
        except Exception:
            pass

        driver.set_page_load_timeout(page_load_timeout)
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.warning("Error quitting driver: %s", e)

        # Only remove temp throwaway profiles; never delete persistent ones
        if not is_persistent and is_temporary:
            try:
                shutil.rmtree(profile_path, ignore_errors=True)
            except Exception as e:
                logging.warning("Error removing temp profile dir: %s", e)


# ---------- Driver warmup + context manager ----------
@contextmanager
def spinup_driver(
    headless: bool = False,
    page_load_timeout: int = 30,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
):
    cm = start_driver(
        headless=headless,
        page_load_timeout=page_load_timeout,
        persist_profile=persist_profile,
        profile_name=profile_name,
        profile_dir=profile_dir,
    )
    driver = cm.__enter__()
    try:
        # warmup visits
        for url in random.sample(SEED_URLS, k=3):
            try:
                driver.get(url)
                time.sleep(random.uniform(2, 4))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(1, 2))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                logging.warning(f"⚠️ Failed visiting {url}: {e}")
        yield driver
    finally:
        cm.__exit__(None, None, None)

# ---------- Page → Soup ----------
def get_soup_from_url(
    driver: webdriver.Firefox,
    url: str,
    *,
    wait_css: tuple[By, str] | None = None,
    timeout: int = 12,
    extra_settle_seconds: float = 0.0,
) -> BeautifulSoup | None:
    """
    Navigate to URL and return BeautifulSoup of page_source after a basic wait.

    - wait_css: (By.<KIND>, "selector") to wait for; defaults to body presence.
    - timeout: max seconds to wait for the selector.
    - extra_settle_seconds: post-wait sleep to let SPA content settle (optional).
    """
    try:
        driver.get(url)
        locator = wait_css or (By.TAG_NAME, "body")
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
        if extra_settle_seconds > 0:
            time.sleep(extra_settle_seconds)
        return BeautifulSoup(driver.page_source, "html.parser")
    except NoSuchWindowException:
        print(f"❌ Firefox window closed unexpectedly while loading {url}. Not retrying.")
        return None
    except (TimeoutException, WebDriverException) as e:
        print(f"WebDriver error while loading {url}: {e}")
        return None


# ---------- Convenience capture ----------
def save_page_html(
    driver: webdriver.Firefox,
    url: str,
    *,
    timeout: int = 12,
    extra_settle_seconds: float = 0.0,
) -> dict:
    """
    High-level helper:
    - loads the URL
    - returns dict with paths to both debug and capture files plus soup.

    Returns:
      {
        "soup": BeautifulSoup | None,
        "debug_path": Path | None,
        "capture_path": Path | None,
      }
    """
    from datetime import datetime

    soup = get_soup_from_url(driver, url, timeout=timeout, extra_settle_seconds=extra_settle_seconds)
    if soup is None:
        return {"soup": None, "debug_path": None, "capture_path": None}

    html = str(soup)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = sanitize_for_filename(url)

    debug_path = (_LOG_DEBUG_DIR / f"{ts}__{base}.html")
    debug_path.write_text(html, encoding="utf-8")

    capture_path = write_html_to_file(html, f"{base}.html")
    return {"soup": soup, "debug_path": debug_path, "capture_path": capture_path}
```

---

# 🚀 Use it with your Luma bot

## Option A — No code changes: set env vars once

```powershell
setx FIREFOX_PROFILE_PERSIST 1
setx FIREFOX_PROFILE_NAME luma_bot
```

Now both:

```powershell
# 1) interactive sign-in run (non-headless)
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 3

# 2) scheduled/headless runs reuse the same profile
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

## Option B — Pass args in code (explicit)

In `luma_bot/setup_driver_session.py`, change:

```python
with start_driver() as driver:
```

to:

```python
with start_driver(persist_profile=True, profile_name="luma_bot") as driver:
```

In `luma_bot/register_events.py`, change:

```python
with start_driver() as driver:
```

to:

```python
with start_driver(headless=args.headless, persist_profile=True, profile_name="luma_bot") as driver:
```

Both approaches are interoperable; other scrapers keep using ephemeral profiles by default.

---

# 📝 Notes

* First run should be **non-headless** to complete Luma + Google sign-ins (via your `setup_driver_session.py`). After that, headless is fine.
* The persistent profile lives at:

  * `.selenium-profiles/luma_bot` (if you used `profile_name`), or
  * your custom `FIREFOX_PROFILE_DIR` path.
* We only delete the profile when it’s a temp throwaway. Persistent profiles are never removed by `driver_session`.

If you want, I can also push the tiny **two-line edits** to `setup_driver_session.py` and `register_events.py` verbatim.

-------------------------------------------------------------------------------

I pushed the edits myself, but I still need instructions for using the luma_bot/setup_driver_session.py; on the new run it wasn't called

-------------------------------------------------------------------------------

Gotcha — `setup_driver_session.py` doesn’t run automatically. It’s a **one-time (or as-needed) step you call explicitly** to do the human sign-ins, then it hands off to `register_events.py`.

Here’s exactly how to use it.

# Quick start (PowerShell)

1. **Enable a persistent Firefox profile** (so your logins stick):

```powershell
# one-time machine/user setup
setx FIREFOX_PROFILE_PERSIST 1
setx FIREFOX_PROFILE_NAME luma_bot
```

2. **Run the setup script non-headless** (so you can sign in):

```powershell
# from your repo root
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 3
```

What happens:

* A Firefox window opens to **Luma** → you sign in → press Enter in the console.
* Then it opens **Google Calendar** → sign in (same account as in `calendars.json`) → press Enter.
* The setup window closes and the script **automatically launches** `register_events.py` with the same args you passed (`--cities`, `--max-per-city`, `--headless` if you add it).

3. **Subsequent runs** (headless is fine now; same persistent profile):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

# Common “why didn’t it run?” fixes

* You ran `register_events.py` directly. That’s fine after you’ve done the setup once. If you still weren’t logged in, run `setup_driver_session.py` explicitly as shown above.
* You used a different profile name. Make sure both runs use the **same** profile (env vars above, or pass `persist_profile=True, profile_name="luma_bot"` in your `start_driver()` calls).
* You tried setup headless. Don’t — you won’t see the login UI. Do the first setup **non-headless**.
* You expected your wrapper to call setup. It won’t unless you wire it. See below.

# Optional: wire setup into your PowerShell wrapper

If you want a “do setup first” switch in `scripts/run-luma-bot.ps1`, add a flag and call the setup script:

```powershell
param(
  [Parameter(Mandatory = $true)] [string]$Cities,
  [string]$RepoRoot = ".",
  [string]$VenvPath = ".\.venv\Scripts\python.exe",
  [string]$ProfileJson = "luma_bot\profile.json",
  [int]$MaxPerCity = 0,
  [switch]$Headless,
  [switch]$SetupFirst   # <— add this
)

Set-Location -Path $RepoRoot

if ($SetupFirst) {
  $setupArgs = @("--cities", $Cities)
  if ($MaxPerCity -gt 0) { $setupArgs += @("--max-per-city", "$MaxPerCity") }
  # NOTE: setup script performs the handoff to register_events for you.
  & $VenvPath "luma_bot\setup_driver_session.py" @setupArgs
  exit $LASTEXITCODE
}

# normal direct run
$argList = @("--cities", $Cities, "--profile-json", $ProfileJson)
if ($MaxPerCity -gt 0) { $argList += @("--max-per-city", "$MaxPerCity") }
if ($Headless) { $argList += "--headless" }
& $VenvPath "luma_bot\register_events.py" @argList
exit $LASTEXITCODE
```

Usage:

```powershell
# first time (does interactive logins, then runs the bot)
powershell -ExecutionPolicy Bypass -File .\scripts\run-luma-bot.ps1 -Cities "seattle" -SetupFirst

# later (headless)
powershell -ExecutionPolicy Bypass -File .\scripts\run-luma-bot.ps1 -Cities "seattle,portland" -Headless
```

# Sanity check that logins “stuck”

* After the setup run finishes, start a new run of `register_events.py` (headless or not).
* If it’s still acting logged-out: confirm the env vars are set (new shell needed after `setx`), or pass `persist_profile=True, profile_name="luma_bot"` in your `start_driver()` calls.

If anything still feels off, paste the exact command you ran + console output and I’ll zero in on it.

-------------------------------------------------------------------------------

I feel like we should add all these generated files to .gitignore

-------------------------------------------------------------------------------

**Edited files**

* `.gitignore` (new/updated)

Here’s a ready-to-drop **.gitignore** that covers everything this bot generates (logs, debug HTML, Selenium profiles, de-dupe DB, downloads), plus standard Python/OS/IDE noise. It also ignores your **real config files** and encourages checking in safe `*.example.json` templates instead.

```gitignore
# =========================
# Python
# =========================
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
*.egg
*.egg-info/
.eggs/
build/
dist/
develop-eggs/
.installed.cfg
*.manifest
*.spec
pip-wheel-metadata/
.venv/
venv/
.env
.env.*
.pytest_cache/
.mypy_cache/
.ruff_cache/
.pyre/
.pytype/
.coverage*
htmlcov/

# =========================
# OS cruft
# =========================
.DS_Store
Thumbs.db
desktop.ini

# =========================
# Editors/IDEs
# =========================
.vscode/
.idea/
*.code-workspace

# =========================
# Selenium profiles & temp profiles
# (persistent profile lives here if you used FIREFOX_PROFILE_NAME=luma_bot)
# =========================
.selenium-profiles/
ff-profile-*/

# Firefox download subfolders (when using temp profiles)
**/downloads/

# =========================
# Bot artifacts
# =========================
# Debug HTML & logs
html_captures/
logs/
logs/**

# Luma-bot runtime data (registered events de-dupe store)
luma_bot/data/
luma_bot/data/**

# If you want to keep example configs checked in, ignore the real ones:
luma_bot/profile.json
luma_bot/calendars.json

# Optionally allow example templates
!luma_bot/profile.example.json
!luma_bot/calendars.example.json

# =========================
# Misc
# =========================
*.log
*.tmp
*.swp
*.bak
```

### Recommended follow-ups (one time)

1. Keep **sanitized templates** in git:

   * `luma_bot/profile.example.json`
   * `luma_bot/calendars.example.json`
2. Keep your real, private configs untracked:

   * `luma_bot/profile.json`
   * `luma_bot/calendars.json`

If you’ve already committed any of the ignored files, run:

```bash
git rm -r --cached html_captures logs luma_bot/data luma_bot/profile.json luma_bot/calendars.json .selenium-profiles
git commit -m "chore(gitignore): stop tracking generated artifacts and private configs"
```

Want me to spit out `profile.example.json` and `calendars.example.json` with placeholders next? I can draft them to match what the bot expects.

---

**Conventional Commit**

chore(gitignore): ignore selenium profiles, logs, debug html, luma data, and private configs; keep example templates tracked


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
