"""Mechanical checks for articles written or changed by Codex (2026-11-14, the user's request: move work from Claude to
ChatGPT Codex to save Claude usage, without lowering quality). Anything that fails a check is NOT used: the original stays.
Standard library only.

  prep-fill <edition.json> <research/ED dir> <jobs dir> <n>   job folders for the 書き足し (per story: article.json, pages.txt,
                                                              refs_allowed.txt) in <jobs>/<k>/<id>/
  prep-fact <edition.json> <factcheck/ED dir> <jobs dir> <n>  job folders for the 事実の点検 (article.json, pages.txt)
  collect   fill|fact <jobs dir> <out dir>                   checks every <job>/out.json against <job>/article.json:
                                                              good ones -> <out>/<id>.json, plus <out>/report.md (and for
                                                              fact: <out>/changes.md made from each job's changes.txt)
  art       fill|fact <orig.json> <new.json> [allowed.txt]    check one article (prints problems; exit 1 if rejected)
  writer    <worker.json> <news/ED/worker dir> <used.txt> <edition> <out.json>
                                                              checks a new worker file (codex-write.yml): bad stories are
                                                              dropped, the rest go to <out.json>; report on stdout
Rejected when: invalid JSON; id/category/image/source_url/published changed; pictures added or removed; refs > 6 or not https
or (fill) not one of the fetched pages with status 200 / (fact) not one of the old refs; required blocks missing; a paragraph
> 200 chars; rina > 120 chars; backstage phrases (style.md 8); a URL in the text; text much shorter than before.
Smaller things (summary > 50 chars, sentence > 60 chars, stat value not in the body) are only warnings.
"""
import json, os, re, shutil, sys, datetime

BACKSTAGE = ["見つけられず", "見つけられません", "今回読んだ", "参照した", "参照ページ", "私は", "私が", "私の", "読んだ記事",
             "元の記事は", "他の記事には載って", "ほかの記事には載って", "取得できな", "pages.txt", "article.json"]
# reprints / aggregators: never a ref (tools/README.md 「Codexの調査」: まとめサイト・転載は使わない)
AGGREGATOR = ("news.yahoo.co.jp", "nordot.app", "news.livedoor.com", "msn.com", "excite.co.jp", "news.goo.ne.jp", "smartnews.com",
              "newspicks.com", "gunosy.com", "antenna.jp", "togetter.com", "matome", "2ch", "5ch", "news.google.", "infoseek.co.jp",
              "news.biglobe.ne.jp", "dmenu", "auone.jp", "line.me", "flipboard.com", "headtopics.com", "newsbreak.com", "ground.news")
TEXT_TYPES = ("keys", "p", "h", "point", "rina", "stat")


def host(u):
    m = re.match(r"https?://([^/]+)", u or "")
    return m.group(1).lower() if m else ""


def norm(u):
    """same page: ignore tracking parameters (?p1=..., ?trk=...), #fragments and a trailing slash"""
    return re.sub(r"[?#].*$", "", str(u or "")).rstrip("/")


def is_aggregator(u):
    h = host(u)
    return any(a in h for a in AGGREGATOR)


def texts(a):
    """every reader-visible text of an article, as (where, text)"""
    out = [("title", a.get("title", "")), ("summary", a.get("summary", ""))]
    for i, b in enumerate(a.get("body", []) if isinstance(a.get("body"), list) else []):
        t = b.get("type") if isinstance(b, dict) else None
        if t in ("p", "h", "rina"): out.append((f"{t}{i}", str(b.get("text", ""))))
        elif t in ("keys", "point"): out += [(f"{t}{i}", str(x)) for x in b.get("items", [])]
        elif t == "stat": out += [(f"stat{i}", f"{x.get('value', '')} {x.get('label', '')}") for x in b.get("items", []) if isinstance(x, dict)]
        elif t == "img": out.append((f"caption{i}", str(b.get("caption", ""))))
        elif t == "gallery": out += [(f"caption{i}", str(x.get("caption", ""))) for x in b.get("items", []) if isinstance(x, dict)]
    return out


def pics(a):
    s = []
    if isinstance(a.get("image"), dict): s.append(a["image"].get("src"))
    for b in a.get("body", []) if isinstance(a.get("body"), list) else []:
        if not isinstance(b, dict): continue
        if b.get("type") == "img": s.append(b.get("src"))
        if b.get("type") == "gallery": s += [x.get("src") for x in b.get("items", []) if isinstance(x, dict)]
    return s


def sentences(t):
    return [x for x in re.split(r"(?<=[。！？])|\n", t) if x.strip()]


