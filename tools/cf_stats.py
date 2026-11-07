"""Collect visitor numbers for the public site 星餓りなのテックニュース from Cloudflare Web Analytics.

usage: CF_API_TOKEN=... python3 -I tools/cf_stats.py out.json
Runs in GitHub Actions (.github/workflows/site-stats.yml); the token is the repository secret CF_API_TOKEN
(a Cloudflare API token with only "Account Analytics: Read"). Writes one JSON file with:
  daily    [{date, visits, pageviews}]           last 30 days (Japan dates)
  pages    [{path, title, category, pageviews, visits}]  top 100 pages, last 30 days
  sources  [{source, visits}]                    where visitors came from (referring site), last 30 days
  devices  [{device, visits}], countries [{country, visits}]
  updated  ISO time
The numbers are Cloudflare's sampled estimates (bots excluded where the API allows it).
"""
import json, os, sys, glob, re, datetime, urllib.request

ACCOUNT = "18d5f3540376bf1393a1082f7d5caa5d"
SITE = "13c6f29ed3da4bb8b251eb7958858369"   # rina-tech-news.pages.dev
TOKEN = os.environ["CF_API_TOKEN"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(datetime.timezone.utc)
start = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
end = now.strftime("%Y-%m-%dT%H:%M:%SZ")


def gql(query, variables):
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=60))
    if r.get("errors"): raise SystemExit("Cloudflare API error: " + json.dumps(r["errors"], ensure_ascii=False))
    return r["data"]["viewer"]["accounts"][0]


def groups(dim, order, limit, bot=True):
    f = '{siteTag: $site, datetime_geq: $start, datetime_leq: $end' + (', bot: 0' if bot else '') + '}'
    q = ('query($acc: string!, $site: string!, $start: Time!, $end: Time!) { viewer { accounts(filter: {accountTag: $acc}) {'
         f' g: rumPageloadEventsAdaptiveGroups(filter: {f}, limit: {limit}, orderBy: [{order}])'
         f' {{ count sum {{ visits }} dimensions {{ {dim} }} }} }} }} }}')
    try:
        return gql(q, {"acc": ACCOUNT, "site": SITE, "start": start, "end": end})["g"]
    except SystemExit as e:
        if bot and "bot" in str(e): return groups(dim, order, limit, bot=False)
        raise


# article titles for paths (/news/<date>/<id>/)
titles = {}
for f in glob.glob(os.path.join(ROOT, "data/20??-??-??.json")):
    ed = json.load(open(f, encoding="utf-8"))
    for a in ed.get("articles", []):
        p = f"/news/{ed['date']}/{re.sub(r'[^a-z0-9-]', '-', a['id'].lower())}/"
        titles[p] = (a.get("title", ""), a.get("category", ""))
NAMES = {"/": "トップページ", "/about/": "このサイトについて", "/privacy/": "プライバシーポリシー"}

# hourly rows -> Japan dates (Cloudflare dates are UTC)
hourly = groups("datetimeHour", "datetimeHour_ASC", 1000)
daily = {}
for g in hourly:
    d = datetime.datetime.fromisoformat(g["dimensions"]["datetimeHour"].replace("Z", "+00:00")).astimezone(JST).date().isoformat()
    x = daily.setdefault(d, {"date": d, "visits": 0, "pageviews": 0})
    x["visits"] += g["sum"]["visits"]; x["pageviews"] += g["count"]
day0 = (now.astimezone(JST).date() - datetime.timedelta(days=29))
days = [(day0 + datetime.timedelta(days=i)).isoformat() for i in range(30)]
daily_rows = [daily.get(d, {"date": d, "visits": 0, "pageviews": 0}) for d in days]

pages = []
for g in groups("requestPath", "count_DESC", 100):
    p = g["dimensions"]["requestPath"] or "/"
    t, c = titles.get(p, (NAMES.get(p, ""), ""))
    if not t and p.startswith("/category/"): t = "カテゴリ一覧：" + p.split("/")[2]
    if not t and p.startswith("/date/"): t = "日付別：" + p.split("/")[2]
    pages.append({"path": p, "title": t or p, "category": c, "pageviews": g["count"], "visits": g["sum"]["visits"]})


def simple(dim, label, limit=20, blank="（直接・不明）"):
    out = []
    for g in groups(dim, "sum_visits_DESC", limit):
        v = g["dimensions"][dim] or blank
        out.append({label: v, "visits": g["sum"]["visits"]})
    return out

sources = simple("refererHost", "source")
for s in sources:
    if s["source"] == "rina-tech-news.pages.dev": s["source"] = "（サイト内の移動）"
out = {"updated": now.isoformat(timespec="seconds"), "daily": daily_rows, "pages": pages, "sources": sources,
       "devices": simple("deviceType", "device", 10), "countries": simple("countryName", "country", 15)}
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"days {len(daily_rows)}, pages {len(pages)}, total visits {sum(d['visits'] for d in daily_rows)}")
