import mechanize
import time
import os

current_directory = os.getcwd()
tifs_directory = current_directory + "\\Anthony"
os.chdir(tifs_directory)

br = mechanize.Browser()
br.set_handle_robots(False)  # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

# make list of prefixes
prefixlist = ["https://www.oscn.net/dockets/GetCaseInformation.aspx?db=tulsa&number="] * 2 #EDIT NUMBER HERE

items = ["SC-2009-21866", #insert lists here
        "SC-2021-21862"]


# concatenate to make URLs
urls = [i + j for i, j in zip(prefixlist, items)]

t0 = time.time()
count = 0

for i in urls:
    page = br.open(i)
    html = page.read().decode("utf-8", errors='ignore')

    filename = items[count] + ".html"
    print(filename)

    with open(filename, "w") as text_file:
        print(html, file=text_file)

        count = count + 1


t1 = time.time()
total = t1 - t0
print(total)
