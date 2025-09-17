Ahh, yes — this is classic CCFS “bot protection” behavior, and the console output you’re seeing confirms it.

Here’s what’s happening:

* The **“View Documents”** click in the Filing History triggers an **XHR request** from the AngularJS SPA to their API endpoint:

  ```
  https://ccfs-api.prod.sos.wa.gov/api/Common/GetTransactionDocumentsList
  ```
* When browsing normally, this succeeds because the session/cookies/headers are consistent.
* Under Selenium automation, after a few requests, the server flips a switch: the API starts returning **CORS errors / null responses**, which are surfaced in the SPA as `Cannot read properties of null (reading 'Message')`.
* The network error (`No 'Access-Control-Allow-Origin' header`) is a *red herring*: this isn’t really a CORS misconfig, it’s the API rejecting your automated session.

So yes — you’ve hit their **anti-bot detection**.

---

### What you can do about it

#### 1. Make Selenium stealthier

* Use [selenium-stealth](https://github.com/diprajpatra/selenium-stealth) or undetected-chromedriver (but you’re using Firefox, so selenium-stealth is more relevant).
* These patch webdriver fingerprints: `navigator.webdriver`, Chrome/Firefox extension leaks, user-agent hints, etc.

#### 2. Slow down & randomize

* Add **random sleep intervals** between actions.
* Rotate through different action paths (sometimes click Back, sometimes navigate home, etc).
* This reduces your “bot-like” rhythm.

#### 3. Preserve cookies & headers

* Right now, every CCFS API call is done via the SPA. If CCFS starts flagging you, you can:

  * Export the **auth cookies** and **XSRF token** from Selenium.
  * Re-run the exact API request with `requests` (bypassing the SPA).
  * That way you don’t rely on AngularJS firing an XHR.

#### 4. Handle the “null Message” gracefully

* When the modal fails because of the blocked API call, the UI will show nothing.
* You could detect this case, log the UBI as “blocked”, and retry later with a fresh browser profile.

#### 5. Rotate browser profiles / IPs

* CCFS may be watching IP addresses. If you’re running thousands of UBIs in one go from a single IP, eventually they’ll flag you.
* Running multiple smaller batches, or routing some requests through a residential proxy, can extend your run.

---

### Pragmatic recommendation

Since you already have the workflow working for the **first few UBIs**, the simplest next step is:

* **Batch smaller runs**: e.g. process 50 UBIs per Firefox profile, then restart.
* **Randomize sleeps** between 1–7 seconds for each click, not fixed `time.sleep(2)`.
* Add stealth with selenium-stealth (patch `navigator.webdriver`, etc).

That alone usually bypasses this “CORS null response” style block.

---

👉 Question for you: do you want me to **add retry logic inside `save_latest_annual_report`** so that if the modal fails (blocked), the script kills the browser, restarts a fresh profile, and resumes from the same UBI? That would make it resilient to these detections.

-------------------------------------------------------------------------------

I think it's just regular rate limiting, not bot detection.  I'll link the documentation pages I got by clicking through the network requests:
1:
```
Error 1015 Ray ID: 97fa64a67be0c4dd • 2025-09-15 19:05:01 UTC
You are being rate limited
What happened?
The owner of this website (ccfs-api.prod.sos.wa.gov) has banned you temporarily from accessing this website.

Please see https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1015/ for more details.

Was this page helpful? Yes No
Cloudflare Ray ID: 97fa64a67be0c4dd • Your IP: Click to reveal • Performance & security by Cloudflare
```
2: https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1015/
3: https://developers.cloudflare.com/waf/reference/legacy/old-rate-limiting/


It looks like the last sucessful PDF save before being rate limited was number 104/721607; can we try to reverse engineer what the maximum allowable rate is?  Maybe rotate the IP?  I'm on a residential internet connection

-------------------------------------------------------------------------------

Got it — thank you for catching that and pulling the Cloudflare error page. That makes it much clearer:

You’re not bot-flagged per se, you’re hitting **Cloudflare’s Error 1015 “rate limited”**. That means CCFS’s API (behind Cloudflare) is configured with a hard throttle on requests per IP, not just Selenium.

---

### What we know from your run

* You got **\~104 filings** successfully processed before the ban hit.
* That strongly suggests they allow **a fixed number of requests per time window** (per IP).
* The fact it took until UBI #104 means you can squeeze a decent amount through before being cut.

---

### Reverse engineering the throttle

Cloudflare’s legacy rate-limiting (see your docs link #3) typically enforces:

* **X requests per Y seconds per IP** (common thresholds are 60/minute, 100/5min, or 1000/hour).
* Once the threshold is exceeded, your IP is temporarily banned (cool-off: often 5–15 minutes).

If you got \~104 requests before a block:

* It could be **100 requests / 5 minutes** (classic).
* Or **100 requests / 10 minutes**.
* Hard to be exact without timing how long those 104 requests took.

---

### What you can do about it

1. **Throttle yourself**

   * Insert delays to stay under \~10–12 filings/minute (≈1 every 5–6s).
   * That should keep you under Cloudflare’s 100/5min or 100/10min rule.
   * Better to run slower than to get cut off and lose continuity.

2. **Batch runs with cooldowns**

   * Do 90–95 filings, then `sleep(600)` (10min).
   * Resume where you left off.
   * This avoids tripping the ban hammer while still running steadily.

3. **IP rotation**

   * With a single residential IP, you’ll always hit the wall eventually.
   * Options:

     * Tailscale exit nodes (switch between locations).
     * A second ISP line / mobile hotspot for alternating IPs.
     * Residential proxy service if you want to go industrial.

4. **Parallelization with multiple IPs**

   * Split UBIs across IPs.
   * E.g., if you have 3 IPs, each can do \~100 filings per cycle, for \~300 filings before hitting Cloudflare.
   * Much more scalable.

---

### Recommended approach for your case

Since you’re on **residential internet** (single IP), the most reliable path is:

* **Throttle to 1 UBI every \~7 seconds** (≈8/min).
* That’s \~480 per hour, \~5k per day, without hitting the 100/5min threshold.
* Add `--start_n / --stop_n` splits and let it churn in the background.

If you need faster throughput, you’ll have to introduce **IP rotation**. A cheap trick is tethering a phone hotspot for the second batch, or using a VPN with residential exit.

---

⚡ Question for you: do you want me to **add an automatic rate-limit manager** into `ccfs_lookup.py` (something like “after every 80 filings, sleep 10 minutes”)? That way you won’t need to babysit runs or guess the safe speed.

-------------------------------------------------------------------------------

I'm not sure that the threshold is 100/5min, but I would like to start measuring the runtime of the script and counting the number of sucessful requests before they start habitually failing to determine what the threshold is.

Can you add detailed logging that we could use to detemine thresholds for powering the automatic rate-limit manager?

-------------------------------------------------------------------------------

Perfect — that’s exactly the right next step: **instrumentation before automation**. We’ll add **detailed timing + counters** into `ccfs_lookup.py` so we can see:

* When each UBI starts and ends.
* How long the request took.
* How many have succeeded vs failed.
* Rolling request rate (per minute, per 5 minutes, etc.).
* First sign of “blocked” (timeouts, missing docs, etc.).

That log will let us empirically see the “cliff” where Cloudflare kicks in.

---

Here’s a refactor you can drop into your script (logging + counters):

```python
import time
from datetime import datetime, timedelta

# Global counters
success_count = 0
fail_count = 0
start_time = time.time()
block_detected = False

def log_progress(ubi: str, index: int, total: int, status: str):
    """
    Log a standardized line for each UBI with timing + status.
    """
    global success_count, fail_count, block_detected

    now = time.time()
    elapsed = now - start_time
    elapsed_str = str(timedelta(seconds=int(elapsed)))

    if status == "success":
        success_count += 1
    elif status == "fail":
        fail_count += 1
    elif status == "blocked":
        block_detected = True

    print(
        f"[LOG] {datetime.now().isoformat()} | "
        f"UBI {index}/{total}: {ubi} | "
        f"Status: {status} | "
        f"Elapsed: {elapsed_str} | "
        f"Success: {success_count} | Fail: {fail_count}"
    )

def process_ubi(driver, ubi: str, index: int, total: int):
    global block_detected
    ubi_clean = ubi.replace(" ", "")
    ubi_dir = HTML_CAPTURE_DIR / ubi_clean

    start = time.time()
    print(f"[INFO] Processing UBI {index}/{total}: {ubi}")

    try:
        # ... your normal navigation + save logic ...

        # If everything works:
        log_progress(ubi, index, total, "success")

    except TimeoutException:
        log_progress(ubi, index, total, "fail")
        # if this is likely a rate-limit symptom:
        if "ccfs-api.prod.sos.wa.gov" in driver.page_source or "rate limited" in driver.page_source.lower():
            log_progress(ubi, index, total, "blocked")
    except Exception as e:
        log_progress(ubi, index, total, f"fail ({type(e).__name__})")
    finally:
        duration = time.time() - start
        print(f"[DEBUG] UBI {ubi} took {duration:.2f} sec")
```

---

### What this gives you

Every processed UBI will output something like:

```
[INFO] Processing UBI 104/721607: 604 598 424
[LOG] 2025-09-15T13:08:45 | UBI 104/721607: 604 598 424 | Status: success | Elapsed: 0:17:32 | Success: 104 | Fail: 0
[DEBUG] UBI 604598424 took 7.23 sec
```

If a block happens:

```
[LOG] 2025-09-15T13:09:10 | UBI 105/721607: 605 516 993 | Status: blocked | Elapsed: 0:17:57 | Success: 104 | Fail: 1
```

---

### Next Step

Once you run a batch and collect logs, we can:

* Count **how many successes before first “blocked”**.
* Measure **avg time per UBI**.
* Derive **max sustainable throughput**.
* Then bake those values into an **automatic rate-limit manager** (auto-throttle / sleep cycles).

---

👉 Do you want me to also write a **log summarizer** (e.g., a Python function that parses these logs after the run and reports thresholds) so you don’t have to eyeball it?

-------------------------------------------------------------------------------

Yes, and implement it into a logfile with logger.  Keep all the print statements for easy viewing, so print output is both written in the console and saved in the logger.  I like to do this by just having 2 function calls everywhere I print; one for print(), and another for logger.log()

Keep in mind that our webdriver isn't navigating to the blocked page--that's just a network request from clicking the "View Documents" button, and when it fails we see output in the devtools browser console and network tab, but the actual DOM html doesn't update.

-------------------------------------------------------------------------------

Got it ✅ — we’ll build this so that **all prints also get logged** (to a rotating logfile in `wa_corps/logs/ccfs_lookup.log`).
We’ll also add a **log summarizer** to parse that logfile after a run and calculate thresholds (success rate, failures before block, runtime per UBI, etc.).

---

### Step 1. Setup logger

At the top of `ccfs_lookup.py`:

```python
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = ROOT / "wa_corps" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "ccfs_lookup.log"

# Configure logger
logger = logging.getLogger("ccfs")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
```

---

### Step 2. Dual print+log helper

```python
def dual_log(message: str, level: str = "info"):
    """Print to console and log to file at the same time."""
    print(message)
    if level == "info":
        logger.info(message)
    elif level == "warn":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "debug":
        logger.debug(message)
    else:
        logger.info(message)
```

Replace every `print()` and `log_progress()` call with `dual_log(...)`.

Example:

```python
dual_log(f"[INFO] Processing UBI {index}/{total}: {ubi}")
```

---

### Step 3. Enhanced log\_progress

```python
def log_progress(ubi: str, index: int, total: int, status: str):
    global success_count, fail_count, block_detected

    now = time.time()
    elapsed = now - start_time
    elapsed_str = str(timedelta(seconds=int(elapsed)))

    if status == "success":
        success_count += 1
    elif status.startswith("fail"):
        fail_count += 1
    elif status == "blocked":
        block_detected = True

    msg = (f"[LOG] {datetime.now().isoformat()} | "
           f"UBI {index}/{total}: {ubi} | "
           f"Status: {status} | "
           f"Elapsed: {elapsed_str} | "
           f"Success: {success_count} | Fail: {fail_count}")
    dual_log(msg)
```

---

### Step 4. Add log summarizer

Put this at the bottom of the file (or in `utils/summary.py` if you prefer):

```python
def summarize_log(log_path: Path = LOG_FILE):
    """
    Parse the ccfs_lookup.log file and summarize performance.
    """
    if not log_path.exists():
        print(f"[ERROR] No logfile found at {log_path}")
        return

    successes, fails, blocks = 0, 0, 0
    first_block_idx, first_block_time = None, None

    with log_path.open(encoding="utf-8") as f:
        for line in f:
            if "Status:" not in line:
                continue
            parts = line.strip().split("|")
            if len(parts) < 4:
                continue
            status = parts[3].split(":")[-1].strip().lower()

            if "success" in status:
                successes += 1
            elif "fail" in status:
                fails += 1
            elif "blocked" in status:
                blocks += 1
                if first_block_idx is None:
                    first_block_idx = successes + fails
                    first_block_time = parts[0]

    dual_log("==== SUMMARY ====", "info")
    dual_log(f"Total successes: {successes}", "info")
    dual_log(f"Total fails: {fails}", "info")
    dual_log(f"Total blocked: {blocks}", "info")
    if first_block_idx:
        dual_log(f"First block after {first_block_idx} requests at {first_block_time}", "warn")
    dual_log("=================", "info")
```

You can call it after the main run:

```python
if __name__ == "__main__":
    main()
    summarize_log()
```

---

### Key Notes

* Since the block is only visible in **network/XHR** failures, not the DOM, the best way to detect it is by logging **when no fulfilled documents are found** after a successful filing-row click. We’ll log that as `"blocked?"` instead of `"fail"`.
* With this logging, you’ll be able to see exactly **after how many successes** the first failures/blocks start showing up.

---

Would you like me to also add an **incremental sleep throttle** (e.g. exponential backoff if too many consecutive `"blocked?"`) — or do you prefer to **just measure cleanly first** with no slowdown so we can find the true ceiling?

-------------------------------------------------------------------------------

I'd like just clean measurements first, and auto-exit main once 5 PDFs in a row fail, so that we can call summarize_log() and get some measurements.  Implement measurement logging across multiple runs in a separate file.

-------------------------------------------------------------------------------

Perfect 👍 — let’s make this *measurement-first* with a **fail-5 consecutive auto-exit** and a separate **measurements log** that persists across runs.

Here’s how we’ll do it:

---

### 1. Add a global measurements file

At the top of `ccfs_lookup.py`:

```python
MEASUREMENTS_FILE = LOG_DIR / "ccfs_measurements.csv"

# ensure file has header if it doesn’t exist
if not MEASUREMENTS_FILE.exists():
    with MEASUREMENTS_FILE.open("w", encoding="utf-8", newline="") as f:
        f.write("timestamp,total_ubis,successes,fails,blocks,elapsed_sec,first_block_idx\n")
```

---

### 2. Track consecutive failures + auto-exit

Inside `main()` loop:

```python
consecutive_failures = 0
for i, ubi in enumerate(ubis_to_process, start=start_n):
    status = process_ubi(driver, ubi, i, total)
    log_progress(ubi, i, total, status)

    if status.startswith("success"):
        consecutive_failures = 0
    elif status in ("fail", "blocked"):
        consecutive_failures += 1
    else:
        consecutive_failures = 0

    if consecutive_failures >= 5:
        dual_log(f"[WARN] Hit 5 consecutive failures at UBI {ubi}. Auto-exiting for measurement run.")
        break
```

Note: `process_ubi` should **return a string status**: `"success"`, `"fail"`, or `"blocked"`.

---

### 3. After run, append measurement row

At the end of `main()`:

```python
end_time = time.time()
elapsed_sec = int(end_time - start_time)

# compute first_block_idx if any
first_block_idx = None
with LOG_FILE.open(encoding="utf-8") as f:
    for line in f:
        if "Status: blocked" in line:
            try:
                ubi_part = line.split("UBI")[1].split(":")[0].strip()
                first_block_idx = ubi_part
                break
            except Exception:
                pass

with MEASUREMENTS_FILE.open("a", encoding="utf-8", newline="") as f:
    f.write(
        f"{datetime.now().isoformat()},"
        f"{total},{success_count},{fail_count},{1 if block_detected else 0},"
        f"{elapsed_sec},{first_block_idx or ''}\n"
    )

dual_log(f"[INFO] Measurements appended to {MEASUREMENTS_FILE}")
summarize_log()
```

---

### 4. Adjust `process_ubi` return values

At the bottom of `process_ubi`:

```python
# on success
return "success"

# on warn / no results
return "fail"

# if modal doc fetch clearly failed → treat as blocked
return "blocked"

# on TimeoutException
return "fail"

# on unexpected Exception
return "fail"
```

---

### 5. What you’ll get

* **`ccfs_lookup.log`** → detailed per-UBI logs (console + file).
* **`ccfs_measurements.csv`** → one row per run, easy to analyze across multiple runs. Example:

```csv
timestamp,total_ubis,successes,fails,blocks,elapsed_sec,first_block_idx
2025-09-15T12:45:23,721607,104,7,1,900,105
2025-09-15T13:10:42,721607,98,5,1,870,99
```

---

Do you want me to also add a **CSV parser utility** (separate script, `analyze_measurements.py`) to graph or summarize thresholds across multiple runs, or would you rather keep it raw CSV for now?

-------------------------------------------------------------------------------

You’re right—the early exit + traceback are from a few small wiring issues:

1. `start_time` wasn’t initialized before `log_progress()` used it
2. the counters (`success_count`, `fail_count`, `block_detected`) weren’t initialized
3. your loop checks `elif status in ("fail","blocked"):` but your functions return strings like `"fail: …"` / `"blocked: …"`
4. a few `return` strings in `save_latest_annual_report()` missed the leading `f`
5. `summarize_log()` was called twice (end of `main()` **and** under `if __name__ == "__main__"`)

Below are **surgical patches**—copy/paste as-is.

---

# 1) Initialize globals (top-level, near other globals)

```python
# --- progress tracking globals ---
MEASUREMENTS_FILE = LOG_DIR / "ccfs_measurements.csv"

# runtime / counters used by log_progress()
start_time = None
success_count = 0
fail_count = 0
block_detected = False
```

(Keep your existing MEASUREMENTS\_FILE header init below this.)

---

# 2) Fix `log_progress` (no logic change needed once globals exist)

No code change here, but it now finds `start_time`, `success_count`, etc.

---

# 3) Set/Reset globals at start of `main()` and record start time

```python
def main():
    global start_time, success_count, fail_count, block_detected
    start_time = time.time()
    success_count = 0
    fail_count = 0
    block_detected = False
```

Put those lines right after `def main():` and before parsing args.

---

# 4) Fix the loop’s failure/blocked detection

Replace this block in `main()`:

```python
if status.startswith("success"):
    consecutive_failures = 0
elif status in ("fail", "blocked"):
    consecutive_failures += 1
else:
    consecutive_failures = 0
```

with:

```python
if status and status.startswith("success"):
    consecutive_failures = 0
elif status and (status.startswith("fail") or status.startswith("blocked")):
    consecutive_failures += 1
else:
    consecutive_failures = 0
```

---

# 5) Make the three returns in `save_latest_annual_report()` real f-strings

Find these three lines and change them:

```python
return "fail: no annual report rows found for UBI {ubi}"
return "blocked: modal not displayed after clicking View Documents for UBI {ubi}"
return "fail: no fulfilled annual report found for UBI {ubi}"
```

→

```python
return f"fail: no annual report rows found for UBI {ubi}"
return f"blocked: modal not displayed after clicking View Documents for UBI {ubi}"
return f"fail: no fulfilled annual report found for UBI {ubi}"
```

Everything else in that function already uses `f""`.

---

# 6) Avoid double summary (remove the extra call at the bottom)

At the very end of the file, change:

```python
if __name__ == "__main__":
    main()
    summarize_log()
```

→

```python
if __name__ == "__main__":
    main()
```

(`main()` already calls `summarize_log()`.)

---

# 7) (Optional, but nice) Use the processed slice size in measurements

In `main()` where you append to `MEASUREMENTS_FILE`, you currently write `total` (all UBIs in CSV). If you want per-run math to be cleaner, replace `total` with `len(slice_ubis)`:

```python
with MEASUREMENTS_FILE.open("a", encoding="utf-8", newline="") as f:
    f.write(
        f"{datetime.now().isoformat()},"
        f"{len(slice_ubis)},{success_count},{fail_count},{1 if block_detected else 0},"
        f"{elapsed_sec},{first_block_idx or ''}\n"
    )
```

---

After these edits:

* `start_time` exists when `log_progress()` runs
* counters are properly tracked across the run
* statuses are correctly classified as fail/blocked even with extra text
* f-strings display real UBIs
* no duplicate summary calls

Shout if you want me to fold in a small guard so `first_block_idx` is derived more robustly (right now it scrapes from the log line; we could instead pass the index into `log_progress` and stash the first “blocked” index directly).

-------------------------------------------------------------------------------

Here's the summary:

INFO:ccfs:[INFO] Measurements appended to C:\Users\240SSD\git repos\wellfound-bot\wa_corps\logs\ccfs_measurements.csv
==== SUMMARY ====
INFO:ccfs:==== SUMMARY ====
Total successes: 51
INFO:ccfs:Total successes: 51
Total fails: 26
INFO:ccfs:Total fails: 26
Total blocked: 6
INFO:ccfs:Total blocked: 6
=================
INFO:ccfs:=================

And csv:
timestamp,total_ubis,successes,fails,blocks,elapsed_sec,first_block_idx
2025-09-16T09:19:46.184498,721607,51,24,3,1757,76

Based on this data, can you implement self-throttling / batch cooldowns?

-------------------------------------------------------------------------------

Got it — thanks for sharing the fresh summary + CSV. ✅
You’re already collecting enough measurement data to implement **self-throttling** logic that will help stretch out your run without hitting Cloudflare’s rate limiter.

---

## Observations from your data

* **51 successes** before the first hard block, then **24 fails**, then **3 blocks**【ccfs\_measurements.csv】.
* That matches what you observed earlier: you can grab **\~50 annual reports** quickly before Cloudflare pushes back.
* The runtime until blocking: **1757s ≈ 29 minutes** → average throughput \~1.7 UBIs/minute.

This suggests the limiter is based on **number of document downloads in a rolling window** (Cloudflare Error 1015), not just raw page views.

---

## Throttling Strategy

We want to **avoid** racking up consecutive fails/blocks. Instead:

1. **Batch control**

   * Group UBIs into batches (e.g. 30–40 UBIs).
   * After each batch, pause (cooldown).

2. **Adaptive cooldown**

   * If consecutive fails/blocks ≥ 2 → increase cooldown (e.g. +2 min).
   * If smooth run → keep cooldown short (e.g. 30–60 s).

3. **Reset on block detection**

   * If “blocked” detected, immediately pause for a long cooldown (e.g. 15 min).
   * Then resume from where you left off.

---

## Example Patch for `main()`

Here’s how you can wire this in without breaking existing logging:

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_n", type=int, default=1)
    parser.add_argument("--stop_n", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=40,
                        help="Number of UBIs to process before cooldown")
    parser.add_argument("--cooldown", type=int, default=60,
                        help="Cooldown seconds between batches")
    args = parser.parse_args()

    # ... load UBIs same as before ...

    with start_driver() as driver:
        driver.get(BASE_URL)
        consecutive_failures = 0
        batch_count = 0

        for i, ubi in enumerate(slice_ubis, start=start_n):
            status = process_ubi(driver, ubi, i, total)
            log_progress(ubi, i, total, status)

            # Update counters
            if status.lower().startswith("success"):
                consecutive_failures = 0
            elif status.lower().startswith("fail") or status.lower().startswith("blocked"):
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            batch_count += 1

            # --- adaptive cooldowns ---
            if consecutive_failures >= 5:
                dual_log(f"[WARN] Hit {consecutive_failures} consecutive failures. Cooling down 15m.")
                time.sleep(15 * 60)
                consecutive_failures = 0
                batch_count = 0

            elif batch_count >= args.batch_size:
                dual_log(f"[INFO] Completed batch of {batch_count} UBIs. Cooling down {args.cooldown}s.")
                time.sleep(args.cooldown)
                batch_count = 0
```

---

## How This Works

* By default:

  * Every 40 UBIs → pause 60s.
  * If 5 consecutive fails/blocks → force pause 15m.
* You can tune `--batch_size` and `--cooldown` via CLI.

---

## Next Step

I suggest:

1. Run with `--batch_size 30 --cooldown 90` first.
2. Inspect the log/measurements to see if blocks disappear.
3. If you still hit blocking around \~50 UBIs, increase cooldown (2–3 min) or lower batch size (20 UBIs).

---

Do you want me to also add **CSV metrics per batch** (like “batch start/end time, successes, fails”), so you can later chart what cooldown settings are most effective? That’d make tuning much easier.

-------------------------------------------------------------------------------

Perfect 👍 — let’s extend the current measurement system so you’ll get **both global run stats** *and* **per-batch metrics**.

---

## Design

We’ll add a new CSV:
`wa_corps/logs/ccfs_batches.csv`

Each row will track:

* `timestamp` – when batch ended
* `batch_id` – sequential batch counter
* `start_idx` / `end_idx` – UBI row indices in that batch
* `successes` – successes in batch
* `fails` – fails in batch
* `blocks` – blocks in batch
* `elapsed_sec` – runtime of batch
* `cooldown_sec` – how long we cooled down after the batch

---

## Code Patch

Add these near your logging helpers:

```python
BATCH_FILE = LOG_DIR / "ccfs_batches.csv"

# ensure header
if not BATCH_FILE.exists():
    with BATCH_FILE.open("w", encoding="utf-8", newline="") as f:
        f.write("timestamp,batch_id,start_idx,end_idx,successes,fails,blocks,elapsed_sec,cooldown_sec\n")

def log_batch(batch_id, start_idx, end_idx, successes, fails, blocks, elapsed_sec, cooldown_sec):
    """
    Append one row of batch metrics to ccfs_batches.csv
    """
    with BATCH_FILE.open("a", encoding="utf-8", newline="") as f:
        f.write(
            f"{datetime.now().isoformat()},"
            f"{batch_id},{start_idx},{end_idx},"
            f"{successes},{fails},{blocks},"
            f"{elapsed_sec},{cooldown_sec}\n"
        )

    dual_log(f"[BATCH] #{batch_id} | UBIs {start_idx}-{end_idx} | "
             f"Succ={successes} Fail={fails} Block={blocks} | "
             f"Elapsed={elapsed_sec}s | Cooldown={cooldown_sec}s")
```

---

## Update `main()`

Modify your batch loop:

```python
with start_driver() as driver:
    driver.get(BASE_URL)
    consecutive_failures = 0
    batch_count = 0
    batch_id = 0
    batch_start_idx = start_n
    batch_success, batch_fail, batch_block = 0, 0, 0
    batch_start_time = time.time()

    for i, ubi in enumerate(slice_ubis, start=start_n):
        status = process_ubi(driver, ubi, i, total)
        log_progress(ubi, i, total, status)

        if status.lower().startswith("success"):
            consecutive_failures = 0
            batch_success += 1
        elif status.lower().startswith("fail"):
            consecutive_failures += 1
            batch_fail += 1
        elif status.lower().startswith("blocked"):
            consecutive_failures += 1
            batch_block += 1
        else:
            consecutive_failures = 0

        batch_count += 1

        # --- forced cooldown on consecutive failures ---
        if consecutive_failures >= 5:
            cooldown = 15 * 60
            batch_id += 1
            elapsed = int(time.time() - batch_start_time)
            log_batch(batch_id, batch_start_idx, i, batch_success, batch_fail, batch_block, elapsed, cooldown)
            dual_log(f"[WARN] Hit {consecutive_failures} consecutive failures. Cooling {cooldown}s.")
            time.sleep(cooldown)
            # reset batch
            batch_start_idx = i + 1
            batch_start_time = time.time()
            batch_success, batch_fail, batch_block = 0, 0, 0
            consecutive_failures = 0
            batch_count = 0

        # --- regular batch cooldown ---
        elif batch_count >= args.batch_size:
            cooldown = args.cooldown
            batch_id += 1
            elapsed = int(time.time() - batch_start_time)
            log_batch(batch_id, batch_start_idx, i, batch_success, batch_fail, batch_block, elapsed, cooldown)
            dual_log(f"[INFO] Completed batch of {batch_count} UBIs. Cooling {cooldown}s.")
            time.sleep(cooldown)
            # reset batch
            batch_start_idx = i + 1
            batch_start_time = time.time()
            batch_success, batch_fail, batch_block = 0, 0, 0
            batch_count = 0
```

---

## Result

Now you’ll have two CSVs:

* `ccfs_measurements.csv` → whole-run stats (like before)
* `ccfs_batches.csv` → per-batch breakdown, perfect for plotting block-onset trends

And both still log to console + logfile for visibility.

---

Do you want me to also wire in a **summarize\_batches()** helper (like `summarize_log`) so you can quickly see average throughput, time to block, etc. after each run?

-------------------------------------------------------------------------------

Got it ✅ — let’s add a `summarize_batches()` helper that parses your new `ccfs_batches.csv` and prints per-batch averages, totals, and time-to-block info.

---

## Code to Add

Drop this near your `summarize_log()`:

```python
def summarize_batches(batch_path: Path = BATCH_FILE):
    """
    Parse the ccfs_batches.csv file and summarize batch-level performance.
    """
    if not batch_path.exists():
        dual_log(f"[ERROR] No batch file found at {batch_path}", "error")
        return

    total_batches = 0
    total_success = total_fail = total_block = 0
    total_elapsed = total_cooldown = 0
    first_block_batch = None

    with batch_path.open(encoding="utf-8") as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 9:
                continue
            (
                timestamp, batch_id, start_idx, end_idx,
                succ, fail, block, elapsed, cooldown
            ) = parts

            batch_id = int(batch_id)
            succ, fail, block = int(succ), int(fail), int(block)
            elapsed, cooldown = int(elapsed), int(cooldown)

            total_batches += 1
            total_success += succ
            total_fail += fail
            total_block += block
            total_elapsed += elapsed
            total_cooldown += cooldown

            if block > 0 and first_block_batch is None:
                first_block_batch = batch_id

    dual_log("==== BATCH SUMMARY ====", "info")
    dual_log(f"Total batches: {total_batches}", "info")
    dual_log(f"Total successes: {total_success}", "info")
    dual_log(f"Total fails: {total_fail}", "info")
    dual_log(f"Total blocked: {total_block}", "info")
    dual_log(f"Avg successes/batch: {total_success // total_batches if total_batches else 0}", "info")
    dual_log(f"Avg fails/batch: {total_fail // total_batches if total_batches else 0}", "info")
    dual_log(f"Avg runtime/batch: {total_elapsed // total_batches if total_batches else 0}s", "info")
    dual_log(f"Avg cooldown/batch: {total_cooldown // total_batches if total_batches else 0}s", "info")
    if first_block_batch:
        dual_log(f"First block occurred in batch #{first_block_batch}", "warn")
    dual_log("======================", "info")
```

---

## Where to Call

At the end of `main()` (right after your existing `summarize_log()`):

```python
summarize_log()
summarize_batches()
```

---

## What You’ll See

Example output after a run:

```
==== BATCH SUMMARY ====
Total batches: 4
Total successes: 51
Total fails: 26
Total blocked: 6
Avg successes/batch: 12
Avg fails/batch: 6
Avg runtime/batch: 437s
Avg cooldown/batch: 900s
First block occurred in batch #3
======================
```

---

Do you want me to also add a **CSV plotter** (matplotlib quick chart of successes/fails/blocks per batch) so you can visualize rate-limit onset, or keep it strictly textual for now?

-------------------------------------------------------------------------------

Thanks for pasting that long run log — it confirms the cooldown logic isn’t enough. Here’s what’s happening:

* You’re hitting the API “modal not displayed” block consistently after \~20–25 UBIs (≈ 7–8 minutes of runtime).
* Even after a **900s (15 min) cooldown**, the block persists (batches #2 and #3 are 100% blocked).
* This suggests Cloudflare’s **rate-limit window is longer than your cooldown** — likely **30–60 min**, not 5–15.

---

## Adjustments I recommend

### 1. Exponential backoff cooldown

Instead of a fixed 900s:

```python
cooldown = base_cooldown * (2 ** consecutive_block_batches)
cooldown = min(cooldown, MAX_COOLDOWN)  # cap at e.g. 1 hour
```

* First block batch → wait 15m
* Second block batch → wait 30m
* Third → wait 1h
* Then cap.

This lets you “probe” until the block actually clears.

---

### 2. Batch-level slowdown before blocking

We can self-throttle **before** Cloudflare blocks us:

* Insert a small random sleep (e.g. 10–20s) between each UBI.
* Measure average throughput per batch; if successes < threshold (say 70%), automatically stretch inter-request delay by +5s per UBI.

---

### 3. Record per-batch block persistence

Add to your batch CSV:

* `block_persisted=1` if *all* UBIs in batch failed as blocked.
  That way we can measure how many cooldown cycles are wasted.

---

### 4. Optional: human-in-the-loop resume

Sometimes Cloudflare bans your **IP for hours**. In that case, automation alone won’t recover quickly. Best fallback:

* Auto-exit after N consecutive block-only batches.
* Summarize & suggest waiting longer / switching IP.

---

## Example Snippet (drop-in)

```python
# in main loop after each batch
if block_count > 0:
    consecutive_block_batches += 1
    cooldown = BASE_COOLDOWN * (2 ** (consecutive_block_batches - 1))
    cooldown = min(cooldown, MAX_COOLDOWN)
    dual_log(f"[WARN] Batch #{batch_id} had blocks. Cooling {cooldown//60} minutes.")
    time.sleep(cooldown)
else:
    consecutive_block_batches = 0
    cooldown = BASE_COOLDOWN  # reset
```

---

📊 With your logs, I’d suggest:

* `BASE_COOLDOWN = 900` (15m)
* `MAX_COOLDOWN = 3600` (1h)
* Add **10s jitter** between requests inside each batch.

---

Do you want me to **patch your current `main()`** with this exponential cooldown + inter-request jitter, so you can test on the next run?

-------------------------------------------------------------------------------

Got it — thanks for pasting the current `main()`. I’ll patch **just the batch/cooldown logic** to add:

1. **Exponential backoff** for block-driven cooldowns (`15m → 30m → 1h`).
2. **Random inter-UBI jitter** (5–15s sleep) to smooth traffic.
3. Preserve all existing features: measurement logging, batch summaries, early exit rules, etc.

Here’s a safe drop-in replacement for your `main()`:

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_n", type=int, default=1)
    parser.add_argument("--stop_n", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=30,
                        help="Number of UBIs to process before cooldown")
    parser.add_argument("--cooldown", type=int, default=90,
                        help="Base cooldown seconds between batches (adaptive if blocked)")
    args = parser.parse_args()

    global start_time, success_count, fail_count, block_detected, block_count, first_block_at_index
    start_time = time.time()
    success_count = 0
    fail_count = 0
    block_detected = False
    block_count = 0
    first_block_at_index = None

    if not INPUT_CSV.exists():
        print(f"[ERROR] Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    # Read all UBIs
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ubis = [row["UBI#"].strip() for row in reader if row.get("UBI#")]

    total = len(ubis)
    if total == 0:
        print("[ERROR] No UBIs found in input CSV")
        sys.exit(1)

    start_n = max(1, args.start_n)
    stop_n = args.stop_n if args.stop_n is not None else total
    if start_n > total:
        print(f"[ERROR] start_n {start_n} > total {total}")
        sys.exit(1)
    stop_n = min(stop_n, total)

    slice_ubis = ubis[start_n - 1: stop_n]
    print(f"[INFO] Loaded {total} UBIs, processing {len(slice_ubis)} (rows {start_n}..{stop_n})")

    # Adaptive cooldown state
    base_cooldown = args.cooldown
    max_cooldown = 3600  # cap at 1h
    consecutive_block_batches = 0

    with start_driver() as driver:
        driver.get(BASE_URL)
        consecutive_failures = 0
        batch_count = 0
        batch_id = 0
        batch_start_idx = start_n
        batch_success, batch_fail, batch_block = 0, 0, 0
        batch_start_time = time.time()

        for i, ubi in enumerate(slice_ubis, start=start_n):
            # --- per-UBI jitter to avoid bursts ---
            jitter = random.randint(5, 15)
            time.sleep(jitter)

            status = process_ubi(driver, ubi, i, total)
            log_progress(ubi, i, total, status)

            if status.lower().startswith("success"):
                consecutive_failures = 0
                batch_success += 1
            elif status.lower().startswith("fail"):
                consecutive_failures += 1
                batch_fail += 1
            elif status.lower().startswith("blocked"):
                consecutive_failures += 1
                batch_block += 1
            else:
                consecutive_failures = 0

            batch_count += 1

            # --- forced cooldown on consecutive failures ---
            if consecutive_failures >= 5:
                batch_id += 1
                elapsed = int(time.time() - batch_start_time)
                # exponential cooldown for blocks
                consecutive_block_batches += 1
                cooldown = min(base_cooldown * (2 ** (consecutive_block_batches - 1)), max_cooldown)
                log_batch(batch_id, batch_start_idx, i,
                          batch_success, batch_fail, batch_block, elapsed, cooldown)
                dual_log(f"[WARN] Hit {consecutive_failures} consecutive failures. Cooling {cooldown}s (exp backoff).")
                time.sleep(cooldown)
                # reset batch
                batch_start_idx = i + 1
                batch_start_time = time.time()
                batch_success, batch_fail, batch_block = 0, 0, 0
                consecutive_failures = 0
                batch_count = 0
                continue  # move on to next UBI

            # --- regular batch cooldown ---
            if batch_count >= args.batch_size:
                batch_id += 1
                elapsed = int(time.time() - batch_start_time)

                if batch_block > 0:
                    consecutive_block_batches += 1
                    cooldown = min(base_cooldown * (2 ** (consecutive_block_batches - 1)), max_cooldown)
                    dual_log(f"[WARN] Batch #{batch_id} had {batch_block} blocks. Cooling {cooldown}s (exp backoff).")
                else:
                    consecutive_block_batches = 0
                    cooldown = base_cooldown
                    dual_log(f"[INFO] Completed batch of {batch_count} UBIs. Cooling {cooldown}s.")

                log_batch(batch_id, batch_start_idx, i,
                          batch_success, batch_fail, batch_block, elapsed, cooldown)

                time.sleep(cooldown)
                # reset batch
                batch_start_idx = i + 1
                batch_start_time = time.time()
                batch_success, batch_fail, batch_block = 0, 0, 0
                batch_count = 0

    # After all done, append measurements
    end_time = time.time()
    elapsed_sec = int(end_time - start_time)

    with MEASUREMENTS_FILE.open("a", encoding="utf-8", newline="") as f:
        f.write(
            f"{datetime.now().isoformat()},"
            f"{len(slice_ubis)},{success_count},{fail_count},{block_count},"
            f"{elapsed_sec},{first_block_at_index or ''}\n"
        )

    dual_log(f"[INFO] Measurements appended to {MEASUREMENTS_FILE}")
    summarize_log()
    summarize_batches()
```

---

✅ All existing features preserved.
➕ Adds jitter + exponential cooldown for blocked batches.
➕ Keeps per-batch metrics intact.

Do you want me to also make the **cooldown strategy visible in the measurements CSV** (extra columns for `cooldown_used` per batch)?

-------------------------------------------------------------------------------

Nice, thanks for sharing the batch-level log — this is exactly the kind of data you need to tune throttling. Let’s look at the pattern:

---

### Batch Results Recap

```
Batch 1 (25 UBIs) → 16 succ, 5 fail, 4 block → 900s cooldown
Batch 2 (5 UBIs)  → all blocked → 900s cooldown
Batch 3 (5 UBIs)  → all blocked → 900s cooldown

Batch 1 (50 UBIs) → 35 succ, 13 fail, 2 block → 3600s cooldown
Batch 2 (50 UBIs) → 32 succ, 18 fail, 0 block → 3600s cooldown
Batch 3 (50 UBIs) → 38 succ, 12 fail, 0 block → 3600s cooldown
Batch 4 (50 UBIs) → 26 succ, 24 fail, 0 block → 3600s cooldown
Batch 5 (50 UBIs) → 37 succ, 13 fail, 0 block → 3600s cooldown
```

---

### What this tells us

1. **Short cooldowns (900s = 15min) were not enough**
   You hit immediate blocking after the first small batch. Cloudflare rate-limit hadn’t reset fully.

2. **Longer cooldowns (3600s = 1h) worked much better**
   After the switch, you consistently got \~70–80% success per batch, with blocks basically gone.

   * Fails are still \~20–25% — likely timeouts/network retries, not rate limits.
   * No consistent blocking until the very first batch of 50 (2 blocks, then gone).

3. **Throughput balance**
   At 50 UBIs per \~27min batch (elapsed\_sec \~1600s), plus a 1h cooldown, you’re netting \~35–40 UBIs/hr.
   Scaling: \~1k UBIs/day per machine if you let it run continuously.

---

### Suggested Tuning

* **Batch size:** 40–50 UBIs seems safe (keeps elapsed time per batch around 25–30min).
* **Cooldown:** Stick with **3600s (1h)** between batches — this clearly clears the Cloudflare 1015 threshold.

  * You could experiment with 2700s (45min), but don’t go shorter unless you want to risk creeping block rates.
* **Dynamic adjustment:** Add logic:

  * If a batch has >5 blocks → bump next cooldown +30min.
  * If a batch has 0 blocks for 3 runs → try reducing cooldown by 15min (to probe the threshold).

---

### Recommendation for your script

Default params:

```bash
--batch_size 50 --cooldown 3600
```

And let the adaptive logic shrink/grow around those anchors.

---

Would you like me to write a **dynamic cooldown manager** for you — so instead of fixed `--cooldown`, it automatically increases/decreases based on the last batch’s block/fail ratio? That way you can maximize throughput without babysitting.

-------------------------------------------------------------------------------

Perfect — here’s how you can drop in a **dynamic cooldown manager** without breaking your existing batch/failure handling. It wraps your current `cooldown` with a feedback loop based on recent batch outcomes.

---

### Updated main loop (excerpt)

```python
        adaptive_cooldown = args.cooldown  # start from user-supplied baseline
        min_cooldown = 1200                # 20 min floor
        max_cooldown = 7200                # 2 hr ceiling

        for i, ubi in enumerate(slice_ubis, start=start_n):
            status = process_ubi(driver, ubi, i, total)
            log_progress(ubi, i, total, status)

            if status.lower().startswith("success"):
                consecutive_failures = 0
                batch_success += 1
            elif status.lower().startswith("fail"):
                consecutive_failures += 1
                batch_fail += 1
            elif status.lower().startswith("blocked"):
                consecutive_failures += 1
                batch_block += 1
            else:
                consecutive_failures = 0

            batch_count += 1

            # --- forced cooldown on consecutive failures ---
            if consecutive_failures >= 5:
                cooldown = 15 * 60
                batch_id += 1
                elapsed = int(time.time() - batch_start_time)
                log_batch(batch_id, batch_start_idx, i, batch_success, batch_fail, batch_block, elapsed, cooldown)
                dual_log(f"[WARN] Hit {consecutive_failures} consecutive failures. Cooling {cooldown}s.")
                time.sleep(cooldown)

                # reset batch + adaptive_cooldown unchanged
                batch_start_idx = i + 1
                batch_start_time = time.time()
                batch_success = batch_fail = batch_block = batch_count = consecutive_failures = 0

            # --- regular batch cooldown ---
            elif batch_count >= args.batch_size:
                cooldown = adaptive_cooldown
                batch_id += 1
                elapsed = int(time.time() - batch_start_time)
                log_batch(batch_id, batch_start_idx, i, batch_success, batch_fail, batch_block, elapsed, cooldown)

                # --- adaptive tuning here ---
                block_rate = batch_block / max(1, batch_count)
                fail_rate = batch_fail / max(1, batch_count)

                if block_rate >= 0.1:  # >10% blocked → increase cooldown
                    adaptive_cooldown = min(max_cooldown, int(adaptive_cooldown * 1.25))
                    dual_log(f"[ADAPT] High block rate ({block_rate:.1%}), increasing cooldown → {adaptive_cooldown}s")
                elif block_rate == 0 and fail_rate < 0.2:
                    adaptive_cooldown = max(min_cooldown, int(adaptive_cooldown * 0.9))
                    dual_log(f"[ADAPT] Clean batch, decreasing cooldown → {adaptive_cooldown}s")
                else:
                    dual_log(f"[ADAPT] Keeping cooldown at {adaptive_cooldown}s")

                dual_log(f"[INFO] Completed batch of {batch_count} UBIs. Cooling {cooldown}s.")
                time.sleep(cooldown)

                # reset batch
                batch_start_idx = i + 1
                batch_start_time = time.time()
                batch_success = batch_fail = batch_block = batch_count = 0
```

---

### What this does

* Starts at `--cooldown` (say 3600s).
* **If ≥10% blocked in a batch** → increase cooldown by +25%, up to 2h.
* **If no blocks + <20% fails** → decrease cooldown by −10%, down to 20min.
* Otherwise → leave cooldown unchanged.
* Forced cooldowns on 5 consecutive failures are **separate** and don’t affect the adaptive cooldown.

---

### Example

* Batch 1: 35/50 success, 13 fail, 2 block → block rate = 4% → stays at 3600s.
* Batch 2: 50/50 clean → cooldown drops to 3240s.
* Batch 3: 50/50 clean again → cooldown drops to \~2900s.
* Batch 4: 20% blocked → cooldown jumps back up toward 4500s.

---

Do you want me to also **log adaptive cooldown changes into your measurements CSV** (extra column), so you can analyze cooldown behavior later?

-------------------------------------------------------------------------------

Perfect — we can fold your requested **adaptive cooldown logic** right into the `main()` without breaking the rest of your logging / measurement system. Here’s the plan:

### Adaptive Cooldown Rules

* **Successful batch (no blocks, mostly successes):**

  * Reduce cooldown by **10%**, down to a floor of e.g. 600 s (10 min).
* **Partially blocked batch (≥1 block but not fully blocked):**

  * Increase cooldown by **25%**, capped by `max_cooldown`.
* **Fully blocked (all UBIs in batch blocked or 5 consecutive fails):**

  * Use exponential backoff, starting at **3600 s (1h)**, doubling up to `max_cooldown`.

---

Here’s the updated `main()` implementation with your adaptive cooldown integrated:

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_n", type=int, default=1)
    parser.add_argument("--stop_n", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=50,
                        help="Number of UBIs to process before cooldown")
    parser.add_argument("--cooldown", type=int, default=3600,
                        help="Base cooldown seconds between batches (adaptive)")
    args = parser.parse_args()

    global start_time, success_count, fail_count, block_detected, block_count, first_block_at_index
    start_time = time.time()
    success_count = 0
    fail_count = 0
    block_detected = False
    block_count = 0
    first_block_at_index = None

    if not INPUT_CSV.exists():
        print(f"[ERROR] Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    # Read UBIs
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ubis = [row["UBI#"].strip() for row in reader if row.get("UBI#")]

    total = len(ubis)
    if total == 0:
        print("[ERROR] No UBIs found in input CSV")
        sys.exit(1)

    start_n = max(1, args.start_n)
    stop_n = args.stop_n if args.stop_n is not None else total
    if start_n > total:
        print(f"[ERROR] start_n {start_n} > total {total}")
        sys.exit(1)
    stop_n = min(stop_n, total)

    slice_ubis = ubis[start_n - 1: stop_n]
    print(f"[INFO] Loaded {total} UBIs, processing {len(slice_ubis)} (rows {start_n}..{stop_n})")

    # Adaptive cooldown state
    cooldown = args.cooldown
    min_cooldown = 600       # 10 minutes floor
    max_cooldown = 3600 * 8  # cap at 8h
    consecutive_block_batches = 0

    with start_driver() as driver:
        driver.get(BASE_URL)
        consecutive_failures = 0
        batch_count = 0
        batch_id = 0
        batch_start_idx = start_n
        batch_success, batch_fail, batch_block = 0, 0, 0
        batch_start_time = time.time()

        for i, ubi in enumerate(slice_ubis, start=start_n):
            # --- per-UBI jitter to avoid bursts ---
            jitter = random.randint(5, 15)
            time.sleep(jitter)

            status = process_ubi(driver, ubi, i, total)
            log_progress(ubi, i, total, status)

            if status.lower().startswith("success"):
                consecutive_failures = 0
                batch_success += 1
            elif status.lower().startswith("fail"):
                consecutive_failures += 1
                batch_fail += 1
            elif status.lower().startswith("blocked"):
                consecutive_failures += 1
                batch_block += 1
            else:
                consecutive_failures = 0

            batch_count += 1

            # --- forced cooldown on consecutive failures ---
            if consecutive_failures >= 5:
                batch_id += 1
                elapsed = int(time.time() - batch_start_time)
                consecutive_block_batches += 1
                cooldown = min(3600 * (2 ** (consecutive_block_batches - 1)), max_cooldown)
                log_batch(batch_id, batch_start_idx, i,
                          batch_success, batch_fail, batch_block, elapsed, cooldown)
                dual_log(f"[WARN] Hit {consecutive_failures} consecutive failures. Cooling {cooldown}s (exp backoff).")
                time.sleep(cooldown)
                # reset batch
                batch_start_idx = i + 1
                batch_start_time = time.time()
                batch_success, batch_fail, batch_block = 0, 0, 0
                consecutive_failures = 0
                batch_count = 0
                continue

            # --- regular batch cooldown ---
            if batch_count >= args.batch_size:
                batch_id += 1
                elapsed = int(time.time() - batch_start_time)

                if batch_block > 0 and batch_success == 0:
                    # fully blocked
                    consecutive_block_batches += 1
                    cooldown = min(3600 * (2 ** (consecutive_block_batches - 1)), max_cooldown)
                    dual_log(f"[WARN] Batch #{batch_id} fully blocked. Cooling {cooldown}s (exp backoff).")
                elif batch_block > 0:
                    # partial block
                    consecutive_block_batches = 0
                    cooldown = min(int(cooldown * 1.25), max_cooldown)
                    dual_log(f"[WARN] Batch #{batch_id} had {batch_block} blocks. Cooling {cooldown}s (+25%).")
                else:
                    # success
                    consecutive_block_batches = 0
                    cooldown = max(int(cooldown * 0.9), min_cooldown)
                    dual_log(f"[INFO] Batch #{batch_id} succeeded. Cooling {cooldown}s (-10%).")

                log_batch(batch_id, batch_start_idx, i,
                          batch_success, batch_fail, batch_block, elapsed, cooldown)

                time.sleep(cooldown)
                # reset batch
                batch_start_idx = i + 1
                batch_start_time = time.time()
                batch_success, batch_fail, batch_block = 0, 0, 0
                batch_count = 0

    # Final measurements
    end_time = time.time()
    elapsed_sec = int(end_time - start_time)
    with MEASUREMENTS_FILE.open("a", encoding="utf-8", newline="") as f:
        f.write(
            f"{datetime.now().isoformat()},"
            f"{len(slice_ubis)},{success_count},{fail_count},{block_count},"
            f"{elapsed_sec},{first_block_at_index or ''}\n"
        )
    dual_log(f"[INFO] Measurements appended to {MEASUREMENTS_FILE}")
    summarize_log()
    summarize_batches()
```

---

✨ Changes vs. your last `main()`:

* Added `min_cooldown = 600` (10 min floor).
* On **success batch** → cooldown = max(cooldown × 0.9, min).
* On **partial block** → cooldown = min(cooldown × 1.25, max).
* On **full block** → exponential backoff starting at 1h.

This way the script **automatically adapts** based on observed block pressure.

---

Want me to also add **per-batch summary lines** into the measurements CSV (with the adjusted cooldown values), so you can track how the cooldown evolves across runs?

-------------------------------------------------------------------------------

Got it ✅ — the skip check is straightforward and won’t break your adaptive cooldown logic. We’ll just check before `process_ubi()` if both the JSON and PDF exist for that UBI. If so, we log and skip immediately.

Here’s how you can integrate it:

---

### Update inside `main()` loop:

```python
        for i, ubi in enumerate(slice_ubis, start=start_n):
            ubi_dir = PDF_DIR / ubi.replace(" ", "")
            pdf_path = ubi_dir / "annual_report.pdf"
            json_path = JSON_DIR / f"{ubi.replace(' ', '')}.json"

            if pdf_path.exists() and json_path.exists():
                dual_log(f"[SKIP] UBI {ubi} already has JSON + PDF, skipping.")
                continue

            # --- per-UBI jitter to avoid bursts ---
            jitter = random.randint(5, 15)
            time.sleep(jitter)

            status = process_ubi(driver, ubi, i, total)
            log_progress(ubi, i, total, status)
```

---

### Why both JSON and PDF?

* If **only JSON exists**: we still want to try downloading the annual report again.
* If **only PDF exists**: we still want JSON for metadata.
* If **both exist**: fully processed → safe to skip.

---

This way, re-runs won’t waste time (or trigger rate limiting) on UBIs you’ve already processed.

Do you also want me to add a **counter for skipped UBIs** into your logs and batch summaries, so you can track how many were skipped in each run?

-------------------------------------------------------------------------------

Perfect — we’ll add a **skip counter** into:

1. **Per-UBI logging** → `[SKIP]` line when a UBI is skipped.
2. **Batch stats** → include `skipped` count alongside successes/fails/blocks.
3. **Final summary** → include total skips.
4. **Measurements CSV** → add a `skips` column.

---

### Changes

#### 1. Initialize skip counter

At top of `main()`:

```python
    global start_time, success_count, fail_count, block_detected, block_count, first_block_at_index, skip_count
    start_time = time.time()
    success_count = 0
    fail_count = 0
    block_detected = False
    block_count = 0
    skip_count = 0
    first_block_at_index = None
```

---

#### 2. Per-UBI skip check

Inside `for i, ubi in enumerate(slice_ubis, start=start_n):`

```python
            ubi_dir = PDF_DIR / ubi.replace(" ", "")
            pdf_path = ubi_dir / "annual_report.pdf"
            json_path = JSON_DIR / f"{ubi.replace(' ', '')}.json"

            if pdf_path.exists() and json_path.exists():
                skip_count += 1
                batch_skip += 1
                dual_log(f"[SKIP] UBI {i}/{total}: {ubi} already has JSON + PDF, skipping.")
                continue
```

---

#### 3. Track in batch

Initialize at batch start:

```python
        batch_success, batch_fail, batch_block, batch_skip = 0, 0, 0, 0
```

Reset after cooldown same way:

```python
        batch_success, batch_fail, batch_block, batch_skip = 0, 0, 0, 0
```

---

#### 4. Update `log_batch`

Change signature + log line to include skips:

```python
def log_batch(batch_id, start_idx, end_idx, succ, fail, block, skip, elapsed, cooldown):
    line = (f"{datetime.now().isoformat()},{batch_id},{start_idx},{end_idx},"
            f"{succ},{fail},{block},{skip},{elapsed},{cooldown}\n")
    with BATCHES_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
    dual_log(f"[BATCH] #{batch_id} | UBIs {start_idx}-{end_idx} | "
             f"Succ={succ} Fail={fail} Block={block} Skip={skip} "
             f"| Elapsed={elapsed}s | Cooldown={cooldown}s")
```

---

#### 5. Measurements CSV

At end of `main()`:

```python
    with MEASUREMENTS_FILE.open("a", encoding="utf-8", newline="") as f:
        f.write(
            f"{datetime.now().isoformat()},"
            f"{len(slice_ubis)},{success_count},{fail_count},{block_count},{skip_count},"
            f"{elapsed_sec},{first_block_at_index or ''}\n"
        )
```

---

#### 6. Summaries

Update `summarize_batches()` and `summarize_log()` to print skip counts.
E.g. in summary:

```
==== SUMMARY ====
Total successes: X
Total fails: Y
Total blocked: Z
Total skipped: W
=================
```

---

👉 Do you want me to also **retrofit your existing `ccfs_measurements.csv`** (add a `skips` column header even if past rows have blanks), so all runs are compatible going forward?

-------------------------------------------------------------------------------

Got it 👍

Here’s exactly what I’ll change for **skip support + retrofitting your existing CSVs**:

---

### 1. Add `skip_count` globally

```python
global start_time, success_count, fail_count, block_detected, block_count, skip_count, first_block_at_index
...
skip_count = 0
```

---

### 2. Check per-UBI for existing outputs

```python
ubi_dir = BUSINESS_PDF_DIR / ubi.replace(" ", "")
pdf_path = ubi_dir / "annual_report.pdf"
json_path = BUSINESS_JSON_DIR / f"{ubi.replace(' ', '')}.json"

if pdf_path.exists() and json_path.exists():
    skip_count += 1
    batch_skip += 1
    dual_log(f"[SKIP] UBI {i}/{total}: {ubi} already has JSON + PDF, skipping.")
    continue
```

---

### 3. Track in batch

Initialize:

```python
batch_success, batch_fail, batch_block, batch_skip = 0, 0, 0, 0
```

Reset after cooldown with same four variables.

---

### 4. Update `log_batch`

Now include `skip` column:

```python
def log_batch(batch_id, start_idx, end_idx, succ, fail, block, skip, elapsed, cooldown):
    line = (f"{datetime.now().isoformat()},{batch_id},{start_idx},{end_idx},"
            f"{succ},{fail},{block},{skip},{elapsed},{cooldown}\n")
    with BATCHES_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
    dual_log(f"[BATCH] #{batch_id} | UBIs {start_idx}-{end_idx} | "
             f"Succ={succ} Fail={fail} Block={block} Skip={skip} "
             f"| Elapsed={elapsed}s | Cooldown={cooldown}s")
```

---

### 5. Final measurement CSV

Write skips into `ccfs_measurements.csv`:

```python
with MEASUREMENTS_FILE.open("a", encoding="utf-8", newline="") as f:
    f.write(
        f"{datetime.now().isoformat()},"
        f"{len(slice_ubis)},{success_count},{fail_count},{block_count},{skip_count},"
        f"{elapsed_sec},{first_block_at_index or ''}\n"
    )
```

---

### 6. Retrofitting `ccfs_measurements.csv`

On startup, ensure file has `skips` column header:

```python
if not MEASUREMENTS_FILE.exists():
    with MEASUREMENTS_FILE.open("w", encoding="utf-8", newline="") as f:
        f.write("timestamp,total_ubis,successes,fails,blocks,skips,elapsed_sec,first_block_idx\n")
else:
    # check header retroactively
    with MEASUREMENTS_FILE.open("r", encoding="utf-8") as f:
        header = f.readline().strip()
    if "skips" not in header:
        tmp = MEASUREMENTS_FILE.with_suffix(".tmp")
        with MEASUREMENTS_FILE.open("r", encoding="utf-8") as fin, tmp.open("w", encoding="utf-8") as fout:
            fout.write(header.replace("elapsed_sec,", "skips,elapsed_sec,") + "\n")
            for line in fin:
                parts = line.strip().split(",")
                if len(parts) == 7:  # old format
                    parts.insert(5, "")  # blank skips
                fout.write(",".join(parts) + "\n")
        tmp.replace(MEASUREMENTS_FILE)
```

---

### 7. Summaries

Print skip totals:

```
==== SUMMARY ====
Total successes: X
Total fails: Y
Total blocked: Z
Total skipped: W
=================
```

---

✅ This way:

* Old `ccfs_measurements.csv` gets automatically patched to include `skips`.
* All new runs record and log skips consistently.
* Batches + summaries show skips.

Do you also want **skips added to `ccfs_batches.csv`** retroactively, same as measurements, or is it fine if that only applies going forward?

-------------------------------------------------------------------------------

ToDo: unhandled edge case when no annual report b/c only docs are 'Initial Report' and 'Certificate of Formation'

ToDo: unhandled adge case where skips do not reset fail counter, so exponential backoff (1hr sleep) is triggered unnecessarily

-------------------------------------------------------------------------------


-------------------------------------------------------------------------------

