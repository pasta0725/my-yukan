"""Take a Short's materials back from Google Drive (the zip that drive-store.yml made), 2026-11-14.
Used by .github/workflows/short-restore.yml, e.g. to make an old video again or to test the automatic pipeline.
Uses the same sign-in as tools/drive_store.py (DRIVE_CLIENT_ID, DRIVE_CLIENT_SECRET, DRIVE_REFRESH_TOKEN). Never prints a key.

  python3 tools/drive_get.py list <name>            list the zips 「<name>_素材_*.zip」 in 「星餓りな 保管（自動）/素材と試作」
  python3 tools/drive_get.py get <name> <out.zip>   download the newest of them (exit 1 if there is none)"""
import os, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drive_store as ds  # noqa: E402


def zips(tok, name):
    dest = ds.folder(tok, ds.SUB["assets"], ds.folder(tok, ds.ROOT))
    q = f"name contains '{name}_素材_' and trashed = false and '{dest}' in parents"
    r = ds.api(tok, "GET", "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(
        {"q": q, "fields": "files(id,name,size,createdTime)", "spaces": "drive", "orderBy": "createdTime desc"}))
    return [f for f in r.get("files", []) if f["name"].startswith(name + "_素材_")]


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("list", "get"): print(__doc__); sys.exit(2)
    tok = ds.token(); fs = zips(tok, sys.argv[2])
    for f in fs: print(f["name"], f"{int(f.get('size', 0)) / 1e6:.1f}MB", f.get("createdTime", ""))
    if sys.argv[1] == "get":
        if not fs: print("no zip for", sys.argv[2]); sys.exit(1)
        req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{fs[0]['id']}?alt=media", headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=1800) as r, open(sys.argv[3], "wb") as o:
            while True:
                b = r.read(1 << 20)
                if not b: break
                o.write(b)
        print("got", fs[0]["name"], os.path.getsize(sys.argv[3]), "bytes")
