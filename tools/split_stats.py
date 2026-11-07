"""Split stats.json (from the site-stats workflow) into the 5 files the dashboard reads.

usage: python3 -I tools/split_stats.py stats.json out_dir
writes out_dir/daily.json, pages.json, sources.json, devices.json, countries.json
"""
import json, os, sys

src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
os.makedirs(out, exist_ok=True)
for k in ("daily", "pages", "sources", "devices", "countries"):
    rows = d.get(k) or []
    json.dump(rows, open(os.path.join(out, k + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(k, len(rows))
print("updated", d.get("updated"))
