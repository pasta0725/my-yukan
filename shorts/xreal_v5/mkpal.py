import json, numpy as np, sys
sys.path.insert(0,'../palette')
src=open('../palette/pal.py').read().split('P={')[0]; exec(src)   # oklch2rgb, lum, cr, hexs
def H(L,Cc,h): return hexs(oklch2rgb(L,Cc,h))
def rgba(L,Cc,h,a): r,g_,b=oklch2rgb(L,Cc,h); return f'rgba({r},{g_},{b},{a})'
pal={}
def light(name,bg0,bg1,card2,text,sub,acc,brand,warn,bar,dotoff,cardtint=None,linehue=255):
    pal[name]=dict(bg0=H(*bg0),bg1=H(*bg1),card=H(*cardtint) if cardtint else '#FFFFFF',card2=H(*card2),text=H(*text),sub=H(*sub),acc=H(*acc),brand=H(*brand),warn=H(*warn),
      ink=H(*text),bar=H(*bar),line=rgba(0.3,0.05,linehue,0.045),capText=H(*text),capEdge='#FFFFFF',capShadow=rgba(0.3,0.05,linehue,0.22),capNum=H(*acc),dotOff=H(*dotoff),
      overlay='rgba(255,255,255,0.80)',glow=H(*brand),glowA=0.45,litShadow=rgba(0.25,0.05,linehue,0.28),litBlur=34,onAcc='#FFFFFF',buyFill=H(*acc),buyInk='#FFFFFF',waitText='#F4F1F3',
      cardShadow=rgba(0.3,0.05,linehue,0.14))
# B: white x navy x orange  (complementary: blue family vs orange accent)
light('B',(0.985,0.004,255),(0.935,0.016,255),(0.30,0.06,265),(0.25,0.05,265),(0.50,0.03,265),(0.60,0.185,42),(0.58,0.15,255),(0.55,0.21,25),(0.80,0.015,255),(0.88,0.01,255))
# C: ivory x teal (natural harmony: light colours lean yellow; accent teal = split complement of the warm base, caution red opposite teal)
light('C',(0.98,0.014,88),(0.94,0.022,82),(0.32,0.05,230),(0.27,0.04,250),(0.52,0.03,250),(0.54,0.115,195),(0.58,0.15,255),(0.56,0.20,28),(0.82,0.022,85),(0.89,0.015,85),cardtint=(0.995,0.006,88),linehue=80)
# D: light grey x blue (tone-on-tone of the character's blue; caution in the complementary orange-red)
light('D',(0.975,0.006,255),(0.93,0.016,255),(0.28,0.06,265),(0.24,0.05,265),(0.50,0.03,265),(0.53,0.21,262),(0.64,0.14,248),(0.60,0.19,38),(0.82,0.015,255),(0.88,0.01,255))
json.dump(pal,open('pals.json','w'),indent=1)
def rgb(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
for n,p in pal.items():
    print(n, {k:p[k] for k in ['bg0','bg1','text','sub','acc','warn','brand']})
    for k in ['text','sub','acc','warn','brand']:
        print('   ',k,'on bg1 %.1f'%cr(rgb(p[k]),rgb(p['bg1'])),'on card %.1f'%cr(rgb(p[k]),rgb(p['card'])))
    print('    white on acc %.1f'%cr((255,255,255),rgb(p['acc'])),' white on warn %.1f'%cr((255,255,255),rgb(p['warn'])))
