"""Find official images for stories that have few of them (runs on GitHub Actions).

usage: python3 tools/find_official_images.py --dates 2026-11-08[,2026-11-07...] [--extra imgjobs/extra.json] [--max-press 1] --out out

Why: in the daily scheduled session many official pages cannot be opened, so stories end up
with no official picture. The Actions runner can open them. For every story with at most
--max-press official images it:
 1. opens the story's refs (news articles) and collects links that point to the company's own
    pages (press release, PR TIMES, newsroom, product page, official blog, store page),
 2. adds any refs that are already official pages and any pages listed in --extra
    ({"<story id>": ["https://official page", ...]} -- found with WebSearch),
 3. opens those pages and lists their pictures (og:image + pictures in the main text),
 4. downloads each picture with the public site as Referer (so it can be shown there),
    keeps only big enough ones, drops logos/icons/banners and pictures shared by several
    stories (site-wide share images), removes near-duplicates,
 5. writes out/candidates.json and contact sheets out/sheet_NN.jpg (one row per story:
    "row label" + numbered thumbnails) so a person/agent can pick the good ones.
Nothing in data/ is changed here. Picks are merged later with tools/pick_official_images.py.
"""
import argparse, concurrent.futures as cf, glob, io, json, os, re, sys, time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
REFERER = "https://rina-tech-news.pages.dev/"
NEWS = ("itmedia.co.jp", "impress.co.jp", "mynavi.jp", "gizmodo.jp", "nikkei.com", "techcrunch.com", "theverge.com",
        "arstechnica.com", "venturebeat.com", "reuters.com", "4gamer.net", "famitsu.com", "dengekionline.com",
        "ecnomikata.com", "cnet.com", "publickey1.jp", "sorae.info", "engadget.com", "ascii.jp", "gigazine.net",
        "zdnet.com", "bloomberg", "nhk.or.jp", "asahi.com", "yomiuri.co.jp", "mainichi.jp", "sankei.com",
        "nikkansports", "yahoo.co.jp", "livedoor", "phileweb.com", "gamespark.jp", "inside-games.jp",
        "automaton-media.com", "wired.jp", "wired.com", "businessinsider", "forbesjapan", "toyokeizai.net",
        "diamond.jp", "president.jp", "keitai", "androidheadlines.com", "9to5", "macrumors.com", "theguardian.com",
        "nytimes.com", "cnbc.com", "axios.com", "zenn.dev", "qiita.com", "note.com", "kakaku", "zaikei.co.jp",
        "ismcdn.jp", "j-cast.com", "response.jp", "jiji.com", "kyodo", "techno-edge.net", "hashout.jp", "saiganak.com",
        "commercepick.com", "sbbit.jp", "smhn.info", "jetstream.blog", "dempa-digital.com", "tsuhannews.jp",
        "realsound.jp", "thenextweb.com", "dev.to", "medium.com", "gamebiz.jp", "game-watch", "itmedia",
        "netshop.impress", "cnn.com", "bbc.", "wsj.com", "ft.com", "theinformation.com", "semafor.com", "zdnet",
        "tomshardware.com", "pcgamer.com", "ign.com", "gamesindustry.biz", "eurogamer", "polygon.com", "kotaku",
        "news.mynavi", "atmarkit", "watch.impress", "jbpress", "newspicks", "biz-journal", "sbcr.jp", "appbank.net",
        "iphone-mania.jp", "gori.me", "ascii.", "excite.co.jp", "goo.ne.jp", "msn.com", "news.google", "lifehacker",
        "dime.jp", "getnavi.jp", "monoist", "eetimes", "nikkeibp", "xtech", "japan.cnet", "techcrunch", "venturebeat",
        "the-decoder.com", "siliconangle.com", "theregister.com", "neowin.net", "windowscentral.com", "androidpolice",
        "9to5google", "9to5mac", "appleinsider", "digitaltrends", "mashable", "cnbc", "fortune.com", "time.com",
        "spaceflightnow", "space.com", "nasaspaceflight", "uchubiz.com", "sorae", "itmedia.co.jp", "ledge.ai", "aismiley",
        "bcnretail.com", "av.watch", "markezine.jp", "netkeizai.com", "ryutsuu.biz", "tsuhan-shinbun", "senken.co.jp",
        "wwdjapan.com", "fashionsnap.com", "stereonet.com", "game8.jp", "biggo", "notebookcheck",
        "interestingengineering.com", "gamebiz.jp", "newswitch.jp", "compositesworld.com", "gaming-style", "gamewith.jp",
        "appmedia.jp", "altema.jp", "dotesports", "gamerant.com", "thurrott.com", "winaero.com", "bleepingcomputer.com",
        "securityweek.com", "thehackernews.com", "darkreading.com", "scan.netsecurity.ne.jp", "security-next.com",
        "cybersecurity-jp.com", "itmedia", "nordot.app", "news.yahoo", "tbsnews", "fnn.jp", "ntv.co.jp", "tv-asahi",
        "sponichi", "oricon.co.jp", "natalie.mu", "animatetimes.com", "gamer.ne.jp", "gamespot.com", "videogameschronicle",
        "insider-gaming", "rockpapershotgun", "pocketgamer", "androidauthority", "gsmarena.com", "phonearena", "xda-developers")
