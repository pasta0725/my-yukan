# 4 thumbnail proposals for 「AIがAIを作る時代、もうすぐ？」 following tools/thumbnail_rules.md
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
S='/tmp/claude-0/-home-claude/0af991d2-2b1f-514d-b255-157946716558/scratchpad'
T=f'{S}/thumb2'; FB='/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
NAVY=(20,33,61); ORG=(255,138,0); WHITE=(255,255,255)
def font(sz): return ImageFont.truetype(FB,sz,index=0)
def bg_img(path, dark=False):
    bg=Image.open(path).convert('RGB'); bg=ImageOps.fit(bg,(1080,1920),Image.LANCZOS).convert('RGBA')
    return bg
def vignette(bg, col=(10,40,110), a=120):
    ov=Image.new('L',bg.size,0); d=ImageDraw.Draw(ov); d.rectangle([0,0,1080,1920],fill=a); d.rounded_rectangle([60,80,1020,1840],radius=300,fill=0)
    ov=ov.filter(ImageFilter.GaussianBlur(120)); bg.alpha_composite(Image.merge('RGBA',[Image.new('L',bg.size,c) for c in col]+[ov]))
def band_dark(bg,a=120):
    ov=Image.new('RGBA',bg.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    for y in range(540,1380): d.line([(0,y),(1080,y)],fill=(8,14,40,int(a*(1-abs(y-960)/440)**0.7)))
    bg.alpha_composite(ov)
def speedlines(bg,cx,cy,n=70,col=(255,255,255,170)):
    import math,random; random.seed(3); ov=Image.new('RGBA',bg.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    for i in range(n):
        t=2*math.pi*i/n+random.uniform(-.03,.03); r0=random.uniform(330,470); w=random.uniform(.010,.022)
        p=[(cx+r0*math.cos(t),cy+r0*math.sin(t)),(cx+2400*math.cos(t-w),cy+2400*math.sin(t-w)),(cx+2400*math.cos(t+w),cy+2400*math.sin(t+w))]
        d.polygon(p,fill=col)
    bg.alpha_composite(ov)
def text(bg,*a,**k): return
def _old_text(bg,txt,xy,sz,fill=NAVY,edge=WHITE,sw=None,anchor='ls',shadow=True):
    f=font(sz); d=ImageDraw.Draw(bg); sw=sw if sw is not None else max(sz//8,6)
    if shadow:
        sh=Image.new('RGBA',bg.size,(0,0,0,0)); ImageDraw.Draw(sh).text((xy[0]+6,xy[1]+9),txt,font=f,fill=(0,0,0,140),anchor=anchor,stroke_width=sw,stroke_fill=(0,0,0,140))
        bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d.text(xy,txt,font=f,fill=fill,anchor=anchor,stroke_width=sw,stroke_fill=edge)
    return d.textbbox(xy,txt,font=f,anchor=anchor,stroke_width=sw)
def label(bg,*a,**k): return
def _old_label(bg,txt,x=60,y=642,sz=64):
    f=font(sz); d=ImageDraw.Draw(bg); w=d.textlength(txt,font=f)
    d.rounded_rectangle([x,y,x+w+52,y+sz+34],radius=22,fill=ORG,outline=WHITE,width=5)
    d.text((x+26,y+sz//2+17),txt,font=f,fill=NAVY,anchor='lm')
def band(bg,*a,**k): return
def _old_band(bg,txt,x,y,sz=78,pad=26):
    f=font(sz); d=ImageDraw.Draw(bg); w=d.textlength(txt,font=f)
    sh=Image.new('RGBA',bg.size,(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle([x+6,y+8,x+w+2*pad+6,y+sz+2*pad-4+8],radius=18,fill=(0,0,0,110)); bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d.rounded_rectangle([x,y,x+w+2*pad,y+sz+2*pad-4],radius=18,fill=ORG,outline=WHITE,width=6)
    d.text((x+pad,y+(sz+2*pad-4)//2),txt,font=f,fill=NAVY,anchor='lm')
def char(bg,name,height,x,y,flip=False,shadow=True,fade=0):
    c=Image.open(f'{T}/assets/{name}.png'); sc=height/c.height; c=c.resize((int(c.width*sc),height),Image.LANCZOS)
    if fade:
        import numpy as np
        arr=np.asarray(c).copy(); g=np.ones(height); g[-fade:]=np.linspace(1,0,fade)**1.5; arr[...,3]=(arr[...,3]*g[:,None]).astype('uint8'); c=Image.fromarray(arr,'RGBA')
    if flip: c=ImageOps.mirror(c)
    # white outline so she separates from any background
    a=c.getchannel('A'); ol=a.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(1.5))
    if shadow:
        s=a.filter(ImageFilter.GaussianBlur(18)).point(lambda v:int(v*0.45)); bg.alpha_composite(Image.merge('RGBA',[Image.new('L',c.size,0)]*3+[s]),(x+14,y+18))
    bg.alpha_composite(Image.merge('RGBA',[Image.new('L',c.size,255)]*3+[ol]),(x,y)); bg.alpha_composite(c,(x,y))
def logo(bg,y=300,w=760):
    lg=Image.open('/home/claude/my-yukan-repo/channel/logo.png').convert('RGBA'); lg=lg.resize((w,int(lg.height*w/lg.width)),Image.LANCZOS); bg.alpha_composite(lg,((1080-w)//2,y))
def save(bg,n):
    bg.convert('RGB').save(f'{T}/base_{n}.png'); return
    bg.convert('RGB').save(f'{T}/out/サムネ{n}.jpg',quality=93)

# A: robot hand building a robot (literally "AI makes AI") + surprised pointing
bg=bg_img(f'{S}/thumb/bg1.png'); band_dark(bg)
char(bg,'rina_surprised_point_left',1222,420,800,fade=260)
label(bg,'AI速報')
text(bg,'AIが',(62,890),165); text(bg,'AIを作る',(62,1075),165)
band(bg,'時代がもうすぐ？',62,1140,74)
save(bg,'A')

# B: spiral staircase of robots climbing toward the light + thinking
bg=bg_img(f'{S}/thumb/bg2.png'); band_dark(bg,140)
char(bg,'rina_thinking_left',1400,500,610)
label(bg,'AIの警告')
text(bg,'AIが自分を',(62,895),136); text(bg,'育てる日',(62,1060),170)
band(bg,'開発ペース2倍へ',62,1120,74)
save(bg,'B')

# C: no character — the rising arrow does the talking
bg=bg_img(f'{S}/thumb/bg3.png'); band_dark(bg)
label(bg,'AI速報')
text(bg,'開発ペース',(62,890),150); text(bg,'2倍',(62,1120),240,fill=ORG,edge=NAVY,sw=14)
band(bg,'AIがAIを作る時代へ',62,1150,70)
save(bg,'C')

# D: chibi, shocked, full body with manga speed lines filling the frame
bg=bg_img(f'{T}/bgplate.png'); vignette(bg)
speedlines(bg,850,900)
char(bg,'rina_chibi_shocked',1150,540,620,flip=True)
label(bg,'速報')
text(bg,'AIが',(62,900),180); text(bg,'AIを作る!?',(62,1085),132)
band(bg,'もうすぐ来るかも',62,1140,74)
save(bg,'D')

