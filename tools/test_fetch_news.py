"""少ない候補と空の本文を、実際の朝刊の3記事を使って通信なしで確かめる。"""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch


class FetchNewsTests(unittest.TestCase):
    def test_short_list_and_empty_article(self):
        script = Path(__file__).with_name("fetch_news.py").resolve()
        edition = "2026-11-26-am"
        data = script.parent.parent / "data" / (edition + ".json")
        articles = json.loads(data.read_text(encoding="utf-8"))["articles"][:3]
        entries = [{"title": a["title"], "url": a["source_url"]} for a in articles]
        site = "https://example.invalid/"
        lists = {site + str(n): entries[:n] for n in (1, 2, 3)}
        article_text = {a["source_url"]: a["summary"] for a in articles[1:]}
        article_text[articles[0]["source_url"]] = ""

        def respond(url, **kwargs):
            if url in lists:
                return Mock(text="", headers={"content-type": "application/json"},
                            encoding="utf-8", **{"json.return_value": lists[url]})
            if url == site + "missing":
                return Mock(**{"raise_for_status.side_effect": OSError("404")})
            return Mock(text=article_text[url], headers={}, encoding="utf-8")

        def soup(text, parser):
            return MagicMock(**{"find.return_value": None, "find_all.return_value": [],
                                "body.find_all.return_value": [], "body.get_text.return_value": text})

        # 取得先の応答と、HTMLからの文字の読み出しを置き換える。
        modules = {"requests": SimpleNamespace(get=respond), "feedparser": SimpleNamespace(),
                   "bs4": SimpleNamespace(BeautifulSoup=soup)}
        workers = {"ai_A": ("1", "missing"), "ai_B": ("1", "2", "missing"), "ai_C": ("1", "3")}
        config = {worker: {"period_h": 72, "sites": [{"name": "一覧", "urls": [site + path for path in paths]}]}
                  for worker, paths in workers.items()}
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
            Path("tools").mkdir()
            Path("tools/news_sites.json").write_text(json.dumps(config), encoding="utf-8")
            with patch.dict(sys.modules, modules), patch.object(sys, "argv", [str(script), edition, "out"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(script), run_name="__main__")

            for worker, count in zip(workers, (1, 2, 3)):
                with self.subTest(worker=worker):
                    directory = Path("out") / worker
                    rows = (directory / "index.md").read_text(encoding="utf-8").splitlines()[2:]
                    self.assertEqual(len(rows), count)
                    self.assertTrue(rows[0].endswith("（本文なし）"))
                    for row, entry in zip(rows, entries):
                        self.assertIn(entry["url"], row)
                    self.assertTrue(all("（本文なし）" not in row for row in rows[1:]))
            report = Path("out/report.md").read_text(encoding="utf-8")
            self.assertIn("記事ページ 2/3 本の本文を取得", report)
            self.assertIn("404", report)


if __name__ == "__main__":
    unittest.main()
