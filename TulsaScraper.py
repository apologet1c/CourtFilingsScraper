import mechanize
import urllib.request
import pandas as pd
from textwrap import wrap
import string
import re
import time

pd.options.mode.chained_assignment = None  # default='warn'

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this per what someone on the internet says

#get the webpage
page = br.open('https://www.oscn.net/applications/oscn/report.asp?report=WebJudicialDocketJudgeCaseTypeAll&errorcheck=true&Judge=1012&database=&db=Tulsa&CaseTypeID=26&StartDate=08%2F23%2F2021&GeneralNumber=1&generalnumber1=1&GeneralCheck=on')
html = page.read().decode("utf-8")

#now find each docket # and format it into an excel link
dockets = re.findall("SC-\d+-\d+", html)
snippets = re.findall("GetCaseInformation.asp\?submitted=true&db=Tulsa&casemasterid=\d+", html)
urls = ["https://www.oscn.net/applications/oscn/" + e for e in snippets]
excellinks = ["=HYPERLINK(\"" + e + "\", \"Summary\")" for e in urls]

#initialize all lists
addresses = []
times = []
cares = []
petitions = []
cares = []
petitions = []

for i in urls:
    #open page
    print(i)
    page = br.open(i)
    html = page.read().decode("utf-8", errors='ignore')
    
    #generate file links
    caseID= i.replace('https://www.oscn.net/applications/oscn/GetCaseInformation.asp?submitted=true&db=Tulsa&casemasterid=', '')
    barcodes = re.findall("barcode=\d+", html)
    print(barcodes)
    
    #what if we don't find any documents?
    if len(barcodes) is 0:
        print("zero")
        petitions.append("NONE")
        cares.append("NONE")

    if len(barcodes) is 1:
        petitioncode = barcodes[0]
        carescode = "NONE"
        print("one")
        petitions.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + petitioncode)
        cares.append("NONE")

    if len(barcodes) >= 2:
        petitioncode = barcodes[0]
        carescode = barcodes[1]
        petitions.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + petitioncode)
        cares.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + carescode)

    time.sleep(1)

excelpets = ["=HYPERLINK(\"" + e + "\", \"Petition\")" for e in petitions]
excelcares = ["=HYPERLINK(\"" + e + "\", \"Cares Verification\")" for e in cares]

#send to dataframe and export to csv
df = pd.DataFrame()
df["Docket Number"] = dockets
df["Docket Links"] = excellinks
df["Petition"] = excelpets
df["Cares Act Affidavit"] = excelcares

df.to_csv('evictions.csv', index=False)

print("done!")
