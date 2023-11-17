import os
import re
import csv

current_directory = os.getcwd()
directory = current_directory + "\\Appellate"
os.chdir(directory)

# Regex pattern to identify characteristics
pattern1 = re.compile(r'motion to dismiss', re.IGNORECASE)
pattern2 = re.compile(r'appealable', re.IGNORECASE)
pattern3 = re.compile(r'990A', re.IGNORECASE)
pattern4 = re.compile(r'premature', re.IGNORECASE)
pattern5 = re.compile(r'final order', re.IGNORECASE)

# File path for the output CSV
output_csv = 'cases.csv'

# Open the CSV file for writing
with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
    writer = csv.writer(csv_file)
    # Write the header row
    writer.writerow(['Case Number', 'Motion to Dismiss', 'Appealable', '990A', 'premature', 'final order'])

    # Iterate over all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith('.html'):
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                content = file.read()
                has_1 = pattern1.search(content) is not None
                has_2 = pattern2.search(content) is not None
                has_2 = pattern3.search(content) is not None
                has_3 = pattern4.search(content) is not None
                has_5 = pattern5.search(content) is not None
                
                print(filename)
                # Extract case number from the filename
                case_number = filename.split('.')[0]
                writer.writerow([case_number, has_1, has_2, has_3,  has_4, has_5])

print(f"Data exported to {output_csv}")
