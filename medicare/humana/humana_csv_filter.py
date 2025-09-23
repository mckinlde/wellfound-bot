import pandas as pd

# Input and output file names
# Note: relative paths are used here
input_file = "medicare/plan_links.csv"
output_file = "medicare/humana/humana_plan_links.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Filter only Humana rows
output_df = df[df["company"] == "Humana"]

# Save to new CSV
output_df.to_csv(output_file, index=False)

print(f"Filtered file saved as {output_file} with {len(output_df)} rows.")
