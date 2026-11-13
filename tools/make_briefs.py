"""Make one short brief per edition worker from tools/spec.md + tools/style.md (2026-11-14, the user's request: save Claude usage
without lowering quality). Nothing is cut from the rules themselves: only the parts written for OTHER categories are left out
(each of the 16 workers used to read all 34KB, twice a day).
usage: python3 tools/make_briefs.py <out dir> [TODAY=2026-11-14 WORKDIR=/x NEWS=/x/news/ED EDITION=朝刊]
       -> <out>/brief_<worker>.md for every worker in tools/news_sites.json ({KEY} in the rules is replaced by the values given)
The workers read their brief instead of spec.md + style.md. If this script fails, give them spec.md + style.md as before."""
import json, os, re, sys

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
SUBS = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
spec = open("tools/spec.md", encoding="utf-8").read().split("\n")
style = open("tools/style.md", encoding="utf-8").read().split("\n")
workers = [k for k in json.load(open("tools/news_sites.json", encoding="utf-8")) if not k.startswith("_")]
# category key -> words used for it in style.md
JA = {"ai": ["AI"], "mobile": ["スマホ・パソコン"], "gadget": ["家電・ガジェット"], "service": ["ネットサービス・アプリ"],
      "game": ["ゲーム"], "ec": ["EC・決済"], "future": ["宇宙・未来技術"], "other": ["その他"]}
ALLJA = [w for v in JA.values() for w in v]


def spec_for(cat, worker):
    out, skip = [], False
    for ln in spec:
        m = re.match(r"^- (\w+) = ", ln)                         # a category definition bullet
        if m and m.group(1) in JA:
            skip = m.group(1) != cat
            if not skip: out.append(ln)
            continue
        if skip and ln.startswith("  ") and not ln.startswith("  -"): continue   # its continuation lines
        skip = False
        if ln.startswith("## Overseas") and worker != "ai_D":
            out.append(ln + " (you may meet one; the short version: say whether it is available in Japan, keep foreign prices in their currency)")
            skip_over = True
            continue
        out.append(ln)
    # drop the body of the Overseas section for non-ai_D workers
    if worker != "ai_D":
        res, inside = [], False
        for ln in out:
            if ln.startswith("## Overseas"): inside = True; res.append(ln); continue
            if inside and ln.startswith("## "): inside = False
            if not inside: res.append(ln)
        out = res
    return out


def style_for(cat):
    mine = JA[cat]; out, skip = [], False
    for ln in style:
        m = re.match(r"^- \*\*(.+?)\*\*", ln)                    # category blocks in section 1
        if m and any(w in m.group(1) for w in ALLJA):
            skip = not any(w in m.group(1) for w in mine)
            if not skip: out.append(ln)
            continue
        if skip and (ln.startswith("  ") or ln.strip() == ""):
            if ln.strip() == "": skip = False; out.append(ln)
            continue
        skip = False
        m2 = re.match(r"^  - (.+?)：", ln)                        # the rina-view per-category list
        if m2 and any(w in m2.group(1) for w in ALLJA) and not any(w in m2.group(1) for w in mine) and "新商品" not in m2.group(1): continue
        if m2 and "新商品" in m2.group(1) and cat not in ("mobile", "gadget", "game"): continue
        out.append(ln)
    return out


for w in workers:
    cat = w.split("_")[0]
    text = (f"# {w} の指示書（tools/spec.md と tools/style.md から、担当 {cat} に要る部分だけを集めたもの。ルールは省いていない）\n\n"
            + "\n".join(spec_for(cat, w)) + "\n\n---\n\n" + "\n".join(style_for(cat)) + "\n")
    for k, v in SUBS.items(): text = text.replace("{" + k + "}", v)
    open(os.path.join(OUT, f"brief_{w}.md"), "w", encoding="utf-8").write(text)
full = os.path.getsize("tools/spec.md") + os.path.getsize("tools/style.md")
sizes = {w: os.path.getsize(os.path.join(OUT, f"brief_{w}.md")) for w in workers}
print(f"spec+style {full} bytes -> briefs {min(sizes.values())}-{max(sizes.values())} bytes")
