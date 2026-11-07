"""Build the public site 「星餓りなのテックニュース」 from マイ夕刊 data.
usage: python3 tools/build_site.py [out_dir]   (default: site_dist)
Standard library only (runs on Cloudflare's build image).
Public rules: only official (press) images whose host is not a news site, no X posts,
every article gets its own page, sitemap/RSS for search engines.
"""
import json, glob, os, re, shutil, sys, html, datetime
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "site_dist")
CFG = json.load(open(os.path.join(ROOT, "site/config.json"), encoding="utf-8"))
ICONS = json.load(open(os.path.join(ROOT, "site/icons.json"), encoding="utf-8"))
BASE = (os.environ.get("SITE_URL") or CFG.get("base_url") or "").rstrip("/")
PREFIX = (os.environ.get("SITE_PREFIX") or "").rstrip("/")  # preview under a sub-path (e.g. /my-yukan/preview); also sets noindex
NAME = CFG["site_name"]
WD = "月火水木金土日"
E = lambda s: html.escape(str(s or ""), quote=True)

CATS = {  # id: (label, icon, css var)
    "ai": ("AI", "ai", "--ai"), "mobile": ("スマホ・パソコン", "phone", "--mobile"),
    "gadget": ("家電・ガジェット", "appliance", "--gadget"), "service": ("ネットサービス・アプリ", "globe", "--service"),
    "game": ("ゲーム", "game", "--game"), "ec": ("EC・決済", "cart", "--ec"),
    "future": ("宇宙・未来技術", "spark", "--future"), "other": ("その他", "chart", "--other")}
LEGACY = {"kaden": "gadget", "fukugyo": "ec"}
SLUG = {"ai": "ai", "mobile": "mobile", "gadget": "gadget", "service": "service", "game": "game", "ec": "ec", "future": "future", "other": "other"}
# images hosted on / found on news sites are not used on the public site
NEWS_HOSTS = ("itmedia.co.jp", "impress.co.jp", "mynavi.jp", "gizmodo.jp", "nikkei.com", "techcrunch.com", "theverge.com",
              "arstechnica.com", "venturebeat.com", "reuters.com", "4gamer.net", "famitsu.com", "dengekionline.com",
              "ecnomikata.com", "cnet.com", "publickey1.jp", "sorae.info", "engadget.com", "ascii.jp", "gigazine.net",
              "zdnet.com", "bloomberg", "nhk.or.jp", "asahi.com", "yomiuri.co.jp", "mainichi.jp", "sankei.com",
              "nikkansports", "yahoo.co.jp", "livedoor", "phileweb.com", "av.watch", "gamespark.jp", "inside-games.jp",
              "automaton-media.com", "wired.jp", "wired.com", "businessinsider", "forbesjapan", "toyokeizai.net",
              "diamond.jp", "president.jp", "keitai", "ketaiwatch", "androidheadlines.com", "9to5", "macrumors.com",
              "theguardian.com", "nytimes.com", "cnbc.com", "axios.com", "zenn.dev", "qiita.com", "note.com", "kakaku",
              "zaikei.co.jp", "ismcdn.jp", "mezamashi", "j-cast.com", "itmedia", "response.jp", "jiji.com", "kyodo")
PRESS_CDN = ("prcdn.freetls.fastly.net", "prtimes.jp", "atpress.ne.jp")  # press-release distribution: images are for media use

def host(u):
    try: return urlparse(u).netloc.lower()
    except Exception: return ""
def public_img(x):
    if not isinstance(x, dict) or x.get("kind") != "press": return None
    src = x.get("src", "")
    if not src.startswith("https://"): return None
    if any(host(src).endswith(p) for p in PRESS_CDN): return x
    for u in (src, x.get("page", "")):
        h = host(u)
        if any(n in h for n in NEWS_HOSTS): return None
    return x
def cat_of(a):
    c = LEGACY.get(a.get("category"), a.get("category"))
    return c if c in CATS else "other"
def jdate(d):
    y, m, dd = map(int, d.split("-")); return f"{m}月{dd}日（{WD[datetime.date(y, m, dd).weekday()]}）"
def url(path): return (BASE + path) if BASE else path

