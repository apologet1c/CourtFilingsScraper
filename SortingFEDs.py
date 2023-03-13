import os
import re
import shutil

current_directory = os.getcwd()
SC_directory = current_directory + "\\SC-22"
FEDs_directory = SC_directory + "\\FEDs\\"
os.chdir(SC_directory)

filelist = os.listdir()

for x in filelist:
    with open(x,'r', encoding='utf-8', errors = 'ignore') as src:
        html = src.read()
        match = re.search("FORCIBLE ENTRY", html)
        testfed = bool(match)

    if testfed is True:
        print(x)
        newfilename = FEDs_directory + str(x)
        shutil.move(x, newfilename)
