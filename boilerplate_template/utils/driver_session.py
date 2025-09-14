# driver_session.py
"""
driver_session abstracts Selenium WebDriver state from the rest of the app.
- Provides a context-managed Firefox driver with sane defaults.
- Works whether or not FIREFOX_BIN / GECKODRIVER_PATH are set (falls back to Selenium Manager).
- Creates a throwaway Firefox profile per run and cleans it up deterministically.
- Includes small utilities to fetch BeautifulSoup from a URL and persist HTML safely.

Env (optional):
  FIREFOX_BIN          -> path to firefox.exe (overrides system default)
  GECKODRIVER_PATH     -> path to geckodriver.exe (overrides Selenium Manager)
  FIREFOX_HEADLESS     -> "1" to run headless (default: windowed)
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import logging
import time
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


# ---------- Driver lifecycle ----------
@contextmanager
def start_driver(
    *,
    headless: bool | None = None,
    page_load_timeout: int = _DEFAULT_TIMEOUT,
) -> webdriver.Firefox:
    """
    Start a Firefox WebDriver with a temporary profile. Cleans up on exit.

    headless: override env; if None uses FIREFOX_HEADLESS env.
    """
    _ensure_dirs()
    profile_dir = tempfile.mkdtemp(prefix="ff-profile-")
    logging.info("Using temp Firefox profile: %s", profile_dir)

    # Options
    opts = FirefoxOptions()
    if headless if headless is not None else _HEADLESS:
        opts.add_argument("-headless")

    # Optional custom Firefox binary
    if _FIREFOX_BIN:
        opts.binary_location = _FIREFOX_BIN

    # Use our temp profile dir explicitly
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)

    # Preferences (downloads, noisiness)
    # Note: 'download.dir' must be an absolute path
    downloads_dir = str(Path(profile_dir, "downloads"))
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
        driver.set_page_load_timeout(page_load_timeout)
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.warning("Error quitting driver: %s", e)
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception as e:
            logging.warning("Error removing temp profile dir: %s", e)


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
