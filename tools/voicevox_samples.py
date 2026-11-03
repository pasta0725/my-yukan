"""Make sample clips with a running VOICEVOX engine (http://127.0.0.1:50021).
usage: python3 -I tools/voicevox_samples.py <out_dir> "<text>"
Picks young female-sounding characters by name and writes <out_dir>/<character>_<style>.wav
Credit needed when used in videos: "VOICEVOX:<character name>"."""
import json, os, sys, urllib.parse, urllib.request

BASE = "http://127.0.0.1:50021"
out, text = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
WANT = {  # character: styles to try (first match wins if the style is missing)
    "四国めたん": ["ノーマル", "あまあま"],
    "春日部つむぎ": ["ノーマル"],
    "冥鳴ひまり": ["ノーマル"],
    "雨晴はう": ["ノーマル"],
    "九州そら": ["あまあま"],
    "WhiteCUL": ["たのしい"],
    "桜歌ミコ": ["ノーマル"],
    "小夜/SAYO": ["ノーマル"],
}
speakers = json.load(urllib.request.urlopen(f"{BASE}/speakers"))
for sp in speakers:
    if sp["name"] not in WANT:
        continue
    for st in sp["styles"]:
        if st["name"] not in WANT[sp["name"]]:
            continue
        q = urllib.request.urlopen(urllib.request.Request(
            f"{BASE}/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": st["id"]}), method="POST")).read()
        qd = json.loads(q); qd["speedScale"] = 1.1
        wav = urllib.request.urlopen(urllib.request.Request(
            f"{BASE}/synthesis?speaker={st['id']}", data=json.dumps(qd).encode(),
            headers={"Content-Type": "application/json"})).read()
        name = f"{sp['name'].replace('/', '_')}_{st['name']}.wav"
        open(os.path.join(out, name), "wb").write(wav)
        print("made", name)
