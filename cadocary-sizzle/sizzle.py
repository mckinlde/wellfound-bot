import time
import os
import requests
import subprocess
import subprocess, pyautogui
import pygetwindow as gw
import shutil, zipfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------
# Configuration
# -----------------

DOWNLOAD_DIR = "H5521-060-2025"  # or PLAN_ID
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
BASE_DIR = DOWNLOAD_DIR
DETAILS_DIR = os.path.join(BASE_DIR, "plan_details")
os.makedirs(DETAILS_DIR, exist_ok=True)

pdf_links = [
    ("Evidence of Coverage (EOC)", "https://www.aetna.com/medicare/documents/individual/2025/eoc/Y0001_S5601_CHOICE_EOC2025_C.pdf"),
    ("Star Ratings", "https://www.aetna.com/medicare/documents/individual/2025/star_rating/STAR_2025_S5601_000_EN.pdf"),
    ("Formulary", "https://www.aetna.com/medicare/documents/individual/2025/formularies/FORM_2025_25096A2z_EN.pdf"),
]
# -----------------
# Helper functions
# -----------------
def scroll_into_view(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(1)  # pause for visibility

def wait_and_click(driver, by, selector, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )
    scroll_into_view(driver, el)
    el.click()
    time.sleep(1)
    return el

def wait_and_type(driver, by, selector, text, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, selector))
    )
    scroll_into_view(driver, el)
    el.clear()
    el.send_keys(text)
    time.sleep(1)
    return el

from selenium.webdriver.common.keys import Keys

def wait_and_type_zip(driver, by, selector, text, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )
    scroll_into_view(driver, el)
    el.click()
    time.sleep(0.1)

    # Type slowly so React/auto-suggest registers each keystroke
    for char in text:
        el.send_keys(char)
        time.sleep(0.2)


def browserDemo():
    driver = webdriver.Chrome()
    driver.set_window_size(1024, 768)  # don’t maximize for demo
    # snap window right
    pyautogui.hotkey("win", "right")
    time.sleep(0.3)  
    driver.get("https://www.aetna.com/medicare.html")
    time.sleep(2)
    # Close cookie banner
    print("[STEP] Closing cookie banner")
    wait_and_click(driver, By.CSS_SELECTOR, "button.onetrust-close-btn-handler.banner-close-button.ot-close-link")
    # Enter ZIP code
    print("[STEP] Entering ZIP code 99336")
    wait_and_type_zip(driver, By.ID, "1499736971-ZipCode", "99336")
    # Hard navigate to next step
    target_url = f"https://enrollmedicare.aetna.com/s/shop?PlanYear=2025&ZipCode=99336&step=Coverage"
    driver.get(target_url)
    
    # Click "No I don't" for existing coverage question
    print("[STEP] Selecting 'No, I don't'")
    wait_and_click(driver, By.XPATH, "//div[contains(@class, 'nds-radio_text') and normalize-space(text())=\"No, I don't\"]")
    # Click Next
    print("[STEP] Clicking 'Next'")
    wait_and_click(driver, By.XPATH, "//span[normalize-space(text())='Next']/ancestor::button")
    # Hard navigate to skip optional steps
    target_url = f"https://enrollmedicare.aetna.com/s/shop?PlanYear=2025&ZipCode=99336&step=PlanList&CountyFIPS=53005"
    driver.get(target_url)
    # Wait for "View details" button after page load
    print("[STEP] Waiting for 'View details' button to appear")
    view_btn = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//button[@data-button-type='view-details-button' and normalize-space(text())='View details']"))
    )
    time.sleep(1)

    print("[STEP] Clicking 'View details'")
    scroll_into_view(driver, view_btn)
    view_btn.click()
    time.sleep(1)

    # Scroll to PDFs
    link_el = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, f"//a[@href='{pdf_links[0][1]}']"))
    )
    scroll_into_view(driver, link_el)

    # Open File Explorer to the download directory
    print(f"[STEP] Opening File Explorer at {DOWNLOAD_DIR}")
    subprocess.Popen(["explorer", DOWNLOAD_DIR])
    # Snap window right
    pyautogui.hotkey("win", "right")
    time.sleep(0.5)
    # Snap window up
    pyautogui.hotkey("win", "up")
    time.sleep(0.5)
    pyautogui.press("enter")
        
    for label, href in pdf_links:
        print(f"[STEP] Scrolling to {label}")
        link_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//a[@href='{href}']"))
        )
        scroll_into_view(driver, link_el)
        time.sleep(1)

        print(f"[STEP] Downloading {label}")
        resp = requests.get(href, timeout=30)
        fname = os.path.join(DOWNLOAD_DIR, f"{label.replace(' ', '_')}.pdf")
        with open(fname, "wb") as f:
            f.write(resp.content)
        time.sleep(1)

    print("[STEP] Closing browser but leaving File Explorer open")
    driver.quit()  # Chrome closes
    return True


