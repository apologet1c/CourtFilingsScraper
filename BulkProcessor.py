#index list of files
import os
import re
import pandas as pd

current_directory = os.getcwd()
SC_directory = current_directory + "\\Anthony"
os.chdir(SC_directory)

filelist = os.listdir()

docketnums = []
plaintiffs = []
defendants = []
url1 = []
petitions = []
cares = []
atty1 = []
atty2 = []
answers = []
transfers = []
allmoney = []
advisements = []
executionforms = []
executionreturns = []
journalentries = []
voluntarydismissals = []
courtdismissals = []
alldismissed = []

for x in filelist:
    with open(x,'r', encoding='utf-8', errors = 'ignore') as src:
        html = src.read()
        match = re.search("FORCIBLE ENTRY", html)
        testfed = bool(match)

    if testfed is True:
        url1.append(x)
        print(x)

        match = re.search("TRANSFERRED", html)
        transfers.append(bool(match))
        match = re.search("UNDER ADVISEMENT", html)
        advisements.append(bool(match))
        match = re.search("EXECUTION INSTRUCTION FORM", html, re.IGNORECASE)
        executionforms.append(bool(match))
        match = re.search("EXECUTION RETURNED", html, re.IGNORECASE)
        executionreturns.append(bool(match))
        match = re.search("JOURNAL ENTRY OF JUDGMENT", html, re.IGNORECASE)
        journalentries.append(bool(match))
        match = re.search("ANSWER", html, re.IGNORECASE)
        answers.append(bool(match))
        match = re.search("VOLUNTARY DISMISSAL", html, re.IGNORECASE)
        voluntarydismissals.append(bool(match))
        match = re.search("Dismissed by Court", html, re.IGNORECASE)
        courtdismissals.append(bool(match))
        match = re.search("DISMISSED", html, re.IGNORECASE)
        alldismissed.append(bool(match))

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
    defendant = re.findall("v.<br />[\r\n]+([^\r\n]+)(.*)(?=,)",
                           html)  # looks for the v. and then looks on the next line

    if plaintiff == []:
        plaintiff = ['.']
    if defendant == []:
        defendant = ['.']

    plaintiffs.append(plaintiff[0])
    defendants.append(defendant[0])

    # now we get the amount sued for
    money = re.findall("(?<=AMOUNT IN DEBT OF )(.*)(?= \+)", html)
    if money == []:
        money = re.findall("(?<=AMOUNT IN DEBT OF)(.*)(?= POSS)",
                           html)  # captures the weird <..$..> that some clerks use
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

#reformats the urls into excel hyperlinks
excellinks = ["=HYPERLINK(\"" + e + "\", \"Summary\")" for e in url1]
excelpets = ["=HYPERLINK(\"" + e + "\", \"Petition\")" for e in petitions]
excelcares = ["=HYPERLINK(\"" + e + "\", \"NTQ\")" for e in cares]

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
df["Rent"] = allmoney
df["Atty1"] = atty1
df["Atty2"] = atty2
df["Answer"] = answers
df["Transfer"] = transfers
df["JUA"] = advisements
df["ExecutionForms"] = executionforms
df["ExecutionReturns"] = executionreturns
df["JEs"] = journalentries
df["VoluntaryDismissal"] = voluntarydismissals
df["CourtDismissal"] = courtdismissals
df["Dismissed"] = alldismissed

df.to_csv('evictions.csv', index=False) #look in the TIFs folder
print("Done exporting to Excel. Output saved as evictions.csv in the folder where this .exe is located.")
input("Press enter to close this window.")
