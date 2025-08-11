Here’s an updated `windows_runner/README.md` that captures exactly what we just did and where we’re at:

---

````markdown
### 4) One-time Windows setup (quick)

1. **Install Python 3** (check “Add to PATH”).
2. **Install Firefox** from [mozilla.org](https://www.mozilla.org/firefox/new/).
3. **Install geckodriver** using [Scoop](https://scoop.sh/) (simplifies PATH handling):

```powershell
# Install Scoop
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
Invoke-RestMethod get.scoop.sh | Invoke-Expression

# Install geckodriver via Scoop
scoop install geckodriver
````

4. **Create a venv and install deps**:

```powershell
cd <your-project-root>
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r windows_runner/requirements-windows.txt
```

5. **Set environment variables** (only needed if your code references them directly):

```powershell
$env:FIREFOX_BIN = 'C:\Program Files\Mozilla Firefox\firefox.exe'
$env:GECKODRIVER_PATH = (Get-Command geckodriver).Source
```

6. **Run it**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows_runner\windows_run_main.ps1 atlanta --send_emails
```

---

### Current status

As of 2025-08-10:

* **DB connectivity works** over Tailnet — confirmed via `Test-NetConnection` and initial scraper run.
* **Firefox + geckodriver** run locally on Windows using Scoop-installed geckodriver and system Firefox.
* The runner sets `GECKODRIVER_PATH` and `FIREFOX_BIN` if they’re not already defined, keeping parity with NixOS expectations.
* Initial scraping and email sending are working end-to-end; warnings about Postgres collation mismatch are harmless but can be fixed later with:

```sql
ALTER DATABASE "DVc4_data" REFRESH COLLATION VERSION;
```

---

### Notes / parity with your Nix setup

* The scripts preserve `AREA_SET` (positional arg 1) and `SEND_EMAILS_FLAG` (positional arg 2) semantics.
* Environment variables `GECKODRIVER_PATH` and `FIREFOX_BIN` are optional if using Selenium Manager — required only if your code explicitly checks them.
* If migrating to Chrome later, you can drop these env vars and let Selenium Manager fetch `chromedriver` automatically.
* If desired, we can later fold both runners into a single cross-platform Python launcher (`run.py`) with per-OS defaults.

```

---

Do you want me to also add a short **troubleshooting** section for WinError 10054/10061 driver drops so it’s all in one place? That would make this README fully self-contained.
```
