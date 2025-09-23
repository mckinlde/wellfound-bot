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
from typing import Iterator
from selenium.webdriver.remote.webdriver import WebDriver


from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# add Chrome support (keep Firefox as default)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver  # for the return type

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

_BROWSER = (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()

# Chrome profile envs (optional)
_CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR") or None
_CHROME_PROFILE_NAME = os.getenv("CHROME_PROFILE_NAME") or "luma_bot_chrome"
_CHROME_PROFILE_BASE = Path(os.getenv("CHROME_PROFILE_BASE_DIR") or ".selenium-profiles/chrome")


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


# ---------- Browser choice runtime getter ----------
def _get_browser_choice() -> str:
    return (os.getenv("SELENIUM_BROWSER") or os.getenv("BROWSER") or "firefox").lower()


# ---------- Driver lifecycle ----------
@contextmanager
def start_driver(
    *,
    headless: bool | None = None,
    page_load_timeout: int = _DEFAULT_TIMEOUT,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> Iterator[WebDriver]:
    """
    Start a WebDriver with either:
      - default throwaway temporary profile (deleted on exit), or
      - persistent profile (reused across runs) if requested via args or env.

    Browser is selected via env:
      SELENIUM_BROWSER=firefox (default) or chrome
      (BROWSER works too if SELENIUM_BROWSER unset)
    """
    _ensure_dirs()
    logging.info("Browser engine: %s", _get_browser_choice())

    # Resolve a profile directory (works for both Firefox and Chrome)
    profile_path, is_persistent, is_temporary = _resolve_profile(
        persist_profile=persist_profile, profile_name=profile_name, profile_dir=profile_dir
    )

    driver: WebDriver | None = None
    try:
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


# ---------- Driver warmup + context manager ----------
@contextmanager
def spinup_driver(
    headless: bool = False,
    page_load_timeout: int = 30,
    persist_profile: bool | None = None,
    profile_name: str | None = None,
    profile_dir: str | Path | None = None,
) -> Iterator[WebDriver]:
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
