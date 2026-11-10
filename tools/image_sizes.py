"""Write the width/height of official pictures into the editions (2026-11-11).
The site uses only pictures 1200px wide or more for search/Discover/X cards (tools/build_site.py share_img);
pictures added by pick_official_images.py already carry their size, this fills in older ones.
  python3 -I tools/image_sizes.py data/2026-11-10-pm.json [more editions...]
Reads only the first bytes of each picture (Range request). Pictures that cannot be read are left as they are."""
import io, json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (compatible; rina-tech-news image size check)"}


def size(src):
    for rng in ("bytes=0-131071", None):
        try:
            h = dict(UA, **({"Range": rng} if rng else {}))
            data = urllib.request.urlopen(urllib.request.Request(src, headers=h), timeout=30).read(8_000_000)
            return Image.open(io.BytesIO(data)).size
        except Exception:
            continue
    return None


def pics(a):
    if isinstance(a.get("image"), dict): yield a["image"]
    for b in a.get("body", []):
        if b.get("type") == "img": yield b
        for x in b.get("items", []) if b.get("type") == "gallery" else []: yield x


for f in sys.argv[1:]:
    ed = json.load(open(f, encoding="utf-8"))
    todo = [p for a in ed["articles"] for p in pics(a) if p.get("kind") == "press" and str(p.get("src", "")).startswith("https://") and not p.get("w")]
    srcs = sorted({p["src"] for p in todo})
    with ThreadPoolExecutor(12) as ex: got = dict(zip(srcs, ex.map(size, srcs)))
    n = 0
    for p in todo:
        s = got.get(p["src"])
        if s: p["w"], p["h"] = s; n += 1
    json.dump(ed, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)   # same format as add_official_images.py
    print(f, f"{n}/{len(todo)} sizes", sum(1 for s in got.values() if s and s[0] >= 1200), "of", len(srcs), "pictures are 1200px or wider")