def problems(a):
    """-> (hard, soft): lists of short problem strings. The text is part of each string so that the same problem in the
    original and in the new version compare equal."""
    hard, soft = [], []
    if not isinstance(a, dict): return ["not an object"], []
    for k in ("id", "category", "title", "summary", "body", "source_url"):
        if not a.get(k): hard.append(f"missing {k}")
    body = a.get("body") if isinstance(a.get("body"), list) else []
    types = [b.get("type") if isinstance(b, dict) else None for b in body]
    if None in types: hard.append("a body block is not an object")
    if not types or types[0] != "keys": hard.append("body does not start with keys")
    if types.count("keys") != 1: hard.append(f"keys blocks: {types.count('keys')}")
    if not (3 <= types.count("h") <= 5): hard.append(f"h sections: {types.count('h')}")
    if types.count("stat") != 1: hard.append(f"stat blocks: {types.count('stat')}")
    if types.count("point") != 1: hard.append(f"point blocks: {types.count('point')}")
    if types.count("rina") != 1 or types[-1:] != ["rina"]: hard.append("rina must be the one last block")
    if types.count("p") < 4: hard.append(f"only {types.count('p')} paragraphs")
    for b in body:
        if not isinstance(b, dict): continue
        t = b.get("type")
        if t == "keys" and len(b.get("items", [])) != 3: hard.append(f"keys items: {len(b.get('items', []))}")
        if t == "point" and not (3 <= len(b.get("items", [])) <= 4): soft.append(f"point items: {len(b.get('items', []))}")
        if t == "stat" and not (2 <= len(b.get("items", [])) <= 3): soft.append(f"stat items: {len(b.get('items', []))}")
        if t == "p":
            x = str(b.get("text", ""))
            if len(x) > 200: hard.append(f"paragraph {len(x)} chars: {x[:30]}")
            for s in sentences(x):
                if len(s) > 60: soft.append(f"sentence {len(s)} chars: {s[:30]}")
        if t == "h" and not (4 <= len(str(b.get("text", ""))) <= 20): soft.append(f"h length: {b.get('text')}")
        if t == "rina":
            x = str(b.get("text", ""))
            if len(x) > 120: hard.append(f"rina {len(x)} chars")
            if re.match(r"^\s*【?りなの見方", x): hard.append("rina starts with its heading")
    for where, x in texts(a):
        for w in BACKSTAGE:
            if w in x: hard.append(f"backstage phrase 「{w}」 in {where}: {x[:30]}")
        if re.search(r"https?://|www\.", x): hard.append(f"URL in text {where}: {x[:30]}")
    if len(a.get("summary", "")) > 50: soft.append(f"summary {len(a.get('summary', ''))} chars")
    if len(a.get("title", "")) > 40: hard.append(f"title {len(a.get('title', ''))} chars")
    elif len(a.get("title", "")) > 32: soft.append(f"title {len(a.get('title', ''))} chars")
    refs = a.get("refs", [])
    if not isinstance(refs, list): hard.append("refs is not a list"); refs = []
    if len(refs) > 6: hard.append(f"refs: {len(refs)} (max 6)")
    urls = []
    for r in refs:
        if not isinstance(r, dict) or not str(r.get("url", "")).startswith("https://") or not r.get("name"):
            hard.append(f"bad ref: {str(r)[:60]}"); continue
        urls.append(r["url"])
        if is_aggregator(r["url"]): hard.append(f"aggregator/reprint ref: {host(r['url'])}")
    if len(urls) != len(set(urls)): hard.append("duplicate refs")
    ps = [p for p in pics(a) if p]
    if len(ps) != len(set(ps)): hard.append("a picture appears twice")
    # stat numbers must be explained in the body (style.md 1-5)
    plain = " ".join(x for w, x in texts(a) if not w.startswith("stat"))
    for b in body:
        if isinstance(b, dict) and b.get("type") == "stat":
            for it in b.get("items", []):
                nums = re.findall(r"\d[\d,.]*", str(it.get("value", "")) if isinstance(it, dict) else "")
                if any(n not in plain for n in nums): soft.append(f"stat value not in body: {it.get('value')}")
    return hard, soft


def textlen(a):
    return sum(len(x) for w, x in texts(a) if not w.startswith("caption"))


def pages_in(txt):
    """research/factcheck page file -> [(url, status, text)]"""
    out = []
    for part in re.split(r"(?m)^===== ", txt)[1:]:
        lines = part.split("\n")
        url = lines[0].strip()
        m = re.match(r"\((?:status (\d+)|failed)", lines[1] if len(lines) > 1 else "")
        st = int(m.group(1)) if m and m.group(1) else 0
        out.append((url, st, "\n".join(lines[2:])))
    return out


