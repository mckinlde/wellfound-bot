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
