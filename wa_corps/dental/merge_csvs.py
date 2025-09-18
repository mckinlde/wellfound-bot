import pandas as pd

# List your CSV files here
files = [
    "wa_corps\dental\Business Search Result (1).csv",
    "wa_corps\dental\Business Search Result (2).csv",
    "wa_corps\dental\Business Search Result.csv"
]

# Read and concatenate
dfs = [pd.read_csv(f) for f in files]
merged = pd.concat(dfs, ignore_index=True)

# Drop duplicates (based on all columns)
merged = merged.drop_duplicates()

# Save the merged CSV
merged.to_csv("merged_deduped.csv", index=False)

print(f"Merged {len(files)} files into merged_deduped.csv")
