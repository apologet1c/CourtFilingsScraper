import mechanize
import time
import os

current_directory = os.getcwd()
tifs_directory = current_directory + "\\SC-21"
os.chdir(tifs_directory)

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

# what case numbers are we downloading?
start = 1
end = 13001

# make list of prefixes
prefixlist = ["https://www.oscn.net/dockets/GetCaseInformation.aspx?db=tulsa&number=SC-21-"] * end

# make list of numbers from 1 to 10000
numbers = [str(x) for x in range(start, end)]

# concatenate to make URLs
urls = [i + j for i, j in zip(prefixlist, numbers)]

t0 = time.time()

for i in urls:
  
    page = br.open(i)
    html = page.read().decode("utf-8", errors='ignore')
    
    filename = str(start) + ".html"
    print(filename)
    
    with open(filename, "w") as text_file:
        print(html, file=text_file)
        
    start = start + 1

t1 = time.time()
total = t1-t0
print(total)
