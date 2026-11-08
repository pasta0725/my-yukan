"""Merge the pictures chosen from find_official_images.py's candidates into the editions.

usage: python3 -I tools/pick_official_images.py candidates.json picks.json [picks2.json ...]
picks: {"<story id>": [{"n": 2, "caption": "何が写っているか（本文と同じ言葉で）"}, ...], ...}
       (n = the number under the thumbnail on the contact sheet; the first pick becomes the main picture
        if the story has no official one yet)
Runs tools/add_official_images.py and tools/place_images.py on each edition that changed.
"""
import json, os, subprocess, sys, tempfile

cand = json.load(open(sys.argv[1], encoding="utf-8"))
picks = {}
for f in sys.argv[2:]:
    for k, v in json.load(open(f, encoding="utf-8")).items(): picks.setdefault(k, []).extend(v or [])
by_date = {}
for sid, ps in picks.items():
    c = cand.get(sid)
    if not c: print("unknown story:", sid); continue
    imgs = {i["n"]: i for i in c["imgs"]}
    out = []
    for p in ps:
        i = imgs.get(p.get("n"))
        if not i: print("unknown number:", sid, p.get("n")); continue
        out.append({"src": i["src"], "credit": i["credit"], "caption": p.get("caption") or i.get("alt", ""), "page": i["page"]})
    if out: by_date.setdefault(c["date"], {})[sid] = out
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d, res in sorted(by_date.items()):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(res, tmp, ensure_ascii=False); tmp.close()
    ed = os.path.join(root, "data", f"{d}.json")
    subprocess.run([sys.executable, "-I", os.path.join(root, "tools/add_official_images.py"), ed, tmp.name], check=True)
    subprocess.run([sys.executable, "-I", os.path.join(root, "tools/place_images.py"), ed], check=True)
    os.unlink(tmp.name)
    print(d, len(res), "stories,", sum(len(v) for v in res.values()), "pictures")
