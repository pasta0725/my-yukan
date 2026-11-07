"""Spread the pictures of a story through its text instead of one block at the end.

usage: python3 -I tools/place_images.py data/<date>.json [data/<date>.json ...]

The user's rule (2026-11-08): when a story has several pictures, put each one in the
right place between the paragraphs, not all together near the end.

- Every "gallery" block is taken apart. Each picture goes after the section
  (a "h" heading and its paragraphs) whose words match its caption best.
- A picture whose caption matches nothing goes to the section with the fewest pictures,
  in order, so the pictures are spread evenly.
- At most 4 pictures per section. They are shared out after the section's paragraphs;
  one picture is shown as a normal image, two or more at the same spot become a small
  gallery with no title (a row of pictures). What does not fit stays in a gallery
  "そのほかの画像" just before the "point" block.
- Pictures are never put before the lead paragraph or after "point"/"rina".
- Running it again does nothing (there is no gallery left to take apart).
"""
import json, re, sys

KATA = re.compile(r"[ァ-ヴー]{2,}")
LATIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+\-]{1,}")
KANJI = re.compile(r"[一-龥々]{2,}")
STOP = {"画像", "写真", "公式", "イメージ", "提供", "出典", "発表", "ページ", "製品"}


def tokens(s):
    s = s or ""
    out = set()
    for m in KATA.findall(s): out.add(m)
    for m in LATIN.findall(s): out.add(m.lower())
    for m in KANJI.findall(s):
        if len(m) <= 3: out.add(m)
        for i in range(len(m) - 1): out.add(m[i:i + 2])
    return {t for t in out if t not in STOP}


def sections(body):
    """list of (start, end) index ranges for each h-section (h + its p blocks)."""
    out, i = [], 0
    while i < len(body):
        if body[i].get("type") == "h":
            j = i + 1
            while j < len(body) and body[j].get("type") in ("p", "img"): j += 1
            out.append((i, j)); i = j
        else:
            i += 1
    return out


def place(a):
    body = a.get("body") or []
    gals = [b for b in body if b.get("type") == "gallery"]
    if not gals: return 0
    pics = [x for g in gals for x in g.get("items", []) if x.get("src")]
    body = [b for b in body if b.get("type") != "gallery"]
    secs = sections(body)
    if not secs:  # older stories without headings: each paragraph after the lead is a spot
        ps = [i for i, b in enumerate(body) if b.get("type") == "p"][1:]
        secs = [(i, i + 1) for i in ps]
    if not secs:
        a["body"] = body; return restore(a, body, pics)
    text = [" ".join(body[k].get("text", "") for k in range(s, e)) for s, e in secs]
    stoks = [tokens(t) for t in text]
    have = [sum(1 for k in range(s, e) if body[k].get("type") == "img") for s, e in secs]
    slots = [[] for _ in secs]
    # sections about what is still unknown / next steps / cautions get unmatched pictures last
    late = {k for k, (s, e) in enumerate(secs) if body[s].get("type") == "h" and re.search(r"わかって|未定|未発表|今後|これから|注意|課題|まとめ|気をつけ|ただし", body[s].get("text", ""))}
    rest = []
    # best match first, then spread the rest
    scored = []
    for n, p in enumerate(pics):
        ct = tokens((p.get("caption") or "") + " " + (p.get("alt") or ""))
        sc = [len(ct & st) for st in stoks]
        scored.append((max(sc) if sc else 0, n, sc))
    for best, n, sc in sorted(scored, key=lambda x: (-x[0], x[1])):
        order = sorted(range(len(secs)), key=lambda k: (-sc[k], have[k] + len(slots[k]), k)) if best > 0 \
            else sorted(range(len(secs)), key=lambda k: (k in late, have[k] + len(slots[k]), k))
        for k in order:
            if have[k] + len(slots[k]) < (4 if body[secs[k][0]].get("type") == "h" else 2):
                slots[k].append(pics[n]); break
        else:
            rest.append(pics[n])
    # keep the original order of pictures inside each section
    for k in range(len(slots)): slots[k].sort(key=lambda p: pics.index(p))
    # rebuild: share each section's pictures out after its paragraphs
    def block(chunk):
        if len(chunk) == 1:
            return dict(type="img", **{kk: vv for kk, vv in chunk[0].items() if kk != "type"})
        return {"type": "gallery", "title": "", "items": chunk}
    new, si = [], {s: k for k, (s, e) in enumerate(secs)}
    i = 0
    while i < len(body):
        if i in si:
            k = si[i]; s, e = secs[k]
            q = slots[k]
            paras = [x for x in range(s, e) if body[x].get("type") == "p"] or [e - 1]
            m = len(paras); chunks = []
            for j in range(m):
                lo = round(len(q) * j / m); hi = round(len(q) * (j + 1) / m); chunks.append(q[lo:hi])
            for x in range(s, e):
                new.append(body[x])
                if x in paras:
                    c = chunks[paras.index(x)]
                    if c: new.append(block(c))
            i = e
        else:
            new.append(body[i]); i += 1
    a["body"] = new
    if rest: restore(a, new, rest)
    return len(pics) - len(rest)


def restore(a, body, pics):
    if not pics: return 0
    at = next((i for i, b in enumerate(body) if b.get("type") in ("point", "rina")), len(body))
    title = "そのほかの画像"
    body.insert(at, {"type": "gallery", "title": title, "items": pics})
    a["body"] = body
    return 0


def main():
    for path in sys.argv[1:]:
        ed = json.load(open(path, encoding="utf-8"))
        moved = stories = 0
        for a in ed.get("articles", []):
            n = place(a)
            if n: moved += n; stories += 1
        json.dump(ed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{path}: placed {moved} pictures in the text of {stories} stories")


if __name__ == "__main__":
    main()
