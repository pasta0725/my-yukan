"""Prepare the PNGTuber pictures of 星餓りな (tools/shorts_rules.md 「りなの動かし方」, 2026-11-09).

usage: python3 tools/rina_puppet_prep.py
reads  channel/rina_puppet/src/* and channel/rina_poses/*.png (green-screen pictures)
writes channel/rina_puppet/<name>.png (transparent) and channel/rina_puppet/index.json

index.json describes every picture: size, where the eyes and the mouth are (in the picture's own pixels),
the skin colour used to cover the mouth/eyes, and for the big poses how they are placed on the 720x1280 pose canvas.
Add a new pose or expression = add an entry to ASSETS below (measure the eyes/mouth on a grid crop) and run again.
short pages draw them with shorts/_template/puppet.js.
"""
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "channel", "rina_puppet")
SRC = os.path.join(OUT, "src")
POSES = os.path.join(ROOT, "channel", "rina_poses")

# eyes = iris centres (left, right on screen); mouth = centre and width of the closed mouth line
ASSETS = {
    # small presenter (left-bottom): super-deformed Rina, full body, sticker style (bold outlines) — chosen by the user 2026-11-09
    # (the first version is kept as src/chibi_v1_raw.png: eyes [[360,488],[580,488]], eye_box [113,125], mouth [470,590], w60)
    "chibi": {"src": os.path.join(SRC, "chibi_sticker_raw.png"), "kind": "chibi",
              "eyes": [[543, 412], [715, 412]], "eye_box": [110, 82], "mouth": [629, 490], "mouth_w": 52, "skin_at": [629, 470]},
    # big presenter (登場・最後): normal proportions, 720x1280 pose canvas
    "big_base": {"src": os.path.join(POSES, "base_green.png"), "kind": "big",
                 "eyes": [[310.6, 256], [416.9, 256]], "mouth": [363.8, 312.5], "mouth_w": 44, "skin_at": [364, 296]},
    "big_finger1": {"src": os.path.join(POSES, "rina_fingers_1.png"), "kind": "big",
                    "eyes": [[313.8, 268.8], [420, 260.6]], "mouth": [375, 334], "mouth_w": 46, "skin_at": [375, 306],
                    "close_mouth": {"c": [378, 330], "rx": 48, "ry": 28}, "match_colour_to": "big_base"},
    # in-between drawings for the move 立ち絵 → 指1本 (1/3 and 2/3 of the way); aligned by the eyes
    "big_ib_finger1_1": {"src": os.path.join(SRC, "ib1_raw.png"), "kind": "between",
                         "eyes": [[415.6, 350], [550, 333.75]], "align_to": ["big_base", "big_finger1", 1 / 3], "match_colour_to": "big_base"},
    "big_ib_finger1_2": {"src": os.path.join(SRC, "ib2_raw.png"), "kind": "between",
                         "eyes": [[518.75, 296.25], [631.25, 283.75]], "align_to": ["big_base", "big_finger1", 2 / 3], "match_colour_to": "big_base"},
}
TRANSITIONS = {"base_to_finger1": ["big_base", "big_ib_finger1_1", "big_ib_finger1_2", "big_finger1"]}


def key(path):
    x = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    gd = g - np.maximum(r, b)
    a = np.clip(1 - (gd - 30) / 80, 0, 1)
    a[a < 0.04] = 0  # faint noise left in the green
    g = np.minimum(g, np.maximum(r, b) + 8)  # remove the green fringe
    return np.dstack([r, g, b, a * 255])


def skin_mask(x):
    r, g, b, a = x[..., 0], x[..., 1], x[..., 2], x[..., 3]
    return (a > 250) & (r > 200) & (r > g + 8) & (g > b - 6) & (r - b > 15) & (r - b < 80) & (g > 160)


def colour_match(x, ref):
    """per-channel gain so the skin has the same average colour as the reference picture (the finger pose was a bit red)"""
    m, mr = skin_mask(x), skin_mask(ref)
    gain = ref[mr][:, :3].mean(0) / x[m][:, :3].mean(0)
    y = x.copy(); y[..., :3] = np.clip(x[..., :3] * gain, 0, 255)
    return y, gain


