"""Make narration audio with Gemini TTS (no key in this file).
The API key is attached by the cloud environment's "network secret"
(host generativelanguage.googleapis.com, header x-goog-api-key), so the code never sees it.

usage: python3 -I tools/tts_gemini.py <lines.json> <out_dir>
lines.json: {"lines": ["scene1 text", ...], "voice": "Leda", "style": "...", "model": "gemini-3.8-flash-tts"}
writes <out_dir>/s1.wav, s2.wav, ... (24 kHz mono 16-bit) and prints each length in seconds."""
import base64, json, os, sys, time, urllib.error, urllib.request, wave

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
model = cfg.get("model", "gemini-3.8-flash-tts")
voice = cfg.get("voice", "Leda")
style = cfg.get("style", "若い女性のニュース読み上げ。明るく可愛らしく、親しみやすい声で、ややテンポよく、はっきり読む。")
# Instructions and spoken words are separated so the model never reads the style aloud
# (an unseparated style line was read out in a test on 2026-11-04).
PROMPT = """Synthesize speech for the performance below. The notes are direction only. Do NOT speak them. Speak ONLY the lines under #### TRANSCRIPT.

### PERFORMANCE
Style: {style}
Language: Japanese

#### TRANSCRIPT
{text}"""
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def speak(text):
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(style=style, text=text)}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    headers = {"Content-Type": "application/json"}
    if os.environ.get("GEMINI_API_KEY"):  # GitHub Actions: key comes from the repository secret
        headers["x-goog-api-key"] = os.environ["GEMINI_API_KEY"]
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.load(r)
            part = d["candidates"][0]["content"]["parts"][0]["inlineData"]
            return base64.b64decode(part["data"])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(15 * (attempt + 1)); continue
            sys.exit(f"Gemini TTS error {e.code}: {msg}")


for i, text in enumerate(cfg["lines"], 1):
    pcm = speak(text)
    path = os.path.join(out, f"s{i}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    print(f"s{i}.wav {len(pcm) / 48000:.2f}s")
    time.sleep(7)  # stay under ~10 requests per minute
