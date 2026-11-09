"""Collect the numbers the weekly review learns from (2026-11-10, user: let the whole activity improve itself from data).
Runs daily on GitHub Actions (.github/workflows/metrics.yml); output goes to the branch "metrics" as metrics/<date>.json.
Each part is optional: if a key or service is missing, that part says why and the rest still runs. Never prints secrets.

  python3 tools/collect_metrics.py out.json
parts:
  youtube  every Short in channel/shorts_log.csv: views/likes/comments (Data API) and, if the token has the
           yt-analytics.readonly scope, engagedViews / averageViewPercentage / subscribersGained / traffic from Shorts feed
  site     Cloudflare Web Analytics, last 7 days: visits per day, per category, top articles, sources (tools/cf_stats.py)
  editions last 14 days of editions: articles per category, refs per article, single-ref articles, official/press images,
           diagrams, articles with Xの声
  quality  open/closed AIからの報告 issues, failed workflow runs per workflow (7 days)
  cost     Modal spend this month, Colab compute units left, workflow runs per kind (Gemini TTS, Codex, LongCat) in 7 days
"""
import csv, glob, json, os, re, subprocess, sys, datetime, urllib.request
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(JST)
REPO = os.environ.get("GITHUB_REPOSITORY", "pasta0725/my-yukan")
out = {"date": NOW.strftime("%Y-%m-%d"), "collected": NOW.isoformat(timespec="minutes")}


def part(name):
    def deco(fn):
        try: out[name] = fn()
        except Exception as e: out[name] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
        print(name, "ok" if "error" not in out[name] else out[name]["error"], flush=True)
    return deco


def gh(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


@part("youtube")
def _():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    rows = list(csv.DictReader(open(os.path.join(ROOT, "channel", "shorts_log.csv"), encoding="utf-8")))
    ids = [r["動画ID"].strip() for r in rows if r.get("動画ID", "").strip()]
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    vids = {}
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="statistics,snippet,status", id=",".join(ids[i:i + 50])).execute()["items"]:
            s = v["statistics"]
            vids[v["id"]] = {"title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"], "privacy": v["status"]["privacyStatus"],
                             "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))}
    for r in rows:   # what the log says about each video (title type, time slot, notes with the selection points)
        vid = r.get("動画ID", "").strip()
        if vid in vids: vids[vid]["log"] = {k: r[k] for k in ("タイトルの型", "全角文字数", "数字あり", "時刻テスト枠", "メモ") if k in r}
    ch = yt.channels().list(part="statistics", mine=True).execute()["items"][0]["statistics"]
    res = {"subscribers": int(ch.get("subscriberCount", 0)), "channel_views": int(ch.get("viewCount", 0)), "videos": vids}
    try:   # needs the extra scope yt-analytics.readonly (the user re-authorizes once); otherwise skipped
        ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        start = min((v["published"][:10] for v in vids.values()), default=out["date"])
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=out["date"], dimensions="video",
                               metrics="views,engagedViews,averageViewPercentage,averageViewDuration,subscribersGained,likes,shares",
                               filters="video==" + ",".join(vids), maxResults=200).execute()
        cols = [c["name"] for c in r["columnHeaders"]]
        for row in r.get("rows", []):
            d = dict(zip(cols, row)); vids.get(d.pop("video"), {})["analytics"] = d
        res["analytics"] = "ok"
    except Exception as e:
        res["analytics"] = f"unavailable ({type(e).__name__}: {str(e)[:120]})"
    return res


@part("site")
def _():
    tmp = "/tmp/cf_stats.json"
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "cf_stats.py"), tmp], check=True, capture_output=True, timeout=300)
    d = json.load(open(tmp, encoding="utf-8"))
    cat = defaultdict(lambda: {"pageviews": 0, "visits": 0})
    for p in d.get("pages", []):
        if p.get("category"):
            cat[p["category"]]["pageviews"] += p["pageviews"]; cat[p["category"]]["visits"] += p["visits"]
    return {"daily": d.get("daily", [])[-14:], "by_category_30d": dict(cat), "top_pages_30d": d.get("pages", [])[:20],
            "sources_30d": d.get("sources", [])[:10], "devices_30d": d.get("devices", [])}


@part("editions")
def _():
    eds = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "20*.json")))[-28:]:
        ed = os.path.basename(f)[:-5]
        try: d = json.load(open(f, encoding="utf-8"))
        except Exception: continue
        arts = d.get("articles", [])
        if not arts: continue
        imgs = Counter(b.get("kind", "?") for a in arts for b in a.get("body", []) if b.get("type") in ("img", "image", "gallery"))
        refs = [len(a.get("refs", [])) for a in arts]
        xf = os.path.join(ROOT, "data", "x", f"{ed}.json")
        xn = 0
        if os.path.exists(xf):
            try: xd = json.load(open(xf, encoding="utf-8")); xn = len(xd.get("items", xd) if isinstance(xd, dict) else xd)
            except Exception: pass
        eds.append({"edition": ed, "articles": len(arts), "by_category": dict(Counter(a.get("category") for a in arts)),
                    "refs_avg": round(sum(refs) / len(refs), 2), "single_ref": sum(1 for r in refs if r <= 1),
                    "images_by_kind": dict(imgs), "no_image": sum(1 for a in arts if not any(b.get("type") in ("img", "image", "gallery") for b in a.get("body", []))),
                    "diagrams": len(glob.glob(os.path.join(ROOT, "data", "diagrams", ed, "*.png"))), "x_items": xn})
    return eds[-14:]


@part("quality")
def _():
    since = (NOW - datetime.timedelta(days=7)).astimezone(datetime.timezone.utc)
    iss = gh("issues?labels=AI%E3%81%8B%E3%82%89%E3%81%AE%E5%A0%B1%E5%91%8A&state=all&per_page=100")
    runs = gh(f"actions/runs?per_page=100&created=>={since.strftime('%Y-%m-%d')}")["workflow_runs"]
    by = defaultdict(lambda: Counter())
    for r in runs: by[r["name"]][r["conclusion"] or r["status"]] += 1
    return {"reports_open": [{"n": i["number"], "title": i["title"]} for i in iss if i["state"] == "open"],
            "reports_closed_7d": sum(1 for i in iss if i["state"] == "closed" and i.get("closed_at", "") >= since.isoformat()[:10]),
            "workflow_runs_7d": {k: dict(v) for k, v in by.items()}}


@part("cost")
def _():
    res = {}
    try:
        t = subprocess.run(["modal", "billing", "report", "--for", "this month"], capture_output=True, text=True, timeout=120).stdout
        res["modal_usd_this_month"] = round(sum(float(x) for x in re.findall(r"│\s*([0-9]+\.[0-9]+)\s*│\s*$", t, re.M)), 2)
    except Exception as e: res["modal"] = f"unavailable ({e})"
    try:
        t = subprocess.run(["colab", "--auth=adc", "usage"], capture_output=True, text=True, timeout=120).stdout
        m = re.search(r"Current balance:\s*([0-9.]+)", t); res["colab_units_left"] = float(m.group(1)) if m else None
    except Exception as e: res["colab"] = f"unavailable ({e})"
    wr = out.get("quality", {}).get("workflow_runs_7d", {})
    res["runs_7d"] = {k: sum(wr.get(k, {}).values()) for k in ("narration", "codex-research", "codex-images", "longcat-colab", "modal-avatar", "voice-check")}
    return res


json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written", sys.argv[1])