# press-release services: their pages count as official
PRESS = ("prtimes.jp", "atpress.ne.jp", "value-press.com", "dreamnews.jp", "newscast.jp", "businesswire.com",
         "prnewswire.com", "globenewswire.com", "kyodonewsprwire.jp")
SKIP_LINK = ("twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com", "youtu.be", "line.me", "lin.ee",
             "google.com", "goo.gl", "bit.ly", "amazon.co.jp", "amazon.com", "amzn", "rakuten.co.jp", "a8.net",
             "valuecommerce", "linksynergy", "hatena", "getpocket", "linkedin.com", "tiktok.com", "wikipedia.org",
             "doubleclick", "googlesyndication", "adservice", "taboola", "outbrain", "zucks", "logly", "popin",
             "microad", "i-mobile", "gstatic.com", "googletagmanager", "addtoany", "threads.net", "bsky.app",
             "pinterest", "reddit.com", "discord.gg", "t.co", "feedly", "apple.news", "flipboard", "smartnews",
             "creativecommons.org", "w3.org", "schema.org", "accounts.", "akamaized", "cloudfront.net")
PATH_HINT = re.compile(r"press|news|release|newsroom|blog|topics|info|announce|product|item|lineup|ir/|/en/|/ja/|"
                       r"campaign|event|games?/|special|store|lp/|series|model|story|stories|article", re.I)
BAD_IMG = re.compile(r"logo|icon|favicon|bnr|banner|btn|button|sns|share|social|sprite|avatar|profile|author|"
                     r"thumb_?s\b|noimage|no_image|placeholder|loading|spacer|blank|pixel|badge|qr|arrow|bg_|"
                     r"header|footer|common/|/ad/|ads/|emoji|ogp?_?default|default_?og|og-default|site_?og", re.I)
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})


def host(u):
    try: return urlparse(u).netloc.lower().split(":")[0]
    except Exception: return ""


DOMAIN = re.compile(r"\.[a-z]{2,}$")


def match(u, names):
    """domain-like names (example.com) must be the host or a parent of it; other names are substrings."""
    h = host(u); low = u.lower()
    for n in names:
        if DOMAIN.search(n) and "/" not in n:
            if h == n or h.endswith("." + n): return True
        elif n in (h if "/" not in n else low):
            return True
    return False


def is_news(u):
    if is_press(u): return False
    return match(u, NEWS)


def is_press(u):
    return match(u, PRESS)


