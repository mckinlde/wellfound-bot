High-level plan

Input: wa_corps/constants/Business Search Result.csv (with UBI column).

Output:

For each UBI:

Save search list.html into wa_corps/html_captures/{UBI}/list.html

Save detail detail.html into wa_corps/html_captures/{UBI}/detail.html

Save parsed JSON into wa_corps/business_json/{UBI}.json

No CSV flattening for now — we’ll just collect JSONs.

Progress bar: print [INFO] Processing UBI {i}/{total}: {ubi}.

Driver stability: keep the Firefox window open, explicit waits, no unnecessary quit/relaunch.

-------------------------------------------------------------------------------

Do you want me to also add a secondary parser script (takes the saved detail.html files → regenerates JSON) so you can rerun parsing offline without hitting CCFS again? That’s useful if you ever discover new fields and want to re-extract.

Not yet.  For now I'm more interested in adding a start_n and stop_n so I can run multiple instances of this in parallel.  I think next I'll want a secondary parser script that takes the saved list.html files and checks if there are multiple detail.html files, but I don't want to do that just yet either.  Focus on a complete and correct ccfs_lookup.py

-------------------------------------------------------------------------------

How you’d run parallel jobs

Say you have 10,000 UBIs:

```bash
# First 1,000
python ccfs_lookup.py --start_n 1 --stop_n 1000

# Next 1,000
python ccfs_lookup.py --start_n 1001 --stop_n 2000
```

Each job will only touch its slice of UBIs and create separate JSON + HTML files.
