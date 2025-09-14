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