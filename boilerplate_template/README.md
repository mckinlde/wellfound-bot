# Boilerplate webscraping dev environment
├───utils: folder for breaking out common utils, most notably driver_session, but also stuff to abstract away emails/databases/navigation/parsing
    ├─── ...
├───csv_io: usually these scripts are run with a "do for every row in this CSV" kind of mindset
├───html_captures: save html pages from the driver for debug/parsing
├───json_captures: usually it's best to save JSON before flattening into a CSV in case columns are missing
└───logs: logs from running main.py
- main.py: the scraper.  Typical workflow will be something like:
```
- Reads UBIs from wa_corps/constants/Business Search Result.csv
- Navigates CCFS SPA
- Saves:
    - list.html
    - detail.html
    - structured JSON
into wa_corps/html_captures and wa_corps/business_json.

Adds start_n / stop_n CLI args for splitting runs in parallel.

# ToDo: separate this into a scrape.py that gets and saves html (navigation), and a parse.py that saves json/csv
# ToDo: turn 'main.py' into an 'orchestration.py' that launches scrapers and parsers dynamically & in parallel
# Note: this is left as a ToDo because it's more straightforward to start from a single main.py that just works, and then later on separate it into a scraper.py/parser.py with main.py orchestrating multiple instances.
```
- README.md: explain what you're trying to scrape, the high-level plan
- Snippets.md: useful devops snippets like activate venv / install requirements
- gitignore: you want to ignore large files, logs, basically stuff that exists after a run

Note: It's generally better to solve captchas with user input and script resuming afterwards.  Horizontal scaling probably involves multiplexing to many machines for captcha solving.