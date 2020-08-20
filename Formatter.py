import pandas as pd
from textwrap import wrap
import string
pd.options.mode.chained_assignment = None 

#TARRANT COUNTY++++++++++++++++++++++++++++++++++++++
tarrant = open("tarrant.html", "r")
tarrant = pd.read_html(tarrant) #use pandas to extract the html datatables and turn them into dataframes

for i, value in enumerate(tarrant):
    globals()[string.ascii_lowercase[i]] = value

#let's choose table f (the one we want) and drop the blank columns from it
df = f.drop(f.columns[[1, 5]], axis=1)

#let's keep only the evictions
df = df[df["Type/Status"].str.contains("Evictions|Landlord", na=False)]

#let's split the dates and JP court numbers now
dates = []
location = []
for i in df["Filed/Location"]:
    split1, split2 = wrap(i, 10)
    dates.append(split1)
    location.append(split2)
print(dates)
    
#let's add the dates and court numbers as columns to the dataframe
df['Date'] = dates
df['Location'] = location

#dropping the old date/location column since we didn't need it
dftarrant = df.drop(df.columns[2], axis=1)

#COLLIN COUNTY++++++++++++++++++++++++++++++++++++++
collin = open("collin.html", "r")

#use pandas to extract the html datatables and turn them into dataframes
collin = pd.read_html(collin) 

#the web page is kinda messy so pandas finds a bunch of tables. Lets number with letters
for i, value in enumerate(collin):
    globals()[string.ascii_lowercase[i]] = value

df = f
#let's keep only the evictions
df = df[df["Type/Status"].str.contains("Evictions|Landlord", na=False)]

#let's split the dates and JP court numbers now
dates = []
location = []
for i in df["Filed/Location"]:
    split1, split2 = wrap(i, 19)
    date, precinct = wrap(split1, 10)
    dates.append(date)
    location.append(split2)

#let's add the dates and court numbers as columns to the dataframe
df['Date'] = dates
df['Location'] = location

#dropping the old date/location column since we didn't need it
dfcollin = df.drop(df.columns[2], axis=1)
print(dfcollin)

#DENTON COUNTY++++++++++++++++++++++++++++++++++++++
denton = open("denton.html", "r")
denton = pd.read_html(denton) #use pandas to extract the html datatables and turn them into dataframes

#the web page is kinda messy so pandas finds a bunch of tables. Lets number with letters
for i, value in enumerate(denton):
    globals()[string.ascii_lowercase[i]] = value

df = f
#let's keep only the evictions
df = df[df["Type/Status"].str.contains("Evictions|Landlord", na=False)]

#let's split the dates and JP court numbers now
dates = []
location = []
for i in df["Filed/Location/Judicial Officer"]:
    date, precinct = wrap(i, 19)
    dates.append(date)
    location.append(precinct)

#let's add the dates and court numbers as columns to the dataframe
df['Date'] = dates
df['Location'] = location

#dropping the old date/location column since we didn't need it
dfdenton = df.drop(df.columns[2], axis=1)
print(dfdenton)

#SAVEFILES++++++++++++++++++++++++++++++++++++++
dfcollin.to_csv('collin.csv', index=False)
dfdenton.to_csv('denton.csv', index=False)
dftarrant.to_csv('tarrant.csv', index=False)