def calcdemo():
    print("[STEP] Opening Calc")
    subprocess.Popen(["soffice", "--calc"])
    time.sleep(3)

    # snap window right
    pyautogui.hotkey("win", "right")
    time.sleep(0.3)

    # --- Step 1: Enter some demo data ---
    data = [
        ["Region", "Product", "Sales"],
        ["North", "Apples", "120"],
        ["North", "Bananas", "90"],
        ["South", "Apples", "150"],
        ["South", "Bananas", "130"],
        ["North", "Bananas", "90"],
        ["South", "Apples", "150"],
        ["North", "Bananas", "90"],
        ["South", "Apples", "150"],
    ]
    for row in data:
        pyautogui.typewrite("\t".join(row), interval=0.05)
        pyautogui.press("enter")
    time.sleep(1)

    # --- Step 2: Select all data ---
    pyautogui.hotkey("ctrl", "home")
    pyautogui.hotkey("shift", "ctrl", "end")
    time.sleep(0.5)

    # Borders via Format menu (still works, less brittle than pivot):
    pyautogui.hotkey("alt", "o")
    pyautogui.press("enter")
    pyautogui.press("b")
    time.sleep(0.2)

    # Background fill (defaults OK)
    pyautogui.hotkey("alt", "o")
    pyautogui.press("b")
    pyautogui.press("f")
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(2)

    # --- Step 6: Close Calc without saving ---
    pyautogui.hotkey("alt", "f4")
    time.sleep(1)
    pyautogui.press("right")   # move from Save → Don’t Save
    pyautogui.press("enter")

    return True


def filesDemo():
    
    print("[STEP] Moving PDFs into plan_details/")
    for fname in os.listdir(BASE_DIR):
        if fname.lower().endswith(".pdf"):
            src = os.path.join(BASE_DIR, fname)
            dst = os.path.join(DETAILS_DIR, fname)
            shutil.move(src, dst)
            time.sleep(1)  # so it looks incremental

    # Create zip
    ZIP_PATH = os.path.join(BASE_DIR, "plan_details.zip")
    print("[STEP] Creating zip archive")
    with zipfile.ZipFile(ZIP_PATH, 'w') as zipf:
        for fname in os.listdir(DETAILS_DIR):
            zipf.write(os.path.join(DETAILS_DIR, fname), fname)
    time.sleep(1)
    return True



def thunderbirdDemo(
    attachments_dir: str = "plan_details",
    to_addr: str = "mail@cadocary.com",
    subject: str = "Cadocary Automation",
    body: str = (
        "I want to automate ___, and my budget is ___; "
        "can you help me?  See attached for context!"
    ),
):
    """
    Open Thunderbird, compose a new email to `to_addr` with `subject` and `body`,
    attach all PDFs from `attachments_dir`, and send it.
    Works on Windows with Thunderbird 25.x.

    Requirements:
      - Thunderbird installed
      - pyautogui installed
      - If Thunderbird isn't on PATH, the function will try common install paths.
    """

    # Resolve Thunderbird executable
    candidates = [
        r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe",
        r"C:\Program Files (x86)\Mozilla Thunderbird\thunderbird.exe",
    ]
    
    tb_path = None
    for c in candidates:
        if os.path.isabs(c):
            if Path(c).exists():
                tb_path = c
                break
    if tb_path is None:
        raise RuntimeError("Thunderbird not found. Install it or add to PATH.")

    # Collect PDF attachments
    attach_uris = []
    attach_dir_path = Path(attachments_dir).expanduser().resolve()
    if attach_dir_path.exists():
        for p in sorted(attach_dir_path.glob("*.pdf")):
            try:
                attach_uris.append(p.as_uri())  # file:///C:/...
            except Exception:
                # Fallback for weird paths; skip if not URI-safe
                pass

    # Build compose string for Thunderbird
    # Multiple attachments are comma-separated inside a single attachment=''
    compose_parts = [
        f"to='{to_addr}'",
        f"subject='{subject}'",
        f"body='{body}'",
    ]
    if attach_uris:
        compose_parts.append("attachment='" + ",".join(attach_uris) + "'")
    compose_str = ",".join(compose_parts)

    print("[STEP] Opening Thunderbird compose window")
    # Launch compose window directly
    subprocess.Popen([tb_path, "-compose", compose_str])

    # Give the compose window time to appear and take focus
    time.sleep(3.5)

    # Optionally: bring the compose window to front (you said you have focus handled,
    # so this is commented out. Leave here in case you want it.)
    # import pygetwindow as gw
    # wins = [w for w in gw.getAllWindows() if "Write" in w.title or "Thunderbird" in w.title]
    # if wins:
    #     wins[0].activate()
    #     time.sleep(0.5)

    print("[STEP] Sending email (Ctrl+Enter)")
    # Send the message
    pyautogui.hotkey("ctrl", "enter")
    time.sleep(1.0)

    # If Thunderbird prompts (e.g., “Send message?”), confirm with Enter
    # (Sometimes there can be a security/confirm dialog.)
    pyautogui.press("enter")
    time.sleep(0.6)
    # Some environments show a second confirm; harmless to press Enter again.
    pyautogui.press("enter")

    print("[DONE] Thunderbird email sent (or queued if offline).")
    return True
    

