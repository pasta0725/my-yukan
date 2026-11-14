# 夕刊から1本、自動でショートを作る（2026-11-10〜、ユーザーの依頼）

ユーザーの確認なしで毎日1本。夕刊（data/<今日>-pm.json）の記事から選んで作り、21:00 に予約公開する。
予約公開までの間にユーザーが止められるよう、アップロードしたら必ず通知する。手で「この記事を動画にして」と頼まれたときも、選ぶ手順以外は同じ。
作り方の決まりは rina-shorts / rina-youtube-publish スキルと tools/shorts_rules.md・metadata_rules.md・thumbnail_rules.md がもと。この文書は「自動でやるときの順番と、人の代わりの確認」。

## 時間割（日本時間）
| 時刻 | やること |
|---|---|
| 17:36 | 開始（夕刊の完成 17:30 の後）。リポジトリは毎回 GitHub から新しく clone する |
| 〜18:00 | 記事選び・台本・事実確認 |
| 〜19:30 | 読み上げ・画面・締めの話す動画・書き出し・サムネ・項目 |
| 〜20:30 | 自動の確認（下の「人の代わりの確認」）をすべて通す |
| 20:30まで | 予約公開でアップロードし、ユーザーに通知（公開は params.json の publish_time、初期値 21:00。07:00・12:15 なら翌日のその時刻。今日の時刻がもう近い・過ぎていれば「今から60分後」） |
| 20:30 を過ぎても確認が通らない | アップロードしない。理由を通知して終わる |

## 1. 記事選び（YouTubeで見られそうなもの）
- **最初に channel/next_short.json を見る**：date が今日なら、点数で選ばずにその article_id の記事を作る（ユーザーの指定。通知の「選んだ理由」は「あなたの指定」）。使ったら date を null に戻してコミットする（1回限り）。ユーザーが「この記事を動画にして」と言ったときも、Claude はここに書けばよい。
- 点数と公開時刻の値は tools/learning/params.json の shorts（selection_points・category_bonus・publish_time）を使う。週1回の見直しが少しずつ調整する（下の数字は初期値）。選んだ記事の点数の内訳は channel/shorts_log.csv のメモに書く（見直しで使う）。
- 候補はその日の夕刊と朝刊の全記事（朝刊の大きな話を逃さないため。2026-11-14）。点数の高い順に1本：
  - 誰でも知っている会社・製品（Apple・Google・OpenAI・Anthropic・任天堂・SONY・Microsoft・Amazon・メタ など）＋3点
  - 新製品・新機能・料金の変更・発売日など「自分に関係がある」話＋2点、多くの人に影響する事故や流出＋2点
  - 画面に出せる公式の画像や動画がある＋2点（ない話は絵で持たない）
  - 数字で言い切れる（価格・倍率・人数・日付）＋1点
  - 参考記事が2本以上ある（research/<号>/ か refs）＋1点。1本だけなら選ばない
  - 「えっ」となる驚きがある（初・最大・歴代1位・辞任や撤退・大幅な値下げや値上げ・常識が変わる）＋2点（surprise）
  - 地味・先の話・一部の人だけの話は−3点（niche_or_later）：一部の機種だけの小さな更新、1〜2年以上先の予定や実験、特定の地域だけ、海外だけで日本では使えない、など（2026-11-13 ユーザー指摘：Xperiaの更新は「どうでもいい内容」で142回、JRの改札（2027年の体験）は15回。伸びたのは NVIDIA CEO辞任・Claude・OpenAI・ゼルダ歴代1位などで約1000〜1250回）
  - 最後に「知らない人がスクロール中に止まるか？」を自分に問う。止まらないと思う記事は点数が高くても選ばない。迷ったら、伸びている他のショート（git fetch origin metrics の competitors/ の最新）で同じ会社・話題が伸びているかを見る
  - 直近7本（channel/shorts_log.csv）と同じ会社・同じ話題は−3点。政治・規制の賛否が分かれる話、事件・事故の被害者が中心の話は選ばない
- 選んだ理由（点数の内訳）を作業メモに残し、通知に1行で書く。

