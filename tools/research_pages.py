"""Codex research helper (2026-11-10, user: let ChatGPT/Codex share the searching so Claude's 200-search limit is not hit).
Runs on GitHub Actions (.github/workflows/codex-research.yml).

  split:  python3 tools/research_pages.py split <stories.json> <n> <out_dir> [max_refs]
          stories.json = [{"id","title","summary","source_url"}...] or an edition file data/<ED>.json -> <out_dir>/shard_<k>.json
  fetch:  python3 tools/research_pages.py fetch <found.json> <out_dir>
          found.json = {"<id>": {"refs":[{"url","site","title"}], "official":{"url","images":[...]}}} (what Codex wrote)
          -> <out_dir>/<id>.txt  (each page: '===== url' line then its text) and <out_dir>/<id>.json (the found list, checked)
  export: python3 tools/research_pages.py export data/<ED>.json <dir>      one file <dir>/<id>.json per article (for the rewrite workers)
  import: python3 tools/research_pages.py import data/<ED>.json <dir>      put rewritten <dir>/<id>.json back (same id; id/category/image kept),
          and copy title/summary into data/x-todo.json
  imgjobs: python3 tools/research_pages.py imgjobs <research/ED dir> imgjobs/<ED>.json
          official pages Codex found -> {"<id>": [url]} for official-images.yml's "extra" input
"""
import json, os, re, sys, concurrent.futures as cf

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"}


def text_of(u):
    import requests
    from bs4 import BeautifulSoup
    try:
        r = requests.get(u, headers=UA, timeout=30)
        r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
        if "pdf" in r.headers.get("content-type", ""): return r.status_code, "(PDF: not extracted)"
        s = BeautifulSoup(r.text, "html.parser")
        for t in s(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]): t.decompose()
        body = s.find("article") or s.find("main") or s.body or s
        return r.status_code, re.sub(r"\n\s*\n+", "\n", body.get_text("\n")).strip()[:20000]
    except Exception as e:
        return 0, f"(failed: {e})"


if sys.argv[1] == "split":
    src, n, out = sys.argv[2], int(sys.argv[3]), sys.argv[4]
    d = json.load(open(src))
    arts = d["articles"] if isinstance(d, dict) else d
    rows = [{"id": a["id"], "title": a["title"], "summary": a.get("summary", ""), "source_url": a.get("source_url", ""),
             "have": [r.get("url") for r in a.get("refs", []) if isinstance(r, dict)]} for a in arts]
    if len(sys.argv) > 5: rows = [r for r in rows if len(r["have"]) <= int(sys.argv[5])]   # only stories with few refs
    os.makedirs(out, exist_ok=True)
    for k in range(n):
        json.dump(rows[k::n], open(f"{out}/shard_{k}.json", "w"), ensure_ascii=False, indent=1)
    print(len(rows), "stories in", n, "shards")

elif sys.argv[1] == "fetch":
    found, out = json.load(open(sys.argv[2])), sys.argv[3]
    os.makedirs(out, exist_ok=True)

    def job(item):
        sid, f = item
        refs = [r for r in f.get("refs", []) if isinstance(r, dict) and str(r.get("url", "")).startswith("http")][:5]
        off = f.get("official") or {}
        urls = [r["url"] for r in refs] + ([off["url"]] if str(off.get("url", "")).startswith("http") else [])
        parts, ok = [], 0
        for u in dict.fromkeys(urls):
            st, t = text_of(u)
            ok += 200 <= st < 300 and len(t) > 500
            parts.append(f"===== {u}\n(status {st})\n{t}")
        open(f"{out}/{sid}.txt", "w").write("\n\n".join(parts))
        json.dump({"refs": refs, "official": off}, open(f"{out}/{sid}.json", "w"), ensure_ascii=False, indent=1)
        return sid, len(refs), ok

    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(job, found.items()))
    for sid, n, ok in res: print(sid, "refs", n, "pages ok", ok)
    print("stories", len(res), "avg refs", round(sum(r[1] for r in res) / max(1, len(res)), 2))

elif sys.argv[1] == "export":
    ed, out = sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    for a in json.load(open(ed))["articles"]:
        json.dump(a, open(f"{out}/{a['id']}.json", "w"), ensure_ascii=False, indent=1)
    print("exported", len(os.listdir(out)))

elif sys.argv[1] == "import":
    ed, src = sys.argv[2], sys.argv[3]
    d = json.load(open(ed)); n = 0; bad = []
    for i, a in enumerate(d["articles"]):
        f = f"{src}/{a['id']}.json"
        if not os.path.exists(f): continue
        try:
            b = json.load(open(f))
            assert isinstance(b.get("body"), list) and b.get("title") and any(x.get("type") == "rina" for x in b["body"])
        except Exception as e:
            bad.append(f"{a['id']}: {e}"); continue
        for k in ("id", "category", "image"):
            if k in a: b[k] = a[k]
        refs = [r for r in b.get("refs", []) if isinstance(r, dict) and str(r.get("url", "")).startswith("http")]
        b["refs"] = list({r["url"]: r for r in refs}.values())[:6]
        if b != a: d["articles"][i] = b; n += 1
    json.dump(d, open(ed, "w"), ensure_ascii=False, indent=1)
    xt = os.path.join(os.path.dirname(ed), "x-todo.json")
    if os.path.exists(xt):
        x = json.load(open(xt)); by = {a["id"]: a for a in d["articles"]}
        for r in x.get("articles", []):
            if r["id"] in by: r["title"], r["summary"] = by[r["id"]]["title"], by[r["id"]]["summary"]
        json.dump(x, open(xt, "w"), ensure_ascii=False, indent=1)
    print("updated", n, "articles; skipped (broken):", bad)
    print("avg refs", round(sum(len(a.get("refs", [])) for a in d["articles"]) / max(1, len(d["articles"])), 2))

elif sys.argv[1] == "imgjobs":
    src, out = sys.argv[2], sys.argv[3]
    jobs = {}
    for f in sorted(os.listdir(src)):
        if not f.endswith(".json"): continue
        u = str((json.load(open(f"{src}/{f}")).get("official") or {}).get("url", ""))
        if u.startswith("http"): jobs[f[:-5]] = [u]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(jobs, open(out, "w"), ensure_ascii=False, indent=1)
    print("official pages:", len(jobs))
