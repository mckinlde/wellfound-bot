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

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
