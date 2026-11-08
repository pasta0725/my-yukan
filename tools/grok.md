# Grok Bot ルーティン「マイ夕刊 Xの声」

Grok Bot（自分のクラウドPCあり）が毎日2回、朝刊は 6:10、夕刊は 16:20（日本時間）に Xの声を集め、tools/save_x.py で data/x/<号のID>.json を作って GitHub に直接 push する（2026-11-10〜。号のIDは朝刊 YYYY-MM-DD-am、夕刊 YYYY-MM-DD-pm）。
push できなかったときは、同じ JSON を pastachannel0725@gmail.com にメールし、Claude の取り込み作業（6:41・6:56／17:04・17:19）が Gmail から取り込む。
Grok のルーティンは2つ（6:10 と 16:20）。指示文はどちらも下の同じ文章でよい（時刻で朝刊か夕刊かを判断する）。
GitHub の鍵：fine-grained token（pasta0725/my-yukan だけ、Contents: Read and write）を Grok Bot のクラウドPCの git 認証に保存してある。

## 最初の1回（Grok Bot に送る）

マイ夕刊（私専用のニュースアプリ）用の準備をお願いします。あなたのクラウドPCのターミナルで次をしてください。
1. 次の GitHub トークンを、git の認証情報として保存してください（今後も使えるように、git config --global credential.helper store を使い、github.com 用に保存）。ユーザー名は pasta0725 です。
   トークン：（ここに貼る）
2. git config --global user.name "pasta0725"、git config --global user.email "pasta0725@users.noreply.github.com" を設定してください。
3. git clone https://github.com/pasta0725/my-yukan.git ~/my-yukan を実行してください。
4. テストとして ~/my-yukan/data/_grok_test.txt に今の日時を書いて commit・push し、成功したらそのファイルを git rm して commit・push してください。
5. 結果（成功／失敗とエラー文）を教えてください。トークンは返事に書かないでください。

## ルーティンの指示文（毎日 6:10 と 16:20、同じ文章）

マイ夕刊（私専用のニュースアプリ）の「Xの声」を集めて、GitHub に保存してください。マイ夕刊は1日2回、朝刊（7時）と夕刊（17時半）を出しています。

1. クラウドPCのターミナルで cd ~/my-yukan && git pull を実行してください（フォルダが無ければ git clone https://github.com/pasta0725/my-yukan.git ~/my-yukan）。
2. 今が日本時間の12時より前なら、今回集めるのは今日の朝刊で、号のIDは「今日の日付-am」（例 2026-11-10-am）です。12時以降なら今日の夕刊で「今日の日付-pm」（例 2026-11-10-pm）です。
3. data/x-todo.json を読んでください。中の date が手順2の号のIDと違うときは、まだ号ができていません。10分待って git pull し直してください（3回まで）。それでも違うときは、何もせずに「号がまだできていませんでした」と書いて終わってください。
4. 各記事（articles の1件ずつ）について、Xを検索して、そのニュースへの「個人の感想・意見」の投稿を探してください。
   - 載せる：その話題について自分の言葉で感想・意見・体験・期待・不満を書いている投稿（日本語）
   - 載せない：ニュースの見出しやリンクを共有しただけの投稿、記事の内容を要約しただけの投稿、ニュースサイト・企業・公式アカウントの投稿、宣伝・アフィリエイト・クーポン、ボット、20文字未満の短い投稿、別の話題の投稿、誹謗中傷や差別的な投稿
   - そのニュースが出てからの投稿だけ（目安は号の日付の前後数日）
   - 1記事あたり最大10件。見つからなければその記事は空でかまいません。無理に集めないでください
   - 同じ投稿を2つの記事に入れないでください
5. 実在を確認した投稿のURLだけを使ってください。URLを推測したり作ったりしないでください。
6. 結果を次の形で ~/answer.json に保存してください（text は投稿の本文をそのまま）。
{"date":"(x-todo.json の date)","posts":{"(記事の id)":[{"url":"https://x.com/ユーザー名/status/数字","text":"投稿の本文"}]}}
7. ~/my-yukan で python3 -I tools/save_x.py ~/answer.json (x-todo.json の date) を実行してください。data/x/(date).json ができます。
8. git add data/x && git commit -m "Xの声（Grok）(date)" && git push を実行してください。push に失敗したら git pull --rebase してからもう一度 push してください。
9. それでも push できなかったときだけ、~/answer.json の中身を本文にして、件名「マイ夕刊 Xの声 (date)」で pastachannel0725@gmail.com にメールしてください。
10. 朝刊は6時40分まで、夕刊は17時までに終えてください。間に合わないときは、それまでに集まった分で手順6からに進んでください。
