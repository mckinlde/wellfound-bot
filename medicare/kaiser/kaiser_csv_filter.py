import pandas as pd

# Input and output file names
input_file = "medicare/plan_links.csv"
output_file = "medicare/kaiser/kaiser_plan_links.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Filter only Kaiser Permanente rows
output_df = df[df["company"] == "Kaiser Permanente"]

# Drop duplicates, keeping the first occurrence of each plan_id
output_df = output_df.drop_duplicates(subset="plan_id", keep="first")

# Save to new CSV
output_df.to_csv(output_file, index=False)

print(f"Filtered file saved as {output_file} with {len(output_df)} unique rows.")
