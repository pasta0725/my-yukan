# マイ夕刊の作り方（Claude用メモ）

> gh コマンドが使えない環境（ログインできない）では、GitHub の道具（ワークフローの実行・実行の一覧・成果物の取得）で同じことをしてよい（2026-11-13 Issue #17）。

0. 号は1日2回（2026-11-10〜）：朝刊 `YYYY-MM-DD-am`（4:12開始・6:05までに push・7:00完成）と夕刊 `YYYY-MM-DD-pm`（14:22開始・16:15までに push・17:30完成）。それより前の号は `YYYY-MM-DD`。どちらも同じ予定作業の指示文で、日本時間12時より前に動いたら朝刊、後なら夕刊を作る。
   | 時刻（朝刊／夕刊） | 作業 |
   |---|---|
   | 4:12 ／ 14:22 | 号づくり（Claude） |
   | 6:10 ／ 16:20 | Xの声を集める（Grok Bot、tools/grok.md） |
   | 6:12 ／ 16:31 | 公式画像の補充（Claude） |
   | 6:41 ／ 17:04 | Xの声の取り込み1回目（Grok が push できなかったときのメールから） |
   | 6:56 ／ 17:19 | Xの声の取り込み2回目と完成報告 |
1. `git pull` して最新にする。作業フォルダ WORKDIR を作り、data/index.json の号の「source_url（タブ）見出し」を1行ずつ `WORKDIR/used.txt` に書き出す。spec.md の {EDITION} は「朝刊」か「夕刊」に置き換える。
1-2. ニュース一覧と記事本文を GitHub 側で先に取る（2026-11-12〜、Issue #7。担当が自分でページを開くと許可確認が出るため）：`gh api -X POST repos/pasta0725/my-yukan/actions/workflows/fetch-news.yml/dispatches -f ref=main -f 'inputs[edition]=ED'` で動かし（1〜2分）、終わったら `git fetch origin news && git archive origin/news news/ED | tar -x -C WORKDIR` で取り出す。担当ごとに WORKDIR/news/ED/<担当名>/index.md（候補の一覧）と <id>.txt（本文・公開日時・画像URL）ができる。取得の結果は report.md。どのサイトから取るかは tools/news_sites.json（URLを直すときはここ）。spec.md の {NEWS} を WORKDIR/news/ED に置き換える。4:30／14:40 になっても取れなければ、{NEWS} のフォルダなしで進める（担当は自分の WebSearch の結果だけ開く）。
2. サブエージェントへの指示にサイトのURLを書かない（許可確認が出るため）。担当は自分のニュースフォルダのファイルを読み、WebFetch は自分の WebSearch の結果のURLだけに使う（spec.md の How to reach pages）。`tools/spec.md` の {TODAY}・{WORKDIR}・{NEWS} を置き換えた指示で、Sonnet のサブエージェント16本を並列に動かす（本数は下の表のとおり。カテゴリの範囲は spec.md の Categories）。2026-11-07 にユーザーの希望で8カテゴリに変更。
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
   - ユーザーが個人的に関心のある話題（Apple・Google・Xiaomi・Anker・Dreame・任天堂・SONY・GeForce NOW・ChatGPT・Claude・Grok・Muse）は積極的に記事にする（2026-11-09）。各担当が自分のカテゴリに合うものを検索で探し、build_edition.py はこれらを優先して残し、カテゴリごとに上限を2本まで超えてよい。詳しくは spec.md の Personal-interest topics。
3. `python3 -I tools/build_edition.py WORKDIR YYYY-MM-DD-am（または -pm） [重複して外すid ...]` で data/ を作る（重複・ニュース写真2枚制限・14日分の一覧を自動処理）。公式画像の補充（add_official_images.py）のあとに `python3 -I tools/place_images.py data/YYYY-MM-DD.json` で画像を本文の合間に配る（2026-11-08 ユーザーの希望）。
4. 見出し一覧を見て、同じ出来事が別ジャンルにも入っていれば id を指定して作り直す。
5. コミットして main に push する。

## 自動で賢くなる仕組み（2026-11-10〜）
- 毎日 metrics.yml が数字を集め（ブランチ metrics）、毎週月曜の「週1回の見直し」が tools/learning/README.md の手順で週報を書き、tools/learning/params.json（カテゴリ本数・記事選びの点数・公開時刻）を少しずつ自動で動かし、大きな変更はユーザーに提案する。

