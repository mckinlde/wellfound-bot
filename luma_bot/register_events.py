from __future__ import annotations
import re
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

DATA_DIR = Path("luma_bot/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
REGISTERED_DB = DATA_DIR / "registered_events.json"  # simple de-dupe store


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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
        default=str(Path("luma_bot/profile.json")),
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
        with start_driver(headless=args.headless, persist_profile=True, profile_name="luma_bot") as driver:
            for city in cities:
                process_city(driver, city, logger, max_events=args.max_per_city)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as e:
        logger.fail(f"[FATAL] {e!r}")


if __name__ == "__main__":
    main()
