"""Keep finished Shorts and their materials in Google Drive, from GitHub Actions (2026-11-12, Issue #11; user's choice).
Runs only on GitHub (.github/workflows/drive-login.yml once, then drive-store.yml). Never prints a key or token.

  python3 tools/drive_store.py login <out_file>
      Google's "device" sign-in: prints a short code and https://www.google.com/device. The user opens that page on any
      phone or PC, signs in as pastachannel0725 and allows access. The refresh token is written to <out_file> only
      (the workflow saves it as the GitHub secret DRIVE_REFRESH_TOKEN and deletes the file).
  python3 tools/drive_store.py put <kind> <file> [<file> ...]
      kind = video  -> Drive folder 「星餓りな 保管（自動）/ショート動画」
      kind = assets -> Drive folder 「星餓りな 保管（自動）/素材と試作」
      Skips a file whose name and size are already there. Exit 0 only when every file is in Drive with the same size.

Access is "drive.file": the app sees only the files and folders it made itself, nothing else in the Drive.
That is why it keeps its own folder 「星餓りな 保管（自動）」 (the user may move that folder anywhere; it keeps working).
Env: DRIVE_CLIENT_ID, DRIVE_CLIENT_SECRET (an OAuth client of the type "TVs and Limited Input devices" in the Google
Cloud project rina-youtube), DRIVE_REFRESH_TOKEN (after login)."""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

SCOPE = "https://www.googleapis.com/auth/drive.file"
ROOT = "星餓りな 保管（自動）"
SUB = {"video": "ショート動画", "assets": "素材と試作"}
# a client made for Drive if there is one, else the YouTube one (works only if that client allows the device sign-in)
CID = os.environ.get("DRIVE_CLIENT_ID") or os.environ.get("YT_CLIENT_ID", "")
CSEC = os.environ.get("DRIVE_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET", "")


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}")


def login(out):
    d = post("https://oauth2.googleapis.com/device/code", {"client_id": CID, "scope": SCOPE})
    if "user_code" not in d:
        print("could not start the sign-in:", d.get("error"), d.get("error_description", ""),
              "- if the client is not of the type 'TVs and Limited Input devices', make one and register DRIVE_CLIENT_ID / DRIVE_CLIENT_SECRET"); sys.exit(1)
    msg = (f"## Googleドライブの許可\n\n1. スマホかパソコンで {d['verification_url']} を開く\n"
           f"2. コード **{d['user_code']}** を入れる\n3. pastachannel0725 で入り、「許可」を押す\n\n"
           f"（{d['expires_in'] // 60}分以内に。この画面は待っていれば自動で進みます）\n")
    print(msg, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"): open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(msg)
    end, wait = time.time() + d["expires_in"], d.get("interval", 5)
    while time.time() < end:
        time.sleep(wait)
        t = post("https://oauth2.googleapis.com/token", {"client_id": CID, "client_secret": CSEC, "device_code": d["device_code"],
                                                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if "refresh_token" in t:
            with open(out, "w") as f: f.write(t["refresh_token"])
            print("ok: allowed (the key was saved, not shown)"); return
        if t.get("error") == "slow_down": wait += 5
        elif t.get("error") != "authorization_pending":
            print("sign-in stopped:", t.get("error")); sys.exit(1)
    print("time ran out - run the workflow again"); sys.exit(1)


def token():
    t = post("https://oauth2.googleapis.com/token", {"client_id": CID, "client_secret": CSEC, "grant_type": "refresh_token",
                                                    "refresh_token": os.environ["DRIVE_REFRESH_TOKEN"]})
    if "access_token" not in t: print("Drive sign-in failed:", t.get("error"), "- run drive-login.yml again"); sys.exit(1)
    return t["access_token"]


def api(tok, method, url, body=None, headers=None):
    h = {"Authorization": f"Bearer {tok}"} | (headers or {})
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    if isinstance(body, dict): h["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=600) as r:
        return r if method == "POST" and "uploadType=resumable" in url else json.load(r)


def find(tok, name, parent=None, folder=False):
    q = f"name = '{name}' and trashed = false" + (f" and '{parent}' in parents" if parent else "")
    q += " and mimeType " + ("=" if folder else "!=") + " 'application/vnd.google-apps.folder'"
    r = api(tok, "GET", "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id,name,size)", "spaces": "drive"}))
    return r.get("files", [])


def folder(tok, name, parent=None):
    f = find(tok, name, parent, folder=True)
    if f: return f[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"} | ({"parents": [parent]} if parent else {})
    return api(tok, "POST", "https://www.googleapis.com/drive/v3/files?fields=id", body)["id"]


def put(kind, files):
    tok = token()
    dest = folder(tok, SUB[kind], folder(tok, ROOT))
    bad = 0
    for p in files:
        name, size = os.path.basename(p), os.path.getsize(p)
        if any(int(x.get("size", -1)) == size for x in find(tok, name, dest)):
            print("already in Drive:", name); continue
        r = api(tok, "POST", "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id,size",
                {"name": name, "parents": [dest]}, {"X-Upload-Content-Length": str(size)})
        loc = r.headers["Location"]
        with open(p, "rb") as f:
            req = urllib.request.Request(loc, data=f.read(), method="PUT", headers={"Content-Length": str(size)})
        got = json.load(urllib.request.urlopen(req, timeout=1800))
        ok = int(got.get("size", -1)) == size
        print(("ok: " if ok else "SIZE MISMATCH: ") + name, f"{size / 1e6:.1f}MB")
        bad += not ok
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if sys.argv[1] == "check":   # can this client start the device sign-in? (no sign-in is made)
        d = post("https://oauth2.googleapis.com/device/code", {"client_id": CID, "scope": SCOPE})
        print("client:", "Drive" if os.environ.get("DRIVE_CLIENT_ID") else "YouTube", "| device sign-in:", "ok" if "user_code" in d else d.get("error"))
        sys.exit(0 if "user_code" in d else 1)
    if sys.argv[1] == "login": login(sys.argv[2])
    elif sys.argv[1] == "put": put(sys.argv[2], sys.argv[3:])
    else: print(__doc__); sys.exit(2)
