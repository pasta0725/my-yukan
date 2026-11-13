"""Official-picture choice by Codex (2026-11-14, the user's request: move work from Claude to Codex to save Claude usage).
Runs on GitHub Actions in official-images.yml (input codex_pick=yes), after tools/find_official_images.py.

  prep    <find out dir> <jobs dir>     one job folder per story: story.jpg (the candidates, bigger than on the contact sheet,
                                        numbered like candidates.json) and info.md (the article and each candidate's page/size)
  collect <find out dir> <jobs dir> <out dir>
                                        checks every <job>/pick.json and writes <out>/picks_codex.json (the format
                                        tools/pick_official_images.py takes) and <out>/report.md (picked / skipped and why)
"""
import io, json, os, re, sys

REFERER = "https://rina-tech-news.pages.dev/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def article(date, sid):
    try:
        for a in json.load(open(f"data/{date}.json", encoding="utf-8"))["articles"]:
            if a["id"] == sid: return a
    except Exception:
        pass
    return {}


def prep(src, jobs):
    import requests
    from PIL import Image, ImageDraw, ImageFont
    cand = json.load(open(os.path.join(src, "candidates.json"), encoding="utf-8"))
    try: f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    except Exception: f1 = ImageFont.load_default()
    CW, CH, COLS = 480, 330, 4
    for sid, c in cand.items():
        d = os.path.join(jobs, sid); os.makedirs(d, exist_ok=True)
        imgs = c["imgs"]
        rows = (len(imgs) + COLS - 1) // COLS
        sheet = Image.new("RGB", (CW * COLS, (CH + 50) * rows), "white")
        dr = ImageDraw.Draw(sheet)
        for i, im in enumerate(imgs):
            x, y = (i % COLS) * CW, (i // COLS) * (CH + 50)
            try:
                r = requests.get(im["src"], headers={"User-Agent": UA, "Referer": REFERER}, timeout=30)
                pic = Image.open(io.BytesIO(r.content)).convert("RGB"); pic.thumbnail((CW - 10, CH - 10))
                sheet.paste(pic, (x + (CW - pic.width) // 2, y + (CH - pic.height) // 2))
            except Exception:
                dr.text((x + 20, y + 140), "(could not load)", fill="red", font=f1)
            dr.rectangle([x, y + CH, x + 70, y + CH + 48], fill=(255, 138, 0))
            dr.text((x + 12, y + CH), str(im["n"]), fill="black", font=f1)
            dr.rectangle([x, y, x + CW - 1, y + CH + 49], outline=(190, 190, 190))
        sheet.save(os.path.join(d, "story.jpg"), quality=88)
        a = article(c["date"], sid)
        txt = [b.get("text", "") for b in a.get("body", []) if b.get("type") in ("h", "p")]
        info = [f"# {c['title']}", "", f"summary: {c.get('summary', '')}", "", "## article text", *txt, "",
                f"## pictures already in the article: {sum(1 for b in a.get('body', []) if b.get('type') == 'img') + (1 if a.get('image') else 0)}",
                "", "## candidates (n | size | page it was found on | credit | alt text)"]
        info += [f"{im['n']} | {im.get('w')}x{im.get('h')} | {im['page']} | {im.get('credit', '')} | {im.get('alt', '')}" for im in imgs]
        open(os.path.join(d, "info.md"), "w", encoding="utf-8").write("\n".join(info) + "\n")
    print("pick jobs:", len(cand))


def collect(src, jobs, out):
    cand = json.load(open(os.path.join(src, "candidates.json"), encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    picks, rows = {}, []
    for sid, c in cand.items():
        f = os.path.join(jobs, sid, "pick.json")
        if not os.path.exists(f): rows.append((sid, "未処理", "no pick.json")); continue
        try:
            p = json.load(open(f, encoding="utf-8"))
            items = p.get(sid, p.get("picks", [])) if isinstance(p, dict) else p
            assert isinstance(items, list)
        except Exception as e:
            rows.append((sid, "却下", f"invalid: {e}")); continue
        ns = {im["n"] for im in c["imgs"]}
        ok, bad = [], []
        for it in items:
            n, cap = (it.get("n"), str(it.get("caption", "")).strip()) if isinstance(it, dict) else (None, "")
            if n not in ns: bad.append(f"unknown n {n}"); continue
            if any(o["n"] == n for o in ok): continue
            if not cap or len(cap) > 60 or not re.search(r"[぀-ヿ一-鿿]", cap) or re.search(r"https?://", cap):
                bad.append(f"bad caption for {n}"); continue
            ok.append({"n": n, "caption": cap})
        if bad: rows.append((sid, "却下", "; ".join(bad))); continue
        why = ""
        if os.path.exists(os.path.join(jobs, sid, "why.txt")): why = open(os.path.join(jobs, sid, "why.txt"), encoding="utf-8").read().strip().replace("\n", " ")[:200]
        if ok: picks[sid] = ok
        rows.append((sid, f"{len(ok)}枚" if ok else "選ばず", why))
    json.dump(picks, open(os.path.join(out, "picks_codex.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep = [f"# Codexの公式画像選び：{len(picks)}本に{sum(len(v) for v in picks.values())}枚（候補のある{len(cand)}本中）", "",
           "| 記事id | 結果 | 理由 |", "|---|---|---|"] + [f"| {s} | {r} | {w.replace('|', '/')} |" for s, r, w in rows]
    open(os.path.join(out, "report.md"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    if sys.argv[1] == "prep": prep(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "collect": collect(sys.argv[2], sys.argv[3], sys.argv[4])
    else: sys.exit(__doc__)