## 2. 作る
- 順番（2026-11-10 Issue #4）：台本 → **事実確認（下の「人の代わりの確認」3、codex-short-factcheck.yml）を読み上げの前に通す** → 読み上げ → 画面。夕刊の言い回しや「りなの見方」をそのまま台本や締めに使わない（言い過ぎ・誤解が残りやすい）。つかみは25字前後まで（Leda の速さで約4秒）。
- rina-shorts スキルの手順どおり（構成・吹き出し・声 Leda・息継ぎなし・{SEC}・登場の使い回し）。
- 事実は夕刊の記事・research/<号>/<id>.txt・factcheck/<号>/<id>.txt の本文で確かめる（ウェブは開かない。足りなければ fetch-to-branch.yml で取ってくる）。数字は2つ以上の記事で裏を取る。
- 読み上げは台本全部を1回でまとめて作り（15文を超えるときだけ2回）、split_tts.py で分け、check_split.py で1文ずつ文字起こしして切れ目を確かめる（short-voice.yml が自動で行う。2-2）。1文だけの作り直しは前後の文と一緒に頼む。読み直しを入れても1本3回まで（Gemini の無料枠は1モデル1日10回。2026-11-12 の試験で12文を1回で作って正しく分けられた）。モデルは gemini-3.8-flash-tts だけを使い、別のモデルに切り替えない（声の感じが変わるため。2026-11-12 ユーザー決定）。読み間違えやすい数字はひらがな。
- 締めの話す動画は longcat-colab.yml（Colab を最大20分借り直し、だめなら自動で Modal）。
- **素材の置き場（2026-11-12〜、ユーザー決定）**：音声・画像・動画は main に入れず、使い捨てのブランチ work に置く（main の履歴は消えずに1日約18MBずつ増えていたため）。読み上げ（tts.yml）と公式画像（fetch-media.yml）の結果は自動で work に入る。手元に取るのは `python3 tools/work_branch.py get narration/<名前> media/<名前>`、自分で作った音声・画像（longcat の入力、サムネなど）を置くのは `python3 tools/work_branch.py put <ファイルやフォルダ>`。longcat-colab.yml と youtube-upload.yml は work からも読む。main の .gitignore がこれらを main に入れないようにしている。台本・spec.json・short.html・lines.json・urls.txt など文字のファイルは今までどおり main。
- サムネは codex-images.yml、項目は metadata_rules.md、字幕SRTと英訳も作る。

## 2-2. 分担（利用枠の節約、2026-11-14 ユーザーの依頼。品質は変えない）
- **親（この作業の本体、Opus）がやること**：記事選び、台本、場面の設計（short.html の絵・図解・レイアウト・色）、サムネの案と主コピー、タイトル・概要欄・固定コメントの質問、確認で出た問題の判断と直し方の決定。
- 決まった手順は **GitHub の自動作業（AI なし。確認の一部だけ Codex）** が行う。サブエージェントは使わない。親は「動かす → `gh run watch <ID>` で1回待つ → 結果の1行目（RESULT: OK／LOOK／FAILED）と「- LOOK 場所｜何が｜…」の行だけ読む」。ログやファイルは、直すのに要る部分だけ見る。結果はその実行の要約（`gh run view <ID>`）と、ブランチ checks の checks/<名前>/ に出る（`git fetch origin checks && git show origin/checks:checks/<名前>/<ファイル>`）。
- 動かし方：`gh workflow run <ファイル> -R pasta0725/my-yukan --ref main -f name=<名前> …`（--ref main が要る）。実行IDは `gh run list -R pasta0725/my-yukan -w <ファイル> -L 1`。
  1. **事実**（台本ができたら、読み上げの前）：spec.json と channel/meta/<名前>.json（まだならタイトル・概要欄の案）を main に push → codex-short-factcheck.yml（refs=<号>/<記事ID> を空白区切りで（shorts/<名前>/refs.txt に書けば省ける）、extra=fetched:<パス>（fetch-to-branch.yml で取った元記事・公式ページ。資料に無い数字は LOOK になるので、使った元記事は必ず渡す））→ facts.md。
  2. **声**：narration/<名前>/lines.json を main に push（tts.yml が自動で読み上げる）→ short-voice.yml（lines=narration/<…>/lines.json）。音声を待ち、1文ずつに分けて文字起こしまで行う → voice_<フォルダ>.md（今日この動画で使った読み上げの回数も出る）。LOOK の文だけ、前後の文と一緒に narration/<名前>_fix<N>/lines.json で作り直す（1日3回まで。上限を超えるときは short-voice が tts.yml を動かさない）。どの音声を使うかは short-build が決める（台本の say と同じ文のうち新しいもの、check で LOOK でないものを優先。行に "wav": "<パス>" を書けば固定）。
  3. **書き出しと確認**：spec.json・short.html・（締めのりながあれば）longcat/jobs.json・channel/meta を main に、画面の画像と channel/thumbs/<名前>.jpg を work に置いてから short-build.yml（refs、extra は 1 と同じ）。中で 音声のつなぎ → short_plan.py → 長さと無音 → 締めの話す動画（longcat-colab.yml。音声が変わったときだけ。Colab を最大20分、だめなら Modal）→ 大きいりなのコマ → check_fit.js → render_par.js → 声（check_voice.py）・画面（Codex）・事実（Codex）を行い、全部の LOOK を build.md にまとめる。plan.js と字幕（channel/captions/<名前>_ja.srt）は自動で main に入る。完成動画は work の final/<名前>.mp4、1秒ごとのコマ一覧は final/<名前>_sheets/。直したら short-build をもう一度。
  4. **投稿**：build.md が OK（LOOK は親が問題なしと判断したものだけ）なら short-upload.yml（publish_at、comment、log=shorts_log.csv の1行（動画IDの所は {ID}））。upload-tmp への配置・youtube-upload.yml・記録の追加までを1回で行い、upload.md の「ID:」の行が動画ID。公開15分後のサムネ確認（short-thumb-check.yml、違えば入れ直す → thumb.md）も自動で始まる。試すときは dry_run=yes（何も上げない）。
