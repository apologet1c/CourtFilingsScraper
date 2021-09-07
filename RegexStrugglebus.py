import re

text = "That the defendant resides at 8947 E. detahant \n in Tulsa County, and the defendant's mailing\naddress is 8947 E. MArshall St TulsA ,ok 74015"

print(text)
address1 = re.findall("(?<=resides at ).*?\n", text)
address2 = re.findall("(?<=address is ).*?\n", text)

print(address1)
print(address2)
