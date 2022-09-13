import mechanize
import pandas as pd
import re
import os
import requests
import boto3
from PIL import Image, ImageSequence
import ssl

ssl._create_default_https_context = ssl._create_unverified_context # because SSL certificates broke on 8/29 for some reason
pd.options.mode.chained_assignment = None # stop pandas from throwing errors

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

# PART 1: SETUP
# get url from user
docketurl = input("What is the docket URL? ") # example input: https://www.oscn.net/applications/oscn/report.asp?report=WebJudicialDocketJudgeAll&errorcheck=true&Judge=1058&database=&db=Tulsa&StartDate=9%2F13%2F22&GeneralNumber=1&generalnumber1=1&GeneralCheck=on
print("Thank you, now finding links.")

# get the docket list
page = br.open(docketurl)
html = page.read().decode("utf-8")

# now generate links to every case on the docket and add to a urls list
snippets = re.findall("GetCaseInformation.asp\?submitted=true&db=.*&casemasterid=\d+", html)
urls = ["https://www.oscn.net/applications/oscn/" + e for e in snippets]

# PART 2: SCRAPING LINKS
# initialize all lists
docketnums = []
plaintiffs = []
defendants = []
url1 = []
petitions = []
cares = []
atty1 = []
atty2 = []
allmoney = []
count = 0

# open each docket summary URL
for i in urls:

    count = count + 1
    try:
        # open page
        page = br.open(i)
        html = page.read().decode("utf-8", errors='ignore')

        match = re.search("captcha", html)
        testcaptcha = bool(match)

    except:
        # we don't want it in the list if not FED or if link doesn't exist
        print("Something is wrong: check your internet connection?")

        # only add the FEDs to list url1
    if testcaptcha is True:
        input("Captcha Detected. Please open browser, open a docket sheet on OSCN and do a captcha.")

        # try again
        try:
            page = br.open(i)
            html = page.read().decode("utf-8", errors='ignore')
        except:
            print("Something is wrong: check your internet connection?")

    # test to see if it's an FED
    match = re.search("FORCIBLE ENTRY", html)
    testfed = bool(match)

    if testfed is True:
        url1.append(i)
    else:
        print("dropped non-FED case")
        continue

        # now we get the docket number and add to a list
    docketnum = re.findall("..-20\d+-\d+", html)

    if docketnum == []:
        docketnum = ['captcha']

    docketnums.append(docketnum[0])
    print(docketnum[0])

    # split out plaintiff and defendant
    plaintiff = re.findall("(?<=td valign=\"center\" width=\"50%\">)(.*)(?=,)", html)
    defendant = re.findall("v.<br />[\r\n]+([^\r\n]+)(.*)(?=,)", html)  # looks for the v. and then looks on the next line

    if plaintiff == []:
        plaintiff = ['.']
    if defendant == []:
        defendant = ['.']

    plaintiffs.append(plaintiff[0])
    defendants.append(defendant[0])

    # now we get the amount sued for
    money = re.findall("(?<=AMOUNT IN DEBT OF )(.*)(?= \+)", html)
    if money == []:
        money = re.findall("(?<=AMOUNT IN DEBT OF)(.*)(?= POSS)", html)  # captures the weird <..$..> that some clerks use
    if money == []:
        money = ['.']  # if nothing is found at all

    allmoney.append(money[0])

    # get barcodes that link to the specific files.
    barcodelinks = re.findall("(&bc=\d+&fmt=tif)", html)

    # remove amp; from barcodelinks
    barcodelinks = [e.replace("amp;", "") for e in barcodelinks]

    # append the barcode to the end of every link
    barcodelinks = ["https://www.oscn.net/dockets/GetDocument.aspx?ct=tulsa" + e for e in barcodelinks]

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

    # now we get the attorneys who have registered appearances and drop the names into lists
    atty = []
    atty = re.findall("(?<=\<td valign=\"top\" width=\"50%\"\>)(.*)(?=,&nbsp;)", html)

    # (?<=<td valign=\"top\" width=\"50%\">) #(?!Bar #\d+)
    # tries to append first name
    try:
        atty1.append(atty[0])
    except:
        atty = [" ", " "]
        atty1.append(atty[0])

    # tries to append a second name
    try:
        atty2.append(atty[1])
    except:
        atty = [" ", " "]
        atty2.append(atty[1])

print("Done with dockets.")

# reformats the urls into excel hyperlinks
excellinks = ["=HYPERLINK(\"" + e + "\", \"Summary\")" for e in url1]
excelpets = ["=HYPERLINK(\"" + e + "\", \"Petition\")" for e in petitions]
excelcares = ["=HYPERLINK(\"" + e + "\", \"NTQ\")" for e in cares]

#manually check if all match
print("Done. Found the following number of FED cases:")
print(len(docketnums))
print(len(url1))
print(len(petitions))
print(len(cares))

