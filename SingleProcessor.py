import os
import re
import pandas as pd
import shutil

current_directory = os.getcwd()
SC_directory = current_directory + "\\SC-21"
os.chdir(SC_directory)

filelist = os.listdir()

url1 = []
docketnums = []
expunge = []

for x in filelist:
    with open(x,'r', encoding='utf-8', errors = 'ignore') as src:
        html = src.read()

        match = re.search("vacate", html, re.IGNORECASE)
        expunge.append(bool(match))

        # now we get the docket number and add to a list
    docketnum = re.findall("..-20\d+-\d+", html)

    docketnums.append(docketnum[0])
    print(docketnum[0])

#PART 3: EXPORT TO EXCEL
#send to dataframes so pandas can export to csv
df = pd.DataFrame()

#set up columns and writes from variables
df["Docket Number"] = docketnums
df["Garnishment"] = expunge


df.to_csv('evictions.csv', index=False) #look in the TIFs folder
print("Done exporting to Excel. Output saved as evictions.csv in the folder where this .exe is located.")
input("Press enter to close this window.")
