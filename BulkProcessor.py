import os
import re
import csv

current_directory = os.getcwd()
directory = current_directory + "\\Small Claims\SC-23"
os.chdir(directory)

# File path for the output CSV
output_csv = 'cases.csv'

def FED_processor(html):
    try:
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
        
        # what if we don't find any documents?
        if len(barcodelinks) == 0:
            print("No Petition Uploaded")
            petition = "NONE"
            cares = "NONE"

        # what if we find one document?
        if len(barcodelinks) == 1:
            petition = barcodelinks[0]
            cares = "NONE"

        # what if we find 2+ documents?
        if len(barcodelinks) >= 2:
            petition = barcodelinks[0]
            cares = barcodelinks[1]
        
        #if no attorneys   
        try:
            atty1 = atty[0]
        except:
            atty1 = ""

        # tries to append a second name
        try:
            atty2 = atty[1]
        except:
            atty2 = ""
        try:
            atty3 = atty[2]
        except:
            atty3 = ""

        return plaintiff, defendant, petition, cares, money, atty1, atty2, atty3
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None, None, None, None, None, None

# Regex pattern to identify characteristics
pattern1 = re.compile(r'ANSWER', re.IGNORECASE)
pattern2 = re.compile(r'TRANSFERRED', re.IGNORECASE)
pattern3 = re.compile(r'Defendant appeared', re.IGNORECASE)
pattern4 = re.compile(r'EXECUTION INSTRUCTION FORM', re.IGNORECASE)
pattern5 = re.compile(r'EXECUTION RETURNED', re.IGNORECASE)
pattern6 = re.compile(r'JOURNAL ENTRY OF JUDGMENT', re.IGNORECASE)
pattern7 = re.compile(r'VOLUNTARY DISMISSAL', re.IGNORECASE)
pattern8 = re.compile(r'Dismissed by Court', re.IGNORECASE)
pattern9 = re.compile(r'DISMISSED', re.IGNORECASE)
pattern10 = re.compile(r'motion to vacate', re.IGNORECASE)
pattern11 = re.compile(r'jury trial', re.IGNORECASE)
pattern12 = re.compile(r'PERS SERV', re.IGNORECASE)
pattern13 = re.compile(r'SERVED - POST', re.IGNORECASE)
pattern14 = re.compile(r'by serving', re.IGNORECASE)
pattern15 = re.compile(r'DEFENDANT APPEARED NOT', re.IGNORECASE)
pattern16 = re.compile(r'Defendant appeared', re.IGNORECASE)
pattern17 = re.compile(r'unserved', re.IGNORECASE)
count = 0

# Open the CSV file for writing
with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
    writer = csv.writer(csv_file)
    # Write the header row
    writer.writerow([
        'Docket Number', 'Plaintiff', 'Defendant', 'Docket Links', 'Petition', 'Document2', 'Rent', 
        'Answer', 'Transfer', 'JUA', 'ExecutionFiled', 'ExecutionReturns', 'JEs', 'VoluntaryDismissal', 
        'CourtDismissal', 'Dismissed', 'MTV', 'Trial', 'PersonalService', 
        'ConstructiveService', 'OccupantService', 'Served', 'DefNoAppear', 'DefAppear', 
        'Unserved', 'Atty1', 'Atty2'
    ])
    # Iterate over all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith('.html'):
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                content = file.read()
                
                #call FED Processor
                plaintiff, defendant, petition, cares, money, atty1, atty2, atty3 = FED_processor(content)

                #boolean searches
                has_1 = pattern1.search(content) is not None
                has_2 = pattern2.search(content) is not None
                has_3 = pattern3.search(content) is not None
                has_4 = pattern4.search(content) is not None
                has_5 = pattern5.search(content) is not None
                has_6 = pattern6.search(content) is not None
                has_7 = pattern7.search(content) is not None
                has_8 = pattern8.search(content) is not None
                has_9 = pattern9.search(content) is not None
                has_10 = pattern10.search(content) is not None
                has_11 = pattern11.search(content) is not None
                has_12 = pattern12.search(content) is not None
                has_13 = pattern13.search(content) is not None
                has_14 = pattern14.search(content) is not None
                has_15 = pattern15.search(content) is not None
                has_16 = pattern14.search(content) is not None
                has_17 = pattern15.search(content) is not None   
                
                # Extract case number from the filename
                case_number = filename.split('.')[0]
                docketnum = "SC-23-" + str(case_number)
                print(docketnum)
                writer.writerow([docketnum, plaintiff, defendant, petition, cares, money, has_1, has_2, has_3, has_4, has_5, has_6, has_7, has_8, has_9, has_10, has_11, has_12, has_13, has_14, has_15, has_16, has_17, atty1, atty2, atty3])  
                count = count + 1
                print(count)
    print(f"Data exported to {output_csv}")
