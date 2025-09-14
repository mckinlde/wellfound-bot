import pandas as pd

# Input and output file names
input_file = "medicare/plan_links.csv"
output_file = "medicare/BlueCrossBlueShield/bcbs_plan_ids.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Filter rows where "company" contains "Blue Cross"
output_df = df[df["company"].str.contains("Blue Cross", case=False, na=False)]

# Keep only the plan_id column
output_df = output_df[["plan_id"]]

# Save to new CSV
output_df.to_csv(output_file, index=False)

print(f"Filtered file saved as {output_file} with {len(output_df)} rows.")
