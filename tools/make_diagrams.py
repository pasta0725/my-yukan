"""Make a diagram picture (図解) for stories that have no official picture.

usage: python3 tools/make_diagrams.py data/<edition>.json [--specs specs.json] [--force] [--ids id1,id2]

The user's choice (2026-11-09): stories without an official image get a diagram made from the
story's own facts (not an AI-drawn picture), in the site's colors.

- Target: stories with no official ("press") picture, unless --force / --ids.
- A spec says what to draw. Without one, it is made automatically:
    "stat" block (1-3 numbers) -> type "number"; otherwise the "keys" block -> type "points".
- specs.json (optional, written by Claude for a better fit): {"<story id>": spec}
    {"type":"number",  "title":"...", "items":[{"value":"約3億7600万件","label":"2026年の累計"}, ...]}   1-3 items
    {"type":"timeline","title":"...", "items":[{"when":"11月4日","what":"発表"}, ...]}                    2-5 items
    {"type":"compare", "title":"...", "left":"今まで", "right":"これから", "rows":[{"label":"料金","left":"…","right":"…"}]}  1-4 rows
    {"type":"who",     "title":"...", "items":[{"label":"対象","text":"…"}, ...]}                        2-4 items
    {"type":"points",  "title":"...", "items":["…","…","…"]}                                             2-3 items
  Every number in a spec must appear in the story text, or the spec is rejected and the automatic one is used.
- Output: data/diagrams/<edition>/<story id>.png (1200x675) and story["diagram"] = {src, caption, credit}.
  The app and the public site show it when the story has no official picture.
"""
import argparse, html, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = {"ai": ("AI", "#735BA9"), "mobile": ("スマホ・パソコン", "#007894"), "gadget": ("家電・ガジェット", "#007D70"),
       "service": ("ネットサービス・アプリ", "#A44A5E"), "game": ("ゲーム", "#92508C"), "ec": ("EC・決済", "#806A00"),
       "future": ("宇宙・未来技術", "#427C35"), "other": ("その他", "#474D58"), "kaden": ("家電・ガジェット", "#007D70"),
       "fukugyo": ("EC・決済", "#806A00")}
E = lambda s: html.escape(str(s or ""))


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[,\s]", "", s)


def story_text(a):
    parts = [a.get("title", ""), a.get("summary", "")]
    for b in a.get("body", []):
        if b.get("text"): parts.append(b["text"])
        for it in b.get("items", []) or []:
            parts.append(json.dumps(it, ensure_ascii=False) if isinstance(it, dict) else str(it))
    return norm(" ".join(parts))


def numbers_ok(spec, text):
    bad = []
    for s in re.findall(r'"([^"]*)"', json.dumps(spec, ensure_ascii=False)):
        for n in re.findall(r"\d[\d,.]*", norm(s)):
            if n.rstrip(".") not in text: bad.append(n)
    return bad


def has_press(a):
    if (a.get("image") or {}).get("kind") == "press": return True
    for b in a.get("body", []):
        if b.get("type") == "img" and b.get("kind") == "press": return True
        if b.get("type") == "gallery" and any(x.get("kind") == "press" for x in b.get("items", [])): return True
    return False


def auto_spec(a):
    stat = next((b for b in a.get("body", []) if b.get("type") == "stat" and b.get("items")), None)
    title = a.get("title", "")
    if stat:
        items = [{"value": i.get("value", ""), "label": i.get("label", "")} for i in stat["items"][:3] if i.get("value")]
        if items: return {"type": "number", "title": title, "items": items}
    keys = next((b for b in a.get("body", []) if b.get("type") == "keys" and b.get("items")), None)
    if keys: return {"type": "points", "title": title, "items": [str(x) for x in keys["items"][:3]]}
    return {"type": "points", "title": title, "items": [a.get("summary", "")]}