- **予備（自動が動かない・FAILED のとき）**：従来どおり個別に動かす（tts.yml → split_tts.py・check_split.py → short_plan.py → longcat-colab.yml → check_fit.js → render_par.js → voice-check.yml・codex-frame-check.yml → upload-tmp・youtube-upload.yml）。そのときは決まった手順を Sonnet の実行役（effort high）に任せてよい（親への返事は OK か LOOK の1〜3行だけ、台本・場面は変えない）。画面・事実が FAILED（Codex が答えなかった）のときだけ、作った本人ではない Sonnet のサブエージェント（effort high）で同じ項目を確かめる。
- 素材のブランチを試しに戻すとき（公開済みの動画）：short-restore.yml（name）でドライブの zip を work に戻せる。

## 3. 人の代わりの確認（全部通ったときだけ投稿）
1. **声**：short-build.yml の中で自動（単独なら voice-check.yml。tools/check_voice.py）。似ている度合いは「調整後」（表記の違いを除いた similarity_adjusted）で0.95以上。そのままの数字は、製品名をカタカナで読ませると0.95を下回りやすい（2026-11-13 Issue #19）。出てきたずれ（1字でも）は全部、台本の say と見比べて理由を書く（2026-11-10 の試験：読み違い「ようとうかん」は1字のずれ、外した文の切れ端「料金は2倍です」は台本にない声として出た）（数字・英語の書き方の違いは問題なし。読み違い・切れ端・抜けは直して作り直す）。
2. **画面**：short-build.yml の中で自動（単独なら codex-frame-check.yml。2026-11-14〜、Claude の利用枠の節約）。単独で動かすときは、完成動画を upload-tmp か work に置き、name・video（work:<パス> か upload-tmp:<ファイル>）・script（空なら shorts/<名前>/spec.json）・thumb（空なら work の channel/thumbs/<名前>.jpg）で動かす。ChatGPT（Codex、最も強いモデル（初期値 gpt-6-astra、断られたらアカウントの既定）・effort high。使ったモデルは結果に出る）が1秒ごとのコマと字幕の切り替えごとの原寸の切り出し・サムネを見て、吹き出しが空、改行、はみ出し、YouTube の画面との重なり、誤字、サムネの誤字と幅168pxでの読みやすさを点検する。字幕は Codex に書き写させ、改行・空・台本との字の違いは決まりどおり機械でも判定する。結果はブランチ checks の checks/<名前>/frames.md（1行目が RESULT: OK / LOOK / FAILED、LOOK は「- LOOK 時刻｜何が｜どこ｜内容」。ジョブが緑なのは OK のときだけ）。指摘は直して、もう一度動かす。FAILED（Codex が答えなかった）のときだけ、従来どおり1秒ごとのコマ一覧を作った本人ではない Sonnet のサブエージェント（effort high）に見せて、同じ項目で点検させる。
3. **事実**：Codex（gpt-6.1-sol・effort high、2026-11-14〜。Claude Sonnet のサブエージェントの代わり）が、台本（say と show）・字幕・タイトル・概要欄・タグ・英語の項目の数字・日付・固有名詞・「誰が・いつから・誰に」・報道か発表かを、参考記事の本文（夕刊の記事、research/<号>/<id>.txt、factcheck/<号>/<id>.txt、extra の元記事）と照らす（codex-short-factcheck.yml、tools/codex/short_factcheck.md。short-build.yml の中でも動く）。資料と違う・資料に無い・場所によって食い違う・言い過ぎは LOOK。結果は checks/<名前>/facts.md（「- LOOK 場所｜何が｜正しい値｜出どころ」）。「資料に記載なし」は、元記事で確かめられれば問題なし（そのときは extra に渡して確かめ直すのがよい）。FAILED のときだけ従来の Sonnet。
4. **文字のはみ出し**：short-build.yml が書き出しの前に自動で行う（手でなら、ショートのフォルダで `node ../_template/check_fit.js`）。カードやアイコンの枠から出た文字を OVERFLOW で全部出すので、0件になるまで直す（2026-11-13、「11/17」がカレンダーの絵からはみ出していたのを、コマの点検でも見逃した）。図形の中に置く文字は text(…, maxw) で幅の上限を渡し、自動で縮める。
5. **長さと無音**：登場のあと話し終わりまで60秒以内、0.6秒以上の無音が台本の切れ目以外にない（short-build.yml が自動で確かめる。tools/short_auto.py silence）。
6. サムネの文字の誤字と、幅168pxに縮めても読めるか（2 の codex-frame-check.yml で一緒に見る）。