# ---------- load all editions (newest first) ----------
arts, editions = [], []
for f in sorted(glob.glob(os.path.join(ROOT, "data/20??-??-??.json")), reverse=True):
    ed = json.load(open(f, encoding="utf-8"))
    date = ed["date"]; editions.append(date)
    for a in ed["articles"]:
        a = dict(a); a["_date"] = date; a["_cat"] = cat_of(a)
        a["_path"] = f"/news/{date}/{re.sub(r'[^a-z0-9-]', '-', a['id'].lower())}/"
        img = public_img(a.get("image"))
        body = []
        for b in a.get("body", []):
            t = b.get("type")
            if t == "img":
                if public_img(b): body.append(b)
            elif t == "gallery":
                items = [x for x in b.get("items", []) if public_img(x)]
                if not items: continue
                if not b.get("title"):  # a row of pictures inside the text (tools/place_images.py)
                    body.append(dict(items[0], type="img") if len(items) == 1 else dict(b, items=items))
                else: body.append(dict(b, items=items, title="公式の画像"))
            else: body.append(b)
        if not img:  # fall back to the first public image in the body
            for b in body:
                if b.get("type") == "img": img = b; break
                if b.get("type") == "gallery": img = b["items"][0]; break
        a["_img"], a["_body"] = img, body
        a["_rina"] = next((b.get("text") for b in body if b.get("type") == "rina" and b.get("text")), "")
        arts.append(a)
# voices on X (data/x/<date>.json written later by the Grok bot): {"posts": {"<article id>": [ids or URLs]}}
XPOSTS = {}
for f in glob.glob(os.path.join(ROOT, "data/x/20??-??-??.json")):
    try: XPOSTS[os.path.basename(f)[:10]] = (json.load(open(f, encoding="utf-8")).get("posts") or {})
    except Exception: pass
for a in arts:
    ids = [str(x) for x in (a.get("x_posts") or [])]
    for v in XPOSTS.get(a["_date"], {}).get(a["id"], []):
        m = re.search(r"status(?:es)?/(\d{15,25})", str(v)) or re.fullmatch(r"(\d{15,25})", str(v).strip())
        if m and m.group(1) not in ids: ids.append(m.group(1))
    a["_x"] = [i for i in ids if re.fullmatch(r"\d{5,25}", i)][:10]
by_path = {}
for a in arts:  # keep first (newest) if a path repeats
    by_path.setdefault(a["_path"], a)
arts = list(by_path.values())

def illus(a, w=112, h=84):
    if a["_cat"] == "future":
        return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="宇宙・未来技術"><rect width="{w}" height="{h}" fill="#0b1f4d"/>'
                f'<path d="M0 {h*.78} Q{w/2} {h*.6} {w} {h*.78} V{h} H0z" fill="#f3e9d2"/><circle cx="{w*.62}" cy="{h*.4}" r="{h*.17}" fill="#b3cbf9"/>'
                f'<ellipse cx="{w*.62}" cy="{h*.4}" rx="{h*.32}" ry="{h*.08}" fill="none" stroke="#ff8a00" stroke-width="2.4"/>'
                f'<path d="M{w*.22} {h*.2}l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" fill="#ff8a00"/><circle cx="{w*.85}" cy="{h*.18}" r="1.4" fill="#f3e9d2"/><circle cx="{w*.12}" cy="{h*.55}" r="1.2" fill="#f3e9d2"/></svg>')
    c = CATS[a["_cat"]]; icon = ICONS.get((a.get("visual") or {}).get("icon")) or ICONS[c[1]]
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="{E(c[0])}"><rect width="{w}" height="{h}" fill="var(--blue-soft)" style="fill:color-mix(in oklch,var({c[2]}) 16%,var(--paper))"/>'
            f'<g transform="translate({w/2-18},{h/2-18}) scale(1.5)" fill="none" stroke="var({c[2]})" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{icon}</g></svg>')
def thumb(a):
    i = a["_img"]
    if i: return illus(a, 128, 80) + f'<img src="{E(i["src"])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
    return illus(a, 128, 80)
