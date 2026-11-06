"""Build one day's edition from worker JSON files and update data/index.json.
usage: python3 build_edition.py <src_dir> <YYYY-MM-DD> [drop_id ...]
"""
import json, glob, re, sys, datetime
from collections import defaultdict

REPO = "/home/claude/my-yukan-repo"
SRC, DATE = sys.argv[1], sys.argv[2]
DROP = set(sys.argv[3:])
WD = "月火水木金土日"

def ok(u): return isinstance(u, str) and re.match(r"^https://\S+$", u)

# source_urls already published in recent editions
idx_path = f"{REPO}/data/index.json"
idx = json.load(open(idx_path))
used = set()
for d in idx.get("editions", []):
    if d == DATE: continue
    try:
        for a in json.load(open(f"{REPO}/data/{d}.json"))["articles"]: used.add(a["source_url"])
    except Exception: pass

# categories since 2026-11-07, in display order, with the max number of stories per day
CATS = {"ai": 14, "mobile": 7, "gadget": 7, "service": 7, "game": 7, "ec": 7, "future": 4, "other": 5}
by_cat, seen_urls, seen_ids = defaultdict(list), set(), set()
for f in sorted(glob.glob(f"{SRC}/*_[ABCD].json")):
    try: items = json.load(open(f))
    except Exception as e: print("BAD", f, e); continue
    for a in items:
        cat = a.get("category")
        if cat not in CATS or not ok(a.get("source_url")): continue
        if a.get("id") in DROP or a["id"] in seen_ids or a["source_url"] in seen_urls or a["source_url"] in used: continue
        # sanitize images: https only, no dup, news-site photos <= 2
        seen_src, ogp = set(), [0]
        def keep(x):
            if not isinstance(x, dict) or not ok(x.get("src")) or x["src"] in seen_src: return False
            if x.get("kind") != "press":
                if ogp[0] >= 2: return False
                ogp[0] += 1
            seen_src.add(x["src"]); return True
        if a.get("image") and not keep(a["image"]): a.pop("image")
        body = []
        for b in a.get("body", []):
            t = b.get("type")
            if t == "img":
                if keep(b): body.append(b)
            elif t == "gallery":
                b["items"] = [x for x in b.get("items", []) if keep(x)]
                if b["items"]: body.append(b)
            else: body.append(b)
        a["body"] = body
        by_cat[cat].append(a); seen_ids.add(a["id"]); seen_urls.add(a["source_url"])

for c in by_cat:
    by_cat[c].sort(key=lambda a: a.get("published", ""), reverse=True)
    by_cat[c] = by_cat[c][:CATS[c]]
arts = []
for i in range(max(CATS.values())):
    for c in CATS:
        if i < len(by_cat[c]): arts.append(by_cat[c][i])

dt = datetime.date.fromisoformat(DATE)
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")
ed = {"date": DATE, "label": f"{dt.month}月{dt.day}日（{WD[dt.weekday()]}）の号", "updatedAt": now, "articles": arts}
json.dump(ed, open(f"{REPO}/data/{DATE}.json", "w"), ensure_ascii=False, indent=1)
eds = sorted(set(idx.get("editions", []) + [DATE]), reverse=True)[:14]
json.dump({"editions": eds, "updatedAt": now}, open(idx_path, "w"), ensure_ascii=False, indent=1)
# fixed-URL list of today's stories, read by the Grok Bot routine that collects "Xの声"
todo = {"date": DATE, "output_path": f"data/x/{DATE}.json",
        "articles": [{"id": a["id"], "category": a["category"], "title": a["title"], "summary": a.get("summary", ""),
                      "source_name": a.get("source_name", "")} for a in arts]}
json.dump(todo, open(f"{REPO}/data/x-todo.json", "w"), ensure_ascii=False, indent=1)

def count(a, kind):
    n = 1 if a.get("image", {}).get("kind") == kind else 0
    for b in a["body"]:
        if b.get("type") == "img" and b.get("kind") == kind: n += 1
        if b.get("type") == "gallery": n += sum(1 for x in b["items"] if x.get("kind") == kind)
    return n
print({c: len(v) for c, v in by_cat.items()}, "total", len(arts),
      "with image", sum(1 for a in arts if a.get("image")),
      "press", sum(count(a, "press") for a in arts), "news", sum(count(a, "ogp") for a in arts))
for a in arts: print(a["category"], a.get("published"), a["title"])
