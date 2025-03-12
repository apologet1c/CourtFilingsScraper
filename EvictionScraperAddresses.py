import csv
import mechanize
import re
import os

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

# Set a custom User-Agent header
br.addheaders = [("User-Agent", "6946809d-1344-4e45-9167-f6dfac85305f")]

#PART 1: SETUP
def get_docket_content(docket_url):
    try:
        page = br.open(docket_url)
        html = page.read().decode("ISO-8859-1")
        #now generate links to every case on the docket and add to a urls list
        snippets = re.findall("GetCaseInformation.asp\?submitted=true&db=Tulsa&casemasterid=\d+", html)
        urls = ["https://www.oscn.net/applications/oscn/" + e for e in snippets]
        return urls
    except Exception as e:
        input(f"Error opening URL {docket_url}: {e}; press enter to end.")
        return None

def get_case_content(url):
    try:
        # open page
        page = br.open(url)
        html = page.read().decode("utf-8", errors='ignore')
        match = re.search("captcha", html) # check for captcha
        testcaptcha = bool(match)
        
        if testcaptcha is True: #pauses the script and tries again after user input
            input("Captcha Detected. Please open browser, open a case on OSCN and do the captcha, then press enter to try again")
            page = br.open(url)
            html = page.read().decode("utf-8", errors='ignore')
        return html
    
    except Exception as e:
        input(f"Something is wrong: check your internet connection: {e}")
        return None
    
import re

def FED_processor(html):
    try:
        docketnum = re.findall("..-20\d+-\d+", html)
        docketnum = docketnum[0]

        plaintiff = re.findall("(?<=td valign=\"center\" width=\"50%\">)(.*)(?=,)", html)
        defendant = re.findall("v.<br />[\r\n]+([^\r\n]+)(.*)(?=,)", html)

        plaintiff = plaintiff[0] if plaintiff else '.'
        defendant = defendant[0] if defendant else '.'

        money = re.findall("(?<=AMOUNT IN DEBT OF )(.*)(?= \+)", html)
        if not money:
            money = re.findall("(?<=AMOUNT IN DEBT OF)(.*)(?= POSS)", html)
        money = money[0] if money else '.'

        # Clean the money string
        money = re.sub(r'[^\d.]+', '', money)
        money = re.sub(r'^\.*', '', money)

        barcodelinks = re.findall("(&bc=\d+&fmt=tif)", html)
        barcodelinks = [e.replace("amp;", "") for e in barcodelinks]
        barcodelinks = ["https://www.oscn.net/dockets/GetDocument.aspx?ct=tulsa" + e for e in barcodelinks]

        atty = re.findall("(?<=\<td valign=\"top\" width=\"50%\"\>)(.*)(?=,&nbsp;)", html)

        return docketnum, plaintiff, defendant, money, barcodelinks, atty

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None, None, None, None

#PART 2: Execute, scrape basic info   
#initialize lists
docketnums = []
plaintiffs = []
defendants = []
petitions = []
cares = []
atty1 = []
atty2 = []
atty3 = []
allmoney = []
allhtml = [] 
url1 = []

#Ask user what they want to scrape
print("IMPORTANT MESSAGE: check that (1) the TIFs folder is empty and (2) the .exe is in the same folder as the TIFs folder (but not in the TIFs folder).")
todaysdate = input("What is date of the docket you would like to scrape?")
print("Thank you, now finding links.")

docket_url = "https://www.oscn.net/applications/oscn/report.asp?report=WebJudicialDocketJudgeAll&errorcheck=true&db=Tulsa&Judge=1058&database=&StartDate=" + todaysdate + "&GeneralNumber=1&generalnumber1=1&GeneralCheck=on"

urls = get_docket_content(docket_url)

#classify cases
for i in urls:
    print(i)
    try:
        html = get_case_content(i)
        # test to see if it's an FED
        match = re.search("FORCIBLE ENTRY", html)
        testfed = bool(match)
        if testfed is True:
            url1.append(i)
        else:
            print("dropped non-FED case")
            continue
        allhtml.append(html)
    except Exception as e:
        input(f"Error opening URL {docket_url}: {e}; press enter to end.")
        continue

#get additional info on FED cases
for i in allhtml:
    docketnum, plaintiff, defendant, money, barcodelinks, atty = FED_processor(i)
    print(docketnum)
    try:
        docketnums.append(docketnum)
        plaintiffs.append(plaintiff)
        defendants.append(defendant[0])
        allmoney.append(money)

        # what if we don't find any documents?
        if len(barcodelinks) == 0:
            print("zero")
            petitions.append("NONE")
            cares.append("NONE")

        # what if we find one document?
        if len(barcodelinks) == 1:
            petitions.append(barcodelinks[0])
            cares.append("NONE")

        # what if we find 2+ documents?
        if len(barcodelinks) >= 2:
            petitions.append(barcodelinks[0])
            cares.append(barcodelinks[1])

        try:
            atty1.append(atty[0])
        except:
            atty1.append(" ")

        # tries to append a second name
        try:
            atty2.append(atty[1])
        except:
            atty2.append(" ")
        try:
            atty3.append(atty[2])
        except:
            atty3.append(" ")
    except Exception as e: 
        print(f"cannot process" + docketnum + {e})

# reformats the urls into excel hyperlinks
excellinks = ["=HYPERLINK(\"" + e + "\", \"Summary\")" for e in url1]
excelpets = ["=HYPERLINK(\"" + e + "\", \"Petition\")" for e in petitions]
excelcares = ["=HYPERLINK(\"" + e + "\", \"NTQ\")" for e in cares]