def valid(spec):
    t = spec.get("type")
    if t == "number": return 1 <= len(spec.get("items", [])) <= 3
    if t == "timeline": return 2 <= len(spec.get("items", [])) <= 5
    if t == "compare": return 1 <= len(spec.get("rows", [])) <= 4 and spec.get("left") and spec.get("right")
    if t == "who": return 2 <= len(spec.get("items", [])) <= 4
    if t == "points": return 1 <= len(spec.get("items", [])) <= 3
    return False


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1200px;height:675px;overflow:hidden}
body{font-family:"Noto Sans CJK JP","Noto Sans JP",sans-serif;background:#EEF4FF;color:#0B1F4D;position:relative}
.top{position:absolute;left:0;top:0;width:1200px;height:200px;background:#0B1F4D;clip-path:polygon(0 0,100% 0,100% 78%,0 100%)}
.stripe{position:absolute;right:-40px;top:0;width:260px;height:200px;background:#1246C4;clip-path:polygon(35% 0,100% 0,100% 100%,0 100%)}
.stripe2{position:absolute;right:170px;top:0;width:34px;height:190px;background:#FF8A00;transform:skewX(-18deg)}
.kick{position:absolute;left:56px;top:30px;display:flex;gap:12px;align-items:center}
.cat{background:var(--c);color:#fff;font-weight:900;font-size:22px;padding:5px 16px;transform:skewX(-12deg)}
.cat span{display:inline-block;transform:skewX(12deg)}
.zu{color:#FFB074;font-weight:900;font-size:22px;letter-spacing:.1em}
h1{position:absolute;left:56px;top:74px;width:900px;height:96px;color:#fff;font-weight:900;font-size:40px;line-height:1.2;display:flex;align-items:center;overflow:hidden;text-wrap:balance;word-break:auto-phrase}
.main{position:absolute;left:48px;right:48px;top:222px;bottom:70px;display:flex;gap:22px}
.foot{position:absolute;left:56px;right:56px;bottom:22px;display:flex;justify-content:space-between;font-size:18px;color:#4B5B7A;font-weight:700}
.foot b{color:#1246C4}
.card{background:#fff;border:3px solid #CDDAF1;flex:1 1 0;min-width:0;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:18px 22px;text-align:center;position:relative}
.card:before{content:"";position:absolute;left:0;top:0;width:100%;height:10px;background:var(--c)}
.val{font-weight:900;color:#1246C4;font-size:112px;line-height:1.15;white-space:nowrap;letter-spacing:-.02em}
.val .u{font-size:.5em;letter-spacing:0;margin:0 .03em}
.n1 .val{font-size:150px}
.val.o{color:#C25E00}
.lab{margin-top:16px;font-size:32px;font-weight:700;line-height:1.35;word-break:auto-phrase}
.n1 .lab{font-size:38px}
.pts{flex:1;display:flex;flex-direction:column;gap:14px}
.pt{background:#fff;border-left:12px solid var(--c);flex:1;display:flex;align-items:center;gap:20px;padding:6px 24px;overflow:hidden}
.num{flex:none;width:52px;height:52px;background:#0B1F4D;color:#fff;font-weight:900;font-size:30px;display:flex;align-items:center;justify-content:center;transform:skewX(-10deg)}
.ptx{font-size:31px;font-weight:700;line-height:1.38}
.tl{flex:1;position:relative;display:flex;justify-content:space-between;align-items:center;gap:16px;padding-top:56px}
.tl:before{content:"";position:absolute;left:10px;right:10px;top:50%;margin-top:-4px;height:8px;background:#1246C4;z-index:0}
.ev{flex:1 1 0;min-width:0;position:relative;z-index:1;background:#fff;border:3px solid #CDDAF1;padding:26px 18px;text-align:center;max-height:100%;overflow:hidden}
.ev:before{content:"";position:absolute;left:0;top:0;width:100%;height:10px;background:#FF8A00}
.when{font-size:38px;font-weight:900;color:#1246C4;line-height:1.2}
.what{margin-top:12px;font-size:30px;font-weight:700;line-height:1.38}
table{flex:1;border-collapse:separate;border-spacing:0 10px;table-layout:fixed}
th{font-size:26px;font-weight:900;color:#fff;background:#0B1F4D;padding:10px}
th.r{background:#1246C4}
td{background:#fff;font-size:30px;font-weight:700;padding:10px 18px;line-height:1.3;text-align:center}
td.l{background:#DDE8FF;color:#0938AB;font-weight:900;width:22%}
td.r{color:#0B1F4D;border:3px solid #FF8A00}
.who{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:16px}
.w{background:#fff;border-top:10px solid var(--c);padding:16px 22px;display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.wl{display:inline-block;align-self:flex-start;background:#FFF3EA;color:#A75901;font-weight:900;font-size:22px;padding:3px 12px;margin-bottom:8px}
.wt{font-size:32px;font-weight:700;line-height:1.38}
"""
FIT = """
<script>
(()=>{
function fit(el,min){let s=parseFloat(getComputedStyle(el).fontSize);while((el.scrollHeight>el.clientHeight+1||el.scrollWidth>el.clientWidth+1)&&s>min){s-=1;el.style.fontSize=s+'px';}}
document.querySelectorAll('h1').forEach(e=>fit(e,26));
document.querySelectorAll('.val').forEach(e=>{e.style.display='block';e.style.width='100%';let z=parseFloat(getComputedStyle(e).fontSize);while(e.scrollWidth>e.clientWidth+1&&z>30){z-=2;e.style.fontSize=z+'px';}});
document.querySelectorAll('.card,.pt,.ev,.w').forEach(c=>{let k=0;while(c.scrollHeight>c.clientHeight+1&&k<40){c.querySelectorAll('.lab,.ptx,.what,.wt,.when').forEach(t=>{t.style.fontSize=(parseFloat(getComputedStyle(t).fontSize)-1)+'px'});k++;}});
let m=document.querySelector('.main'),k=0;while(m.scrollHeight>m.clientHeight+1&&k<40){m.querySelectorAll('.lab,.ptx,.what,.wt,td').forEach(t=>{t.style.fontSize=(parseFloat(getComputedStyle(t).fontSize)-1)+'px'});k++;}
document.body.dataset.done='1';
})();
</script>"""


def bignum(v):
    """digits big, words and units half size"""
    out = []
    for part in re.findall(r"[0-9０-９.,，．%％]+|[^0-9０-９.,，．%％]+", str(v or "")):
        out.append(E(part) if re.match(r"[0-9０-９.,，．%％]", part) else f'<span class="u">{E(part)}</span>')
    return "".join(out)


def title_html(t):
    """news titles are often 'A　B': put each part on its own line"""
    parts = [x for x in re.split(r"[\u3000]+| {2,}", str(t or "")) if x]
    return "<br>".join(E(x) for x in parts) if 1 < len(parts) <= 2 else E(t)


def page(a, spec):
    lab, color = CAT.get(a.get("category"), CAT["other"])
    t = spec["type"]
    if t == "number":
        n = len(spec["items"])
        main = f'<div class="nums n{n}" style="display:contents">' + "".join(f'<div class="card n{n}"><div class="val{" o" if i == 0 and n > 1 else ""}">{bignum(x.get("value"))}</div><div class="lab">{E(x.get("label"))}</div></div>'
                       for i, x in enumerate(spec["items"])) + "</div>"
    elif t == "timeline":
        main = '<div class="tl">' + "".join(f'<div class="ev"><div class="when">{E(x.get("when"))}</div><div class="what">{E(x.get("what"))}</div></div>' for x in spec["items"]) + "</div>"
    elif t == "compare":
        main = (f'<table><tr><th style="width:22%"></th><th>{E(spec["left"])}</th><th class="r">{E(spec["right"])}</th></tr>'
                + "".join(f'<tr><td class="l">{E(r.get("label"))}</td><td>{E(r.get("left"))}</td><td class="r">{E(r.get("right"))}</td></tr>' for r in spec["rows"]) + "</table>")
    elif t == "who":
        main = '<div class="who">' + "".join(f'<div class="w"><span class="wl">{E(x.get("label"))}</span><div class="wt">{E(x.get("text"))}</div></div>' for x in spec["items"]) + "</div>"
    else:
        main = '<div class="pts">' + "".join(f'<div class="pt"><div class="num">{i + 1}</div><div class="ptx">{E(x)}</div></div>' for i, x in enumerate(spec["items"])) + "</div>"
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body style="--c:{color}">'
            f'<div class="top"></div><div class="stripe"></div><div class="stripe2"></div>'
            f'<div class="kick"><span class="cat"><span>{E(lab)}</span></span><span class="zu">図解</span></div>'
            f'<h1><span>{title_html(spec.get("title") or a.get("title"))}</span></h1><div class="main">{main}</div>'
            f'<div class="foot"><span>記事の内容をもとに作成</span><b>星餓りなのテックニュース</b></div>{FIT}</body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edition")
    ap.add_argument("--specs", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ids", default="")
    a = ap.parse_args()
    path = a.edition
    ed = json.load(open(path, encoding="utf-8"))
    edid = ed.get("date") or os.path.basename(path)[:-5]
    specs = json.load(open(a.specs, encoding="utf-8")) if a.specs else {}
    only = {x for x in a.ids.split(",") if x}
    outdir = os.path.join(ROOT, "data", "diagrams", edid)
    jobs = []
    for s in ed["articles"]:
        if only and s["id"] not in only: continue
        if not only and not a.force and (has_press(s) or s.get("diagram")): continue
        spec = specs.get(s["id"])
        note = "auto"
        if spec:
            bad = numbers_ok(spec, story_text(s))
            if not valid(spec): note = "spec rejected (shape)"; spec = None
            elif bad: note = f"spec rejected (numbers not in story: {bad})"; spec = None
            else: note = "spec"
        jobs.append((s, spec or auto_spec(s), note))
    if not jobs:
        print("nothing to draw"); return
    os.makedirs(outdir, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=1)
        for s, spec, note in jobs:
            pg.set_content(page(s, spec), wait_until="load")
            pg.wait_for_function("document.body.dataset.done==='1'", timeout=10000)
            fn = re.sub(r"[^a-z0-9-]", "-", s["id"].lower()) + ".png"
            pg.screenshot(path=os.path.join(outdir, fn))
            rel = f"data/diagrams/{edid}/{fn}"
            cap = {"number": "数字で見る", "timeline": "時系列で見る", "compare": "比べて見る", "who": "誰に関係するか", "points": "要点"}[spec["type"]]
            s["diagram"] = {"src": rel, "kind": "diagram", "caption": f"図解：{cap}", "credit": "星餓りなのテックニュース", "type": spec["type"]}
            print(f'{s["id"]}: {spec["type"]} ({note})')
        b.close()
    try:  # make the files smaller (flat colors)
        from PIL import Image
        for s, _, _ in jobs:
            f = os.path.join(ROOT, s["diagram"]["src"])
            Image.open(f).convert("RGB").quantize(colors=128, method=Image.Quantize.MEDIANCUT).save(f, optimize=True)
    except Exception as e:
        print("compress skipped:", e)
    json.dump(ed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(jobs)} diagrams → {outdir}")


if __name__ == "__main__":
    main()
