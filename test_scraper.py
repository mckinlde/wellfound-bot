#!/usr/bin/env python3
"""
test_scraper.py (html capture)

Open a Wellfound page and save the raw HTML to:
- ./logs/debug/<timestamp>__<sanitized-url>.html
- ./html_captures/<sanitized-url>.html  (via driver_session.write_html_to_file)

Usage:
  nix develop
  python3 test_scraper.py
  python3 test_scraper.py --url "https://https://news.ycombinator.com/"
  python3 test_scraper.py --timeout 15
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from utils.driver_session import (
    start_driver,
    get_soup_from_url,
    write_html_to_file,
)

DEFAULT_URL = "https://www.medicare.gov/plan-compare/#/?year=2025&lang=en"


def ensure_dirs() -> None:
    Path("logs/debug").mkdir(parents=True, exist_ok=True)
    Path("html_captures").mkdir(parents=True, exist_ok=True)


def sanitize_for_filename(url: str) -> str:
    s = url.replace("https://", "").replace("http://", "")
    for ch in "/?:&=#%\\":
        s = s.replace(ch, "_")
    return s[:128]


def save_debug_html(html: str, url: str) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = Path("logs/debug") / f"{ts}__{sanitize_for_filename(url)}.html"
    out.write_text(html, encoding="utf-8")
    return out


def capture(url: str, timeout: int) -> Path:
    ensure_dirs()
    with start_driver() as driver:
        soup = get_soup_from_url(driver, url, timeout=timeout)
        if soup is None:
            raise RuntimeError(f"Failed to load or parse: {url}")

        html = str(soup)

        # Save to logs/debug for ad-hoc inspection
        debug_path = save_debug_html(html, url)

        # Save to html_captures using shared helper for consistency
        write_html_to_file(html, f"{sanitize_for_filename(url)}.html")

        print("\nPress Enter to close the browser window...")
        input()

        return debug_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Open page and save raw HTML to html_captures/ (and logs/debug/).")
    ap.add_argument("--url", default=DEFAULT_URL, help=f"URL to load (default: {DEFAULT_URL})")
    ap.add_argument("--timeout", type=int, default=12, help="Load timeout seconds (default: 12)")
    args = ap.parse_args()

    debug_path = capture(args.url, args.timeout)
    print(f"✅ Saved HTML. Debug copy at: {debug_path}")
    print("📂 Also saved into: ./html_captures/")


if __name__ == "__main__":
    main()