# PART 3: DOWNLOAD IMAGE FILES OF THE PETITIONS
# set download folder
current_directory = os.getcwd()
tifs_directory = current_directory + "\\TIFs"
os.chdir(tifs_directory)

count = 1

headers = {
    'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.oscn.net/dockets/GetDocument.aspx?ct=Tulsa&cn=SC-2022-9715&bc=1053032515&fmt=tif',
    'Host': 'www.oscn.net',
    'Connection': 'keep-alive',
    'Cookie': 'ASPSESSIONIDCSRTDDQS=JLNIBGMCELHAAOIFEGEFAGHP; ASPSESSIONIDCCCBTRAB=GBLNIHABNLANKIKIDKCIINGE; ASPSESSIONIDSSCDSRRD=EGJKLHBAEMFGGMGINCMKLFGO; ASPSESSIONIDAACAASDA=NHNOFNGDPANMGADOGLIPAKNB; ASPSESSIONIDSQDCSTRD=LKPKKKODKMKOIOCMMPMHGMIE; ASPSESSIONIDAQRRCCTS=JAOECIODPICOODLLJCCBJIEG',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1'
}

for i in petitions:
    # pulls down tif files from OSCN
    try:
        r = requests.get(i, allow_redirects=True, headers=headers) # , verify=False to ignore SSL certificates if necessary
        filename = str(count) + ".tif"
        newfilename = str(count) + ".png"
        open(filename, 'wb').write(r.content)

        # check if we've been captcha'd
        if os.path.getsize(filename) < 3000:
            print(os.path.getsize(filename))
            input("Captcha Detected. Please open browser, open a docket sheet on OSCN and do a captcha.")
            os.remove(filename)
            print("removed!")

            #try again
            r = requests.get(i, allow_redirects=True, headers=headers)  # , verify=False to ignore SSL certificates if necessary
            filename = str(count) + ".tif"
            newfilename = str(count) + ".png"
            open(filename, 'wb').write(r.content)

    except:
        print("MISSING " + str(count))
        count = count + 1
        continue

    # convert from tif to png
    try:
        im = Image.open(filename)
        for i, page in enumerate(
                ImageSequence.Iterator(im)):  # kernel crashes unless it's done this way for some ungodly reason
            page.save(newfilename)
            break
    except:
        print("MISSING " + str(count))
        count = count + 1
        continue
    # increment counter for filenames
    count = count + 1
    print(count)
print("Done downloading files. Now running OCR.")

# PART 4: OCR PETITION AND RECOGNIZE ADDRESSES
# now we call the textract wrapper and initialize address lists
client = boto3.client('textract')
address1list = []
address2list = []
alltext = []
count = 0

# open each image and read it
while i <= count:

    # clear variables and set count
    address1 = []
    address2 = []
    count = count + 1
    filename = str(count) + ".png"

    # open file
    try:
        with open(filename, 'rb') as document:
            img = bytearray(document.read())

    except:
        # what if there isn't something uploaded? can't just end, gotta check the next one too.
        try:
            print("MISSING " + str(count))
            count = count + 1
            filename = str(count) + ".png"
            with open(filename, 'rb') as document:
                img = bytearray(document.read())
        except:  # if it fails twice--i.e. if there are two missing files in a row
            print("Found all files.")
            break

        # if there's just one missing file
        address1 = "No petition on OSCN."
        address2 = "No petition on OSCN."

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

    # append addresses to addresslists
    address1list.append(address1[0])
    address2list.append(address2[0])

    print(count)

print("Done running OCR. Now exporting to Excel.")

#PART 5: EXPORT TO EXCEL
#send to dataframes so pandas can export to csv
df = pd.DataFrame()

#set up columns and writes from variables
try:
    df["Docket Number"] = docketnums
    df["Plaintiff"] = plaintiffs
    df["Defendant"] = defendants
    df["Docket Links"] = excellinks
    df["Petition"] = excelpets
    df["Document2"] = excelcares
    df["ResAdd"] = address1list
    df["MailAdd"] = address2list
    df["Rent"] = allmoney
    df["Atty1"] = atty1
    df["Atty2"] = atty2
    df["Text"] = alltext

except:
    print("Excel export failed, trying without addresses.")
    df["Docket Number"] = docketnums
    df["Plaintiff"] = plaintiffs
    df["Defendant"] = defendants
    df["Docket Links"] = excellinks
    df["Petition"] = excelpets
    df["Document2"] = excelcares
    #df["ResAdd"] = address1list
    #df["MailAdd"] = address2list
    df["Rent"] = allmoney
    df["Atty1"] = atty1
    df["Atty2"] = atty2

df.to_csv('evictions.csv', index=False) #look in the TIFs folder
print("Done exporting to Excel. Output saved as evictions.csv in the folder where this .exe is located.")
input("Press enter to close this window.")
