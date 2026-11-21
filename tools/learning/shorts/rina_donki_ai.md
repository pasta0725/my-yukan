# rina_donki_ai の作業記録

- 動画：ドンキのAI社員「近藤あい」｜23日に正式デビュー｜https://youtube.com/shorts/kdGWGnDfXNM｜11/22 07:00 予約
- 作り方：自動（朝刊の記事 ai-donki-ai-kondo-ai）
- 今回試した改善：なし（記録の仕組みの前。後から shorts_log.csv・コミット・自動作業の記録で作った）

## 数字
<!-- 数字ここから（short_record.py が書く） -->
- かかった時間：11/21 17:38〜19:16（日本時間）＝約97分
- 工程ごと（回数は主な自動作業の回数。分は待ちも含む）：
  | 工程 | 道具・機械 | 回数 | やり直し | 分 | やり直しの前に直したこと |
  |---|---|---|---|---|---|
  | 台本・場面の設計と直し | Claude（親） | - | - | 12（自動作業が何も動いていない時間。待ちの間の作業は含まない） | 下の「直した履歴」 |
  | 素材（公式の画像・元記事） | GitHub（取り込み） | 1 | 0（要確認・失敗0） | 2 | - |
  | 事実確認 | Codex gpt-6.2-sol | 2 | 1（要確認・失敗2） | 4 | rina_donki_ai: fixes from the fact check, short.html |
  | 声（読み上げ・切り分け） | Gemini 読み上げ（Leda）＋文字起こし | 2 | 1（要確認・失敗0） | 5 | rina_donki_ai: fixes from the build check, re-read one line |
  | サムネ | Codex の画像づくり・公開後の確認 | 1 | 0（要確認・失敗0） | 3 | - |
  | 話す動画（つかみ・締め） | LongCat：Colab（約26分） | 1 | 0 | （書き出しの分に含む） | 下の「話す動画」 |
  | 書き出しと確認（画面・字幕・声・話す動画） | GitHub で書き出し＋Codex の画面確認＋Colab/Modal | 5 | 4（要確認・失敗5） | 74 | rina_donki_ai: fixes from the build check, re-read one line / rina_donki_ai: size of 約1年半, speaker of the quote, English d / rina_donki_ai: quote marks on 社員, one colour for the candida / rina_donki_ai: caption break in the debut line |
  | 投稿 | YouTube（予約・サムネ・固定コメント） | 1 | 0（要確認・失敗0） | 2 | - |
- 話す動画（つかみ・締め）：
  - 11/21 17:54 Colab（約26分）
- 直した履歴（コミット15件）：
  - 17:38 rina_donki_ai: media urls and refs
  - 17:42 rina_donki_ai: script and meta draft
  - 17:44 rina_donki_ai: fixes from the fact check, short.html
  - 17:45 rina_donki_ai: thumbnail jobs, longcat jobs
  - 17:47 rina_donki_ai: narration lines
  - 17:53 rina_donki_ai: manual split s8-s10, screen fixes from preview
  - 17:54 ショート自動：rina_donki_ai の plan.js と字幕
  - 17:54 ショート自動：rina_donki_ai の longcat の区切り数を音声の長さに合わせた
  - 18:31 rina_donki_ai: fixes from the build check, re-read one line
  - 18:34 ショート自動：rina_donki_ai の plan.js と字幕
  - 18:43 rina_donki_ai: size of 約1年半, speaker of the quote, English description
  - 18:53 rina_donki_ai: quote marks on 社員, one colour for the candidates
  - 18:54 ショート自動：rina_donki_ai の plan.js と字幕
  - 19:03 rina_donki_ai: caption break in the debut line
  - 19:04 ショート自動：rina_donki_ai の plan.js と字幕
- Claude の使った量：記録の仕組みの前で不明（11/18 の手作り1本で約46万〜49万・操作180〜250回、auto_short.md 2-2）
<!-- 数字ここまで -->

## 工程ごとのメモ（上の表に無い「なぜ」だけ）
- 読み上げ：2回。自動の切り分けが8〜10文目でずれ、無音の位置で手で切り直し（Issue #19・#24・#25・#36・#50 と同じずれ）。吹き出しで改行される「生み出しました」を「作りました」に変えて読み直し（読み上げの前の --check-captions で拾えたはず）。
- 書き出し（short-build）：5回（目標は1〜2回）。1回ごとに約15分。直しは「preview で見つけた画面」→「確認で出た所と1文の読み直し」→「約1年半の大きさ・話し手・英語の概要欄」→「社員のかぎかっこ・候補の色」→「字幕の切れ目」と、毎回少しずつ出た。
- 事実確認・画面の確認で直したこと：制作会社との関係・試験運用の言い方・「例」の付け方・英語の概要欄。画面は4場面の情報を減らし、字幕の切れ目を2か所。
- 話す動画：記録なし（問題なし）。

## つまずき（時間か量を多く使った所）
- 書き出しの回数（5回・約74分のうち多く）。1回の確認で出た指摘を全部直す前に次を回していた。
- 読み上げの切り分けのずれの手直し（毎回起きている）。

## 品質（良かった所・気になった所）
- 良い：0秒に本人の公式画像＋「実在しません」の言い切り、2文目で答えを伏せた予告。51.5秒で長さに余裕。
- 気になる：実在の人物に見えるAI画像のため「AIの使用」を手で「はい」にする作業が残った（Issue #52）。

## 次の改善（1〜3個。next.md に反映したら「済」）→ 11/21 に next.md へ反映済み
1. 書き出しの確認で出た指摘は全部まとめて直し、書き出しは2回までに（next.md 2）。
2. 台本を書いたら読み上げの前に必ず --check-captions（next.md 3）。
3. 切り分けのずれを道具で直す（next.md 1）。
