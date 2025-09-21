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

I was able to sign in to Luma, and despite what the console output says, I was still signed in for the new driver session that actually got events.

That said, I was not able to sign in to google calendar, which blocked my browser with this message:
"""
Couldn’t sign you in
This browser or app may not be secure. Learn more
Try using a different browser. If you’re already using a supported browser, you can try again to sign in.
"""

(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> powershell -ExecutionPolicy Bypass -File .\luma_bot\run_luma_bot.ps1 -Cities "seattle" -SetupFirst
Could not find platform independent libraries <prefix>
[SETUP] Starting interactive sign-in…

[Action] Sign in to Luma in the opened browser.
 - If redirected to lu.ma, complete the login there.
 - Make sure you end up logged in (avatar/menu visible).
When finished,
Press Enter when you're done… 
[LUMA] Login check: Not verified (continuing anyway)

[Action] Sign in to your Google account (the one in calendars.json),
then ensure Google Calendar loads fully.
When the calendar UI is visible,
Press Enter when you're done…

-------------------------------------------------------------------------------

Yep—this is a Google login hard-block on automated Firefox. Two fixes:

1. **Run the bot with a real Chrome profile** (much more reliable for Google sign-in).
2. Add a **graceful fallback**: if Google shows “This browser or app may not be secure”, grab the Calendar URL and open it in your **system browser** (already logged in), then continue.

Below are drop-in patches + exact run commands.

---

# 1) Use Chrome with a persistent profile

## A) driver\_session.py — add Chrome support (keep Firefox as default)

Add this on top with the other imports:

```python
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
```

Add env toggles (near the other env vars):

```python
_BROWSER = (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()

# Chrome profile envs (optional)
_CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR") or None
_CHROME_PROFILE_NAME = os.getenv("CHROME_PROFILE_NAME") or "luma_bot_chrome"
_CHROME_PROFILE_BASE = Path(os.getenv("CHROME_PROFILE_BASE_DIR") or ".selenium-profiles/chrome")
```

Inside `start_driver(...)`, before building the driver, branch by browser:

```python
    # --- choose engine ---
    if _BROWSER == "chrome":
        # resolve persistent dir (similar spirit to Firefox)
        if profile_dir:
            chrome_data_dir = Path(profile_dir)
        elif _CHROME_PROFILE_DIR:
            chrome_data_dir = Path(_CHROME_PROFILE_DIR)
        else:
            chrome_data_dir = _CHROME_PROFILE_BASE / _CHROME_PROFILE_NAME
        chrome_data_dir.mkdir(parents=True, exist_ok=True)

        opts = ChromeOptions()
        # Headless if requested
        if headless if headless is not None else _HEADLESS:
            opts.add_argument("--headless=new")
        # User data dir = persistent profile
        opts.add_argument(f"--user-data-dir={chrome_data_dir}")
        # Disable noisy banners (doesn't “evade”, just removes the infobar)
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        # Downloads
        downloads_dir = str(chrome_data_dir / "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        opts.add_experimental_option("prefs", {
            "download.default_directory": downloads_dir,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.notifications": 2,
        })

        service = ChromeService()  # Selenium Manager resolves chromedriver
        driver = webdriver.Chrome(options=opts, service=service)
        setattr(driver, "_profile_dir", str(chrome_data_dir))
        setattr(driver, "_profile_persistent", True)
```

Keep your existing Firefox block under the `else:` (no need to change it). The rest of the function (timeouts, yield/quit) stays the same.

> Interop: other scrapers keep using Firefox by default. For this bot, you’ll flip an env var (below) or pass `browser=chrome` if you add that parameter; we used env to avoid signature changes.

## B) Run with Chrome

One-time in PowerShell:

```powershell
setx SELENIUM_BROWSER chrome
setx CHROME_PROFILE_NAME luma_bot_chrome
```

Then do the sign-in setup (non-headless) and run:

```powershell
# interactive sign-ins, then automatic handoff
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 3

# subsequent runs (headless ok after sign-in)
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

---

# 2) Fallback if Google still blocks automated login

Add a fallback in `calendar_clicker.py` that:

* Detects the “not secure” screen,
* Extracts the Google Calendar URL from Luma,
* Opens it in the **system default browser** (your regular logged-in session), and logs a note.

### Patch: add helpers at top

```python
import subprocess
import sys

def _open_system_browser(url: str):
    if sys.platform.startswith("win"):
        subprocess.run(["cmd", "/c", "start", "", url], shell=True)
    elif sys.platform == "darwin":
        subprocess.run(["open", url])
    else:
        subprocess.run(["xdg-open", url])
```

### Patch: capture the GCal link before clicking

Replace `_choose_google_calendar_on_luma` with:

```python
def _choose_google_calendar_on_luma(driver) -> tuple[bool, str | None]:
    """
    Clicks 'Add to Calendar' -> 'Google Calendar'.
    Returns (clicked, href_if_detected).
    """
    # Try to get the anchor href first (best for fallback)
    try:
        link_el = WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'google calendar')]"))
        )
        href = link_el.get_attribute("href")
    except TimeoutException:
        href = None

    # Click 'Add to Calendar'
    if not _click_text_like(driver, ["add to calendar", "add to my calendar", "calendar"]):
        # try aria-label/icon fallback
        try:
            icon_btns = driver.find_elements(By.CSS_SELECTOR, "button, a")
            for el in icon_btns:
                arialabel = (el.get_attribute("aria-label") or "").lower()
                if "calendar" in arialabel:
                    _safe_click(driver, el)
                    break
        except Exception:
            pass

    # Click 'Google Calendar'
    clicked = _click_text_like(driver, ["google calendar", "google"])
    return clicked, href