def get(url, timeout=20, referer=None, stream=False):
    hd = {"Referer": referer} if referer else {}
    for i in range(2):
        try:
            r = S.get(url, timeout=timeout, headers=hd, stream=stream, allow_redirects=True)
            return r
        except Exception:
            time.sleep(1.5)
    return None


HTML_CACHE = {}


def page(url):
    if url in HTML_CACHE: return HTML_CACHE[url]
    r = get(url)
    soup = None
    if r is not None and r.status_code == 200 and "html" in r.headers.get("content-type", ""):
        r.encoding = r.apparent_encoding if (r.encoding or "").lower() in ("iso-8859-1", "") else r.encoding
        try: soup = BeautifulSoup(r.text, "html.parser"); soup._final = r.url
        except Exception: soup = None
    HTML_CACHE[url] = soup
    return soup


def main_box(soup):
    cands = soup.select("article, [itemprop=articleBody], #cmsBody, .article-body, .articleBody, .entry-content, "
                        ".post-content, .main-contents, #main-contents, .article_body, .news-body, .release-body, "
                        ".rich-text, main, #main, .content, #content")
    best, score = None, 0
    for c in cands:
        s = sum(len(p.get_text(strip=True)) for p in c.find_all("p"))
        if s > score: best, score = c, s
    return best if best is not None and score > 200 else soup


def official_links(news_url, title_tokens):
    soup = page(news_url)
    if soup is None: return []
    base = getattr(soup, "_final", news_url)
    box = main_box(soup)
    out = {}
    for a in box.find_all("a", href=True):
        u = urljoin(base, a["href"].strip()).split("#")[0]
        if not u.startswith("http"): continue
        h = host(u); low = u.lower()
        if not h or h == host(base) or match(u, SKIP_LINK) or re.search(r"cookie|privacy|onetrust|trustarc", low): continue
        if is_news(u): continue
        if re.search(r"\.(pdf|zip|mp4|jpg|jpeg|png|gif|webp)(\?|$)", low): continue
        sc = 0
        if is_press(u): sc += 5
        if any(t in h or t in low for t in title_tokens): sc += 3
        if PATH_HINT.search(urlparse(u).path or ""): sc += 1
        text = a.get_text(" ", strip=True)
        if re.search(r"公式|プレスリリース|ニュースリリース|発表|リリース|製品|詳細|特設|ストア|サイト|official|press|announce|blog", text, re.I): sc += 2
        if sc >= 2: out[u] = max(out.get(u, 0), sc)
    return [u for u, _ in sorted(out.items(), key=lambda x: -x[1])][:4]


def credit_of(soup, url):
    t = soup.title.get_text(strip=True) if soup.title else ""
    m = re.search(r"([^｜|]+?)の(?:プレスリリース|ニュースリリース)", t)
    if m and is_press(url): return m.group(1).strip()
    for k in ("og:site_name", "application-name"):
        m = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
        if m and m.get("content"): return m["content"].strip()[:40]
    return host(url).replace("www.", "")


def page_images(url):
    soup = page(url)
    if soup is None: return []
    base = getattr(soup, "_final", url)
    cred = credit_of(soup, base)
    found = []
    for k in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
        m = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
        if m and m.get("content"): found.append((urljoin(base, m["content"].strip()), ""))
    box = main_box(soup)
    for im in box.find_all(["img", "source"]):
        src = None
        for at in ("data-src", "data-original", "data-lazy-src", "src"):
            v = im.get(at)
            if v and not v.startswith("data:"): src = v; break
        ss = im.get("srcset") or im.get("data-srcset")
        if ss:
            best, bw = None, 0
            for part in ss.split(","):
                bits = part.strip().split()
                if not bits: continue
                w = int(re.sub(r"\D", "", bits[1]) or 0) if len(bits) > 1 and bits[1].endswith("w") else 1
                if w >= bw: best, bw = bits[0], w
            if best: src = best
        if not src: continue
        found.append((urljoin(base, src.strip()), (im.get("alt") or "").strip()[:80]))
    out, seen = [], set()
    for src, alt in found:
        if not src.startswith("https://") or src in seen: continue
        if src.lower().split("?")[0].endswith((".svg", ".gif", ".ico")): continue
        if BAD_IMG.search(src): continue
        seen.add(src); out.append({"src": src, "alt": alt, "page": base, "credit": cred})
    return out[:14]


