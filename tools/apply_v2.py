"""Rewrite a published edition's text into the 第2版 structure (keys / lead / h+p sections / stat / point).
usage: python3 -I tools/apply_v2.py <dir with out_*.json> <YYYY-MM-DD>
out_*.json: {"<id>": {"title","summary","blocks":[keys, p(lead), h, p, ..., stat, point]}}
Images (img/gallery) and refs are kept from the current edition."""
import json, glob, re, sys

src, date = sys.argv[1], sys.argv[2]
path = f"data/{date}.json"
ed = json.load(open(path, encoding="utf-8"))
new = {}
for f in sorted(glob.glob(f"{src}/out_*.json")):
    try: new.update(json.load(open(f, encoding="utf-8")))
    except Exception as e: print("BAD", f, e)

META = re.compile(r"見つけられ|見つから|今回読ん|参照した|確認できた記事|読んだ記事|私は|私が|検索では")
done, warns = 0, []
for a in ed["articles"]:
    r = new.get(a["id"])
    if not r or not isinstance(r.get("blocks"), list): continue
    blocks = [b for b in r["blocks"] if isinstance(b, dict) and b.get("type") in ("keys", "p", "h", "stat", "point")]
    if not any(b["type"] == "p" for b in blocks): continue
    imgs = [b for b in a["body"] if b.get("type") == "img"]
    gals = [b for b in a["body"] if b.get("type") == "gallery"]
    head = [b for b in blocks if b["type"] == "keys"][:1]
    rest = [b for b in blocks if b["type"] in ("p", "h")]
    stat = [b for b in blocks if b["type"] == "stat"][:1] or [b for b in a["body"] if b.get("type") == "stat"][:1]
    point = [b for b in blocks if b["type"] == "point"][:1] or [b for b in a["body"] if b.get("type") == "point"][:1]
    lead, sections = rest[:1], rest[1:]
    # second image goes before the 2nd section heading
    h_idx = [i for i, b in enumerate(sections) if b["type"] == "h"]
    if len(imgs) > 1 and len(h_idx) > 1:
        sections = sections[:h_idx[1]] + imgs[1:] + sections[h_idx[1]:]
    else:
        sections = sections + imgs[1:]
    a["body"] = head + lead + imgs[:1] + sections + stat + gals + point
    if isinstance(r.get("title"), str) and 8 <= len(r["title"]) <= 40: a["title"] = r["title"]
    if isinstance(r.get("summary"), str) and 5 <= len(r["summary"]) <= 70: a["summary"] = r["summary"]
    # checks
    text = "".join(b.get("text", "") for b in a["body"] if b["type"] in ("p", "h"))
    if META.search(text): warns.append((a["id"], "meta: " + META.search(text).group(0)))
    for b in a["body"]:
        if b["type"] == "p" and len(b["text"]) > 220: warns.append((a["id"], f"long p {len(b['text'])}"))
    done += 1
json.dump(ed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{done}/{len(ed['articles'])} articles restructured")
for w in warns: print("WARN", *w)