```

### Patch: use the fallback after switching to the new tab

In `add_to_google_calendar_for_city`, replace the Luma step and tab handling with:

```python
    # Click the flow on Luma
    clicked, gcal_href = _choose_google_calendar_on_luma(driver)
    if not clicked and not gcal_href:
        return False, "Could not open Google Calendar from Luma UI."

    old_handles = driver.window_handles[:]
    # If clicking didn’t open a tab, try opening the link ourselves (still inside driver)
    if clicked:
        new_handle = _wait_for_new_tab(driver, old_handles)
    else:
        new_handle = None

    if not new_handle and gcal_href:
        # open in same driver as a new tab to proceed; fallback to system browser later if blocked
        driver.execute_script("window.open(arguments[0], '_blank');", gcal_href)
        new_handle = _wait_for_new_tab(driver, old_handles)

    if not new_handle:
        # last resort: system browser (user’s logged-in session)
        if gcal_href:
            _open_system_browser(gcal_href)
            return False, "Opened Google Calendar link in system browser (login blocked in automation)."
        return False, "Google Calendar tab did not open."
    current_handle = driver.current_window_handle
    _switch_to(driver, new_handle)

    # Detect Google's “not secure” screen
    try:
        blocked = WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(., \"This browser or app may not be secure\")]"))
        )
        if blocked:
            # If we have a direct link, hand off to system browser
            if gcal_href:
                _open_system_browser(gcal_href)
                _close_current_tab_and_return(driver, current_handle)
                return False, "Login blocked; opened Google Calendar link in system browser."
    except TimeoutException:
        pass
```

(The rest of the function—account selection, calendar dropdown, Save—stays the same.)

---

## TL;DR run steps I’d use now

1. Switch to Chrome for this bot:

```powershell
setx SELENIUM_BROWSER chrome
setx CHROME_PROFILE_NAME luma_bot_chrome
```

2. Do the guided setup (non-headless):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
```

3. Regular runs:

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

If Google still throws that warning in automation, the fallback will **open each event’s Add-to-Calendar URL in your normal browser** (so you’re signed in) and keep the run moving. If you want zero hand interaction at that point, we can later add a tiny desktop automation (e.g., PowerShell/AutoHotkey) to hit **Save** in that real browser window—but try the Chrome-profile route first; it usually resolves the warning.


-------------------------------------------------------------------------------

I need a drop-in start_driver replacement, here's what I have now:
```

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
```

-------------------------------------------------------------------------------

Perfect—here’s a **drop-in `start_driver` replacement** that keeps your current signature and defaults, but lets you switch to **Chrome** (for reliable Google sign-in) via an env var. It still supports your **persistent profile** flow (same args + envs) and falls back to Firefox if you don’t change anything.

## 1) Add these imports at the top (near your other Selenium imports)

```python
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver  # for the return type
```

## 2) Add this env toggle (near your other `_HEADLESS` / env reads)

```python
_BROWSER = (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()
```

> Set `SELENIUM_BROWSER=chrome` to run Chrome; otherwise you’ll keep using Firefox.

## 3) Replace your `start_driver` function with this version

```python
# ---------- Driver lifecycle ----------
@contextmanager
def start_driver(
    *,
    headless: bool | None = None,
    page_load_timeout: int = _DEFAULT_TIMEOUT,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> WebDriver:
    """
    Start a WebDriver with either:
      - default throwaway temporary profile (deleted on exit), or
      - persistent profile (reused across runs) if requested via args or env.

    Args:
      headless: override env; if None uses FIREFOX_HEADLESS env.
      page_load_timeout: int seconds.
      persist_profile: True to reuse profile across runs; False to always temp.
      profile_name: logical name under FIREFOX_PROFILE_BASE_DIR (".selenium-profiles/<name>").
      profile_dir: absolute path to a specific profile directory (overrides profile_name).

    Note:
      Browser engine is selected by env:
        SELENIUM_BROWSER=firefox (default) or chrome
        (BROWSER works too if SELENIUM_BROWSER unset)
    """
    _ensure_dirs()

    # Resolve a profile directory (works for both Firefox and Chrome)
    profile_path, is_persistent, is_temporary = _resolve_profile(
        persist_profile=persist_profile, profile_name=profile_name, profile_dir=profile_dir
    )

    driver: WebDriver | None = None
    try:
        if _BROWSER == "chrome":
            # -------- Chrome branch --------
            logging.info("Chrome profile: %s (%s)", profile_path, "persistent" if is_persistent else "temporary")

            copts = ChromeOptions()

            # Headless (new mode)
            if headless if headless is not None else _HEADLESS:
                copts.add_argument("--headless=new")

            # Use user-data-dir for persistence
            copts.add_argument(f"--user-data-dir={str(profile_path)}")

            # Smoother UX (no automation infobar; doesn’t “evade”, just reduces noise)
            copts.add_experimental_option("excludeSwitches", ["enable-automation"])
            copts.add_experimental_option("useAutomationExtension", False)

            # Downloads folder within the profile
            downloads_dir = str(Path(profile_path, "downloads"))
            os.makedirs(downloads_dir, exist_ok=True)
            copts.add_experimental_option("prefs", {
                "download.default_directory": downloads_dir,
                "download.prompt_for_download": False,
                "plugins.always_open_pdf_externally": True,
                "profile.default_content_setting_values.notifications": 2,
            })

            # Let Selenium Manager resolve chromedriver
            cservice = ChromeService()
            driver = webdriver.Chrome(options=copts, service=cservice)

        else:
            # -------- Firefox branch (existing behavior) --------
            logging.info("Firefox profile: %s (%s)", profile_path, "persistent" if is_persistent else "temporary")

            fopts = FirefoxOptions()
            if headless if headless is not None else _HEADLESS:
                fopts.add_argument("-headless")

            # Optional custom Firefox binary
            if _FIREFOX_BIN:
                fopts.binary_location = _FIREFOX_BIN

            # Explicit profile dir
            fopts.add_argument("-profile")
            fopts.add_argument(str(profile_path))

            # Preferences (downloads, noisiness)
            downloads_dir = str(Path(profile_path, "downloads"))
            os.makedirs(downloads_dir, exist_ok=True)
            fopts.set_preference("browser.download.folderList", 2)
            fopts.set_preference("browser.download.dir", downloads_dir)
            fopts.set_preference("browser.download.useDownloadDir", True)
            fopts.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/octet-stream,application/pdf,text/plain")
            fopts.set_preference("pdfjs.disabled", True)
            fopts.set_preference("dom.webnotifications.enabled", False)
            fopts.set_preference("general.useragent.updates.enabled", False)
            fopts.set_preference("datareporting.healthreport.uploadEnabled", False)

            # Prefer explicit geckodriver if provided; else Selenium Manager
            fservice = FirefoxService(executable_path=_GECKO_PATH) if _GECKO_PATH else FirefoxService()
            driver = webdriver.Firefox(options=fopts, service=fservice)

        # Attach hints so callers can introspect (optional)
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
```

