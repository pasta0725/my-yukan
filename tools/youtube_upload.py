"""Upload a finished Short to the 星餓りな channel with the YouTube Data API (no PC needed, user decision 2026-11-09).
Runs on GitHub Actions (.github/workflows/youtube-upload.yml). The keys come from repository secrets
YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN (set by the user; this file never prints them).

usage: python3 tools/youtube_upload.py <name> <video.mp4> [--comment TEXT] [--privacy public|private|unlisted] [--publish-at ISO]
  --publish-at 2026-11-10T21:00:00+09:00 : upload as private and let YouTube publish it at that time (auto shorts, 2026-11-10)
  video can also be a command for an existing video:
    thumb:<id>   set the thumbnail again          stop:<id>    cancel a scheduled publish / make it private
    go:<id>      make it public now               comment:<id> post --comment as the first comment
    status:<id>  print privacy and publish time   banner:<path> replace the channel banner (2560x1440 jpg in the repo)
uses channel/meta/<name>.json (title, description, tags, title_en, description_en),
     channel/thumbs/<name>.jpg (if present), channel/captions/<name>_ja.srt (if present).
Uploads go public right away (checked 2026-11-10), so use --publish-at when nobody has looked at the video yet.
"""
import json, os, sys, argparse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYLIST = "毎日1分AIニュース"

ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("video")
ap.add_argument("--comment", default=""); ap.add_argument("--privacy", default="public"); ap.add_argument("--publish-at", default="")
a = ap.parse_args()

creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                    scopes=["https://www.googleapis.com/auth/youtube.force-ssl", "https://www.googleapis.com/auth/youtube.upload"])
yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

me = yt.channels().list(part="snippet", mine=True).execute()["items"][0]
print("channel:", me["snippet"]["title"], me["id"])
if me["id"] != "UCDIg0hL5OV6xB5V8GtV-g9A":
    sys.exit("not the 星餓りな channel - authorize again and pick 星餓りな")
if a.video == "-":   # setup check only: the keys work and point at the right channel
    print("check ok"); sys.exit(0)
if a.video.startswith("thumb:"):   # thumb:<videoId> = only set the thumbnail again (it can hit "too many thumbnails recently", 2026-11-10)
    t = os.path.join(ROOT, "channel", "thumbs", f"{a.name}.jpg")
    yt.thumbnails().set(videoId=a.video[6:], media_body=MediaFileUpload(t, mimetype="image/jpeg")).execute(); print("ok: thumbnail"); sys.exit(0)
if a.video.startswith("banner:"):   # banner:<image in the repo> = replace the channel banner (2026-11-10, tools/make_banner.py)
    p = os.path.join(ROOT, a.video[7:])
    url = yt.channelBanners().insert(media_body=MediaFileUpload(p, mimetype="image/jpeg")).execute()["url"]
    ch = yt.channels().list(part="brandingSettings", id=me["id"]).execute()["items"][0]
    bs = ch["brandingSettings"]; bs.setdefault("image", {})["bannerExternalUrl"] = url   # resend the rest unchanged (update replaces the whole part)
    yt.channels().update(part="brandingSettings", body={"id": me["id"], "brandingSettings": bs}).execute()
    print("ok: banner"); sys.exit(0)
cmd, _, vid0 = a.video.partition(":")
if cmd in ("stop", "go", "status", "comment") and vid0:
    v = yt.videos().list(part="status", id=vid0).execute()["items"]
    if not v: sys.exit("no such video")
    st0 = v[0]["status"]
    if cmd == "status": print("privacy:", st0["privacyStatus"], "publishAt:", st0.get("publishAt", "-")); sys.exit(0)
    if cmd == "comment":
        yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": vid0, "topLevelComment": {"snippet": {"textOriginal": a.comment}}}}).execute()
        print("ok: comment"); sys.exit(0)
    new = {"privacyStatus": "private" if cmd == "stop" else "public", "selfDeclaredMadeForKids": False,
           "containsSyntheticMedia": st0.get("containsSyntheticMedia", False), "license": st0.get("license", "youtube"),
           "embeddable": st0.get("embeddable", True), "publicStatsViewable": st0.get("publicStatsViewable", True)}
    yt.videos().update(part="status", body={"id": vid0, "status": new}).execute()
    print(f"ok: {cmd}", vid0); sys.exit(0)
meta = json.load(open(os.path.join(ROOT, "channel", "meta", f"{a.name}.json"), encoding="utf-8"))

body = {
    "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta.get("tags", []),
                "categoryId": "28", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
    "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
               "license": "youtube", "embeddable": True, "publicStatsViewable": True},
}
if a.publish_at:   # scheduled: YouTube needs private + publishAt (UTC)
    from datetime import datetime, timezone
    t = datetime.fromisoformat(a.publish_at).astimezone(timezone.utc)
    body["status"]["privacyStatus"] = "private"; body["status"]["publishAt"] = t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
if meta.get("title_en"):
    body["localizations"] = {"en": {"title": meta["title_en"], "description": meta.get("description_en", "")}}
req = yt.videos().insert(part=",".join(body.keys()), body=body, notifySubscribers=True,
                         media_body=MediaFileUpload(a.video, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True))
res = None
while res is None:
    st, res = req.next_chunk()
    if st: print(f"uploading {int(st.progress() * 100)}%")
vid = res["id"]; print("video:", vid, "privacy:", res["status"]["privacyStatus"], res["status"].get("uploadStatus"), "publishAt:", res["status"].get("publishAt", "-"))
open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a").write(f"video_id={vid}\n")

def step(name, fn):
    try: fn(); print("ok:", name)
    except Exception as e: print("FAILED:", name, str(e)[:300])

thumb = os.path.join(ROOT, "channel", "thumbs", f"{a.name}.jpg")
if os.path.exists(thumb):
    step("thumbnail", lambda: yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb, mimetype="image/jpeg")).execute())
srt = os.path.join(ROOT, "channel", "captions", f"{a.name}_ja.srt")
if os.path.exists(srt):
    step("captions ja", lambda: yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "ja", "name": "日本語", "isDraft": False}},
                                                      media_body=MediaFileUpload(srt, mimetype="application/octet-stream")).execute())
def add_playlist():
    pls = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()["items"]
    pl = next(p for p in pls if p["snippet"]["title"] == PLAYLIST)
    yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl["id"], "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
step("playlist", add_playlist)
if a.comment and not a.publish_at:   # a scheduled (private) video gets its comment after it goes public (workflow job "comment")
    step("comment", lambda: yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": a.comment}}}}).execute())
print(f"https://youtube.com/shorts/{vid}")
open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a").write(f"uploaded https://youtube.com/shorts/{vid} ({res['status']['privacyStatus']})\n")
