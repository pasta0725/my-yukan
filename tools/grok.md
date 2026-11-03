# Grok Bot ルーティン「マイ夕刊 Xの声」

Grok Bot（自分のクラウドPCあり）が毎日 16:20（日本時間）に Xの声を集め、tools/save_x.py で data/x/<date>.json を作って GitHub に直接 push する。
push できなかった日は、同じ JSON を pastachannel0725@gmail.com にメールし、Claude の 17:19 の作業が Gmail から取り込む。
GitHub の鍵：fine-grained token（pasta0725/my-yukan だけ、Contents: Read and write）を Grok Bot のクラウドPCの git 認証に保存してある。

## 最初の1回（Grok Bot に送る）

マイ夕刊（私専用のニュースアプリ）用の準備をお願いします。あなたのクラウドPCのターミナルで次をしてください。
1. 次の GitHub トークンを、git の認証情報として保存してください（今後も使えるように、git config --global credential.helper store を使い、github.com 用に保存）。ユーザー名は pasta0725 です。
   トークン：（ここに貼る）
2. git config --global user.name "pasta0725"、git config --global user.email "pasta0725@users.noreply.github.com" を設定してください。
3. git clone https://github.com/pasta0725/my-yukan.git ~/my-yukan を実行してください。
4. テストとして ~/my-yukan/data/_grok_test.txt に今の日時を書いて commit・push し、成功したらそのファイルを git rm して commit・push してください。
5. 結果（成功／失敗とエラー文）を教えてください。トークンは返事に書かないでください。

## ルーティンの指示文（毎日 16:20）

マイ夕刊（私専用のニュースアプリ）の「Xの声」を集めて、GitHub に保存してください。

1. クラウドPCのターミナルで cd ~/my-yukan && git pull を実行してください（フォルダが無ければ git clone https://github.com/pasta0725/my-yukan.git ~/my-yukan）。
2. data/x-todo.json を読んでください。date が今日（日本時間）でなければ、15分待って git pull し直してください（2回まで）。それでも古ければ、そのまま進めてください。
3. 各記事（articles の1件ずつ）について、Xを検索して、そのニュースへの「個人の感想・意見」の投稿を探してください。
   - 載せる：その話題について自分の言葉で感想・意見・体験・期待・不満を書いている投稿（日本語）
   - 載せない：ニュースの見出しやリンクを共有しただけの投稿、記事の内容を要約しただけの投稿、ニュースサイト・企業・公式アカウントの投稿、宣伝・アフィリエイト・クーポン、ボット、20文字未満の短い投稿、別の話題の投稿、誹謗中傷や差別的な投稿
   - 記事の日付（date）の前後数日の投稿だけ
   - 1記事あたり最大10件。見つからなければその記事は空でかまいません。無理に集めないでください
   - 同じ投稿を2つの記事に入れないでください
4. 実在を確認した投稿のURLだけを使ってください。URLを推測したり作ったりしないでください。
5. 結果を次の形で ~/answer.json に保存してください（text は投稿の本文をそのまま）。
{"date":"(x-todo.json の date)","posts":{"(記事の id)":[{"url":"https://x.com/ユーザー名/status/数字","text":"投稿の本文"}]}}
6. ~/my-yukan で python3 -I tools/save_x.py ~/answer.json (x-todo.json の date) を実行してください。data/x/(date).json ができます。
7. git add data/x && git commit -m "Xの声（Grok）(date)" && git push を実行してください。push に失敗したら git pull --rebase してからもう一度 push してください。
8. それでも push できなかったときだけ、~/answer.json の中身を本文にして、件名「マイ夕刊 Xの声 (date)」で pastachannel0725@gmail.com にメールしてください。
