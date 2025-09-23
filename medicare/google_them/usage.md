dedupe plan links 
```
python medicare/google_them/dedupe_plan_links.py `
  --input medicare/google_them/plan_links_for_google.csv `
  --output medicare/google_them/plan_links_for_google_deduped.csv
```

pdf_grabber.py
```
python medicare/google_them/pdf_grabber.py `
  --input medicare/google_them/plan_links_for_google_deduped.csv `
  --output medicare/google_them/testrun/plan_pdfs.csv `
  --outdir medicare/google_them/testrun `
  --start 1
```

after pdf_grabber.py has finished:
```
python medicare/google_them/pdf_validator.py `
  --input medicare/google_them/testrun/plan_pdfs.csv `
  --output medicare/google_them/testrun/plan_pdfs_validated.csv

```