## 4. 投稿と通知
- short-upload.yml（2-2 の 4）を name・publish_at（例 2026-11-10T21:00:00+09:00）・comment・log で動かす（中で upload-tmp に置き、youtube-upload.yml を動かす）。予約公開の動画は非公開で上がり、21:00 に YouTube が公開する。公開の数分後に、サムネの入れ直しと固定コメントが自動で行われる。公開15分後に short-thumb-check.yml がショート一覧のサムネ（i.ytimg.com/vi/<ID>/sardefault.jpg）を入れた画像と比べ、違えば入れ直す（checks/<名前>/thumb.md が LOOK のときだけ thumb:<ID> で手で入れ直す）。コメントの固定は、毎日21:23の予定作業「星餓りな 固定コメントの固定」が内蔵ブラウザで行う（手順は tools/pin_comment.md）。
- 通知（PushNotification と SendUserMessage の両方、日本語）：
  「今日の自動ショート：<タイトル>（<選んだ理由1行>）。21:00に公開されます。https://youtube.com/shorts/<ID>　止めたいときは Claude に『動画止めて <ID>』と言うか、YouTube Studio アプリで非公開にしてください。」
- 止める：youtube-upload.yml の video=stop:<ID>。すぐ出す：video=go:<ID>。状態：video=status:<ID>。
- channel/shorts_log.csv の1行は short-upload.yml の log で足される（動かなかったときは手で足す）。完成動画と素材のドライブへの移動は、youtube-upload.yml が公開を確かめたあと drive-store.yml を自動で動かす（動いていなければ name=<名前> で手で動かす。media の名前が rina_ を外した名前と違うときは extra=media/<名前>）。

## 5. うまくいかないとき
- 号ができていない／候補が選べない／確認が20:30までに通らない → 投稿しない。理由を通知する。
- 見つけた不具合や改善点は GitHub の Issue（ラベル「AIからの報告」）に書く（tools/README.md「不具合・改善点の報告」）。
