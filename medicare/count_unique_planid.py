import pandas as pd
import pprint
from collections import OrderedDict

# Input file name
input_file = "plan_links.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Group by company and count unique plan_id
unique_counts = df.groupby("company")["plan_id"].nunique().to_dict()
total_unique_count = df["plan_id"].nunique()
print("Total unique plan_id count:", total_unique_count)
total_unique_count = df["plan_name"].nunique()
print("Total unique plan_name count:", total_unique_count)


# Sort by count descending
sorted_items = sorted(unique_counts.items(), key=lambda item: item[1], reverse=True)

# Print as list of tuples
pprint.pprint(sorted_items)

# Have to override the default dict sorting to keep it in order for human reading
sorted_dict = OrderedDict(sorted_items)
pprint.pprint(sorted_dict)

# Sites for specific companies
# UnitedHealthcare,  www.uhc.com
# Aetna, www.aetna.com
# Humana, not reliable
# HCSC, www.cigna.com
# Devoted Health, www.devoted.com
# Wellcare, not reliable
# Kaiser Permanente, healthy.kaiserpermanente.org