def ahash(img):
    g = img.convert("L").resize((8, 8))
    px = list(g.getdata()); m = sum(px) / 64
    return sum(1 << i for i, p in enumerate(px) if p > m)


def check_img(c):
    r = get(c["src"], timeout=25, referer=REFERER, stream=True)
    if r is None or r.status_code != 200: return None
    ct = r.headers.get("content-type", "")
    if not ct.startswith("image/") or "svg" in ct: return None
    # browsers refuse to show pictures marked same-origin/same-site on our site
    if r.headers.get("cross-origin-resource-policy", "").lower() in ("same-origin", "same-site"): return None
    data = b""
    for chunk in r.iter_content(65536):
        data += chunk
        if len(data) > 12_000_000: return None
    if len(data) < 12_000: return None
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception: return None
    w, h = im.size
    if w < 500 or h < 280 or not (0.4 <= w / h <= 3.2): return None
    if im.mode not in ("RGB", "L"): im = im.convert("RGB")
    th = im.copy(); th.thumbnail((222, 138))
    return dict(c, w=w, h=h, hash=ahash(im), thumb=th)


def press_count(a):
    n = 1 if (a.get("image") or {}).get("kind") == "press" else 0
    for b in a.get("body", []):
        if b.get("type") == "img" and b.get("kind") == "press": n += 1
        if b.get("type") == "gallery": n += sum(1 for x in b.get("items", []) if x.get("kind") == "press")
    return n


