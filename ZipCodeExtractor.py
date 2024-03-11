import pandas as pd

# Load the Excel file
file_path = 'Checklist - 06 -23 - asdf.xlsx'
all_sheets_df = pd.read_excel(file_path, sheet_name=None)  # This loads all sheets

# Initialize a dictionary to hold zip code counts
zip_code_counts = {}

# Process each sheet
for sheet_name, df in all_sheets_df.items():
    try:
        df['ResidentialAddress'] = df['ResidentialAddress'].astype(str)
        df['ZipCode'] = df['ResidentialAddress'].str.extract('(740\d{2}|741\d{2})')[0]
        # Drop rows where ZipCode is NaN (i.e., no match was found)
        df.dropna(subset=['ZipCode'], inplace=True)
    except:
        continue
    
    # Update counts
    for zip_code in df['ZipCode']:
        if zip_code in zip_code_counts:
            zip_code_counts[zip_code] += 1
        else:
            zip_code_counts[zip_code] = 1

# Convert the counts to a DataFrame for easier handling/viewing
zip_code_counts_df = pd.DataFrame(list(zip_code_counts.items()), columns=['ZipCode', 'Count'])

# Optionally, save the result to a new Excel file
zip_code_counts_df.to_excel('zip_code_counts.xlsx', index=False)

print(zip_code_counts_df)
