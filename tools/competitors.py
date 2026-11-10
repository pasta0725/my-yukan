"""Find Japanese tech/AI Shorts that are doing well this week, so the weekly review can compare them with ours
(2026-11-10, user: research content that is growing and think about how it differs from ours).
Runs weekly on GitHub Actions (.github/workflows/competitors.yml) -> branch "metrics", competitors/<date>.json.

  python3 tools/competitors.py out.json
1. YouTube Data API search (Japan, Japanese, last 7 days, Shorts length) for a few keywords - our own topics of the week
   plus fixed ones. ~100 quota units per search, we use about 10 searches (daily quota is 10,000).
2. Keeps videos up to 3 minutes, adds views, likes, comments, channel size, and "views per day" and
   "views per subscriber" (a small channel with many views = the content itself is working).
3. For the top 6, asks Gemini (free tier, GEMINI_API_KEY) to watch the video by its YouTube URL and describe:
   the first 3 seconds (hook), structure, length, on-screen text, voice/character, ending, thumbnail/title pattern,
   and what makes it work. Gemini only reads public videos; nothing is downloaded or copied.
Never prints secrets.
"""
import json, os, re, sys, datetime, urllib.request, urllib.error
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(JST)
FIXED = ["AIニュース", "ChatGPT 新機能", "生成AI 最新", "ガジェット 新製品", "iPhone 新機能", "スマホ ニュース", "ゲーム ニュース"]
OUR_CHANNEL = "UCDIg0hL5OV6xB5V8GtV-g9A"


def iso_dur(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m: return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def our_topics():
    """Main subjects of this week's editions (most frequent words in titles), to search where we compete."""
    import glob
    words = Counter()
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "20*.json")))[-14:]:
        try: arts = json.load(open(f, encoding="utf-8"))["articles"]
        except Exception: continue
        for a in arts:
            for w in re.findall(r"[A-Za-z][A-Za-z0-9.+-]{2,}|[ァ-ヴー]{3,}", a.get("title", "")):
                words[w] += 1
    stop = {"AI", "App", "The", "ニュース", "サービス", "アプリ"}
    return [f"{w} ニュース" for w, _ in words.most_common(30) if w not in stop][:4]


def main():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    after = (NOW - datetime.timedelta(days=7)).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    queries = FIXED + our_topics()
    found = {}
    for q in queries:
        try:
            r = yt.search().list(part="id", q=q, type="video", videoDuration="short", publishedAfter=after, regionCode="JP",
                                 relevanceLanguage="ja", order="viewCount", maxResults=25).execute()
            for it in r.get("items", []): found.setdefault(it["id"]["videoId"], set()).add(q)
        except Exception as e:
            print("search failed:", q, str(e)[:120])
    ids = list(found)
    vids = []
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()["items"]:
            dur = iso_dur(v["contentDetails"].get("duration"))
            if dur == 0 or dur > 180 or v["snippet"]["channelId"] == OUR_CHANNEL: continue
            if not re.search(r"[ぁ-んァ-ヴ]", v["snippet"]["title"]): continue   # Japanese Shorts only (the first test run picked up Tamil, Indonesian, ...)
            pub = datetime.datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
            days = max(0.5, (NOW - pub).total_seconds() / 86400)
            s = v["statistics"]
            vids.append({"id": v["id"], "url": f"https://www.youtube.com/shorts/{v['id']}", "title": v["snippet"]["title"],
                         "channel": v["snippet"]["channelTitle"], "channel_id": v["snippet"]["channelId"],
                         "published": v["snippet"]["publishedAt"], "seconds": dur, "views": int(s.get("viewCount", 0)),
                         "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0)),
                         "views_per_day": round(int(s.get("viewCount", 0)) / days), "thumbnail": v["snippet"]["thumbnails"].get("high", {}).get("url"),
                         "tags": v["snippet"].get("tags", [])[:10], "queries": sorted(found[v["id"]])})
    chans = list({v["channel_id"] for v in vids})
    subs = {}
    for i in range(0, len(chans), 50):
        for c in yt.channels().list(part="statistics", id=",".join(chans[i:i + 50])).execute()["items"]:
            subs[c["id"]] = int(c["statistics"].get("subscriberCount", 0) or 0)
    for v in vids:
        v["channel_subscribers"] = subs.get(v["channel_id"], 0)
        v["views_per_subscriber"] = round(v["views"] / max(100, v["channel_subscribers"]), 2)
    vids.sort(key=lambda v: v["views_per_day"], reverse=True)
    # the ones to learn from: fast growing, and also "small channel, big views" (the content itself works)
    top = vids[:4] + [v for v in sorted(vids, key=lambda v: v["views_per_subscriber"], reverse=True) if v not in vids[:4]][:2]
    for v in top: v["analysis"] = gemini_watch(v)
    return {"date": NOW.strftime("%Y-%m-%d"), "queries": queries, "count": len(vids), "top_by_views_per_day": vids[:20],
            "studied": [v["id"] for v in top]}


def gemini_model(key):
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key})
    names = [m["name"].split("/")[-1] for m in json.load(urllib.request.urlopen(req, timeout=60)).get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    ok = [n for n in names if "flash" in n and not re.search(r"tts|image|live|audio|lite|exp|embed", n)]
    ok.sort(key=lambda n: [float(x) if x.replace(".", "", 1).isdigit() else 0 for x in re.findall(r"\d+(?:\.\d+)?", n)], reverse=True)
    return ok[0] if ok else "gemini-flash-latest"


def gemini_watch(v):
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return {"error": "no GEMINI_API_KEY"}
    try:
        global _MODEL
        _MODEL = globals().get("_MODEL") or gemini_model(key)
        prompt = ("この縦型ショート動画を見て、日本語で次の項目をJSONで答えてください。キー: hook（最初の3秒に何を見せ何を言うか）, "
                  "structure（場面の流れを短く）, on_screen_text（字幕・テロップの出し方）, voice（声・話し方・キャラクター）, "
                  "visuals（映像の素材：実写・画面録画・イラスト・AI映像など）, ending（終わり方）, title_pattern（タイトルの型）, "
                  "why_it_works（伸びている理由の見立てを3つ）, length_feel（テンポ）。事実だけを書き、推測は推測と書く。")
        body = {"contents": [{"parts": [{"file_data": {"file_uri": v["url"]}}, {"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}}
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent",
                                     data=json.dumps(body).encode(), headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        import time
        for attempt in range(4):   # Gemini often answers 503 (busy) - wait and try again
            try: r = json.load(urllib.request.urlopen(req, timeout=300)); break
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 503) or attempt == 3: raise
                time.sleep(30 * (attempt + 1))
        txt = r["candidates"][0]["content"]["parts"][0]["text"]
        out = json.loads(txt); out["_model"] = _MODEL
        return out
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}


if __name__ == "__main__":
    res = main()
    json.dump(res, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("videos", res["count"], "studied", len(res["studied"]))
    for v in res["top_by_views_per_day"][:6]: print(" ", v["views_per_day"], "/day", v["seconds"], "s", v["channel_subscribers"], "subs |", v["title"][:40])
