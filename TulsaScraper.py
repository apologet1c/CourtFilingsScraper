import mechanize
import urllib.request
import pandas as pd
import string
import re
import time
import os
import requests
import boto3
from PIL import Image, ImageSequence

#can't remember what this does
pd.options.mode.chained_assignment = None

br = mechanize.Browser()
br.set_handle_robots(False)   # ignore robots.txt
br.set_handle_refresh(False)  # can sometimes hang without this

#get the webpage
page = br.open('https://www.oscn.net/applications/oscn/report.asp?report=WebJudicialDocketJudgeCaseTypeAll&errorcheck=true&Judge=1012&database=&db=Tulsa&CaseTypeID=26&StartDate=09%2F09%2F2021&GeneralNumber=1&generalnumber1=1&GeneralCheck=on')
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
atty1 = []
atty2 = []

#open each docket summary URL
for i in urls:
    #open page
    print(i)
    page = br.open(i)
    html = page.read().decode("utf-8", errors='ignore')
    
    #generate file links
    caseID= i.replace('https://www.oscn.net/applications/oscn/GetCaseInformation.asp?submitted=true&db=Tulsa&casemasterid=', '')
    barcodes = re.findall("barcode=\d+", html)
    
    #what if we don't find any documents?
    if len(barcodes) == 0:
        print("zero")
        petitions.append("NONE")
        cares.append("NONE")

    if len(barcodes) == 1:
        petitioncode = barcodes[0]
        carescode = "NONE"
        petitions.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + petitioncode)
        cares.append("NONE")

    if len(barcodes) >= 2:
        petitioncode = barcodes[0]
        carescode = barcodes[1]
        petitions.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + petitioncode)
        cares.append("https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=" + caseID + "&db=TULSA&" + carescode)

    #now we get the attorneys names and drop them into lists
    atty = []
    atty = re.findall("(?<=\t\t\t\t)(.*)(?=\(Bar # \d+)", html)
    try:
        atty1.append(atty[0])
    except:
        atty = ["none", "none"]
        atty1.append(atty[0])
    try:
        atty2.append(atty[1]) 
    except:
        atty = ["none", "none"]
        atty2.append(atty[1])
    
excelpets = ["=HYPERLINK(\"" + e + "\", \"Petition\")" for e in petitions]
excelcares = ["=HYPERLINK(\"" + e + "\", \"Cares Verification\")" for e in cares]

print("done!")

#pull down images and convert to pngs
os.chdir("C:/Users/AnthonySeverin/TIFs")
count = 1

for i in petitions:  
    #pulls down tif file from OSCN
    r = requests.get(i, allow_redirects=True)
    filename = str(count) + ".tif"
    newfilename = str(count) + ".png"
    open(filename, 'wb').write(r.content)
    
    #convert to png
    im = Image.open(filename)
    for i, page in enumerate(ImageSequence.Iterator(im)): #kernel crashes unless this is in a for loop for some ungodly reason
        page.save(newfilename)
        break
    #increment counter for filenames
    count = count + 1
    
print("done")

#now we call the textract wrapper and initialize address lists
client = boto3.client('textract')
address1list = []
address2list = []
count = 0

#open each image and read it
while i <= count:
    
    #clear variables and set count
    address1 = []
    address2 = []
    count = count + 1
    filename = str(count) + ".png"
    
    #open file
    try:
        with open(filename, 'rb') as document:
            img = bytearray(document.read())
    except:
        print("Found all files.")
        break

    #call textract
    response = client.detect_document_text(Document={'Bytes': img})

    #Textract returns one line at a time, so we'll join it all into a single string
    text = ""
    for item in response["Blocks"]:
        if item["BlockType"] == "LINE":
            text += "\n" + item["Text"]

    #use regex to pull out addresses on the next line
    address1 = re.findall("(?<=address is\n).*", text)
    address2 = re.findall("(?<=resides at\n).*", text)
    
    #if that fails, try looking on the same line
    if address1 == []:
        address1 = re.findall("(?<=resides at).*", text)

    if address2 == []:
        address2 = re.findall("(?<=address is).*", text)

    print(count)
    print(address1)
    print(address2)
    
    #append to addresslists
    address1list.append(address1)
    address2list.append(address2)
    
#send to dataframes so pandas can export to csv
df = pd.DataFrame()
df["Docket Number"] = dockets
df["Docket Links"] = excellinks
df["Petition"] = excelpets
df["Cares Act Affidavit"] = excelcares
df["ResAdd"] = address1list
df["MailAdd"] = address2list
df["Atty1"] = atty1
df["Atty2"] = atty2

df.to_csv('evictions.csv', index=False)
