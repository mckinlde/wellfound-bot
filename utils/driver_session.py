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
