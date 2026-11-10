"""YouTube channel banner (2560x1440) built from the end-card logo (channel/logo.png) - 2026-11-10, user request.
  python3 tools/make_banner.py <rina_cutout.png> channel/banner.jpg [preview_dir]
Everything that matters (logo, tagline, Rina's face) sits in the all-devices safe area x 507-2053, y 508-931,
which is what phones show. PCs show the full-width band y 508-931, TVs the whole picture.
Colours follow shorts/_template/pal.js. preview_dir gets pc.png / tablet.png / phone.png / tv.png crops."""
import math, os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 2560, 1440
SAFE = (507, 508, 2053, 931)
BG0, BG1, TEXT, SUB, ACC, BRAND, LIGHT = "#F8FAFD", "#E3EAF4", "#16213A", "#5B6375", "#D64D00", "#337BD0", "#9CCBF0"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def rgb(h, a=255): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def star(d, cx, cy, r, col):   # the 4-point sparkle from the logo
    k = r * 0.22
    d.polygon([(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k), (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)], fill=col)


def circuit(d, pts, col, w=5, end=None):   # a line like the logo's underline, ending in a ring
    d.line(pts, fill=col, width=w, joint="curve")
    x, y = pts[-1]; r = 13
    d.ellipse((x - r, y - r, x + r, y + r), outline=end or col, width=w, fill=rgb(BG0))


def build(rina_path, out, prev=None):
    random.seed(7)
    im = Image.new("RGBA", (W, H))
    # background: soft vertical gradient + a faint dot grid
    top, bot = rgb(BG0), rgb(BG1)
    g = Image.new("RGBA", (1, H))
    for y in range(H):
        t = y / (H - 1); g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(4)))
    im.paste(g.resize((W, H)))
    d = ImageDraw.Draw(im, "RGBA")
    for x in range(40, W, 64):
        for y in range(40, H, 64):
            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=rgb(BRAND, 28))
    # a big pale band behind the visible area, slanted a little, to give the PC strip some depth
    band = Image.new("RGBA", (W, H), (255, 255, 255, 0)); bd = ImageDraw.Draw(band)
    bd.polygon([(0, 560), (W, 470), (W, 960), (0, 1050)], fill=rgb("#FFFFFF", 150))
    im.alpha_composite(band.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(im, "RGBA")
    # circuit lines (left and right of the safe area, so the PC strip is not empty; none crosses the logo)
    blue, pale = rgb(BRAND, 200), rgb(LIGHT, 255)
    circuit(d, [(0, 600), (230, 600), (290, 660), (440, 660)], blue)
    circuit(d, [(0, 860), (150, 860), (210, 800), (380, 800)], pale, 7)
    circuit(d, [(90, 300), (90, 470), (160, 540), (300, 540)], pale, 7)
    circuit(d, [(0, 730), (330, 730)], blue, 4, rgb(ACC))
    circuit(d, [(W, 590), (2420, 590), (2360, 650), (2260, 650)], blue)
    circuit(d, [(W, 880), (2470, 880), (2410, 820), (2300, 820)], pale, 7)
    circuit(d, [(2470, 1150), (2470, 990), (2400, 920)], pale, 7)
    circuit(d, [(W, 740), (2330, 740)], blue, 4, rgb(ACC))
    for (x, y, r, c) in [(420, 560, 26, LIGHT), (250, 900, 18, ACC), (2210, 560, 22, ACC), (2380, 930, 30, LIGHT),
                         (160, 420, 16, BRAND), (2500, 470, 18, BRAND), (600, 1080, 22, LIGHT), (1950, 360, 20, LIGHT)]:
        star(d, x, y, r, rgb(c))
    # Rina on the right of the safe area: face inside the strip, body continues down (seen on TV)
    rina = Image.open(rina_path).convert("RGBA")
    rh = 860; rina = rina.resize((round(rina.width * rh / rina.height), rh), Image.LANCZOS)
    rx = SAFE[2] - rina.width + 30; ry = 498   # head and waving hand inside the strip (y 508-931)
    a = rina.getchannel("A"); fade = Image.linear_gradient("L").resize((rina.width, 180)).point(lambda v: 255 - v)
    m = Image.new("L", rina.size, 255); m.paste(fade, (0, rh - 180))   # soft fade at the cut-off bottom (seen on TV only)
    from PIL import ImageChops; rina.putalpha(ImageChops.multiply(a, m))
    sh = Image.new("RGBA", rina.size, (0, 0, 0, 0)); sh.putalpha(rina.getchannel("A").point(lambda a: a * 0.18))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (rx + 14, ry + 16))
    im.alpha_composite(rina, (rx, ry))
    # logo + tagline, centred in the part of the safe area left of Rina
    logo = Image.open(os.path.join(ROOT, "channel", "logo.png")).convert("RGBA")
    area_r = rx + 60
    lw = min(1000, area_r - SAFE[0] - 70); lh = round(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    lx = SAFE[0] + (area_r - SAFE[0] - lw) // 2; ly = 522
    im.alpha_composite(logo, (lx, ly))
    d = ImageDraw.Draw(im, "RGBA")
    parts = [("AI・ガジェット・家電のニュースを、", TEXT), ("毎日ショート", ACC), ("で。", TEXT)]
    fs = 50
    while True:   # shrink until the line fits left of Rina
        f = ImageFont.truetype(FONT_B, fs); tw = sum(d.textlength(t, font=f) for t, _ in parts)
        if tw <= rx + 20 - SAFE[0] - 40 or fs <= 34: break
        fs -= 2
    x = max(SAFE[0] + 30, lx + (lw - tw) / 2); y = ly + lh + 14
    for t, c in parts:
        d.text((x, y), t, font=f, fill=rgb(c)); x += d.textlength(t, font=f)
    im.convert("RGB").save(out, quality=93)
    if prev:
        os.makedirs(prev, exist_ok=True); base = im.convert("RGB")
        base.crop((0, 508, W, 931)).save(os.path.join(prev, "pc.png"))
        base.crop((352, 508, 2208, 931)).save(os.path.join(prev, "tablet.png"))
        base.crop(SAFE).save(os.path.join(prev, "phone.png"))
        base.resize((1280, 720)).save(os.path.join(prev, "tv.png"))
    return lx, ly, lw, lh, rx, y


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
