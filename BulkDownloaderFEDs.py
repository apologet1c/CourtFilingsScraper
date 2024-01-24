import requests
import time
import os
import pandas as pd

current_directory = os.getcwd()
tifs_directory = current_directory + "\\SC-23"
os.chdir(tifs_directory)

header1 = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5' }
header2 = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.5 Safari/605.1.15', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5'}

# what case numbers are we downloading?
start = 1
end = 17495

#make list of prefixes
prefixlist = ["https://www.oscn.net/dockets/GetCaseInformation.aspx?db=tulsa&number=SC-23-"] * end

# make list of numbers from 1 to 10000
numbers = [str(x) for x in range(start, end)]

# concatenate to make URLs
urls = [i + j for i, j in zip(prefixlist, numbers)]
count = start

with requests.Session() as session:
    
    for i in urls:

        if count % 2 == 0:
            session.headers.update(header1) #switches user agents ever other time
        else:
            session.headers.update(header2)
            
        response = session.get(i)
      
        #captcha handling
        if len(response.content) < 3000:
            print("Captcha Detected. Please open browser, open a docket sheet on OSCN and do a captcha.")
            input("Press Enter after completing the captcha.")
            response = session.get(i)

        filename = str(count) + ".html"
        print(filename)
        
        with open(filename, "wb") as file:
            file.write(response.content)

        count = count + 1

t1 = time.time()
total = t1-t0
print(total)
