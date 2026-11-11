"""Fetch every worker's news listings AND the article pages on GitHub, before the edition workers start (2026-11-12, Issue #7).
The workers then read local files only: a worker that opens a page it did not get from its own WebSearch makes the
session ask the user for permission, which the user does not want.
usage: python3 tools/fetch_news.py <edition id> <out dir> [per_site]
in:  tools/news_sites.json  {worker: {"period_h": 72, "sites": [{"name", "urls": [feed or page, fallbacks...]}]}}
out: <out>/<worker>/index.md   one line per story: id | published | site | title | url
     <out>/<worker>/<id>.txt   URL, TITLE, PUBLISHED, OG_IMAGE, IMAGES (url | alt), then the page text (up to 15000 chars)
     <out>/report.md           which site gave how many stories, and the failures (wrong feed url, refused page)"""
import concurrent.futures as cf, datetime as dt, json, os, re, sys, time
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
import feedparser, requests
from bs4 import BeautifulSoup

ED, OUT = sys.argv[1], sys.argv[2]
PER_SITE = int(sys.argv[3]) if len(sys.argv) > 3 else 12
CFG = {k: v for k, v in json.load(open("tools/news_sites.json", encoding="utf-8")).items() if not k.startswith("_")}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "ja,en;q=0.8"}
NOW = dt.datetime.now(dt.timezone.utc)
JST = dt.timezone(dt.timedelta(hours=9))
os.makedirs(OUT, exist_ok=True)


def get(u, timeout=25):
    r = requests.get(u, headers=UA, timeout=timeout)
    r.raise_for_status()
    if r.encoding in (None, "ISO-8859-1"): r.encoding = r.apparent_encoding
    return r


def when(s):
    if not s: return None
    for f in (parsedate_to_datetime, dt.datetime.fromisoformat):
        try:
            d = f(s.strip().replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=JST)
        except Exception: pass
    m = re.search(r"(20\d\d)[-/.年](\d{1,2})[-/.月](\d{1,2})", s)
    return dt.datetime(int(m[1]), int(m[2]), int(m[3]), 12, tzinfo=JST) if m else None


def from_feed(text):
    f = feedparser.parse(text)
    out = []
    for e in f.entries:
        d = None
        for k in ("published_parsed", "updated_parsed", "created_parsed"):
            if e.get(k): d = dt.datetime(*e[k][:6], tzinfo=dt.timezone.utc); break
        if e.get("link") and e.get("title"): out.append({"title": re.sub(r"\s+", " ", e.title).strip(), "url": e.link, "date": d})
    return out


def from_page(u, html):
    """a page: use its own feed if it names one, else list its article-looking links"""
    s = BeautifulSoup(html, "html.parser")
    for l in s.find_all("link", rel="alternate"):
        if "rss" in (l.get("type") or "") or "atom" in (l.get("type") or ""):
            try:
                items = from_feed(get(urljoin(u, l["href"])).text)
                if len(items) >= 3: return items, "feed:" + urljoin(u, l["href"])
            except Exception: pass
    host, seen, out = urlparse(u).netloc, set(), []
    for a in s.find_all("a", href=True):
        h = urljoin(u, a["href"]).split("#")[0]
        t = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        p = urlparse(h)
        if p.netloc != host or h in seen or len(t) < 12 or len(p.path) < 8 or h.rstrip("/") == u.rstrip("/"): continue
        if not re.search(r"\d{4,}|/20\d\d|/news/|/article|/press|/blog/|/topics/", p.path): continue
        seen.add(h); out.append({"title": t[:120], "url": h, "date": when(t)})
    return out[:40], "page"


def listing(site):
    errs = []
    for u in site["urls"]:
        try:
            r = get(u)
            body = r.text
            ct = r.headers.get("content-type", "")
            if "xml" in ct or "rss" in ct or body.lstrip()[:200].lstrip("﻿").startswith("<?xml") or "<rss" in body[:500] or "<feed" in body[:500]:
                items, how = from_feed(body), "feed"
            elif "json" in ct:
                j = r.json(); j = j if isinstance(j, list) else next((v for v in j.values() if isinstance(v, list)), [])
                items = [{"title": x.get("title", ""), "url": urljoin(u, x.get("url") or x.get("link") or ""), "date": when(x.get("date") or x.get("published") or "")} for x in j if isinstance(x, dict)]
                how = "json"
            else:
                items, how = from_page(u, body)
            if len(items) >= 3: return items, f"{how} {u}", errs
            errs.append(f"{u}: only {len(items)} items")
        except Exception as e:
            errs.append(f"{u}: {type(e).__name__} {str(e)[:80]}")
    return [], "", errs


