import mechanize
import pandas as pd
import re
import os
import requests
import boto3
from PIL import Image, ImageSequence

pd.options.mode.chained_assignment = None #stop pandas from throwing errors

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

#PART 1: SETUP
#get url from user
blank123 = input("Before we begin, have you checked that (1) the TIFs folder is empty and (2) the .exe is in the same folder as the TIFs folder (but not in the TIFs folder)? (y/n)")
docketurl = input("What is the docket URL? ") #example input: https://www.oscn.net/applications/oscn/report.asp?report=WebJudicialDocketJudgeCaseTypeAll&errorcheck=true&Judge=1012&database=&db=Tulsa&CaseTypeID=26&StartDate=10%2F06%2F2021&GeneralNumber=1&generalnumber1=1&GeneralCheck=on
print("Thank you, now finding links.")

#get the docket list
page = br.open(docketurl)
html = page.read().decode("utf-8")

#now generate links to every case on the docket and add to a urls list
snippets = re.findall("GetCaseInformation.asp\?submitted=true&db=Tulsa&casemasterid=\d+", html)
urls = ["https://www.oscn.net/applications/oscn/" + e for e in snippets]

#PART 2: SCRAPING LINKS
#initialize all lists
docketnums = []
captions = []
url1 = []
petitions = []
cares = []
atty1 = []
atty2 = []

#open each docket summary URL
for i in urls:
    
    try:
        #open page
        page = br.open(i)
        html = page.read().decode("utf-8", errors='ignore')
        
        #test to see if it's an FED
        match = re.search("FORCIBLE ENTRY", html)
        testfed = bool(match)

    except:
        #we don't want it in the list if not FED or if link doesn't exist
        print("dropped non-FED case") 
    
    #only add the FEDs to list url1
    if testfed is True:
        url1.append(i)
    else:
        print("dropped non-FED case")
        continue
    
    #now we get the docket number and add to a list
    docketnum = re.findall("SC-\d+-\d+", html)[0]
    docketnums.append(docketnum)
    
    #now we get the case caption
    caption = ""
    caption = re.findall("SC-\d+-\d+- [\r\n]+([^\r\n]+)", html)
    captions.append(caption[0])
    
    #generate file links
    caseID = i.replace('https://www.oscn.net/applications/oscn/GetCaseInformation.asp?submitted=true&db=Tulsa&casemasterid=', '')
    barcodes = re.findall("barcode=\d+", html)
    
    #what if we don't find any documents?
    if len(barcodes) == 0:
        print("zero")
        petitions.append("NONE")
        cares.append("NONE")

    #what if we find one document?
    if len(barcodes) == 1:
        petitioncode = barcodes[0]
        carescode = "NONE"
        petitions.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + petitioncode)
        cares.append("NONE")

    #what if we find 2+ documents?
    if len(barcodes) >= 2:
        petitioncode = barcodes[0]
        carescode = barcodes[1]
        petitions.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + petitioncode)
        cares.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + carescode)

    #now we get the attorneys who have registered appearances and drop the names into lists
    atty = []
    atty = re.findall("(?<=\t\t\t\t)(.*)(?=\(Bar # \d+)", html)
    
    #tries to append first name
    try:
        atty1.append(atty[0])
    except:
        atty = [" ", " "]
        atty1.append(atty[0])
    
    #tries to append a second name
    try:
        atty2.append(atty[1]) 
    except:
        atty = [" ", " "]
        atty2.append(atty[1])

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
print("Now downloading files.")

#PART 3: DOWNLOAD IMAGE FILES OF THE PETITIONS
#set download folder
current_directory = os.getcwd()
tifs_directory = current_directory + "\\TIFs"
os.chdir(tifs_directory)

count = 1

for i in petitions:  
    #pulls down tif files from OSCN
    try:
        r = requests.get(i, allow_redirects=True)
        filename = str(count) + ".tif"
        newfilename = str(count) + ".png"
        open(filename, 'wb').write(r.content)
    except:
        print("MISSING " + count)
        count = count + 1
        continue
    #convert from tif to pdf
    im = Image.open(filename)
    for i, page in enumerate(ImageSequence.Iterator(im)): #kernel crashes unless it's done this way for some ungodly reason
        page.save(newfilename)
        break
    #increment counter for filenames
    count = count + 1
    print(count)
print("Done downloading files. Now exporting to excel.")

#PART 4: EXPORT TO EXCEL
#send to dataframes so pandas can export to csv
df = pd.DataFrame()

#set up columns and writes from variables
df["Docket Number"] = docketnums
df["Captions"] = captions
df["Docket Links"] = excellinks
df["Petition"] = excelpets
df["Cares Act Affidavit"] = excelcares
df["Atty1"] = atty1
df["Atty2"] = atty2

df.to_csv('evictions.csv', index=False) #look in the TIFs folder
print("Done exporting to Excel. Output saved as evictions.csv in the TIFs folder.")
input("Press enter to close this window.")