FACE = {"ai": "thinking", "service": "thinking", "ec": "smug", "mobile": "smug", "gadget": "smug", "game": "smug", "future": "surprised", "other": "surprised"}
def face(c): return f"/assets/rina-{FACE.get(c, 'smug')}.png"
def tag(c, link=True):
    # icon + words, so the category is clear without relying on color (color-vision friendly)
    lab, ic, var = CATS[c]
    svg = (f'<svg class="ti" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" '
           f'stroke-linecap="round" stroke-linejoin="round">{ICONS[ic]}</svg>')
    return (f'<a class="tag" style="--c:var({var})" href="/category/{SLUG[c]}/"><span>{svg}{E(lab)}</span></a>' if link
            else f'<span class="tag" style="--c:var({var})"><span>{svg}{E(lab)}</span></span>')

def page(title, desc, body, path, active=None, og_img=None, extra_head=""):
    full = f"{title}｜{NAME}" if title != NAME else NAME
    navs = "".join(f'<a href="/category/{SLUG[k]}/"{" aria-current=\"page\"" if k == active else ""}><span>{E(v[0])}</span></a>' for k, v in CATS.items())
    og = og_img or url("/assets/og.jpg")
    canon = f'<link rel="canonical" href="{E(url(path))}">' if BASE else ""
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(full)}</title><meta name="description" content="{E(desc)}">{canon}
<meta property="og:site_name" content="{E(NAME)}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="{'article' if path.startswith('/news/') else 'website'}"><meta property="og:image" content="{E(og)}">{f'<meta property="og:url" content="{E(url(path))}">' if BASE else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/icon-192.png"><link rel="apple-touch-icon" href="/assets/icon-180.png">
<link rel="alternate" type="application/rss+xml" title="{E(NAME)}" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@900&family=M+PLUS+Rounded+1c:wght@800&family=Zen+Kaku+Gothic+New:wght@400;700&display=swap">
<link rel="stylesheet" href="/assets/style.css">{extra_head}</head><body>
<header class="top"><div class="wrap"><a class="brand" href="/"><img src="/assets/icon-192.png" alt="" width="34" height="34"><b>{E(NAME)}</b></a>
<nav class="cats" aria-label="カテゴリ">{navs}</nav></div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap"><a href="/">トップ</a><a href="/about/">このサイトについて</a><a href="/privacy/">プライバシーポリシー</a><a href="{E(CFG['youtube'])}">YouTube</a><a href="/feed.xml">RSS</a>
<small>© {datetime.date.today().year} {E(NAME)}</small></div></footer></body></html>'''

# loads X's official embed only when the "Xの声" box comes into view; matches the reader's light/dark setting
XJS = """<script>(()=>{const box=document.querySelector('.xv');if(!box)return;const go=()=>{const d=matchMedia('(prefers-color-scheme: dark)').matches;box.querySelectorAll('blockquote.twitter-tweet').forEach(b=>b.dataset.theme=d?'dark':'light');const s=document.createElement('script');s.src='https://platform.twitter.com/widgets.js';s.async=true;s.charset='utf-8';document.head.append(s)};if('IntersectionObserver' in window){const o=new IntersectionObserver(e=>{if(e.some(x=>x.isIntersecting)){o.disconnect();go()}},{rootMargin:'400px'});o.observe(box)}else go()})();</script>"""
# keeps the current article visible in the left list
LISTJS = """<script>(()=>{const l=document.querySelector('.alist ul'),c=l&&l.querySelector('[aria-current]');if(c&&getComputedStyle(l.parentNode).display!=='none')l.parentNode.scrollTop=c.parentNode.offsetTop-80})();</script>"""
RETRO_FONT = ''  # the heading font (Noto Sans JP 900) is loaded on every page
ORBIT = ('<svg class="orbit" viewBox="0 0 120 60" aria-hidden="true"><ellipse cx="60" cy="34" rx="54" ry="14" fill="none" stroke="#f3e9d2" stroke-width="1.5" stroke-dasharray="3 4"/>'
         '<circle cx="60" cy="34" r="13" fill="#b3cbf9"/><path d="M60 4l3 9 9 3-9 3-3 9-3-9-9-3 9-3z" fill="#ff8a00" transform="translate(40 -2) scale(.6)"/></svg>')
SKEW = re.compile(r'(<div class="sec-h"[^>]*><h2>|<section class="keys"><h2>|<section class="box"><h2>|<h2 class="sub">)(.*?)(</h2>)')
def write(path, content):
    if path.endswith((".html", "/")):
        content = SKEW.sub(lambda m: m.group(1) + "<span>" + m.group(2) + "</span>" + m.group(3), content)
    if PREFIX and path.endswith((".html", "/")):
        content = content.replace('="/', '="' + PREFIX + '/').replace(", /assets", ", " + PREFIX + "/assets")
        content = content.replace("<head>", '<head><meta name="robots" content="noindex">', 1)
    p = os.path.join(OUT, path.lstrip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)

def row(a, show_date=False):
    when = f'<span class="when">{E(jdate(a["_date"]))}</span>' if show_date else ""
    return (f'<li class="row" style="--c:var({CATS[a["_cat"]][2]})"><span class="thumb">{thumb(a)}</span><div class="tx">{tag(a["_cat"])}{when}'
            f'<a class="t" href="{a["_path"]}">{E(a["title"])}</a><p>{E(a.get("summary"))}</p></div></li>')

def side(counts):
    # bottom band (no category list: categories live only in the top bar)
    days = "".join(f'<li><a href="/date/{d}/">{E(jdate(d))}</a></li>' for d in editions[:14])
    return (f'<aside class="side"><a class="yt" href="{E(CFG["youtube"])}"><b>星餓りなのショート動画</b><span>毎日1本、ニュースを1分で。YouTubeで見る</span></a>'
            f'<div class="days"><h3>日付で読む</h3><ul>{days}</ul></div></aside>')

def picks_for(day_arts, n=3):
    def score(a):
        s = 0
        if a["_rina"]: s += 4
        if a["_img"]: s += 2
        if a["_cat"] in ("ai", "mobile", "gadget", "game"): s += 1
        if a.get("pick"): s += 10
        return s
    return sorted(day_arts, key=score, reverse=True)[:n]

# ---------- build ----------
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, "assets"))
for f in glob.glob(os.path.join(ROOT, "site/assets/*")) + [os.path.join(ROOT, "site/style.css")]:
    shutil.copy(f, os.path.join(OUT, "assets"))
counts = {}
for a in arts: counts[a["_cat"]] = counts.get(a["_cat"], 0) + 1

# home
latest = editions[0] if editions else None
today = [a for a in arts if a["_date"] == latest]
pk = picks_for(today, 4)
lead = pk[0] if pk else None
hero = (f'<section class="desk"><picture><source media="(max-width:760px)" srcset="/assets/hero-m.webp" width="750" height="422"><source srcset="/assets/hero-750.webp 750w, /assets/hero.webp 1500w" sizes="(max-width:1120px) 100vw, 1088px"><img src="/assets/hero.jpg" alt="ニュースを手に持つ案内役の星餓りな" width="1500" height="500" fetchpriority="high"></picture>'
        f'<div class="desk-copy"><h1><span>今日のITニュースを、</span><span>りなと一緒に。</span></h1><p>{E(CFG["description"])}</p></div></section>')
pick_html = ""
if lead:
    say = lead["_rina"] or lead.get("summary", "")
    pick_html = (f'<section class="pick"><img src="{face(lead["_cat"])}" alt="案内役の星餓りな" width="72" height="72"><div class="say">'
                 f'<h2>{E(jdate(latest))}、りなのいちおし</h2><a class="t" href="{lead["_path"]}">{E(lead["title"])}</a><p>{E(say)}</p></div></section>')
more_picks = "".join(row(a) for a in pk[1:])
rest = [a for a in today if a not in pk]
home = (hero + pick_html + '<div class="cols"><div>'
        + (f'<div class="sec-h"><h2>{E(jdate(latest))}のニュース</h2><span>{len(today)}本</span></div><ul class="rows">' + more_picks + "".join(row(a) for a in rest) + "</ul>" if latest else "")
        + (f'<p><a class="btn" href="/date/{editions[1]}/">前の日のニュースを読む</a></p>' if len(editions) > 1 else "")
        + '</div>' + side(counts) + '</div>')
write("/", page(NAME, CFG["description"], home, "/", og_img=url("/assets/og.jpg")))

# category pages
for k, (lab, _, var) in CATS.items():
    items = [a for a in arts if a["_cat"] == k]
    banner = ""
    if k == "future":
        banner = ('<section class="retro"><picture><source media="(max-width:760px)" srcset="/assets/future-banner-m.webp" width="600" height="450">'
                  '<img src="/assets/future-banner.webp" alt="宇宙服のヘルメットをかぶった星餓りなと、レトロなロケットの絵" width="1500" height="500" fetchpriority="high"></picture>'
                  f'<div class="retro-copy"><h1>宇宙・未来技術</h1><p>ロケット、人工衛星、自動運転、ロボット、量子コンピューター。未来がいつ暮らしに届くのかを追いかけます。</p></div></section>')
    body = (banner + f'<div class="cols"><div><div class="sec-h" style="border-color:var({var})"><h2>{E(lab)}{"の記事" if k == "future" else ""}</h2><span>{len(items)}本</span></div>'
            f'<ul class="rows">' + ("".join(row(a, True) for a in items[:200]) or '<li class="row empty"><p>この分野の記事はまだありません。毎日夕方に増えていきます。</p></li>') + '</ul></div>' + side(counts) + '</div>')
    write(f"/category/{SLUG[k]}/", page(f"{lab}のニュース", f"{lab}の最新ニュースを、星餓りなの見方つきでまとめています。", body, f"/category/{SLUG[k]}/", active=k,
                                        extra_head=RETRO_FONT if k == "future" else ""))

# date pages
for i, d in enumerate(editions):
    items = [a for a in arts if a["_date"] == d]
    nav = ""
    if i + 1 < len(editions): nav += f'<a class="btn" href="/date/{editions[i+1]}/">前の日</a> '
    if i > 0: nav += f'<a class="btn" href="/date/{editions[i-1]}/">次の日</a>'
    body = (f'<div class="cols"><div><div class="sec-h"><h2>{E(jdate(d))}の号</h2><span>{len(items)}本</span></div>'
            f'<ul class="rows">{"".join(row(a) for a in items)}</ul><p>{nav}</p></div>' + side(counts) + '</div>')
    write(f"/date/{d}/", page(f"{jdate(d)}のITニュース", f"{jdate(d)}のITニュース{len(items)}本。", body, f"/date/{d}/"))

# article pages
def fig(x):
    cap = E(x.get("caption")); cred = E(x.get("credit"))
    return (f'<figure><img src="{E(x["src"])}" alt="{cap}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()">'
            f'<figcaption>{cap}{"　" if cap and cred else ""}{("画像提供：" + cred) if cred else ""}</figcaption></figure>')
for a in arts:
    c = a["_cat"]; lab, _, var = CATS[c]
    parts, first_img_done = [], False
    for b in a["_body"]:
        t = b.get("type")
        if t == "keys" and b.get("items"):
            parts.append('<section class="keys"><h2>3行でわかる</h2><ol>' + "".join(f"<li>{E(x)}</li>" for x in b["items"]) + "</ol></section>")
        elif t == "p" and b.get("text"): parts.append(f"<p>{E(b['text'])}</p>")
        elif t == "h" and b.get("text"): parts.append(f'<h2 class="sub">{E(b["text"])}</h2>')
        elif t == "img": parts.append(fig(b))
        elif t == "stat" and b.get("items"):
            parts.append('<div class="stats">' + "".join(f'<div><b>{E(x.get("value"))}</b><span>{E(x.get("label"))}</span></div>' for x in b["items"]) + "</div>")
        elif t == "gallery": parts.append((f'<h2 class="sub">{E(b.get("title"))}</h2>' if b.get("title") else "") + '<div class="gal">' + "".join(fig(x) for x in b["items"]) + "</div>")
        elif t == "point" and b.get("items"):
            parts.append('<section class="box"><h2>あなたへの影響・やること</h2><ul>' + "".join(f"<li>{E(x)}</li>" for x in b["items"]) + "</ul></section>")
        elif t == "rina" and b.get("text"):
            parts.append(f'<section class="rina"><img src="{face(c)}" alt="案内役の星餓りな" width="64" height="64" loading="lazy"><div class="say"><h2>りなの見方</h2><p>{E(b["text"])}</p></div></section>')
    if a["_img"] and not any(b.get("type") == "img" for b in a["_body"][:4]):
        # show the main official image after the lead
        idx = next((i for i, p in enumerate(parts) if p.startswith("<p>")), 0) + 1
        parts.insert(idx, fig(a["_img"]))
    refs = a.get("refs") or [{"name": a.get("source_name"), "url": a.get("source_url")}]
    src = ('<section class="src"><h2>もとになった記事・発表</h2><ul>'
           + "".join(f'<li><a href="{E(r.get("url"))}" rel="nofollow noopener">{E(r.get("name"))}</a></li>' for r in refs if r.get("url"))
           + f'</ul><a class="btn" href="{E(a.get("source_url"))}" rel="nofollow noopener">元の記事を読む（{E(a.get("source_name"))}）</a></section>')
    same = [x for x in arts if x["_cat"] == c and x is not a][:5]
    more = (f'<section class="more"><div class="sec-h" style="border-color:var({var})"><h2>{E(lab)}のほかのニュース</h2></div><ul class="rows">'
            + "".join(row(x, True) for x in same) + "</ul></section>") if same else ""
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"], "description": a.get("summary", ""),
          "datePublished": a["_date"], "dateModified": a["_date"], "articleSection": lab,
          "author": {"@type": "Organization", "name": NAME}, "publisher": {"@type": "Organization", "name": NAME}}
    if a["_img"]: ld["image"] = [a["_img"]["src"]]
    if BASE: ld["mainEntityOfPage"] = url(a["_path"])
    band = (f'<div class="retro-band">{ORBIT}<span>宇宙・未来技術</span></div>' if c == "future" else "")
    body = (f'<article class="art{" future" if c == "future" else ""}" style="--c:var({var})">{band}<div class="crumb"><a href="/">トップ</a> ＞ <a href="/category/{SLUG[c]}/">{E(lab)}</a></div>'
            f'<h1>{E(a["title"])}</h1><div class="meta">{tag(c, False)}<span>{E(jdate(a["_date"]))}の号</span><span>出典：{E(a.get("source_name"))}</span></div>'
            + ('<p class="prnote"><span class="pr">PR</span>この記事には広告（アフィリエイトリンク）が含まれます。</p>' if a.get("pr") else "")
            + "".join(parts) + src + "</article>")
    day = [x for x in arts if x["_date"] == a["_date"]]
    alist = (f'<nav class="alist" aria-label="{E(jdate(a["_date"]))}のニュース"><h2>{E(jdate(a["_date"]))}のニュース</h2><ul>'
             + "".join(f'<li><a href="{x["_path"]}"{" aria-current=\"page\"" if x is a else ""}><span class="lt">{thumb(x)}</span>'
                       f'<span class="lx">{tag(x["_cat"], False)}<b>{E(x["title"])}</b></span></a></li>' for x in day) + '</ul></nav>')
    if a["_x"]:
        posts = "".join(f'<div class="xcard"><blockquote class="twitter-tweet" data-dnt="true" data-conversation="none" data-lang="ja" data-width="340">'
                        f'<a href="https://twitter.com/i/status/{i}" rel="nofollow noopener">Xで投稿を見る</a></blockquote></div>' for i in a["_x"])
        xv = (f'<aside class="xrail" aria-label="Xの声"><div class="xv"><h2>このニュースへのXの声<span>{len(a["_x"])}件</span></h2>{posts}'
              '<p class="xnote">X（旧Twitter）の公式の埋め込みで表示しています。投稿の内容は投稿者のもので、当サイトの意見ではありません。</p></div></aside>')
    else:
        xv = '<aside class="xrail" aria-label="Xの声"><div class="xv"><h2>このニュースへのXの声</h2><p class="xnote">このニュースについてのXの投稿は、まだ集まっていません。</p></div></aside>'
    body = f'<div class="agrid">{alist}<div class="amain">{body}</div>{xv}<div class="amore">{more}</div></div>' + (XJS if a["_x"] else "") + LISTJS
    og = a["_img"]["src"] if a["_img"] else url("/assets/og.jpg")
    write(a["_path"], page(a["title"], a.get("summary") or a["title"], body, a["_path"], active=c, og_img=og,
                           extra_head=f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' + (RETRO_FONT if c == "future" else "")))

# static pages
about = f'''<div class="doc"><h1>このサイトについて</h1>
<p>{E(NAME)}は、AI、スマホやパソコン、家電、ネットサービス、ゲーム、EC、宇宙など、ITのニュースを毎日夕方にまとめて届けるサイトです。</p>
<h2>記事の作り方</h2><p>1つのニュースにつき、公式発表と複数の報道を読み比べ、事実を整理してまとめています。記事づくりと、数字・日付・価格などの点検にはAIを活用しています。元になった記事や発表は、各記事の最後に載せています。</p>
<h2>星餓りなについて</h2><p>星餓りなは、このサイトとYouTubeチャンネルの案内役のキャラクターです。記事の最後の「りなの見方」では、ニュースを読む人にとっての意味を、りなの目線でひとことにまとめています。</p>
<h2>画像について</h2><p>画像は、メーカーや運営会社が公開している公式の画像を、提供元を明記して使っています。</p>
<h2>広告・アフィリエイトについて</h2><p>商品を紹介する記事に、アフィリエイトリンク（購入されると当サイトに紹介料が入るリンク）を載せることがあります。その場合は「PR」と表示します。</p>
<h2>内容の正確さについて</h2><p>正確な情報を載せるよう努めていますが、価格や提供内容は掲載時点のものです。最新の情報は、各社の公式発表でご確認ください。誤りに気づいた場合は、確認のうえ訂正します。</p>
<h2>YouTube</h2><p>ニュースを1分で紹介するショート動画を、<a href="{E(CFG['youtube'])}">YouTubeチャンネル「星餓りな」</a>で毎日公開しています。</p>
<h2>お問い合わせ</h2><p>お問い合わせ窓口は準備中です。</p></div>'''
write("/about/", page("このサイトについて", f"{NAME}の運営方針と記事の作り方。", about, "/about/"))
privacy = f'''<div class="doc"><h1>プライバシーポリシー</h1>
<h2>アクセス解析</h2><p>当サイトでは、サイトの改善のためにアクセス解析ツールを使うことがあります。個人を特定する情報は集めません。</p>
<h2>広告・アフィリエイト</h2><p>当サイトは、Amazon、楽天市場などのアフィリエイトプログラムに参加することがあります。リンク先のサービスでは、Cookieなどを使って閲覧や購入の情報が扱われることがあります。詳しくは各サービスのプライバシーポリシーをご確認ください。</p>
<h2>Xの投稿の埋め込み</h2><p>記事ページの「Xの声」では、X（旧Twitter）の投稿を公式の埋め込み機能で表示しています。表示するときに、お使いのブラウザとXのサーバーとの間で通信が行われます。詳しくはXのプライバシーポリシーをご確認ください。</p>
<h2>外部リンク</h2><p>記事内のリンク先のサイトで起きたことについて、当サイトは責任を負いません。</p>
<h2>改定</h2><p>このポリシーは、必要に応じて改定します。</p></div>'''
write("/privacy/", page("プライバシーポリシー", f"{NAME}のプライバシーポリシー。", privacy, "/privacy/"))
write("/404.html", page("ページが見つかりません", "ページが見つかりません。", '<div class="doc"><h1>ページが見つかりません</h1><p>URLが変わったか、削除された可能性があります。<a href="/">トップページ</a>から探してください。</p></div>', "/404.html"))

# robots, sitemap, rss
write("/robots.txt", "User-agent: *\nAllow: /\n" + (f"Sitemap: {BASE}/sitemap.xml\n" if BASE else ""))
if BASE:
    locs = ["/", "/about/", "/privacy/"] + [f"/category/{s}/" for s in SLUG.values()] + [f"/date/{d}/" for d in editions] + [a["_path"] for a in arts]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{E(url(p))}</loc></url>" for p in locs) + "</urlset>\n")
items = "".join(f'<item><title>{E(a["title"])}</title><link>{E(url(a["_path"]))}</link><guid>{E(url(a["_path"]))}</guid>'
                f'<description>{E(a.get("summary"))}</description><category>{E(CATS[a["_cat"]][0])}</category>'
                f'<pubDate>{datetime.datetime.fromisoformat(a["_date"]+"T17:30:00+09:00").strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate></item>' for a in arts[:60])
write("/feed.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{E(NAME)}</title><link>{E(url("/"))}</link>'
      f'<description>{E(CFG["description"])}</description><language>ja</language>{items}</channel></rss>\n')
print("pages:", len(arts), "articles,", len(editions), "days → ", OUT)
