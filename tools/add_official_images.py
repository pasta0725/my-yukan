"""Merge official images found later into an edition.

usage: python3 -I tools/add_official_images.py data/<date>.json result1.json [result2.json ...]
each result file: {"<story id>": [{"src","credit","caption","page"}, ...], ...}

- new images are marked kind "press" and de-duplicated against the story's existing images
- if the story's main image is missing or a news-site photo ("ogp"), the first official image becomes the main image
  and the old news-site photo moves into the gallery (so the 2-news-photo limit still holds)
- the rest go into the gallery (created before the "point"/"rina" blocks when missing); at most 12 official images per story
"""
import json, sys

def imgs_of(a):
    out = []
    if (a.get("image") or {}).get("src"): out.append(a["image"])
    for b in a.get("body", []):
        if b.get("type") == "img": out.append(b)
        if b.get("type") == "gallery": out += b.get("items", [])
    return out

def main():
    path = sys.argv[1]
    ed = json.load(open(path, encoding="utf-8"))
    found = {}
    for f in sys.argv[2:]:
        for k, v in json.load(open(f, encoding="utf-8")).items():
            found.setdefault(k, []).extend(v or [])
    added_total, stories = 0, 0
    for a in ed["articles"]:
        new = found.get(a["id"]) or []
        have = {i.get("src") for i in imgs_of(a)}
        press_now = sum(1 for i in imgs_of(a) if i.get("kind") == "press")
        items = []
        for n in new:
            src = (n.get("src") or "").strip()
            if not src.startswith("https://") or src in have: continue
            have.add(src)
            items.append({"src": src, "kind": "press", "credit": n.get("credit", ""), "caption": n.get("caption", ""), "page": n.get("page", "")})
        items = items[:max(0, 12 - press_now)]
        if not items: continue
        stories += 1; added_total += len(items)
        main = a.get("image") or {}
        moved = None
        if not main.get("src") or main.get("kind") != "press":
            if main.get("src"): moved = dict(main)
            first = items.pop(0)
            a["image"] = {k: first[k] for k in ("src", "kind", "credit", "page")}
            a["image"]["caption"] = first.get("caption", "")
        rest = items + ([moved] if moved else [])
        if not rest: continue
        body = a.setdefault("body", [])
        gal = next((b for b in body if b.get("type") == "gallery"), None)
        if gal is None:
            at = next((i for i, b in enumerate(body) if b.get("type") in ("point", "rina")), len(body))
            gal = {"type": "gallery", "title": "公式の画像", "items": []}
            body.insert(at, gal)
        # official first, news-site photos last
        gal["items"] = [x for x in gal["items"] + rest if x.get("kind") == "press"] + [x for x in gal["items"] + rest if x.get("kind") != "press"]
        gal["title"] = "そのほかの画像" if any(x.get("kind") != "press" for x in gal["items"]) else "公式の画像"
    json.dump(ed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"added {added_total} official images to {stories} stories")

if __name__ == "__main__":
    main()