#manually check if all match
print("Done. Found the following number of FED cases:")
print("Length of docketnums:", len(docketnums))
print("Length of plaintiffs:", len(plaintiffs))
print("Length of defendants:", len(defendants))
print("Length of petitions:", len(petitions))
print("Length of cares:", len(cares))
print("Length of atty1:", len(atty1))
print("Length of atty2:", len(atty2))
print("Length of atty3:", len(atty3))
print("Length of allmoney:", len(allmoney))

output_csv = 'noaddresses.csv'

#export initial list in case addresses fail
with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
    writer = csv.writer(csv_file)
    # Write the header row
    writer.writerow(['Case Number', 'Plaintiff', 'Defendant', 'Docket Links', 'Petition', 'Document2', 'Rent', 'Atty1', 'Atty2', 'Atty3'])
    for i in range(len(docketnums)):
         writer.writerow([docketnums[i], plaintiffs[i], defendants[i], excellinks[i], excelpets[i], excelcares[i], allmoney[i], atty1[i], atty2[i], atty3[i]])
print(f"Data exported to {output_csv}")

#PART 3: Download petitions
import requests
from PIL import Image, ImageSequence
current_directory = os.getcwd()
tifs_directory = current_directory + "\\TIFs"
os.chdir(tifs_directory)

count = 1

headers = {'User-Agent' : '6946809d-1344-4e45-9167-f6dfac85305f'}

for i in petitions:
    # pulls down tif files from OSCN
    filename = str(count) + ".tif"
    newfilename = str(count) + ".png"

    try:
        r = requests.get(i, allow_redirects=True, headers=headers) # , verify=False to ignore SSL certificates if necessary
        open(filename, 'wb').write(r.content)

        # check if we've been captcha'd
        if os.path.getsize(filename) < 3000:
            print(os.path.getsize(filename))
            input("Captcha Detected. Please open browser, open a docket sheet on OSCN and do a captcha.")
            os.remove(filename)
            print("removed!")

            # try again
            r = requests.get(i, allow_redirects=True, headers=headers)  # , verify=False to ignore SSL certificates if necessary
            open(filename, 'wb').write(r.content)

        im = Image.open(filename)
        for i, page in enumerate(
                ImageSequence.Iterator(im)):  # kernel crashes unless it's done this way for some ungodly reason
            page.save(newfilename)
            break
        print("Downloaded " + str(count))
              
    except Exception as e:
        print("Error:", e)
        print(count)
        Image.new('RGB', (100, 100), color = 'white').save(newfilename)
    
    count = count + 1
    continue

#PART 4: OCR petitions
import boto3
from threading import Thread, Lock
import collections

filenames = []
ocr_results = collections.OrderedDict()
lock = Lock()
client = boto3.client('textract')
address1list = []
address2list = []
alltext = []
address1 = []
address2 = []
threads = []

def process_ocr(filename):
    try:
        with open(filename, 'rb') as document:
            print(filename)
            img = bytearray(document.read())

    except:
            print("Found all files.")

    # call textract
    response = client.detect_document_text(Document={'Bytes': img})

    # Textract returns one line at a time, so we'll join it all into a single string
    text = ""
    for item in response["Blocks"]:
        if item["BlockType"] == "LINE":
            text += "\n" + item["Text"]

    alltext.append(text)

    # use regex to pull out addresses on the next line
    address1 = re.findall("(?<=address is\n).*", text)
    address2 = re.findall("(?<=resides at\n).*", text)
    
    # if that fails, try looking on the same line
    if address1 == []:
        address1 = re.findall("(?<=address is).*", text)
    # if that fails, is this in Oklahoma county?
    if address1 == []:
        address1 = re.findall("(?<=as follows:\n).*\n.*", text)
    # if that fails, all is lost
    if address1 == []:
        address1 = ['.']

    if address2 == []:
        address2 = re.findall("(?<=resides at).*", text)
    if address2 == []:
        address2 = ['.']
    
    address1 = address1[0].strip() if address1 else ''
    address2 = address2[0].strip() if address2 else ''
    
    print(filename)
    return (filename, address1, address2)

def thread_function(filename):
    result = process_ocr(filename)
    with lock:
        ocr_results[result[0]] = (result[1], result[2])

for x in os.listdir():
    if x.endswith(".png"):
        filenames.append(x)

filenames = sorted({f for f in os.listdir() if f.endswith('.png')}, key=lambda x: int(x.split('.')[0])) #deduplicating list
        
from concurrent.futures import ThreadPoolExecutor

# Use a thread pool with a fixed number of workers
with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(thread_function, filenames)

# Sort the results based on an index which is the filename minus the extension
sorted_ocr_results = collections.OrderedDict(sorted(ocr_results.items(), key=lambda x: int(x[0].split('.')[0])))

address1list = [result[0] for result in sorted_ocr_results.values()]
address2list = [result[1] for result in sorted_ocr_results.values()]

output_csv = 'evictionswithaddresses.csv'

#PART 5: Export final list
with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
    writer = csv.writer(csv_file)
    # Write the header row
    writer.writerow(['Case Number', 'Plaintiff', 'Defendant', 'Docket Links', 'Petition', 'Document2', 'Rent', 'ResidesAt', 'Mailing', 'Atty1', 'Atty2', 'Atty3', 'AllText'])
    for i in range(len(docketnums)):
         writer.writerow([docketnums[i], plaintiffs[i], defendants[i], excellinks[i], excelpets[i], excelcares[i], allmoney[i], address1list[i], address2list[i], atty1[i], atty2[i], atty3[i], alltext[i]])
print(f"Data exported to {output_csv}")