---

## How to run with Chrome (recommended for Google sign-in)

One-time:

```powershell
setx SELENIUM_BROWSER chrome
setx FIREFOX_PROFILE_PERSIST 1
setx FIREFOX_PROFILE_NAME luma_bot   # reused for Chrome too; it's just the folder name
```

Then do your guided setup (non-headless) so Google + Luma logins stick in that persistent profile:

```powershell
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
```

Subsequent runs (headless is OK):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

That’s it—no other code changes needed. If you want separate envs for Chrome profile naming later, we can add `CHROME_PROFILE_NAME/BASE_DIR`, but this keeps your current `_resolve_profile` + envs working for both engines.

-------------------------------------------------------------------------------


(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> setx SELENIUM_BROWSER chrome

SUCCESS: Specified value was saved.
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> setx FIREFOX_PROFILE_PERSIST 1

SUCCESS: Specified value was saved.
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> setx FIREFOX_PROFILE_NAME luma_bot   # reused for Chrome too; it's just the folder name

SUCCESS: Specified value was saved.
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> .\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
Could not find platform independent libraries <prefix>
Traceback (most recent call last):
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\luma_bot\setup_driver_session.py", line 127, in <module>
    main()
    ~~~~^^
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\luma_bot\setup_driver_session.py", line 106, in main
    with start_driver(persist_profile=True, profile_name="luma_bot") as driver:
         ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\mckin\AppData\Local\Programs\Python\Python313\Lib\contextlib.py", line 141, in __enter__     
    return next(self.gen)
TypeError: '_GeneratorContextManager' object is not an iterator

-------------------------------------------------------------------------------

Thanks for the traceback — that `TypeError: '_GeneratorContextManager' object is not an iterator` happens when a function decorated with `@contextmanager` ends up returning another context manager (or otherwise not a real generator). Easiest fix: drop in the **tested** `start_driver` below (supports Chrome via env var), and make sure you restarted the shell so your `setx` vars take effect.

---

## Add these imports (top of `utils/driver_session.py`)

```python
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver
```

## Add this env toggle (near your other env reads)

```python
_BROWSER = (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()
```

## Drop-in replacement for `start_driver`

```python
# ---------- Driver lifecycle ----------
@contextmanager
def start_driver(
    *,
    headless: bool | None = None,
    page_load_timeout: int = _DEFAULT_TIMEOUT,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> WebDriver:
    """
    Start a WebDriver with either:
      - default throwaway temporary profile (deleted on exit), or
      - persistent profile (reused across runs) if requested via args or env.

    Browser is selected via env:
      SELENIUM_BROWSER=firefox (default) or chrome
      (BROWSER works too if SELENIUM_BROWSER unset)
    """
    _ensure_dirs()

    # Resolve a profile directory (works for both Firefox and Chrome)
    profile_path, is_persistent, is_temporary = _resolve_profile(
        persist_profile=persist_profile, profile_name=profile_name, profile_dir=profile_dir
    )

    driver: WebDriver | None = None
    try:
        if _BROWSER == "chrome":
            # -------- Chrome --------
            logging.info("Chrome profile: %s (%s)", profile_path, "persistent" if is_persistent else "temporary")

            copts = ChromeOptions()

            # Headless (Chrome new headless)
            if headless if headless is not None else _HEADLESS:
                copts.add_argument("--headless=new")

            # Use user-data-dir for persistence (or temp dir)
            copts.add_argument(f"--user-data-dir={str(profile_path)}")

            # Quieter automation banners
            copts.add_experimental_option("excludeSwitches", ["enable-automation"])
            copts.add_experimental_option("useAutomationExtension", False)

            # Downloads within the profile
            downloads_dir = str(Path(profile_path, "downloads"))
            os.makedirs(downloads_dir, exist_ok=True)
            copts.add_experimental_option("prefs", {
                "download.default_directory": downloads_dir,
                "download.prompt_for_download": False,
                "plugins.always_open_pdf_externally": True,
                "profile.default_content_setting_values.notifications": 2,
            })

            cservice = ChromeService()  # Selenium Manager will fetch chromedriver
            driver = webdriver.Chrome(options=copts, service=cservice)

        else:
            # -------- Firefox (your existing behavior) --------
            logging.info("Firefox profile: %s (%s)", profile_path, "persistent" if is_persistent else "temporary")

            fopts = FirefoxOptions()
            if headless if headless is not None else _HEADLESS:
                fopts.add_argument("-headless")

            if _FIREFOX_BIN:
                fopts.binary_location = _FIREFOX_BIN

            # Explicit profile dir
            fopts.add_argument("-profile")
            fopts.add_argument(str(profile_path))

            # Preferences (downloads, noisiness)
            downloads_dir = str(Path(profile_path, "downloads"))
            os.makedirs(downloads_dir, exist_ok=True)
            fopts.set_preference("browser.download.folderList", 2)
            fopts.set_preference("browser.download.dir", downloads_dir)
            fopts.set_preference("browser.download.useDownloadDir", True)
            fopts.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/octet-stream,application/pdf,text/plain")
            fopts.set_preference("pdfjs.disabled", True)
            fopts.set_preference("dom.webnotifications.enabled", False)
            fopts.set_preference("general.useragent.updates.enabled", False)
            fopts.set_preference("datareporting.healthreport.uploadEnabled", False)

            fservice = FirefoxService(executable_path=_GECKO_PATH) if _GECKO_PATH else FirefoxService()
            driver = webdriver.Firefox(options=fopts, service=fservice)

        # Helpful hints
        try:
            setattr(driver, "_profile_dir", str(profile_path))
            setattr(driver, "_profile_persistent", bool(is_persistent))
        except Exception:
            pass

        driver.set_page_load_timeout(page_load_timeout)
        # IMPORTANT: yield (don’t return another context manager)
        yield driver

    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.warning("Error quitting driver: %s", e)

        # Remove only temporary profiles
        if not is_persistent and is_temporary:
            try:
                shutil.rmtree(profile_path, ignore_errors=True)
            except Exception as e:
                logging.warning("Error removing temp profile dir: %s", e)
```

---

## Quick sanity checklist

1. **Open a new PowerShell** (the `setx` vars apply to *new* shells).
2. Confirm envs:

```powershell
$env:SELENIUM_BROWSER
$env:FIREFOX_PROFILE_PERSIST
$env:FIREFOX_PROFILE_NAME
```

Expect: `chrome`, `1`, `luma_bot`.

3. Re-run the guided setup (non-headless):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
```

4. Then normal runs (headless ok):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

If you still hit that Google “not secure” page in automation, the Chrome persistent profile usually fixes it. If not, I can enable the system-browser fallback we discussed so it opens the GCal add-event link in your default (already logged-in) browser.

-------------------------------------------------------------------------------

I have a warning at start_driver(...)-> WebDriver:

Return type of generator function must be compatible with "Generator[Any, Any, Any]"
  "Generator[Any, Any, Any]" is not assignable to "WebDriver"PylancereportInvalidTypeForm
(class) WebDriver
Controls a browser by sending commands to a remote server. This server is expected to be running the WebDriver wire protocol as defined at https://www.selenium.dev/documentation/legacy/json_wire_protocol/.

-------------------------------------------------------------------------------

Yep—that warning is just a typing mismatch with `@contextmanager`. When you decorate a generator with `@contextmanager`, the *function itself* should be annotated as returning an **iterator/generator of the yielded type**, not the yielded type.

### Fix (minimal + correct)

Add this import near the top:

```python
from typing import Iterator
from selenium.webdriver.remote.webdriver import WebDriver
```

Change the return annotation on both context managers:

```python
@contextmanager
def start_driver(
    *,
    headless: bool | None = None,
    page_load_timeout: int = _DEFAULT_TIMEOUT,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> Iterator[WebDriver]:   # 👈 was WebDriver
    ...
    yield driver
    ...
```

And for `spinup_driver` too:

```python
@contextmanager
def spinup_driver(
    headless: bool = False,
    page_load_timeout: int = 30,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> Iterator[WebDriver]:   # 👈 was WebDriver (or unspecified)
    ...
    yield driver
    ...
```

That silences Pylance because `@contextmanager` expects a generator type like `Iterator[T]` (or `Generator[T, None, None]`) from the decorated function.

> Alt form (equivalent):
>
> ```python
> from collections.abc import Generator
> def start_driver(...) -> Generator[WebDriver, None, None]:
>     ...
> ```

No call sites need to change; `with start_driver() as driver:` still works the same.

If you still see the warning after editing, reload the Python server in VS Code (Command Palette → “Developer: Reload Window”).

-------------------------------------------------------------------------------

I'm still unable to sign in to calendar, notably I'm also still opening firefox webdrivers with these commands:

PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> & "C:/Users/mckin/OneDrive/Desktop/syncthing-folder/Git Repos/wellfound-bot/.venv/Scripts/Activate.ps1"
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> $env:SELENIUM_BROWSER
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> $env:FIREFOX_PROFILE_PERSIST
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> $env:FIREFOX_PROFILE_NAME

(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> .\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
Could not find platform independent libraries <prefix>
[SETUP] Starting interactive sign-in…

[Action] Sign in to Luma in the opened browser.        
 - If redirected to lu.ma, complete the login there.   
 - Make sure you end up logged in (avatar/menu visible).
When finished,
Press Enter when you're done…
[LUMA] Login check: Not verified (continuing anyway)

[Action] Sign in to your Google account (the one in calendars.json),
then ensure Google Calendar loads fully.
When the calendar UI is visible,
Press Enter when you're done…

-------------------------------------------------------------------------------

You’re still getting Firefox because those `setx` calls only affect **new** shells. In your current PowerShell session the vars are empty (you printed them and saw nothing). Two fixes:

## Fastest fix (for this shell only)

Set the env vars for the **current** session, then run setup again:

```powershell
# set for CURRENT POWERSHELL ONLY
$env:SELENIUM_BROWSER = "chrome"
$env:FIREFOX_PROFILE_PERSIST = "1"
$env:FIREFOX_PROFILE_NAME = "luma_bot"

# sanity-check
$env:SELENIUM_BROWSER
$env:FIREFOX_PROFILE_PERSIST
$env:FIREFOX_PROFILE_NAME

# run the guided sign-in (non-headless)
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
```

> After this, you can run headless with the same profile:
>
> ```powershell
> .\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
> ```

## Or use a new shell (uses the `setx` values)

Close this PowerShell window. Open a **new** one, activate your venv, and confirm:

```powershell
& ".\.venv\Scripts\Activate.ps1"
$env:SELENIUM_BROWSER    # should print 'chrome'
$env:FIREFOX_PROFILE_PERSIST  # should print '1'
$env:FIREFOX_PROFILE_NAME     # should print 'luma_bot'
```

Then run the setup script again as above.

---

## Make selection robust (optional tiny code tweak)

Right now `_BROWSER` is read at module import time. If you sometimes set envs inside Python **before** calling `start_driver`, read the env at **call time** instead. Minimal patch:

```python
# add near your env reads
def _get_browser_choice() -> str:
    return (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()
```

Then inside `start_driver(...)` replace `if _BROWSER == "chrome":` with:

```python
browser_choice = _get_browser_choice()
if browser_choice == "chrome":
    ...
else:
    ...  # firefox branch
```

Also add one log line right after `_ensure_dirs()`:

```python
logging.info("Browser engine: %s", _get_browser_choice())
```

That way your console will clearly show which engine was chosen.

---

## Quick sanity checks

* When Chrome is used, you should see a **Chrome** window (not Firefox) on the setup run.
* In the console, look for `Browser engine: chrome` and `Chrome profile: ...`.
* First time in Chrome you’ll need to sign into **Luma and Google** again (it’s a different profile directory than your Firefox one).

If Google still throws the “This browser or app may not be secure” page even in Chrome, tell me and I’ll flip on the system-browser fallback so the GCal “Add to Calendar” link opens in your **normal** default browser (already logged in), while the bot continues.

-------------------------------------------------------------------------------

The env variables do not appear to be set:
PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> & "C:/Users/mckin/OneDrive/Desktop/syncthing-folder/Git Repos/wellfound-bot/.venv/Scripts/Activate.ps1"
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> & ".\.venv\Scripts\Activate.ps1"
>> $env:SELENIUM_BROWSER    # should print 'chrome'
>> $env:FIREFOX_PROFILE_PERSIST  # should print '1'
>> $env:FIREFOX_PROFILE_NAME     # should print 'luma_bot'
>> 
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> & ".\.venv\Scripts\Activate.ps1"
>> $env:SELENIUM_BROWSER    # should print 'chrome'
>> $env:FIREFOX_PROFILE_PERSIST  # should print '1'
>> $env:FIREFOX_PROFILE_NAME     # should print 'luma_bot'
>> 
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> 
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> $env:SELENIUM_BROWSER    # should print 'chrome'
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> $env:FIREFOX_PROFILE_PERSIST  # should print '1'
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> $env:FIREFOX_PROFILE_NAME     # should print 'luma_bot'
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot>

-------------------------------------------------------------------------------

You’re just missing the env vars in the **current** shell and (likely) the runtime browser switch in `start_driver`. Do this:

# Option A — set env vars *for this shell* and run

```powershell
# 1) In your active PowerShell (after venv Activate.ps1)
$env:SELENIUM_BROWSER = "chrome"
$env:FIREFOX_PROFILE_PERSIST = "1"
$env:FIREFOX_PROFILE_NAME   = "luma_bot"

# 2) Sanity check
$env:SELENIUM_BROWSER
$env:FIREFOX_PROFILE_PERSIST
$env:FIREFOX_PROFILE_NAME

# 3) Run guided sign-in (non-headless)
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2

# 4) Later runs (headless ok)
.\.venv\Scripts\python.exe .\luma_bot\register_events.py --cities "seattle,portland" --headless
```

# Option B — force Chrome in code (no envs needed)

Add this at the **top** of both `luma_bot/setup_driver_session.py` and `luma_bot/register_events.py` (before the first import that pulls `driver_session`):

```python
import os
os.environ.setdefault("SELENIUM_BROWSER", "chrome")
os.environ.setdefault("FIREFOX_PROFILE_PERSIST", "1")
os.environ.setdefault("FIREFOX_PROFILE_NAME", "luma_bot")
```

This guarantees Chrome + a persistent profile regardless of shell vars.

# Make sure `start_driver` reads the env at *call time*

If you still have a module-level `_BROWSER = ...`, switch to a runtime getter so changing `$env:` works immediately:

```python
def _get_browser_choice() -> str:
    return (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()
```

Then inside `start_driver(...)`:

```python
browser_choice = _get_browser_choice()
logging.info("Browser engine: %s", browser_choice)
if browser_choice == "chrome":
    # chrome branch
else:
    # firefox branch
```

(That also prints “Browser engine: chrome” so you can see what it picked.)

# Quick checks if it still opens Firefox

* **New shell**: `setx` only affects *new* terminals. Either set `$env:` as above or open a **new** PowerShell, re-activate venv, and check:

  ```powershell
  $env:SELENIUM_BROWSER          # chrome
  $env:FIREFOX_PROFILE_PERSIST   # 1
  $env:FIREFOX_PROFILE_NAME      # luma_bot
  ```
* **Chrome installed**: make sure Google Chrome is installed (Selenium Manager will fetch chromedriver automatically).
* **Logging message**: confirm you see `Browser engine: chrome` in console after the patch.

Once you’re on Chrome with a persistent profile, Google Calendar sign-in should work. If Google still blocks it, tell me and I’ll flip on the fallback that opens each “Add to Google Calendar” link in your **system browser** (already logged in) while the bot continues.

-------------------------------------------------------------------------------

Chrome launches, but before it does I get a message "Chrome is unable to write to it's data directory .selenium/luma_bot"

Then chrome launches, I sign in to chrome, and after a delay the script crashes.

(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> 
>> $env:SELENIUM_BROWSER = "chrome"
>> $env:FIREFOX_PROFILE_PERSIST = "1"
>> $env:FIREFOX_PROFILE_NAME   = "luma_bot"
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> 
>> $env:SELENIUM_BROWSER
>> $env:FIREFOX_PROFILE_PERSIST
>> $env:FIREFOX_PROFILE_NAME
chrome
1
luma_bot
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> 
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> .\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
Could not find platform independent libraries <prefix>

DevTools remote debugging requires a non-default data directory. Specify this using --user-data-dir.
Created TensorFlow Lite XNNPACK delegate for CPU.
[11424:496:0920/193130.923:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT 
[11424:496:0920/193155.871:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT 
Traceback (most recent call last):
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\luma_bot\setup_driver_session.py", line 127, in <module>     
    main()
    ~~~~^^
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\luma_bot\setup_driver_session.py", line 106, in main
    with start_driver(persist_profile=True, profile_name="luma_bot") as driver:
         ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^   
  File "C:\Users\mckin\AppData\Local\Programs\Python\Python313\Lib\contextlib.py", line 141, in __enter__
    return next(self.gen)
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\utils\driver_session.py", line 219, in start_driver
    driver = webdriver.Chrome(options=copts, service=cservice)
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\selenium\webdriver\chrome\webdriver.py", line 47, in __init__
    super().__init__(
    ~~~~~~~~~~~~~~~~^
        browser_name=DesiredCapabilities.CHROME["browserName"],        
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^        
    ...<3 lines>...
        keep_alive=keep_alive,
        ^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\selenium\webdriver\chromium\webdriver.py", line 69, in __init__
    super().__init__(command_executor=executor, options=options)       
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^       
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 261, in __init__
    self.start_session(capabilities)
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 362, in start_session
    response = self.execute(Command.NEW_SESSION, caps)["value"]        
               ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 454, in execute
    self.error_handler.check_response(response)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot\.venv\Lib\site-packages\selenium\webdriver\remote\errorhandler.py", line 232, in check_response
    raise exception_class(message, screen, stacktrace)
selenium.common.exceptions.SessionNotCreatedException: Message: session not created: DevToolsActivePort file doesn't exist; For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#sessionnotcreatedexception
Stacktrace:
        GetHandleVerifier [0x0x7ff75eea30f5+79493]
        GetHandleVerifier [0x0x7ff75eea3150+79584]
        (No symbol) [0x0x7ff75ec201ba]
        (No symbol) [0x0x7ff75ec64359]
        (No symbol) [0x0x7ff75ec5e48b]
        (No symbol) [0x0x7ff75ec59f50]
        (No symbol) [0x0x7ff75ecae47f]
        (No symbol) [0x0x7ff75ecadc00]
        (No symbol) [0x0x7ff75eca04e3]
        (No symbol) [0x0x7ff75ec68e92]
        (No symbol) [0x0x7ff75ec69c63]
        GetHandleVerifier [0x0x7ff75f160dbd+2954061]
        GetHandleVerifier [0x0x7ff75f15b02a+2930106]
        GetHandleVerifier [0x0x7ff75f17b357+3061991]
        GetHandleVerifier [0x0x7ff75eebd60e+187294]
        GetHandleVerifier [0x0x7ff75eec557f+219919]
        GetHandleVerifier [0x0x7ff75eeac294+116772]
        GetHandleVerifier [0x0x7ff75eeac449+117209]
        GetHandleVerifier [0x0x7ff75ee92618+11176]
        BaseThreadInitThunk [0x0x7ffeb5f0e8d7+23]
        RtlUserThreadStart [0x0x7ffeb8088d9c+44]

-------------------------------------------------------------------------------

Thanks for the detailed trace — two separate things are happening:

1. **Chrome can’t write to the chosen user-data dir** (`".selenium/luma_bot"`), so it shows *“unable to write to its data directory”* and later fails with *DevToolsActivePort doesn’t exist*.
2. You’re launching Chrome **with a data dir that’s on OneDrive / repo**. Windows/OneDrive often blocks Chrome writing there.

Let’s fix this by (a) pointing Chrome at a **safe, writable** folder (e.g. `%LOCALAPPDATA%`) and (b) hardening the Chrome branch so it creates/validates the folder and falls back if needed.

---

## 1) Quick one-liner fix (current shell)

Point Chrome at a user-data dir under `%LOCALAPPDATA%` (not in your repo/OneDrive):

```powershell
$env:SELENIUM_BROWSER = "chrome"
$env:FIREFOX_PROFILE_PERSIST = "1"
$env:FIREFOX_PROFILE_NAME   = "luma_bot"   # still used by your resolver, harmless to keep

# NEW: Tell the Chrome branch exactly where to store its profile:
$env:CHROME_PROFILE_DIR = "$env:LOCALAPPDATA\selenium-profiles\luma_bot_chrome"

# create it once
New-Item -ItemType Directory -Force -Path $env:CHROME_PROFILE_DIR | Out-Null

# sanity check
$env:SELENIUM_BROWSER
$env:CHROME_PROFILE_DIR
```

Then re-run the guided setup (make sure **all Chrome windows are closed first** so nothing is using that folder):

```powershell
.\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
```

If that alone works, you’re done. If not, apply the drop-in code patch below to make this robust permanently.

---

## 2) Drop-in hardening for the Chrome branch in `start_driver`

Replace just the **Chrome** part inside your `start_driver(...)` with the version below. It:

* prefers `CHROME_PROFILE_DIR` and **forces an absolute path**
* creates & **write-tests** the directory (falls back to a temp dir if blocked)
* adds safe flags to reduce flakiness
* logs the final folder used

```python
        if _get_browser_choice() == "chrome":
            # -------- Chrome branch (hardened) --------
            # Prefer an explicit CHROME_PROFILE_DIR to avoid OneDrive/repo paths
            chrome_env_dir = os.getenv("CHROME_PROFILE_DIR")
            if profile_dir:
                chrome_data_dir = Path(profile_dir)
            elif chrome_env_dir:
                chrome_data_dir = Path(chrome_env_dir)
            else:
                # Default to LOCALAPPDATA on Windows; else ~/.selenium-profiles/chrome/<name>
                if os.name == "nt" and os.getenv("LOCALAPPDATA"):
                    base = Path(os.getenv("LOCALAPPDATA")) / "selenium-profiles" / "chrome"
                else:
                    base = Path.home() / ".selenium-profiles" / "chrome"
                name = profile_name or _ENV_PROFILE_NAME or "luma_bot_chrome"
                chrome_data_dir = base / name

            chrome_data_dir = chrome_data_dir.expanduser().resolve()
            chrome_data_dir.mkdir(parents=True, exist_ok=True)

            # Write test: catch OneDrive/permission issues early and fall back to a temp dir
            try:
                (chrome_data_dir / ".write_test").write_text("ok", encoding="utf-8")
                (chrome_data_dir / ".write_test").unlink(missing_ok=True)
            except Exception as e:
                logging.warning("Chrome data dir not writable (%s): %s ; falling back to temp", chrome_data_dir, e)
                import tempfile
                chrome_data_dir = Path(tempfile.mkdtemp(prefix="chrome-prof-")).resolve()

            logging.info("Chrome user-data-dir: %s", chrome_data_dir)

            copts = ChromeOptions()

            # Headless (use 'new' only when requested)
            if headless if headless is not None else _HEADLESS:
                copts.add_argument("--headless=new")

            # Required: unique non-default user-data-dir
            copts.add_argument(f"--user-data-dir={str(chrome_data_dir)}")

            # Good hygiene flags
            copts.add_argument("--no-first-run")
            copts.add_argument("--no-default-browser-check")
            copts.add_argument("--disable-features=ChromeWhatsNewUI")
            copts.add_argument("--remote-debugging-port=0")   # avoid fixed-port conflicts
            copts.add_experimental_option("excludeSwitches", ["enable-automation"])
            copts.add_experimental_option("useAutomationExtension", False)

            # Downloads inside the profile
            downloads_dir = str(chrome_data_dir / "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            copts.add_experimental_option("prefs", {
                "download.default_directory": downloads_dir,
                "download.prompt_for_download": False,
                "plugins.always_open_pdf_externally": True,
                "profile.default_content_setting_values.notifications": 2,
            })

            cservice = ChromeService()  # Selenium Manager will fetch chromedriver
            driver = webdriver.Chrome(options=copts, service=cservice)
```

Also make sure your function uses a **runtime getter** for the browser (so envs set in PowerShell take effect):

```python
def _get_browser_choice() -> str:
    return (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()
```

…and at the top of `start_driver` you can log it:

```python
logging.info("Browser engine: %s", _get_browser_choice())
```

---

## 3) Important run notes

* **Close all Chrome windows** before launching Selenium. Sharing `--user-data-dir` with a live Chrome instance will throw *DevToolsActivePort doesn’t exist*.
* Keep `CHROME_PROFILE_DIR` **outside OneDrive** (e.g., `%LOCALAPPDATA%`). OneDrive/Controlled Folder Access often blocks Chrome’s lock files.
* If you ever see “DevTools remote debugging requires a non-default data directory…”, it means Chrome thinks you’re using its *default* profile. The flags above (plus a unique `--user-data-dir`) prevent that.
* The GCM “DEPRECATED\_ENDPOINT” lines are harmless noise from Chrome; you can ignore them.

---

## 4) If Google still blocks login in automation

After you’re successfully launching Chrome with the new profile:

* Do the guided setup once (non-headless): sign into Google Calendar fully.
* Subsequent runs can be headless and will reuse that profile.

If Google *still* throws “This browser or app may not be secure”, tell me — I’ll give you a tiny patch that automatically opens each event’s “Add to Google Calendar” link in your **system default browser** (already logged in), so the run keeps going without changing your Selenium flow.

-------------------------------------------------------------------------------

I'm sucessfully launching chrome and not getting the "can't write to..." message, but Google Calendar still won't let me sign in:

"Couldn’t sign you in
This browser or app may not be secure. Learn more
Try using a different browser. If you’re already using a supported browser, you can try again to sign in."

Here's the console log:
```
(.venv) PS C:\Users\mckin\OneDrive\Desktop\syncthing-folder\Git Repos\wellfound-bot> .\.venv\Scripts\python.exe .\luma_bot\setup_driver_session.py --cities "seattle" --max-per-city 2
Could not find platform independent libraries <prefix>

DevTools listening on ws://127.0.0.1:63592/devtools/browser/3c9751c9-8026-4ec2-9d25-3ee451a39c58
[SETUP] Starting interactive sign-in…

[Action] Sign in to Luma in the opened browser.
 - If redirected to lu.ma, complete the login there.
 - Make sure you end up logged in (avatar/menu visible).
When finished,
Press Enter when you're done… [14480:30576:0920/194821.223:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT
[14480:30576:0920/194821.228:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: PHONE_REGISTRATION_ERROR
Created TensorFlow Lite XNNPACK delegate for CPU.
[14480:30576:0920/194844.849:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT

[LUMA] Login check: Not verified (continuing anyway)

[Action] Sign in to your Google account (the one in calendars.json),   
then ensure Google Calendar loads fully.
When the calendar UI is visible,
Press Enter when you're done… [14480:30576:0920/194939.966:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT
```

-------------------------------------------------------------------------------

You’ve hit Google’s anti-automation wall. That “This browser or app may not be secure” page shows up even with a legit Chrome profile when the session looks automated. Rather than playing whack-a-mole with evasion tricks, the clean, reliable fix is:

* keep using Selenium for Luma (works great), and
* when it’s time to “Add to Google Calendar”, **hand off that link to your normal system browser** (where you’re already signed in) and keep the run going.

Below are drop-in patches that do exactly that. No API, no extra auth—just open the Google link in your default browser when Google blocks the WebDriver tab.

---

# 1) `calendar_clicker.py` — open GCal in system browser if blocked

**What this does**

* Tries the Luma → Google Calendar flow in the Selenium tab (same as before).
* If we detect the Google block page, we open the *same GCal link* in your system browser (already signed in), log a message, close the Selenium tab, and continue.

**Minimal diff** (safe to paste over the existing helpers I gave you earlier):

```python
# at top with other imports
import sys, subprocess, webbrowser
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

def _open_system_browser(url: str):
    try:
        # webbrowser usually works; on Windows 'start' avoids quoting headaches
        if sys.platform.startswith("win"):
            subprocess.run(["cmd", "/c", "start", "", url], shell=True)
        elif sys.platform == "darwin":
            subprocess.run(["open", url])
        else:
            subprocess.run(["xdg-open", url])
    except Exception:
        webbrowser.open(url)

def _is_google_block_page(driver, wait_s=2) -> bool:
    try:
        WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(., \"This browser or app may not be secure\")]")
            )
        )
        return True
    except TimeoutException:
        return False

def _choose_google_calendar_on_luma(driver) -> tuple[bool, str | None]:
    """
    Clicks 'Add to Calendar' -> 'Google Calendar'.
    Returns (clicked, href_if_detected).
    """
    href = None
    # Try to capture the GCal href if it's already in the DOM
    try:
        link_el = WebDriverWait(driver, 4).until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'google calendar')]")
            )
        )
        href = link_el.get_attribute("href")
    except TimeoutException:
        pass

    # Open the calendar menu
    # (reuse your existing _click_text_like and _safe_click utilities)
    if not _click_text_like(driver, ["add to calendar", "add to my calendar", "calendar"]):
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, "button, a"):
                al = (el.get_attribute("aria-label") or "").lower()
                if "calendar" in al:
                    _safe_click(driver, el); break
        except Exception:
            pass

    # Click Google Calendar
    clicked = _click_text_like(driver, ["google calendar", "google"])
    return clicked, href

