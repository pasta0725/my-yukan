# マイ夕刊の作り方（Claude用メモ）

1. `git pull` して最新にする。作業フォルダ WORKDIR を作り、直近の号の source_url を `WORKDIR/used.txt` に書き出す。
2. サブエージェントへの指示にサイトのURLを書かない（許可確認が出るため）。サイト名だけ伝え、URLは検索結果から辿らせる。`tools/spec.md` の {TODAY} と {WORKDIR} を置き換えた指示で、Sonnet のサブエージェント16本を並列に動かす（本数は下の表のとおり。カテゴリの範囲は spec.md の Categories）。2026-11-07 にユーザーの希望で8カテゴリに変更。
   | 担当 | カテゴリ | 担当サイト | 本数 |
   |---|---|---|---|
   | ai_A | AI | ITmedia AI+・ITmedia NEWS | 4 |
   | ai_B | AI | Impress Watch・Publickey・日経クロステック | 4 |
   | ai_C | AI | 各社公式発表（日本語） | 4 |
   | ai_D | AI | 海外（英語）：TechCrunch・The Verge・Ars Technica・VentureBeat・Reuters と、OpenAI・Anthropic・Google・Meta・Microsoft・NVIDIA の英語の公式ブログ（spec.md の Overseas の節） | 4 |
   | mobile_A | スマホ・パソコン | ケータイ Watch・ITmedia Mobile・各メーカー公式（スマホ・タブレット・スマホのOS） | 4 |
   | mobile_B | スマホ・パソコン | PC Watch・ITmedia PC USER・窓の杜（パソコン・Windows/Mac・周辺機器） | 4 |
   | gadget_A | 家電・ガジェット | 家電 Watch・家電メーカー公式 | 4 |
   | gadget_B | 家電・ガジェット | AV Watch・GIZMODO JAPAN・マイナビニュース（オーディオ・カメラ・ウェアラブル・ガジェット） | 4 |
   | service_A | ネットサービス・アプリ | ITmedia NEWS・Impress Watch・CNET Japan | 4 |
   | service_B | ネットサービス・アプリ | 各サービスの公式お知らせ（YouTube・X・LINEヤフー・Google・Instagram・TikTok・Netflix など） | 4 |
   | game_A | ゲーム | 4Gamer.net・GAME Watch | 4 |
   | game_B | ゲーム | ファミ通・電撃オンライン・任天堂/SIE/Xbox 公式 | 4 |
   | ec_A | EC・決済 | ネットショップ担当者フォーラム・ECのミカタ・公的機関（国税庁・消費者庁など）、7日以内 | 4 |
   | ec_B | EC・決済 | メルカリ・minne・BASE・Amazon・楽天・PayPay など各サービスの公式お知らせ（フリマ・通販・キャッシュレス・ポイント）、7日以内 | 4 |
   | future_A | 宇宙・未来技術 | sorae・MIT Technology Review・日経クロステック・TechCrunch（宇宙・自動運転・ロボット・量子）、7日以内 | 4 |
   | other_A | その他 | 通信・セキュリティ・法律/規制の注目ニュース（基準は spec.md、2026-11-08に引き下げ）：ケータイ Watch・ITmedia NEWS・Security NEXT・総務省/公正取引委員会/デジタル庁の発表、7日以内 | 4 |
   | other_B | その他 | 企業・業界と半導体の注目ニュース：日経クロステック・EE Times Japan・ITmedia NEWS・Reuters、7日以内 | 4 |
   - 出力は WORKDIR/<担当名>.json（例 mobile_A.json）。build_edition.py が1日の上限（AI14・その他8・宇宙4・ほか各7）で切る。
3. `python3 -I tools/build_edition.py WORKDIR YYYY-MM-DD [重複して外すid ...]` で data/ を作る（重複・ニュース写真2枚制限・14日分の一覧を自動処理）。公式画像の補充（add_official_images.py）のあとに `python3 -I tools/place_images.py data/YYYY-MM-DD.json` で画像を本文の合間に配る（2026-11-08 ユーザーの希望）。
4. 見出し一覧を見て、同じ出来事が別ジャンルにも入っていれば id を指定して作り直す。
5. コミットして main に push する。

## Xの声（Grok Bot）
- build_edition.py writes data/x-todo.json (today's story list) every run. Commit it with the edition.
- Grok Bot reads it and returns JSON (prompt: tools/grok.md). Save with `python3 -I tools/save_x.py <answer.txt> <date>` → data/x/<date>.json, commit, push. The site merges it.
- Writing rules: tools/style.md (第2版, from 2026-11-04). Workers must read it.
- Since 2026-11-04 (no PC needed): 14:22 cloud task (Sonnet workers with effort high) 「マイ夕刊 毎日の号づくり」 pushes the edition + data/x-todo.json by 16:15. 16:20 Grok Bot routine (its own cloud PC, GitHub token) runs save_x.py and pushes data/x/<date>.json directly (fallback: mails the JSON, subject 「マイ夕刊 Xの声 <date>」, to pastachannel0725@gmail.com). 17:19 cloud task 「Xの声の取り込み（2回目）と完成報告」 imports from Gmail only if data/x/<date>.json is missing, then sends the completion push notification. Prompts: tools/grok.md.

## 公開サイト「星餓りなのテックニュース」（2026-11-07〜）
- `python3 tools/build_site.py` が data/ の全号から site_dist/ に静的サイトを作る（標準ライブラリのみ）。Cloudflare Pages がプッシュのたびに実行して公開する（ビルドコマンド `python3 tools/build_site.py`、出力 `site_dist`）。
- 公開側のルール：ニュースサイトの写真は出さない（公式・PR TIMESの画像だけ）、Xの声は出さない、記事ごとに1ページ、sitemap.xml・feed.xml・構造化データ付き。
- 見た目は site/style.css、画像は site/assets/（Codexで生成）、サイト名やURLは site/config.json（base_url は Cloudflare のプロジェクト名が決まったら合わせる）。

## 公式画像の補充（2026-11-09〜、毎日16:31の別作業）
号づくりの中では開けない公式ページが多く、画像ゼロの記事が多かった（11/8号は49本中41本）。そこで公開後に、GitHub の実行環境で画像を集めて足す。
1. `gh api -X POST repos/pasta0725/my-yukan/actions/workflows/official-images.yml/dispatches -f ref=main -f 'inputs[dates]=<日付>'`
   （tools/find_official_images.py：公式画像0〜1枚の記事について、参考記事の中の公式ページへのリンクをたどり、画像を集めて候補一覧の画像 sheet_NN.jpg と candidates.json を作る。公開サイトから表示できるかも確かめる）
2. `gh run download <実行ID> -n official-images` で取得。候補一覧を見て、記事に合う画像を選ぶ（顔が主役・ロゴだけ・無関係・ニュースサイトの画像は除く）。選んだ結果は {"記事id":[{"n":番号,"caption":"何が写っているか"}]}。
3. 候補がなかった記事は、WebSearch だけで公式ページを探し（WebFetch は使わない）、{"記事id":["公式ページURL"]} を imgjobs/<日付>.json に置いて push、`inputs[extra]=imgjobs/<日付>.json`・`inputs[only_extra]=yes` でもう一度実行して選ぶ。
4. `python3 -I tools/pick_official_images.py candidates.json picks*.json` で号に取り込み（add_official_images.py と place_images.py も自動で動く）、コミットして push。