def existing_srcs(a):
    s = {(a.get("image") or {}).get("src")}
    for b in a.get("body", []):
        if b.get("type") == "img": s.add(b.get("src"))
        if b.get("type") == "gallery": s |= {x.get("src") for x in b.get("items", [])}
    return s


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def sheets(rows, out):
    """rows: list of (label, [cand...]) -> sheet_NN.jpg, 12 rows per sheet, up to 8 pictures per row"""
    CW, CH, LW, PER = 230, 172, 90, 12
    f1, f2 = font(30), font(22)
    names = []
    for k in range(0, len(rows), PER):
        part = rows[k:k + PER]
        sh = Image.new("RGB", (LW + CW * 8, CH * len(part)), "white")
        d = ImageDraw.Draw(sh)
        for r, (label, cs) in enumerate(part):
            y = r * CH
            d.rectangle([0, y, LW - 4, y + CH - 4], fill=(18, 70, 196))
            d.text((10, y + 60), label, fill="white", font=f1)
            for i, c in enumerate(cs[:8]):
                x = LW + i * CW
                t = c["thumb"]
                sh.paste(t, (x + (CW - 8 - t.width) // 2, y + (CH - 30 - t.height) // 2))
                d.rectangle([x, y + CH - 30, x + 34, y + CH - 4], fill=(255, 138, 0))
                d.text((x + 6, y + CH - 29), str(i + 1), fill="black", font=f2)
                d.text((x + 40, y + CH - 27), f"{c['w']}x{c['h']}", fill=(80, 80, 80), font=font(16))
            d.line([0, y + CH - 2, sh.width, y + CH - 2], fill=(200, 200, 200), width=2)
        n = os.path.join(out, f"sheet_{k // PER + 1:02d}.jpg")
        sh.save(n, quality=85); names.append(n)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True)
    ap.add_argument("--extra", default="")
    ap.add_argument("--max-press", type=int, default=1)
    ap.add_argument("--only-extra", action="store_true", help="only stories listed in --extra")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    extra = json.load(open(a.extra, encoding="utf-8")) if a.extra and os.path.exists(a.extra) else {}
    dates = [d.strip() for d in a.dates.split(",") if d.strip()]
    if dates == ["all"]:
        dates = sorted(os.path.basename(f)[:-5] for f in glob.glob("data/20*.json") if re.fullmatch(r"20\d\d-\d\d-\d\d(-am|-pm)?\.json", os.path.basename(f)))
    stories = []
    for d in dates:
        p = f"data/{d}.json"
        if not os.path.exists(p): continue
        for s in json.load(open(p, encoding="utf-8"))["articles"]:
            if a.only_extra and s["id"] not in extra: continue
            if press_count(s) > a.max_press and s["id"] not in extra: continue
            stories.append((d, s))
    print(f"stories: {len(stories)}", flush=True)

    def pages_for(item):
        d, s = item
        toks = {t.lower() for t in LATIN.findall(s.get("title", "") + " " + s.get("id", "")) if len(t) >= 3}
        toks -= {"the", "and", "for", "with", "app", "pro", "max", "new", "ultra", "plus", "mini", "air"}
        refs = [r["url"] if isinstance(r, dict) else r for r in s.get("refs", [])]
        if s.get("source_url") and s["source_url"] not in refs: refs.insert(0, s["source_url"])
        pages = list(extra.get(s["id"], []))
        for u in refs:
            if not is_news(u): pages.append(u)
        for u in refs:
            if is_news(u):
                pages += official_links(u, toks)
        seen, out = set(), []
        for u in pages:
            if u not in seen: seen.add(u); out.append(u)
        return out[:7]

    with cf.ThreadPoolExecutor(12) as ex:
        plist = list(ex.map(pages_for, stories))
    jobs = []
    for (d, s), pages in zip(stories, plist):
        for u in pages: jobs.append((s["id"], u))
    print(f"official pages: {len(jobs)}", flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        imgs = list(ex.map(lambda j: page_images(j[1]), jobs))
    per = {}
    for (sid, u), ims in zip(jobs, imgs):
        per.setdefault(sid, []).extend(ims)
    flat = [(sid, c) for sid, cs in per.items() for c in cs]
    print(f"pictures to check: {len(flat)}", flush=True)
    with cf.ThreadPoolExecutor(16) as ex:
        checked = list(ex.map(lambda x: check_img(x[1]), flat))
    good = {}
    for (sid, _), c in zip(flat, checked):
        if c: good.setdefault(sid, []).append(c)
    # pictures that appear for several stories are site-wide share images
    owners = {}
    for sid, cs in good.items():
        for c in cs: owners.setdefault(c["hash"], set()).add(sid)
    result, rows = {}, []
    for d, s in stories:
        have = existing_srcs(s)
        cs, hs = [], []
        for c in good.get(s["id"], []):
            if c["src"] in have or len(owners.get(c["hash"], ())) > 1: continue
            if any(bin(c["hash"] ^ h).count("1") <= 6 for h in hs): continue
            hs.append(c["hash"]); cs.append(c)
        cs = cs[:8]
        if not cs: continue
        label = f"R{len(rows) + 1}"
        rows.append((label, cs))
        result[s["id"]] = {"row": label, "date": d, "title": s.get("title", ""), "summary": s.get("summary", ""),
                           "imgs": [{"n": i + 1, "src": c["src"], "page": c["page"], "credit": c["credit"],
                                     "alt": c["alt"], "w": c["w"], "h": c["h"]} for i, c in enumerate(cs)]}
    names = sheets(rows, a.out)
    json.dump(result, open(os.path.join(a.out, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    none = [s["id"] for d, s in stories if s["id"] not in result]
    json.dump({"no_candidates": none, "pages": {s["id"]: p for (d, s), p in zip(stories, plist)}},
              open(os.path.join(a.out, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"stories with candidates: {len(result)} / {len(stories)}; sheets: {len(names)}")


if __name__ == "__main__":
    main()