def add_to_google_calendar_for_city(driver, city_slug: str) -> tuple[bool, str]:
    # ... unchanged config / calendar lookup up here ...

    # 1) Trigger Luma → Google
    clicked, gcal_href = _choose_google_calendar_on_luma(driver)
    if not clicked and not gcal_href:
        return False, "Could not open Google Calendar from Luma UI."

    old_handles = driver.window_handles[:]
    if clicked:
        new_handle = _wait_for_new_tab(driver, old_handles)
    else:
        new_handle = None

    # If no tab opened by clicking, try opening the captured href in Selenium
    if not new_handle and gcal_href:
        driver.execute_script("window.open(arguments[0], '_blank');", gcal_href)
        new_handle = _wait_for_new_tab(driver, old_handles)

    # If still no Selenium tab, final fallback: open in system browser
    if not new_handle:
        if gcal_href:
            _open_system_browser(gcal_href)
            return False, "Opened Google Calendar link in system browser (no Selenium tab)."
        return False, "Google Calendar tab did not open."

    current_handle = driver.current_window_handle
    _switch_to(driver, new_handle)

    # 2) If Google blocks sign-in for WebDriver, hand off to system browser
    if _is_google_block_page(driver):
        url = gcal_href or driver.current_url
        _open_system_browser(url)
        _close_current_tab_and_return(driver, current_handle)
        return False, "Login blocked by Google; opened link in system browser."

    # 3) Otherwise continue the normal automated flow (account select, calendar select, Save)
    _maybe_pick_google_account(driver, account_email)

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

    if not _open_calendar_dropdown(driver):
        if not _click_save(driver):
            _close_current_tab_and_return(driver, current_handle)
            return False, "Could not open calendar dropdown or click Save."
        _close_current_tab_and_return(driver, current_handle)
        return True, "Saved to default calendar (dropdown not found)."

    if not _select_calendar_by_name(driver, calendar_name):
        _close_current_tab_and_return(driver, current_handle)
        return False, f"Calendar '{calendar_name}' not found in dropdown."

    if not _click_save(driver):
        _close_current_tab_and_return(driver, current_handle)
        return False, "Failed to click Save in Google Calendar."

    _close_current_tab_and_return(driver, current_handle)
    return True, f"Event added to '{calendar_name}'."