## 不具合・改善点の報告（2026-11-10〜、ユーザーの依頼）
- 毎日の自動作業のAIは、作業中に不具合（失敗・食い違い・回避した問題）や改善点を見つけたら、GitHub の Issue にラベル「AIからの報告」を付けて書く：
  `gh api -X POST repos/pasta0725/my-yukan/issues -f title="[作業名] 一言の要約" -f body="何が起きたか／どう回避したか／影響／改善の提案" -f 'labels[]=AIからの報告'`
- 先に `gh api -X GET repos/pasta0725/my-yukan/issues -f labels=AIからの報告 -f state=open`（ラベル名を URL に直接書くと失敗する。2026-11-10 Issue #2） で同じ話題を探し、あればコメントを足す（`.../issues/<番号>/comments -f body=...`）。
- 仕組み（指示文・ワークフロー・ルール文書）は自分で変えず、報告だけにする。トークンや鍵の中身は書かない。日本語で書く。
- 保守役の Claude が報告を読んで直し、直したら Issue を閉じる。

## Xの声（Grok Bot）
- build_edition.py writes data/x-todo.json (today's story list) every run. Commit it with the edition.
- Grok Bot reads it and returns JSON (prompt: tools/grok.md). Save with `python3 -I tools/save_x.py <answer.txt> <date>` → data/x/<date>.json, commit, push. The site merges it.
- Writing rules: tools/style.md (第2版, from 2026-11-04). Workers must read it.
- Since 2026-11-04 (no PC needed): 14:22 cloud task (Sonnet workers with effort high) 「マイ夕刊 毎日の号づくり」 pushes the edition + data/x-todo.json by 16:15. 16:20 Grok Bot routine (its own cloud PC, GitHub token) runs save_x.py and pushes data/x/<date>.json directly (fallback: mails the JSON, subject 「マイ夕刊 Xの声 <date>」, to pastachannel0725@gmail.com). 17:19 cloud task 「Xの声の取り込み（2回目）と完成報告」 imports from Gmail only if data/x/<date>.json is missing, then sends the completion push notification. Prompts: tools/grok.md.

## 公開サイト「星餓りなのテックニュース」（2026-11-07〜）
- `python3 tools/build_site.py` が data/ の全号から site_dist/ に静的サイトを作る（標準ライブラリのみ）。Cloudflare Pages がプッシュのたびに実行して公開する（ビルドコマンド `python3 tools/build_site.py`、出力 `site_dist`）。
- 公開側のルール：ニュースサイトの写真は出さない（公式・PR TIMESの画像だけ）、Xの声は出さない、記事ごとに1ページ、sitemap.xml・feed.xml・構造化データ付き。
- 見た目は site/style.css、画像は site/assets/（Codexで生成）、サイト名やURLは site/config.json（base_url は Cloudflare のプロジェクト名が決まったら合わせる）。

## 事実の点検（手順5-2、2026-11-09〜：許可確認を出さないやり方）
ファイルに書かれたURL（refs）を号づくりのセッションで WebFetch すると、出どころが確かめられず許可確認が出ることがある。そこで2段構えにする。
1. 書いた担当が保存前に自分で点検する（spec.md の Self-check の節）。自分で開いたページなので確認は出ない。
2. 号を作ったら（build_edition.py の後）、GitHub 側で参考記事のページを取ってくる：
   `gh api -X POST repos/pasta0725/my-yukan/actions/workflows/factcheck-pages.yml/dispatches -f ref=main -f 'inputs[edition]=<号のID>'`
   （tools/fetch_refs.py：各記事の source_url と refs を最大6本取得し、本文の文字だけを factcheck/<号のID>/<記事id>.txt にして、ブランチ factcheck に push。1〜2分）
   終わったら `git fetch origin factcheck && git archive origin/factcheck factcheck/<号のID> | tar -x -C <作業用フォルダ>` で取り出す。
3. 点検役の Sonnet 4本（effort high）は、その .txt と記事を照らし合わせるだけ。WebFetch・WebSearch・curl は使わない。取得に失敗したページ（403 など）は、その記事の中だけで食い違いを点検し、確かめられない数字は出どころを付けるか削る。

## Codexの調査（手順5-0、2026-11-10〜：検索の上限を避けるため）
Claudeの検索回数には1回の作業あたりの上限（約200回）があり、同じ出来事を伝える別メディア探しで使い切っていた（11/10朝刊：54本中25本が参考記事1本）。そこで別メディアと公式ページ探しは GitHub 上の Codex（ChatGPT のプラン、CODEX_AUTH）に任せる。
1. build_edition.py の後、data/ED.json などをコミットし、git fetch → rebase して main に push。
2. `gh api -X POST repos/pasta0725/my-yukan/actions/workflows/codex-research.yml/dispatches -f ref=main -f 'inputs[edition]=ED' -f 'inputs[max_refs]=3'`（参考記事3本以下の記事が対象。6組に分けて同時に調べ、1組5分ほど）。
3. 終わったら `git fetch origin research && git archive origin/research research/ED | tar -x -C WORKDIR`。research/ED/<記事id>.txt に別メディアと公式ページの本文（`===== URL` と `(status 200)` の行で区切り）、<記事id>.json に見つけたURL・媒体名・公式画像のURL。
4. `python3 -I tools/research_pages.py export data/ED.json WORKDIR/arts` で記事を1本ずつのファイルにし、Sonnet（effort high）8本に分けて書き足させる。各担当は WORKDIR/arts/<id>.json と research/ED/<id>.txt だけを読み、ウェブは開かない。同じ出来事を伝えているページ（status 200 で本文があるもの）から、新しい事実（数字・日付・価格・仕様・対象・背景・各社の反応・今後）を style.md どおり自分の言葉で足す。媒体どうしで食い違えば「〇〇は△△と伝えています」。使ったページだけを refs に {name,url} で足す（最大6本、source_url を先頭のまま）。別の出来事のページ・まとめサイト・転載は使わない。id・category・image は変えない。同じファイルに上書き保存。スクリプトや一時ファイルは自分の組のフォルダ WORKDIR/fill_<組番号>/ にだけ置き、共有のスクラッチパッドや他の組のファイルは使わない・実行しない（2026-11-12 Issue #14：別の組のスクリプトを実行して refs が重複した）。
5. `python3 -I tools/research_pages.py import data/ED.json WORKDIR/arts` で戻す（x-todo.json の見出し・要約も合わせる）。そのあと手順5-1・5-2へ（事実の点検は新しい refs も取得する）。
- Codexが締め切り（5:15／15:25）までに終わらなければ待たずに次へ進む。
- Codexが見つけた公式ページは、あとの「公式画像の補充」がそのまま使う（`python3 -I tools/research_pages.py imgjobs WORKDIR/research/ED imgjobs/ED.json` → official-images.yml の extra。補充の作業は自分では検索しない。2026-11-10）。

## 公式画像の補充（2026-11-09〜、毎日6:12と16:31の別作業）
- 2026-11-10〜：号づくりの各担当は公式ページを検索して探さない（自動の作業では公式サイトが開けず、検索の上限を使い切ったため）。公式画像はこの補充作業が担当する。各担当は自分専用のフォルダ WORKDIR/<担当名>/ を使い、push の前に必ず git fetch → git rebase origin/main で最新に合わせる。
号づくりの中では開けない公式ページが多く、画像ゼロの記事が多かった（11/8号は49本中41本）。そこで公開後に、GitHub の実行環境で画像を集めて足す。
1. `gh api -X POST repos/pasta0725/my-yukan/actions/workflows/official-images.yml/dispatches -f ref=main -f 'inputs[dates]=<号のID>'`
   （tools/find_official_images.py：公式画像0〜1枚の記事について、参考記事の中の公式ページへのリンクをたどり、画像を集めて候補一覧の画像 sheet_NN.jpg と candidates.json を作る。公開サイトから表示できるかも確かめる）
2. `gh run download <実行ID> -n official-images` で取得。候補一覧を見て、記事に合う画像を選ぶ（顔が主役・ロゴだけ・無関係・ニュースサイトの画像は除く）。選んだ結果は {"記事id":[{"n":番号,"caption":"何が写っているか"}]}。
3. 候補がなかった記事は、WebSearch だけで公式ページを探し（WebFetch は使わない）、{"記事id":["公式ページURL"]} を imgjobs/<号のID>.json に置いて push、`inputs[extra]=imgjobs/<号のID>.json`・`inputs[only_extra]=yes` でもう一度実行して選ぶ。
4. `python3 -I tools/pick_official_images.py candidates.json picks*.json` で号に取り込み（add_official_images.py と place_images.py も自動で動く）、コミットして push。

## 図解（2026-11-09〜、公式画像の補充のあと）
公式画像がない記事には、記事の事実から作った図解を付ける（ユーザーの選択。画像生成AIの絵は使わない）。
- `python3 tools/make_diagrams.py data/<号のID>.json [--specs specs.json]` → data/diagrams/<号のID>/<記事id>.png（1200×675）と記事の "diagram"。
- 何も指定しなければ、記事の数字の欄（stat）から「数字カード」、無ければ「3行でわかる」から「要点」を自動で作る。
- 合う記事は specs.json で型を選べる：number（数字1〜3個）／timeline（時系列2〜5個）／compare（今まで・これからの比較）／who（対象・いつから・何が変わる・注意）／points（要点）。書き方は make_diagrams.py の先頭。記事にない数字があると、その指定は使わず自動の図にする。
- アプリと公開サイトは、公式画像がない記事でこの図を一覧の絵と記事の先頭に出す。

## 検索・発見まわり（2026-11-11）
- 共有画像（検索・Discover・Xのカード）は幅1200px以上の公式画像だけ。足りなければ図解、なければサイト共通画像（build_site.py share_img）。画像の大きさは pick_official_images.py が記録し、古い号は tools/image_sizes.py で埋めた。
- サイトマップ（更新日時つき）とニュース用サイトマップ（直近2日）。日付ページは同じ記事の一覧なので検索に出さない（noindex）。
- 号が push されると indexnow.yml が新しい記事のURLを Bing などに知らせる（鍵は site/config.json の indexnow_key、公開してよい種類のもの）。
- 記事には「年月日・時刻」と「文：星餓りなのテックニュース編集部」を表示。運営者名と連絡先は未掲載（ユーザーが決める）。
- 調査の結論（2026-11-11）：他社記事の言い換えを大量に出す形は Google のスパムポリシーの例に近い。検索に出す記事を絞るかは保留中。個人では大手ニュースアプリの媒体登録はほぼ不可。

## ドライブへの保管（2026-11-12〜、Issue #11）
- 完成動画と素材は GitHub の drive-store.yml が Google ドライブ（pastachannel0725）の「星餓りな 保管（自動）」へ移す。道具は tools/drive_store.py。鍵は GitHub の DRIVE_CLIENT_ID・DRIVE_CLIENT_SECRET・DRIVE_REFRESH_TOKEN（中身は表示しない）。
- 最初の1回だけ（ユーザーの作業）：Google Cloud のプロジェクト rina-youtube で Google Drive API を有効にし、OAuth クライアントを「テレビと入力が限られたデバイス」の種類で作り、その ID とシークレットを GitHub の DRIVE_CLIENT_ID・DRIVE_CLIENT_SECRET に登録する。GitHub の細かい権限のトークン（このリポジトリだけ・Secrets の読み書き）を GH_SECRETS_TOKEN に登録する。そのあと drive-login.yml を動かし、実行の要約に出るコードを https://www.google.com/device で入れて pastachannel0725 で許可する。
- ドライブへ上げられなくなったら（鍵の期限切れなど）、drive-login.yml をもう一度動かす。

## GitHub の容量を増やし続けないために（2026-11-12）
- 履歴は消えないので、増え続けるものは main に入れない：ショートの音声・画像・動画はブランチ work（tools/work_branch.py）、完成動画は upload-tmp。どちらも公開後に drive-store.yml がドライブへ移してブランチごと消す。
- news・factcheck・research のブランチは、毎週月曜 3:07 に cleanup-branches.yml が消す（次の号のときに自動で作り直される）。
- 公開サイト（Cloudflare Pages の無料プラン）の上限：1サイト2万ファイル（11月12日で約1,000、1日約100増える）と、月500回のビルド。ファイル数は週1回の見直しで見張る。
- ビルドを減らす設定（2026-11-12、Cloudflare の rina-tech-news → Settings → Build）：Build watch paths は data/*・site/*・tools/build_site.py だけ（ほかの変更では作り直さない）、Preview branch は None（main 以外のブランチでは作らない）。それまでは全部の push で作り直していて、11月12日までに約420回使っていた。
