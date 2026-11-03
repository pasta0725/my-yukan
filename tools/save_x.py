"""Save Grok's "Xの声" answer as data/x/<date>.json (the site merges it into the edition).
usage: python3 -I tools/save_x.py <grok_answer.txt> <YYYY-MM-DD>
The answer may contain extra text; the first {...} JSON object in it is used.
Accepts {"posts":{"<article id>":["https://x.com/user/status/ID", ...]}} or {"<article id>":[...]}."""
import json, re, sys
src, date = sys.argv[1], sys.argv[2]
txt = open(src, encoding="utf-8").read()
start = txt.find("{")
obj, _ = json.JSONDecoder().raw_decode(txt[start:])
posts = obj.get("posts", obj)
ids_ok = {a["id"] for a in json.load(open(f"data/{date}.json"))["articles"]}
out, bad, dropped = {}, [], []
NG = re.compile(r"https?://|t\.co/|【|】|速報|ITmedia|Impress|家電 Watch|日経|プレスリリース|発表しました|#PR|クーポン|ポイント最大", re.I)
for aid, lst in posts.items():
    if aid not in ids_ok: bad.append(aid); continue
    keep = []
    for v in lst if isinstance(lst, list) else []:
        if isinstance(v, dict):
            # drop posts that only share the news (headline / link / outlet name)
            if NG.search(re.sub(r"(https?://)?pic\.(twitter|x)\.com/\S+", "", v.get("text", ""))): dropped.append(v.get("text", "")[:40]); continue
            v = v.get("url", "")
        v = str(v)
        m = re.search(r"status(?:es)?/(\d{15,25})", v) or re.fullmatch(r"(\d{15,25})", re.sub(r"\D", "", v))
        if m and int(m.group(1)) >= 2110000000000000000 and m.group(1) not in keep: keep.append(m.group(1))
    if keep: out[aid] = keep[:10]
json.dump({"date": date, "by": "grok", "posts": out}, open(f"data/x/{date}.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(out)}/{len(ids_ok)} articles, {sum(map(len, out.values()))} posts; unknown ids: {bad}; dropped as news-share: {len(dropped)}")
for d in dropped: print("  drop:", d)