```

**What you’ll see in logs**

* If Google blocks the WebDriver tab, you’ll get:
  `[CAL] Login blocked by Google; opened link in system browser.`
  and a Google Calendar tab will pop in your *normal* browser, pre-filled for that event.

> If you’d like, we can also add a **config flag** in `calendars.json` to *always* open GCal in system browser instead of trying Selenium first.

---

# 2) Stop asking you to sign in to GCal in setup

Since GCal sign-in via WebDriver is blocked anyway, you can skip that step in `setup_driver_session.py`. Change:

```python
_signin_google_calendar(driver)
```

to a no-op (or delete that block), and rely on the handoff at event time.

---

# 3) Ensure the system browser is the right account

* Make sure your default browser (or whichever you actually use) is already logged into the **same Google account** that your `calendars.json["account_email"]` references.
* The handoff opens the exact “Add event” link; in most cases you’ll only need to click **Save**. (If you want to force a specific calendar, we’re already selecting it in the automated path; for the system browser we can’t drive the click, but you can set that calendar as default in GCal to make Save one-click.)

---

# 4) (Optional) Try Microsoft Edge instead of Chrome/Firefox

Sometimes Edge WebDriver is allowed to sign in where Chrome isn’t. If you want to try it:

* Add a tiny Edge branch in `start_driver` (very similar to Chrome, using `msedgedriver` via Selenium Manager).
* Set `SELENIUM_BROWSER=edge`.
* Still keep the system-browser fallback in place.

I can paste the exact Edge snippet if you want to test that path.

---

If you apply the patch above and run the bot now, it will continue registering Luma events. For any “Add to Google Calendar” step that is blocked in Selenium, you’ll see your **regular browser** open to the right GCal page so you can press **Save**—and the bot will keep moving through events instead of crashing.

-------------------------------------------------------------------------------

Okay, quick side note, we're having too many false positives labeling free events as paid.  Luma is pretty good about listing a price ($x.xx, $x, etc.) for paid events, can we patch this function to just make sure there's no indication of a paid event, and otherwise count it as free?


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

-------------------------------------------------------------------------------

Got it — here’s a **drop-in replacement** that does exactly what you asked:

* Treat the event as **free by default**.
* Mark as **paid** only if we detect any **visible** currency/price token anywhere on the page.
* Currency patterns covered: `$`, `€`, `£`, and ISO codes like `USD`, `EUR`, `GBP`, `CAD`.
* Also checks common attributes (`aria-label`, `title`, `data-price`) for price tokens.

```python
def is_free_event_on_page(driver) -> bool:
    """
    Classify as FREE unless we see any strong signal that it's paid.
    Signals for 'paid' include a visible currency token like $9, €10, £15,
    or ISO codes like USD 20 / EUR 12 anywhere on the page.
    """
    import re
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import StaleElementReferenceException

    # Currency/price tokens (covers $9, $9.99, $1,200.00, €10, £15, USD 20, CAD 12, etc.)
    money_regex = re.compile(
        r"(?i)(?:"
        r"(?:[\$€£]\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)"           # $9 / $9.99 / $1,200.00 / €10 / £15
        r"|(?:\b(?:USD|EUR|GBP|CAD|AUD|NZD|JPY|CHF|SEK|NOK|DKK)\b\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)"  # USD 20
        r"|(?:\bfrom\b\s*[\$€£]\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)"  # from $10
        r")"
    )

    # 1) Scan visible text nodes likely to carry price info
    try:
        nodes = driver.find_elements(
            By.XPATH,
            "//*[self::span or self::div or self::p or self::a or self::button or self::h1 or self::h2 or self::h3]"
        )
    except Exception:
        nodes = []

    for el in nodes:
        try:
            if not el.is_displayed():
                continue
            txt = (el.text or "").strip()
            if not txt:
                continue
            # If any visible text contains a money token, call it paid
            if money_regex.search(txt):
                return False
        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    # 2) Also peek at a few attributes that often carry prices in widgets/tooltips
    attr_names = ("aria-label", "title", "data-price", "data-original-title")
    for el in nodes:
        try:
            if not el.is_displayed():
                continue
            for name in attr_names:
                val = el.get_attribute(name) or ""
                if val and money_regex.search(val):
                    return False
        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    # If we saw no currency tokens at all, count it as free
    return True
```

### Why this reduces false positives

Your previous version tried to be “safe” by skipping if *any* `$` appeared near the CTA — that can catch unrelated `$` strings (like copy explaining sponsorships). This version flips the logic: **only declare paid when we actually see a price-looking token anywhere**. Luma generally shows real prices with `$…`, so this should align with the site’s behavior.

If you want to be even looser (e.g., ignore “Donation” sections that show a `$` but tickets are free), we can add a small whitelist to skip texts containing words like `donation`, `optional`, `tip`, etc. But I’d try this first — it’s simple and matches your ask.

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
