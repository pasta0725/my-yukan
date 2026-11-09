"""Codex research helper (2026-11-10, user: let ChatGPT/Codex share the searching so Claude's 200-search limit is not hit).
Runs on GitHub Actions (.github/workflows/codex-research.yml).

  split:  python3 tools/research_pages.py split <stories.json> <n> <out_dir> [max_refs]
          stories.json = [{"id","title","summary","source_url"}...] or an edition file data/<ED>.json -> <out_dir>/shard_<k>.json
  fetch:  python3 tools/research_pages.py fetch <found.json> <out_dir>
          found.json = {"<id>": {"refs":[{"url","site","title"}], "official":{"url","images":[...]}}} (what Codex wrote)
          -> <out_dir>/<id>.txt  (each page: '===== url' line then its text) and <out_dir>/<id>.json (the found list, checked)
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
