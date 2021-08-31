import requests
import os

os.chdir("C:/Users/AnthonySeverin/TIFs")
count = 1
urls = ['https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=3459138&db=TULSA&barcode=1050202093', 'https://www.oscn.net/applications/oscn/getimage.tif?submitted=true&casemasterid=3459129&db=TULSA&barcode=1050202077']

for i in urls:  
    r = requests.get(i, allow_redirects=True)
    filename = str(count) + ".tif"
    open(filename, 'wb').write(r.content)
    count = count + 1
    print("got this many:" + str(count))

###############################

from PIL import Image, ImageSequence
import os 

os.chdir("C:/Users/AnthonySeverin/TIFs")
tiff_path = "2.tif"

pdf_path = tiff_path.replace('.tif', '.pdf')

im = Image.open(tiff_path)

im.save(pdf_path, save_all=True)
