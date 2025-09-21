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
    with start_driver(persist_profile=True, profile_name="luma_bot") as driver:
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
