"""Screen check of a finished Short by ChatGPT (Codex), used by .github/workflows/codex-frame-check.yml (2026-11-14, user's
request: save Claude's quota, keep the quality). Replaces the Claude Sonnet sub-agent that looked at a 1-frame-per-second
contact sheet; that sub-agent stays as the fallback when this says FAILED.

  python3 codex_frame_check.py prep <video.mp4> <workdir> [--script spec.json|lines.json|.srt|.txt] [--plan plan.js] [--thumb thumb.jpg]
      makes <workdir>/frames (full size, 1 per second), <workdir>/sheets (what Codex is shown), prompt.txt and schema.json
  python3 codex_frame_check.py report <workdir> <name> <out.md>
      reads <workdir>/last.json (Codex's answer) and writes the report; exit 0 = OK, 1 = LOOK, 2 = FAILED

Sheets: "all_*" = every second (3x2, with the YouTube cut lines drawn), "tel_*" = the caption area of every caption chunk
at full size (taken at the middle of each chunk from plan.js, else every 0.5 s), "thumb" = thumbnail full + 168 px wide."""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if os.path.exists(f)), None)


def font(n):
    return ImageFont.truetype(FONT, n) if FONT else ImageFont.load_default()


def label(im, s, n=30):
    d = ImageDraw.Draw(im); f = font(n); b = d.textbbox((0, 0), s, font=f)
    d.rectangle((0, 0, b[2] + 16, b[3] + 12), fill=(0, 0, 0)); d.text((8, 4), s, font=f, fill=(255, 255, 0))
    return im


def mmss(t):
    return f"{int(t) // 60}:{t - int(t) // 60 * 60:04.1f}"


def grab(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", out], check=True)
    return os.path.exists(out)


def duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True)
    return float(r.stdout.strip())


def plan_of(path):
    if not path or not os.path.exists(path): return None
    s = open(path, encoding="utf-8").read()
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", s, re.S)
    try: return json.loads(m.group(1)) if m else None
    except Exception: return None


def script_text(path):
    if not path or not os.path.exists(path): return ""
    s = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        try:
            d = json.loads(s); L = d.get("lines", d) if isinstance(d, dict) else d
            return "\n".join(f"- {x.get('show') or x.get('text') or x.get('say', '')}" for x in L if isinstance(x, dict)).replace("{SEC}", "（秒数）")
        except Exception: pass
    if path.endswith(".srt"):
        return "\n".join(l for l in s.splitlines() if l.strip() and not l.strip().isdigit() and "-->" not in l)
    return s[:6000]