def page(u):
    try:
        r = get(u, 30)
        if "pdf" in r.headers.get("content-type", ""): return {"ok": False, "text": "(PDF)"}
        s = BeautifulSoup(r.text, "html.parser")
        meta = lambda *ks: next((m.get("content") for k in ks for m in s.find_all("meta", attrs={"property": k}) + s.find_all("meta", attrs={"name": k}) if m.get("content")), "")
        pub = meta("article:published_time", "og:published_time", "pubdate", "date", "dc.date", "DC.date.issued")
        if not pub:
            t = s.find("time"); pub = (t.get("datetime") or t.get_text(strip=True)) if t else ""
        og = meta("og:image", "twitter:image")
        for t in s(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "iframe"]): t.decompose()
        body = s.find("article") or s.find("main") or s.body or s
        imgs, seen = [], set()
        for im in body.find_all("img"):
            src = im.get("data-src") or im.get("data-original") or im.get("src") or ""
            if not src or src.startswith("data:"): continue
            src = urljoin(u, src)
            if src in seen or re.search(r"logo|icon|avatar|banner|sprite|blank|pixel|ads?[/_.]", src, re.I): continue
            seen.add(src); imgs.append(f"{src} | {(im.get('alt') or '').strip()[:80]}")
        text = re.sub(r"\n{3,}", "\n\n", body.get_text("\n", strip=True))
        return {"ok": True, "pub": pub, "og": og, "imgs": imgs[:15], "text": text[:15000]}
    except Exception as e:
        return {"ok": False, "text": f"(could not open: {type(e).__name__} {str(e)[:80]})"}


t0 = time.time()
jobs = [(w, i, s) for w, c in CFG.items() for i, s in enumerate(c["sites"])]
with cf.ThreadPoolExecutor(12) as ex: lists = dict(zip([(w, i) for w, i, _ in jobs], ex.map(lambda j: listing(j[2]), jobs)))

report, picked = [f"# ニュース一覧の取得 {ED}（{dt.datetime.now(JST):%m-%d %H:%M}）", ""], {}
for w, c in CFG.items():
    cut = NOW - dt.timedelta(hours=c["period_h"])
    rows = []
    for i, s in enumerate(c["sites"]):
        items, how, errs = lists[(w, i)]
        fresh = [x for x in items if not x["date"] or x["date"] >= cut]
        fresh.sort(key=lambda x: x["date"] or NOW, reverse=True)
        fresh = fresh[:PER_SITE]
        rows += [dict(x, site=s["name"]) for x in fresh]
        report.append(f"- {w} {s['name']}: {len(fresh)}本（全{len(items)}） {how}" + ("".join(f"\n  - 失敗 {e}" for e in errs) if errs else ""))
    seen = set(); picked[w] = [r for r in rows if not (r["url"] in seen or seen.add(r["url"]))]

urls = sorted({r["url"] for rs in picked.values() for r in rs})
with cf.ThreadPoolExecutor(16) as ex: pages = dict(zip(urls, ex.map(page, urls)))

for w, rows in picked.items():
    d = os.path.join(OUT, w); os.makedirs(d, exist_ok=True)
    idx = [f"# {w} の候補（{ED}、GitHub で取得済み。ページを開かずにこのフォルダのファイルを読む）", "id | 公開 | サイト | 見出し | URL"]
    for n, r in enumerate(rows, 1):
        p, sid = pages[r["url"]], f"{w}-{n:02d}"
        pub = r["date"].astimezone(JST).strftime("%Y-%m-%d %H:%M") if r["date"] else (p.get("pub") or "?")
        idx.append(f"{sid} | {pub} | {r['site']} | {r['title']} | {r['url']}" + ("" if p["ok"] else " | （本文なし）"))
        with open(os.path.join(d, sid + ".txt"), "w", encoding="utf-8") as f:
            f.write(f"URL: {r['url']}\nTITLE: {r['title']}\nSITE: {r['site']}\nPUBLISHED: {pub} (page: {p.get('pub', '')})\nOG_IMAGE: {p.get('og', '')}\nIMAGES:\n"
                    + "".join(f"- {x}\n" for x in p.get("imgs", [])) + "\nTEXT:\n" + p["text"] + "\n")
    open(os.path.join(d, "index.md"), "w", encoding="utf-8").write("\n".join(idx) + "\n")

ok = sum(1 for p in pages.values() if p["ok"])
report += ["", f"記事ページ {ok}/{len(urls)} 本の本文を取得。{time.time() - t0:.0f}秒"]
open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")
print("\n".join(report))
