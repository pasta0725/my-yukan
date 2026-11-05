# Overlays an approximation of the YouTube Shorts UI on iPhone (measured from the user's screenshot) and crops the sides like the phone does.
import sys
from PIL import Image, ImageDraw
out=sys.argv[1]; ims=[]
for p in sys.argv[2:]:
    im=Image.open(p).convert('RGBA'); o=Image.new('RGBA',im.size,(0,0,0,0)); d=ImageDraw.Draw(o)
    d.rectangle((0,140,1080,230),fill=(0,0,0,70)); d.rounded_rectangle((136,250,1040,326),radius=38,fill=(0,0,0,90))
    for i,y in enumerate([975,1100,1225,1350,1475,1600]): d.ellipse((890,y,945,y+55),fill=(255,0,0,110))
    d.ellipse((132,1483,199,1550),fill=(255,0,0,110)); d.rectangle((210,1495,560,1540),fill=(255,0,0,90)); d.rectangle((132,1565,830,1605),fill=(255,0,0,90)); d.rectangle((132,1630,700,1666),fill=(255,0,0,90))
    d.rectangle((0,1705,1080,1712),fill=(255,0,0,160))
    im=Image.alpha_composite(im,o).crop((98,0,982,1920)); ims.append(im.resize((442,960)))
sheet=Image.new('RGB',(442*len(ims)+10*(len(ims)-1),960),'white')
for i,im in enumerate(ims): sheet.paste(im,(i*452,0))
sheet.save(out)
