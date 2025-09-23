# No; I'd like to write another script dedupe_plan_links.py that will make sure we don't have duplicate plan name and plan ids.  By which I mean if two rows have the same plan name and plan id, then the other rows don't matter, that's the same plan and should only be included once4

#!/usr/bin/env python3
"""
Deduplicate plan_links.csv by (plan_id, plan_name).

Keeps the first occurrence of each unique (plan_id, plan_name).
"""

import pandas as pd
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input CSV file (e.g., plan_links.csv)")
    ap.add_argument("--output", required=True, help="Output CSV file (deduped)")
    args = ap.parse_args()

    # Load CSV
    df = pd.read_csv(args.input)

    # Drop duplicate rows based on both plan_id and plan_name
    before = len(df)
    df_deduped = df.drop_duplicates(subset=["plan_id", "plan_name"])
    after = len(df_deduped)

    # Save result
    df_deduped.to_csv(args.output, index=False)

    print(f"[DONE] Deduped {args.input}: {before} → {after} rows saved in {args.output}")

if __name__ == "__main__":
    main()