def compare(mode, old, new, allowed=()):
    """-> (rejected reasons, warnings)"""
    bad, warn = [], []
    if not isinstance(new, dict): return ["not a JSON object"], []
    for k in ("id", "category", "image", "source_url", "published"):
        if old.get(k) != new.get(k): bad.append(f"{k} changed")
    if sorted(p for p in pics(old) if p) != sorted(p for p in pics(new) if p): bad.append("pictures added or removed")
    oh, os_ = problems(old)
    nh, ns = problems(new)
    bad += [f"new problem: {p}" for p in nh if p not in oh]
    warn += [p for p in ns if p not in os_]
    oldrefs = [r.get("url") for r in old.get("refs", []) if isinstance(r, dict)]
    newrefs = [r.get("url") for r in new.get("refs", []) if isinstance(r, dict)]
    if oldrefs and oldrefs[0] == old.get("source_url") and newrefs[:1] != oldrefs[:1]: bad.append("source_url is no longer the first ref")
    if mode == "fill":
        for u in newrefs:
            if u not in oldrefs and norm(u) not in {norm(x) for x in allowed}: bad.append(f"ref not from a fetched page (status 200): {u}")
        missing = [u for u in oldrefs if u not in newrefs]
        if missing: bad.append(f"old refs removed: {missing}")
        if textlen(new) < textlen(old): bad.append(f"text got shorter ({textlen(old)} -> {textlen(new)})")
    else:
        for u in newrefs:
            if u not in oldrefs: bad.append(f"new ref in the fact check: {u}")
        if textlen(new) < 0.8 * textlen(old): bad.append(f"text cut by more than 20% ({textlen(old)} -> {textlen(new)})")
        ot, nt = [x for w, x in texts(old)], [x for w, x in texts(new)]
        changed = sum(1 for x in nt if x not in ot)
        if changed > max(6, 0.4 * len(ot)): bad.append(f"too many changes for a fact check: {changed} of {len(ot)} texts rewritten")
    return bad, warn


def load(p):
    try:
        return json.load(open(p, encoding="utf-8")), None
    except Exception as e:
        return None, f"invalid JSON: {e}"


