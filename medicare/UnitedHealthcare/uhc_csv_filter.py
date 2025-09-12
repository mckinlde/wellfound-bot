import pandas as pd

# Input and output file names
# Note: relative paths are used here
input_file = "../plan_links.csv"
output_file = "../UnitedHealthcare/uhc_plan_links.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Filter only UnitedHealthcare rows
uhc_df = df[df["company"] == "UnitedHealthcare"]

# Save to new CSV
uhc_df.to_csv(output_file, index=False)

print(f"Filtered file saved as {output_file} with {len(uhc_df)} rows.")