def writerdemo():
    print("[STEP] Opening Writer (windowed)")
    subprocess.Popen(["soffice", "--writer", "--nologo", "--norestore"])
    time.sleep(3)  # let Writer launch
    writer_windows = [w for w in gw.getAllWindows() if "Writer" in w.title]

    if writer_windows:
        win = writer_windows[0]
        win.activate()      # bring it to front
        time.sleep(0.5)
        # now pyautogui can type into Writer

    # Snap window left
    pyautogui.hotkey("win", "left")
    time.sleep(0.5)
    pyautogui.hotkey("alt", "y")  # Styles tab
    time.sleep(0.5)
    pyautogui.press("t")  # Set to "Title" style
    time.sleep(0.5)
    pyautogui.hotkey("alt", "o")  # Format tab
    time.sleep(0.5)
    pyautogui.press("t")  # Set alignment
    time.sleep(0.5)
    pyautogui.press("l")  # left align
    time.sleep(0.5)

    # --- Now type in 36pt ---
    msg = (
        "Cadocary can automate\n"
    )
    pyautogui.typewrite(msg, interval=0.05)
    pyautogui.hotkey("alt", "y")  # Styles tab 
    time.sleep(0.5)
    pyautogui.press("1")  # Set to "Heading 1" style
    msg = (
        " all kinds of tasks; \n\n"
    )
    pyautogui.typewrite(msg, interval=0.05)
    pyautogui.hotkey("alt", "y")  # Styles tab 
    pyautogui.press("1")  # Set to "Heading 1" style
    msg = ("like writing this word document,\n")
    pyautogui.typewrite(msg, interval=0.05)
    # --- sleep a bit so you can see it ---

    pyautogui.hotkey("alt", "y")  # Styles tab 
    pyautogui.press("1")  # Set to "Heading 1" style
    msg = ("or dealing with spreadsheets,\n")
    pyautogui.typewrite(msg, interval=0.05)
    # --- Start the Calc Demo on the right side ---
    calcdemo()

    writer_windows = [w for w in gw.getAllWindows() if "Writer" in w.title]

    if writer_windows:
        win = writer_windows[0]
        win.activate()      # bring it to front
        time.sleep(0.5)
        # now pyautogui can type into Writer


    pyautogui.hotkey("alt", "y")  # Styles tab 
    pyautogui.press("1")  # Set to "Heading 1" style
    msg = ("or filling out webforms,\n")
    pyautogui.typewrite(msg, interval=0.05)
    time.sleep(2)    
    browserDemo()
    
    writer_windows = [w for w in gw.getAllWindows() if "Writer" in w.title]

    if writer_windows:
        win = writer_windows[0]
        win.activate()      # bring it to front
        time.sleep(0.5)
        # now pyautogui can type into Writer

    pyautogui.hotkey("alt", "y")  # Styles tab 
    pyautogui.press("1")  # Set to "Heading 1" style
    msg = ("managing files,\n")
    pyautogui.typewrite(msg, interval=0.05)
    time.sleep(2)    
    filesDemo()
    
    writer_windows = [w for w in gw.getAllWindows() if "Writer" in w.title]

    if writer_windows:
        win = writer_windows[0]
        win.activate()      # bring it to front
        time.sleep(0.5)
        # now pyautogui can type into Writer

    pyautogui.hotkey("alt", "y")  # Styles tab 
    pyautogui.press("1")  # Set to "Heading 1" style
    msg = (",\nand much more.")
    pyautogui.typewrite(msg, interval=0.05)
    time.sleep(2)
    thunderbirdDemo()
    # Close Writer
    pyautogui.hotkey("alt", "f4")
    time.sleep(1)
    pyautogui.press("right")   # move from Save to Don't Save
    pyautogui.press("enter")

    return True


# -----------------
# Demo flow skeleton
# -----------------
def main():
    writerdemo()

    input("[ACTION] Press Enter to exit the demo...")
    exit(0)


if __name__ == "__main__":
    main()
