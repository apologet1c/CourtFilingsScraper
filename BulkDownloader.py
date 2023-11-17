import requests
import time
import os
import pandas as pd

current_directory = os.getcwd()
tifs_directory = current_directory + "\\Appellate"
os.chdir(tifs_directory)

# make list of prefixes
prefix = "https://www.oscn.net/dockets/GetCaseInformation.aspx?db=appellate&number="

t0 = time.time()

# what case numbers are we downloading? Get this from a CSV file and load it into a list called numbers
csv_file_path = 'dfnums.csv'  # Replace with the actual path to your CSV file
case_numbers_df = pd.read_csv(csv_file_path, header=None)  # Read the CSV file without treating the first row as a header
numbers = case_numbers_df[0].tolist()  # Convert the first column of the DataFrame to a list
end = len(numbers)

prefix = "https://www.oscn.net/dockets/GetCaseInformation.aspx?db=appellate&number="

header1 = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5' }

header2 = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.5 Safari/605.1.15', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5'}

count = 0
t0 = time.time()
with requests.Session() as session:
    
    for case_number in numbers:
        count = count + 1
        if count % 2 == 0:
            session.headers.update(header1)
        else:
            session.headers.update(header2)
            
        response = session.get(prefix + case_number)
        print(len(response.content))
        
        if len(response.content) < 3000:
            print("Captcha Detected. Please open browser, open a docket sheet on OSCN and do a captcha.")
            input("Press Enter after completing the captcha.")
            response = session.get(prefix + case_number)

        print(prefix + case_number)
        filename = str(case_number) + ".html"
        print(filename)
        
        with open(filename, "wb") as file:
            file.write(response.content)

t1 = time.time()
total = t1-t0
print(total)
