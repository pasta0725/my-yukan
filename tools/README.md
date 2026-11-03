# マイ夕刊の作り方（Claude用メモ）

1. `git pull` して最新にする。作業フォルダ WORKDIR を作り、直近の号の source_url を `WORKDIR/used.txt` に書き出す。
2. サブエージェントへの指示にサイトのURLを書かない（許可確認が出るため）。サイト名だけ伝え、URLは検索結果から辿らせる。`tools/spec.md` の {TODAY} と {WORKDIR} を置き換えた指示で、Sonnet のサブエージェント9本を並列に動かす（各6本）。
   - ai: A=ITmedia AI+/NEWS、B=Impress Watch・Publickey・日経クロステック、C=各社公式発表
   - kaden: A=家電 Watch、B=ケータイ/AV/PC Watch、C=ITmedia Mobile・PC USER・マイナビ・メーカー公式
   - fukugyo: A=ネットショップ担当者フォーラム、B=各サービス公式お知らせ、C=ECのミカタ・公的機関
   - 出力は WORKDIR/{ai,kaden,fukugyo}_{A,B,C}.json
3. `python3 -I tools/build_edition.py WORKDIR YYYY-MM-DD [重複して外すid ...]` で data/ を作る（重複・ニュース写真2枚制限・14日分の一覧を自動処理）。
4. 見出し一覧を見て、同じ出来事が別ジャンルにも入っていれば id を指定して作り直す。
5. コミットして main に push する。

## Xの声（Grok Bot）
- build_edition.py writes data/x-todo.json (today's story list) every run. Commit it with the edition.
- Grok Bot reads it and returns JSON (prompt: tools/grok.md). Save with `python3 -I tools/save_x.py <answer.txt> <date>` → data/x/<date>.json, commit, push. The site merges it.
- Writing rules: tools/style.md (第2版, from 2026-11-04). Workers must read it.
- Since 2026-11-04 (no PC needed): 14:22 cloud task (Sonnet workers with effort high) 「マイ夕刊 毎日の号づくり」 pushes the edition + data/x-todo.json by 16:15. 16:20 Grok Bot routine (its own cloud PC, GitHub token) runs save_x.py and pushes data/x/<date>.json directly (fallback: mails the JSON, subject 「マイ夕刊 Xの声 <date>」, to pastachannel0725@gmail.com). 17:19 cloud task 「Xの声の取り込み（2回目）と完成報告」 imports from Gmail only if data/x/<date>.json is missing, then sends the completion push notification. Prompts: tools/grok.md.
