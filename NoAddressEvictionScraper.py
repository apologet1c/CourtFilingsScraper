import mechanize
import pandas as pd
import re

pd.options.mode.chained_assignment = None #stop pandas from throwing errors

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

#PART 1: SETUP
#get url from user
docketurl = input("What is the docket URL? ") #example input: https://www.oscn.net/applications/oscn/report.asp?report=WebJudicialDocketJudgeCaseTypeAll&errorcheck=true&Judge=1012&database=&db=Tulsa&CaseTypeID=26&StartDate=10%2F06%2F2021&GeneralNumber=1&generalnumber1=1&GeneralCheck=on
print("Thank you, now finding links.")

#get the docket list
page = br.open(docketurl)
html = page.read().decode("utf-8")

#now generate links to every case on the docket and add to a urls list
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
count = 0

# open each docket summary URL
for i in urls:
    count = count + 1
    try:
        # open page
        page = br.open(i)
        html = page.read().decode("utf-8", errors='ignore')

        # test to see if it's an FED
        match = re.search("FORCIBLE ENTRY", html)
        testfed = bool(match)

    except:
        # we don't want it in the list if not FED or if link doesn't exist
        print("something is broken")

        # only add the FEDs to list url1
    if testfed is True:
        url1.append(i)
    else:
        print("dropped non-FED case")
        continue

    # now we get the docket number and add to a list
    docketnum = re.findall("SC-\d+-\d+", html)[0]
    docketnums.append(docketnum)
    print(docketnum)

    # now we get the case caption
    caption = re.findall("SC-\d+-\d+- [\r\n]+([^\r\n]+)", html)

    # split out plaintiff and defendant
    plaintiff = re.findall("^\t(.*)\sv.\s", caption[0])
    defendant = re.findall("\sv.\s(.*)$", caption[0])
    plaintiffs.append(plaintiff[0])
    defendants.append(defendant[0])

    #get file links, which are in the form of getimage.tif\?submitted=true&casemasterid=\d+&db=.*&barcode=\d+
    barcodelinks = re.findall("getimage\.tif\?submitted=true&amp;casemasterid=\d+&amp;db=.*&amp;barcode=\d+", html)

    #remove amp; from barcodelinks
    barcodelinks = [e.replace("amp;", "") for e in barcodelinks]

    #add https://www.oscn.net/applications/oscn/ to each link
    barcodelinks = ["https://www.oscn.net/applications/oscn/" + e for e in barcodelinks]

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
    atty = re.findall("(?<=\t\t\t\t)(.*)(?=\(Bar # \d+)", html)

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

    print(count)

print("done")

#reformats the urls into excel hyperlinks
excellinks = ["=HYPERLINK(\"" + e + "\", \"Summary\")" for e in url1]
excelpets = ["=HYPERLINK(\"" + e + "\", \"Petition\")" for e in petitions]
excelcares = ["=HYPERLINK(\"" + e + "\", \"Cares Verification\")" for e in cares]

#manually check if all match
print("Done. Found the following number of FED cases:")
print(len(docketnums))
print(len(url1))
print(len(petitions))
print(len(cares))

#PART 3: EXPORT TO EXCEL
#send to dataframes so pandas can export to csv
df = pd.DataFrame()

#set up columns and writes from variables
df["Docket Number"] = docketnums
df["Plaintiff"] = plaintiffs
df["Defendant"] = defendants
df["Docket Links"] = excellinks
df["Petition"] = excelpets
df["Document2"] = excelcares
df["Atty1"] = atty1
df["Atty2"] = atty2

df.to_csv('evictions.csv', index=False) #look in the TIFs folder
print("Done exporting to Excel. Output saved as evictions.csv in the folder where this .exe is located.")
input("Press enter to close this window.")
