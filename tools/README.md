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
- Automatic since 2026-11-04: Grok Bot routine (16:20 JST; edition starts 15:22 and must be pushed by 16:15; all done by 17:30) mails the JSON to pastachannel0725@gmail.com, subject 「マイ夕刊 Xの声 <date>」. Claude imports it at 17:05 (retry 17:20) via the Gmail connector (search `subject:(マイ夕刊 Xの声) newer_than:1d`), saves the mail body to a file, runs save_x.py, commits data/x/<date>.json, pushes.
