"""Replace the text of an already-published edition with richer multi-source text.
usage: python3 -I tools/apply_rich.py <dir with out_*.json> <YYYY-MM-DD>
out_*.json: {"<article id>": {"paras": [...], "point": [...], "refs": [{"name","url"}]}}
Images, the stat block and everything else are kept; only paragraphs/point/refs change."""
import json, glob, re, sys

src, date = sys.argv[1], sys.argv[2]
path = f"data/{date}.json"
ed = json.load(open(path, encoding="utf-8"))
new = {}
for f in sorted(glob.glob(f"{src}/out_*.json")):
    try: new.update(json.load(open(f, encoding="utf-8")))
    except Exception as e: print("BAD", f, e)

def https(u): return isinstance(u, str) and re.match(r"^https://\S+$", u)

done = 0
for a in ed["articles"]:
    r = new.get(a["id"])
    if not r: continue
    paras = [p.strip() for p in r.get("paras", []) if isinstance(p, str) and p.strip()]
    old_len = sum(len(b["text"]) for b in a["body"] if b.get("type") == "p")
    if not paras or sum(map(len, paras)) <= old_len: continue   # keep the old text if the new one is not richer
    imgs = [b for b in a["body"] if b.get("type") == "img"]
    gals = [b for b in a["body"] if b.get("type") == "gallery"]
    stat = [b for b in a["body"] if b.get("type") == "stat"]
    point = [b for b in a["body"] if b.get("type") == "point"]
    pt = [x for x in r.get("point", []) if isinstance(x, str) and x.strip()]
    if pt: point = [{"type": "point", "items": pt[:4]}]
    body, ps = [], [{"type": "p", "text": p} for p in paras]
    body += ps[:2] + imgs[:1] + ps[2:4] + stat + imgs[1:] + ps[4:] + gals + point
    a["body"] = body
    refs = [x for x in r.get("refs", []) if isinstance(x, dict) and https(x.get("url"))]
    if a.get("source_url") and all(x["url"] != a["source_url"] for x in refs):
        refs.insert(0, {"name": a.get("source_name", ""), "url": a["source_url"]})
    a["refs"] = refs[:5]
    done += 1
json.dump(ed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{done}/{len(ed['articles'])} articles rewritten; avg refs",
      round(sum(len(a.get("refs", [])) for a in ed["articles"] if a.get("refs")) / max(done, 1), 1),
      "; avg chars", round(sum(sum(len(b["text"]) for b in a["body"] if b["type"] == "p") for a in ed["articles"]) / len(ed["articles"])))
