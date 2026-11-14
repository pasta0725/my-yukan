"""実際の7記事で、書き足し・点検の一覧に抜けがないか通信なしで確かめる。"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import codex_check as check


class ReportTests(unittest.TestCase):
    def run_check(self, *args):
        subprocess.run([sys.executable, "-B", check.__file__, *map(str, args)],
                       check=True, capture_output=True, text=True)

    def test_report_keeps_skipped_articles(self):
        edition = Path(__file__).resolve().parents[1] / "data/2026-11-14-pm.json"
        articles = json.loads(edition.read_text(encoding="utf-8"))["articles"][:7]
        for mode in ("fill", "fact"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                src, jobs, done, out = [root / name for name in ("src", "jobs", "done", "out")]
                src.mkdir()
                ed = root / "edition.json"
                ed.write_text(json.dumps({"articles": articles}), encoding="utf-8")
                new_url = "https://example.invalid/new"
                body = "\n".join(t for _, t in check.texts(articles[6]))
                pages = [None, (new_url, 403, body), (new_url, 200, "短" * 200),
                         (articles[3]["refs"][0]["url"], 200, body),
                         ("https://news.yahoo.co.jp/articles/test", 200, body),
                         (new_url, 200, body), (new_url, 200, body)]
                for article, page in zip(articles, pages):
                    if page is not None:
                        url, status, text = page
                        (src / (article["id"] + ".txt")).write_text(
                            f"===== {url}\n(status {status})\n{text}", encoding="utf-8")
                self.run_check("prep-" + mode, ed, src, jobs, 3)
                task_ids = {p.parent.name for p in jobs.rglob("article.json")}
                expected = articles[5:] if mode == "fill" else articles[1:]
                self.assertEqual(task_ids, {a["id"] for a in expected})
                for path in jobs.rglob("article.json"):
                    article = json.loads(path.read_text(encoding="utf-8"))
                    if article["id"] == articles[6]["id"]:
                        changed = copy.deepcopy(article)
                        paragraph = next(b for b in changed["body"] if b["type"] == "p")
                        paragraph["text"] = paragraph["text"].replace("。", "。\n", 1)
                        (path.parent / "out.json").write_text(json.dumps(changed), encoding="utf-8")
                    elif article["id"] == articles[5]["id"]:
                        (path.parent / "out.json").write_text(json.dumps(article), encoding="utf-8")
                    elif article["id"] == articles[2]["id"]:
                        (path.parent / "out.json").write_text("{", encoding="utf-8")
                # 実際の作業と同じく、組ごとの成果物を別々のフォルダに集める。
                for shard in jobs.iterdir():
                    shutil.copytree(shard, done / (mode + shard.name))
                self.run_check("collect", mode, done, out)
                report = (out / "report.md").read_text(encoding="utf-8")
                rows = [[cell.strip() for cell in line.strip("|").split("|")]
                        for line in report.splitlines() if line.startswith("| ")][1:]
                self.assertEqual(len(rows), len(articles))
                results = {row[0]: (row[1], row[2]) for row in rows}
                self.assertEqual(set(results), {a["id"] for a in articles})
                for article in articles[:5] if mode == "fill" else articles[:1]:
                    result, reason = results[article["id"]]
                    self.assertEqual(result, "対象外")
                    self.assertTrue(reason)
                if mode == "fact":
                    self.assertEqual(results[articles[1]["id"]][0], "未処理")
                    self.assertEqual(results[articles[2]["id"]][0], "却下")
                self.assertEqual(results[articles[5]["id"]][0], "変更なし")
                self.assertEqual(results[articles[6]["id"]][0], "採用")
                self.assertEqual({p.stem for p in out.glob("*.json")}, {articles[6]["id"]})

    def test_report_when_all_pages_are_missing(self):
        edition = Path(__file__).resolve().parents[1] / "data/2026-11-14-pm.json"
        ids = {a["id"] for a in json.loads(edition.read_text(encoding="utf-8"))["articles"]}
        for mode in ("fill", "fact"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs, out = root / "jobs", root / "out"
                self.run_check("prep-" + mode, edition, root / "missing", jobs, 8)
                self.assertFalse(list(jobs.rglob("article.json")))
                # 記事のフォルダがなければ、Codexを動かす作業も作られない。
                self.assertFalse([p for p in jobs.glob("*/*") if p.is_dir()])
                self.run_check("collect", mode, jobs, out)
                report = (out / "report.md").read_text(encoding="utf-8")
                rows = [line for line in report.splitlines() if " | 対象外 | " in line]
                self.assertEqual({line.split("|")[1].strip() for line in rows}, ids)
                self.assertEqual(len(rows), len(ids))
                self.assertFalse(list(out.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