def grid(tiles, cols, tw, th, out):
    rows = (len(tiles) + cols - 1) // cols; gap = 12
    sheet = Image.new("RGB", (cols * tw + (cols - 1) * gap, rows * th + (rows - 1) * gap), (90, 90, 90))
    for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * (tw + gap), (i // cols) * (th + gap)))
    sheet.save(out)


def guides(im):
    o = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(o)
    d.rectangle((0, 180, W, 280), fill=(255, 0, 255, 60))                 # search icon band
    d.rectangle((0, 0, 50, H), fill=(255, 0, 255, 60)); d.rectangle((W - 50, 0, W, H), fill=(255, 0, 255, 60))  # cut sides
    return Image.alpha_composite(im.convert("RGBA"), o).convert("RGB")


def prep(video, wd, script=None, plan=None, thumb=None):
    for d in ("frames", "sheets"): os.makedirs(os.path.join(wd, d), exist_ok=True)
    T = duration(video); n = int(T)
    # 1 frame per second, full size (Codex may open them with its image viewer to look closer)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", "fps=1", "-start_number", "0", os.path.join(wd, "frames", "t_%03d.png")], check=True)
    secs = sorted(int(f[2:5]) for f in os.listdir(os.path.join(wd, "frames")) if f.startswith("t_"))
    tw, th = 480, 853
    for k in range(0, len(secs), 6):
        tiles = [label(guides(Image.open(os.path.join(wd, "frames", f"t_{s:03d}.png"))).resize((tw, th)), mmss(s), 34) for s in secs[k:k + 6]]
        grid(tiles, 3, tw, th, os.path.join(wd, "sheets", f"all_{k // 6 + 1:02d}.png"))
    # the caption area, full size, once per caption chunk
    P = plan_of(plan); tel = []
    if P and P.get("tel"): tel = [((x["start"] + x["end"]) / 2, x.get("text", "")) for x in P["tel"]]
    else: tel = [(t / 2 + 0.25, "") for t in range(int(T * 2))]
    crops = []
    for i, (t, _) in enumerate(tel):
        f = os.path.join(wd, "frames", f"c_{i:03d}.png")
        if t < T and grab(video, t, f): crops.append((t, Image.open(f).crop((40, 1230, 1040, 1680))))
    for k in range(0, len(crops), 8):
        grid([label(im.copy(), mmss(t), 28) for t, im in crops[k:k + 8]], 2, 1000, 450, os.path.join(wd, "sheets", f"tel_{k // 8 + 1:02d}.png"))
    if thumb and os.path.exists(thumb):
        im = Image.open(thumb).convert("RGB"); small = im.resize((168, round(im.height * 168 / im.width)))
        big = im.resize((900, round(im.height * 900 / im.width)))
        sheet = Image.new("RGB", (900 + 40 + 168, max(big.height, small.height)), (255, 255, 255))
        sheet.paste(big, (0, 0)); sheet.paste(small, (940, 0)); sheet.save(os.path.join(wd, "sheets", "thumb.png"))
    tel_list = "\n".join(f"- {mmss(t)} {s}" for t, s in tel if s)
    prompt = PROMPT.format(T=f"{T:.1f}", script=script_text(script) or "（台本なし）", tel=tel_list or "（予定の字幕一覧なし）",
                           thumb="あり（thumb.png：左が原寸に近い大きさ、右が幅168pxに縮めたもの）" if thumb and os.path.exists(thumb) else "なし")
    open(os.path.join(wd, "prompt.txt"), "w", encoding="utf-8").write(prompt)
    json.dump(SCHEMA, open(os.path.join(wd, "schema.json"), "w"), ensure_ascii=False)
    print("sheets:", " ".join(sorted(os.listdir(os.path.join(wd, "sheets")))))


PROMPT = """あなたは YouTube ショート動画（縦 1080x1920、長さ {T} 秒、日本語）の最終の画面チェック係です。作った人とは別の目で、投稿前に見落としを探してください。
添付画像:
- all_XX.png：1秒ごとの全画面（左上の黄色い字が動画の時刻 分:秒）。ピンクの帯は YouTube の画面で隠れる所（左右の端 50px、上の y180〜280 は検索の虫眼鏡）。帯そのものは動画にはありません。
- tel_XX.png：右下の吹き出し・字幕の部分を原寸で切り出したもの（字幕の切り替えごとに1枚、左上が時刻）。誤字・改行はこちらで細かく見る。
- thumb.png：サムネイル（{thumb}）。
同じフォルダの frames/ に原寸のコマ（t_秒.png、c_番号.png）があります。怪しい所は画像を開く道具で拡大して確かめてよい。ファイルは変更しないこと。

点検する項目（1つでも当てはまれば LOOK）:
1. 空の吹き出し：白い吹き出しが出ているのに中に文字がない（出始め・消え際の一瞬のコマでも、中身が無ければ書く）。
2. 改行：吹き出し・字幕の行頭が助詞（は が を に で と も の へ や から まで より）・小さい字（ゃ ゅ ょ っ ャ ュ ョ ッ ー 、。）・「た」「だ」で始まる。「」の中で改行。数字と単位・カタカナ語・英単語・ひらがなの単語の途中で改行。3文字未満しかない行。
3. はみ出し：文字がカード・吹き出し・アイコン（カレンダー等）の枠から出ている、他の文字や絵と重なって読めない、画面の端で切れている。
4. YouTube の画面との重なり：文字や大事な絵がピンクの帯（左右の端、上の y180〜280）に入っている。りなの体（左下の女の子のイラスト）が下のほうで帯や画面下部に入るのは問題ない。
5. 誤字：画面の文字を下の「台本」「予定の字幕」と比べ、違う漢字（例：疑う→擬う）、抜けた字・余計な字、変換の誤り、数字の違いがないか。台本と言い回しが少し違うだけで意味も字も正しいものは問題なし。
6. サムネイル（ある場合）：誤字、幅168pxでも主な文字が読めるか。
上の項目以外の好み（色・デザイン）は書かない。見えない・判断できない所は推測で OK にせず LOOK にする。

台本（字幕のもと）:
{script}

予定の字幕（時刻と文字。吹き出しに出るはずのもの）:
{tel}

答えは指定の JSON だけ。result は問題が1つもなければ "OK"、1つでもあれば "LOOK"。items は問題ごとに1つ：time は "0:24" のような時刻（サムネは "thumb"）、what は「空の吹き出し」「改行」「はみ出し」「UIと重なり」「誤字」「サムネ」のどれか、where は画面のどこか（例：右下の吹き出し、上のカレンダーのカード）、detail は何がどうおかしいかを日本語で短く（見えた文字をそのまま引用）。checked は見た画像の枚数。thumbnail はサムネの判定を1行（無ければ「なし」）。"""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["result", "items", "thumbnail", "checked"],
          "properties": {"result": {"type": "string", "enum": ["OK", "LOOK"]},
                         "items": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                              "required": ["time", "what", "where", "detail"],
                                                              "properties": {k: {"type": "string"} for k in ["time", "what", "where", "detail"]}}},
                         "thumbnail": {"type": "string"}, "checked": {"type": "integer"}}}


def report(wd, name, out):
    run = os.environ.get("GITHUB_RUN_ID", "local")
    head = f"# 画面の確認（Codex）{name}\n\nrun {run}・{os.environ.get('MODEL', '')}\n\n"
    try:
        d = json.load(open(os.path.join(wd, "last.json"), encoding="utf-8")); assert d["result"] in ("OK", "LOOK")
    except Exception as e:
        body = ("RESULT: FAILED\n\n" + head + f"Codex の答えが得られませんでした（{type(e).__name__}）。"
                "この動画は従来どおり、作った本人ではない Claude Sonnet のサブエージェントに1秒ごとのコマ一覧を見せて確認する"
                "（tools/auto_short.md「人の代わりの確認」2）。\n")
        open(out, "w", encoding="utf-8").write(body); print(body); return 2
    lines = [f"- LOOK {x['time']}｜{x['what']}｜{x['where']}｜{x['detail']}" for x in d["items"]]
    res = "LOOK" if lines else "OK"   # an item always means LOOK, whatever "result" says
    body = f"RESULT: {res}\n\n" + head + ("\n".join(lines) + "\n\n" if lines else "問題は見つかりませんでした。\n\n") + \
        f"サムネ：{d.get('thumbnail', '')}\n\n見た画像：{d.get('checked', '')}枚\n"
    open(out, "w", encoding="utf-8").write(body); print(body); return 0 if res == "OK" else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["prep"] and len(a) >= 3:
        opt = {a[i]: a[i + 1] for i in range(3, len(a) - 1, 2)}
        prep(a[1], a[2], opt.get("--script"), opt.get("--plan"), opt.get("--thumb"))
    elif a[:1] == ["report"] and len(a) == 4: sys.exit(report(a[1], a[2], a[3]))
    else: print(__doc__); sys.exit(2)
