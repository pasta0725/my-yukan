# 星餓りなのテックニュースとショート（pasta0725/my-yukan）

## ユーザーとの話し方
- 日本語だけ。短く、専門用語を使わない（ユーザーはコードを読まない）。
- 質問は本文に書かず、選択式の質問機能で聞く。
- 作業中にウェブサイトの許可確認を出さない（ページは fetch-to-branch.yml などで GitHub 側で取る）。
- パスワード・鍵・トークン・支払い情報は入力も表示もしない。ログインや鍵の登録はユーザーがする。
- 動画は渡す前に自分で1秒ごとに確かめる。動画とサムネはこの画面で見られる形で渡す。

## 作業の決まり
- 最初に、作業に合う文書を読む（決定事項はここが正）：サイトの号づくり＝tools/README.md・tools/style.md・tools/spec.md、ショート＝tools/shorts_rules.md・tools/auto_short.md・tools/learning/shorts/next.md、投稿とサムネ＝tools/metadata_rules.md・tools/thumbnail_rules.md。
- コミットの作者は pasta0725 <pasta0725@users.noreply.github.com>。push の前は git fetch origin && git rebase origin/main。強制 push・ブランチ削除はしない。gh は REST（gh api・gh workflow run）を使う。
- 音声・画像・動画は main に入れず work ブランチへ（tools/work_branch.py）。
- 確かめてから行う：GitHub 側のファイルを消す作業の手動実行（drive-store.yml など）、公開済みのサムネの差し替え、ユーザーのものの完全な削除、Claude の無料リセットボタン（押すのはユーザー）。
- 話す動画は Colab から（longcat-colab.yml。wait=0 で Modal だけにするのは、同じ制作で Colab が実際に止まったときだけ）。
- 外の仕組みが遅い・止まるときは、打ち切りや切り替えで済ませず、原因をこちら側も疑って分析し、tools/shorts_rules.md と Issue に記録する。
- 単純な作業は Sonnet の助手に任せる（必要なだけ並列）。
- 新しく決まったことは、その文書の同じ話題の行を書き換える（足し続けない）。作業の終わりにスキルも更新案を出す。
- ショートは1本ごとに作業記録と振り返りを書き、次の1本の改善を決める（tools/learning/shorts/README.md。投稿のあと、通知の前。省かない）。
- 不具合・改善点は Issue（ラベル「AIからの報告」）に日本語で書く。
- YouTube で「AIで作っている」と書かない。
- Claude の利用枠を節約する：結果は RESULT と「- LOOK」の行だけ読む、同じ文書を読み直さない、待つのは gh run watch を1回（tools/auto_short.md の「利用枠」）。
- 1つの作業＝1つの会話。続きは HANDOFF.md（引き継ぎメモ）から始め、終わったら書き換える。
