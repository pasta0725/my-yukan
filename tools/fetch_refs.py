"""Download the reference pages of one edition and save their text, for the fact check (step 5-2).
Runs on GitHub Actions (.github/workflows/factcheck-pages.yml), so the Claude session never opens a web page itself.
usage: python3 tools/fetch_refs.py <edition id> <out dir> [edition file (default data/<edition id>.json)]
out: <out>/<story id>.txt  (each page: '===== url' line, then the page text, up to 20000 chars)
"""
import json, sys, os, re, concurrent.futures as cf
import requests
from bs4 import BeautifulSoup

ED, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
arts = json.load(open(sys.argv[3] if len(sys.argv) > 3 else f"data/{ED}.json"))["articles"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; my-yukan-factcheck)"}

def urls_of(a):
    us = [a.get("source_url")]
    for r in a.get("refs", []):
        us.append(r.get("url") if isinstance(r, dict) else r)
    seen, res = set(), []
    for u in us:
        if isinstance(u, str) and u.startswith("http") and u not in seen:
            seen.add(u); res.append(u)
    return res[:6]

def text_of(u):
    try:
        r = requests.get(u, headers=UA, timeout=30)
        r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
        if "pdf" in r.headers.get("content-type", ""): return "(PDF: not extracted)"
        s = BeautifulSoup(r.text, "html.parser")
        for t in s(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]): t.decompose()
        body = s.find("article") or s.find("main") or s.body or s
        t = re.sub(r"\n\s*\n+", "\n", body.get_text("\n"))
        return f"(status {r.status_code})\n" + t.strip()[:20000]
    except Exception as e:
        return f"(failed: {e})"

def job(a):
    parts = [f"===== {u}\n{text_of(u)}" for u in urls_of(a)]
    open(f"{OUT}/{a['id']}.txt", "w").write("\n\n".join(parts))

with cf.ThreadPoolExecutor(8) as ex: list(ex.map(job, arts))
print(len(arts), "stories")