def prep(mode, ed, src, jobs, n):
    arts = json.load(open(ed, encoding="utf-8"))["articles"]
    os.makedirs(jobs, exist_ok=True)
    picked = []
    for a in arts:
        f = os.path.join(src, a["id"] + ".txt")
        if not os.path.exists(f): continue
        pages = pages_in(open(f, encoding="utf-8", errors="replace").read())
        have = {r.get("url") for r in a.get("refs", []) if isinstance(r, dict)}
        if mode == "fill":   # only usable new pages: status 200, real text, not a reprint, not already a ref
            pages = [p for p in pages if 200 <= p[1] < 300 and len(p[2].strip()) > 200 and not is_aggregator(p[0]) and p[0] not in have]
            if not pages: continue
        picked.append((a, pages))
    for i, (a, pages) in enumerate(picked):
        d = os.path.join(jobs, str(i % n), a["id"]); os.makedirs(d, exist_ok=True)
        json.dump(a, open(f"{d}/article.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with open(f"{d}/pages.txt", "w", encoding="utf-8") as fh:
            for u, st, t in pages:
                fh.write(f"===== {u}\n(status {st})\n{t.strip()[:15000]}\n\n")
        if mode == "fill":
            open(f"{d}/refs_allowed.txt", "w").write("\n".join(u for u, st, t in pages) + "\n")
    for k in range(n): os.makedirs(os.path.join(jobs, str(k)), exist_ok=True)
    print(mode, "jobs:", len(picked), "of", len(arts), "stories")


def collect(mode, jobs, out):
    os.makedirs(out, exist_ok=True)
    rows, changes, used = [], [], 0
    dirs = sorted(os.path.join(r, d) for r, ds, fs in os.walk(jobs) for d in ds if os.path.exists(os.path.join(r, d, "article.json")))
    for d in dirs:
        sid = os.path.basename(d)
        old = json.load(open(f"{d}/article.json", encoding="utf-8"))
        if not os.path.exists(f"{d}/out.json"): rows.append((sid, "未処理", "Codex wrote no out.json (timeout or error)")); continue
        new, err = load(f"{d}/out.json")
        if err: rows.append((sid, "却下", err)); continue
        allowed = open(f"{d}/refs_allowed.txt").read().split() if os.path.exists(f"{d}/refs_allowed.txt") else []
        bad, warn = compare(mode, old, new, allowed)
        if bad: rows.append((sid, "却下", "; ".join(bad))); continue
        if new == old: rows.append((sid, "変更なし", "")); continue
        json.dump(new, open(f"{out}/{sid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        used += 1
        info = f"{textlen(old)}→{textlen(new)}字, refs {len(old.get('refs', []))}→{len(new.get('refs', []))}"
        if mode == "fact": info += f", 書き換え{sum(1 for w, x in texts(new) if x not in [y for v, y in texts(old)])}か所"
        if warn: info += f"（注意{len(warn)}件: " + "; ".join(w.replace(chr(10), ' ')[:50] for w in warn[:2]) + "）"
        rows.append((sid, "採用", info))
        if mode == "fact" and os.path.exists(f"{d}/changes.txt"):
            c = open(f"{d}/changes.txt", encoding="utf-8").read().strip()
            if c: changes.append(f"## {sid}\n{c}\n")
    title = {"fill": "Codexの書き足し", "fact": "Codexの事実の点検"}[mode]
    rep = [f"# {title}：{used}本を採用（{len(rows)}本中）", "", "| 記事id | 結果 | 内容 |", "|---|---|---|"]
    rep += [f"| {s} | {r} | {w.replace('|', '/')} |" for s, r, w in rows]
    open(f"{out}/report.md", "w", encoding="utf-8").write("\n".join(rep) + "\n")
    if mode == "fact":
        open(f"{out}/changes.md", "w", encoding="utf-8").write(
            "# 事実の点検で直したところ（Codex）\n\n" + ("\n".join(changes) if changes else "直したところはありません。\n"))
    print("\n".join(rep))


def writer(src, news, used_txt, edition, out):
    cat = os.path.basename(news.rstrip("/")).split("_")[0]
    allowed_urls = set()
    for f in os.listdir(news):
        allowed_urls |= set(re.findall(r"https?://[^\s|<>\"'）)]+", open(os.path.join(news, f), encoding="utf-8", errors="replace").read()))
    allowed_urls = {u.rstrip(".,;") for u in allowed_urls}
    used = {ln.split("\t")[0].strip() for ln in open(used_txt, encoding="utf-8")} if os.path.exists(used_txt) else set()
    ed_day = datetime.date.fromisoformat(edition[:10])
    days = 3 if cat in ("ai", "mobile", "gadget", "service", "game") else 7
    items, err = load(src)
    if err or not isinstance(items, list):
        print("REJECTED:", err or "not a JSON array"); json.dump([], open(out, "w")); return 1
    keep = []
    for a in items:
        sid = a.get("id", "?") if isinstance(a, dict) else "?"
        hard, soft = problems(a)
        if isinstance(a, dict):
            if a.get("category") != cat: hard.append(f"category {a.get('category')} (worker is {cat})")
            if not str(sid).startswith(cat + "-"): hard.append("id must start with the category")
            for u in [a.get("source_url")] + [r.get("url") for r in a.get("refs", []) if isinstance(r, dict)] + pics(a):
                if u and u not in allowed_urls and u.replace("https://", "http://") not in allowed_urls:
                    hard.append(f"URL not in the news files: {u}")
            if a.get("source_url") in used: hard.append("already published (used.txt)")
            refs = [r.get("url") for r in a.get("refs", []) if isinstance(r, dict)]
            if refs[:1] != [a.get("source_url")]: hard.append("source_url must be the first ref")
            try:
                p = datetime.date.fromisoformat(str(a.get("published", ""))[:10])
                if not (0 <= (ed_day - p).days <= days): hard.append(f"published {p} is outside {days} days")
            except ValueError:
                hard.append("published is not YYYY-MM-DD")
        if hard: print(f"DROP {sid}: " + "; ".join(hard)); continue
        print(f"OK   {sid}" + (("  (warnings: " + "; ".join(soft) + ")") if soft else ""))
        keep.append(a)
    json.dump(keep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"kept {len(keep)} of {len(items)}")
    return 0 if keep else 1


if __name__ == "__main__":
    c = sys.argv[1]
    if c in ("prep-fill", "prep-fact"): prep(c[5:], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif c == "collect": collect(sys.argv[2], sys.argv[3], sys.argv[4])
    elif c == "art":
        old, new = json.load(open(sys.argv[3], encoding="utf-8")), load(sys.argv[4])
        allowed = open(sys.argv[5]).read().split() if len(sys.argv) > 5 else []
        bad, warn = (["invalid JSON: " + new[1]], []) if new[1] else compare(sys.argv[2], old, new[0], allowed)
        print("\n".join(["REJECTED: " + b for b in bad] + ["warning: " + w for w in warn]) or "OK")
        sys.exit(1 if bad else 0)
    elif c == "writer": sys.exit(writer(*sys.argv[2:7]))
    else: sys.exit(__doc__)
