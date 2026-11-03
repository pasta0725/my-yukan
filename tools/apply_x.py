"""Attach X post ids to a day's edition.
usage: python3 tools/apply_x.py <xres.txt> <YYYY-MM-DD>
xres.txt: lines '@<article id>' followed by post ids (dashes allowed)."""
import json, re, sys
src, date = sys.argv[1], sys.argv[2]
path = f"data/{date}.json"
ed = json.load(open(path))
res, cur = {}, None
for line in open(src, encoding="utf-8"):
    line = line.strip()
    if line.startswith("@"): cur = line[1:]; res.setdefault(cur, []); continue
    pid = re.sub(r"\D", "", line.split(" ")[0])
    if cur and len(pid) >= 18 and int(pid) >= 2110000000000000000 and pid not in res[cur]:
        res[cur].append(pid)
n = 0
for a in ed["articles"]:
    if a["id"] in res and res[a["id"]]:
        a["x_posts"] = res[a["id"]][:10]; n += 1
json.dump(ed, open(path, "w"), ensure_ascii=False, indent=1)
print(f"{n}/{len(ed['articles'])} articles with X posts, total {sum(len(a.get('x_posts',[])) for a in ed['articles'])}")