def close_mouth(x, c, rx, ry, skin):
    """paint the open grin over with skin and draw a closed smile line (the puppet opens it again in the page)"""
    im = Image.fromarray(x.astype(np.uint8), "RGBA")
    patch = Image.new("L", im.size, 0)
    ImageDraw.Draw(patch).ellipse([c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry], fill=255)
    patch = patch.filter(ImageFilter.GaussianBlur(5))
    fill = Image.new("RGBA", im.size, tuple(int(v) for v in skin) + (255,))
    im = Image.composite(fill, im, patch)
    # smooth smile line: drawn 4x larger, then shrunk (anti-aliased)
    S, w = 4, rx * 0.72
    line = Image.new("L", (im.width * S, im.height * S), 0)
    ImageDraw.Draw(line).arc([(c[0] - w) * S, (c[1] - 16) * S, (c[0] + w) * S, (c[1] + 4) * S], 25, 155, fill=255, width=3 * S)
    line = line.resize(im.size, Image.LANCZOS)
    ink = Image.new("RGBA", im.size, (110, 60, 70, 255))
    im = Image.composite(ink, im, line)
    return np.asarray(im, dtype=np.float32)


def place(x, src_eyes, dst_eyes, size=(720, 1280)):
    """scale + move (no rotation) so the eye pair lands on dst_eyes"""
    se, de = np.array(src_eyes, float), np.array(dst_eyes, float)
    s = np.linalg.norm(de[1] - de[0]) / np.linalg.norm(se[1] - se[0])
    ms, md = se.mean(0), de.mean(0)
    im = Image.fromarray(x.astype(np.uint8), "RGBA")
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(im, (round(md[0] - ms[0] * s), round(md[1] - ms[1] * s)))
    return np.asarray(out, dtype=np.float32)


def main():
    pics, index = {}, {"assets": {}, "transitions": TRANSITIONS, "note": "made by tools/rina_puppet_prep.py"}
    for name in ["chibi", "big_base", "big_finger1", "big_ib_finger1_1", "big_ib_finger1_2"]:
        a = ASSETS[name]
        x = key(a["src"])
        info = {"kind": a["kind"]}
        a = dict(a)
        if a["kind"] == "chibi":
            # trim the empty background (the page fits the whole picture into its box), anchors move with it
            ys, xs = np.nonzero(x[..., 3] > 60); m = 8
            l, t, r, b = int(max(0, xs.min() - m)), int(max(0, ys.min() - m)), int(min(x.shape[1], xs.max() + m + 1)), int(min(x.shape[0], ys.max() + m + 1))
            x = x[t:b, l:r]
            a["eyes"] = [[ex - l, ey - t] for ex, ey in a["eyes"]]; a["mouth"] = [a["mouth"][0] - l, a["mouth"][1] - t]
        if a.get("match_colour_to"):
            x, gain = colour_match(x, pics[a["match_colour_to"]]); info["colour_gain"] = [round(float(v), 3) for v in gain]
        if a.get("mouth"):
            # skin colour = the typical skin right around the mouth (a ring around it), so patches blend in
            mx, my = a["mouth"]; r0, r1 = a["mouth_w"] * 0.9, a["mouth_w"] * 1.6
            yy, xx = np.mgrid[0:x.shape[0], 0:x.shape[1]]; d = np.hypot(xx - mx, yy - my)
            ring = (d > r0) & (d < r1) & skin_mask(x)
            info["skin"] = [int(v) for v in np.median(x[ring][:, :3], axis=0)]
        if a.get("close_mouth"):
            cm = a["close_mouth"]; x = close_mouth(x, cm["c"], cm["rx"], cm["ry"], info["skin"])
        if a.get("align_to"):
            p0, p1, f = a["align_to"]
            e0, e1 = np.array(ASSETS[p0]["eyes"]), np.array(ASSETS[p1]["eyes"])
            x = place(x, a["eyes"], (e0 + (e1 - e0) * f).tolist())
        pics[name] = x
        for k in ("eyes", "eye_box", "mouth", "mouth_w"):
            if k in a and not a.get("align_to"): info[k] = a[k]
        info["size"] = [x.shape[1], x.shape[0]]
        Image.fromarray(x.astype(np.uint8), "RGBA").save(os.path.join(OUT, name + ".png"), optimize=True)
        index["assets"][name] = info
        print(name, info)
    json.dump(index, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # the same as a script, because pages opened from file:// cannot fetch() json
    open(os.path.join(OUT, "index.js"), "w", encoding="utf-8").write("window.PUPPET_INDEX=" + json.dumps(index, ensure_ascii=False) + ";\n")


if __name__ == "__main__":
    main()
