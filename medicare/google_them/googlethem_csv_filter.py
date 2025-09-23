import pandas as pd

# Input and output file names
input_file = "medicare/plan_links.csv"
output_file = "medicare/google_them/plan_links_for_google.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Filter out rows where "company" is one of these
exclude = ["Humana", "UnitedHealthcare", "Aetna Medicare"]
output_df = df[~df["company"].isin(exclude)]

# Save to new CSV
output_df.to_csv(output_file, index=False)

print(f"Filtered file saved as {output_file} with {len(output_df)} rows.")
