// X検索結果ページで実行する抽出スクリプト。先頭の K（必須キーワード、小文字）だけ記事ごとに差し替える。
// 感想・意見だけを残す：リンクカード・URL付き、見出し風、サイト名入り、短すぎ、広告を除外。
const K=["キーワード"];
const NG=/https?:|【|】|速報|watch|itmedia|impress|ニュース|日経|記事|発表しました|プレスリリース|公式|お知らせ|#pr|ポイント最大|クーポン/i;
const M=new Map();
const grab=()=>{for(const a of document.querySelectorAll("article")){
  const h=[...a.querySelectorAll("a[href*='/status/']")].map(x=>x.getAttribute("href")).find(h=>/^\/[^/]+\/status\/\d+$/.test(h))||"";
  const id=(h.match(/(\d+)$/)||[])[1]; if(!id||M.has(id)) continue;
  const t=((a.querySelector("[data-testid=tweetText]")||{}).innerText||"").replace(/\s+/g," ");
  const tm=a.querySelector("time");
  const card=!!a.querySelector("[data-testid='card.wrapper']");
  const ad=a.innerText.includes("プロモーション");
  M.set(id,{i:id.match(/.{1,4}/g).join("-"),d:tm?tm.getAttribute("datetime").slice(0,10):"",ok:!card&&!ad&&!NG.test(t)&&t.length>=20,t:t.slice(0,34)});
}};
for(let i=0;i<5;i++){grab();window.scrollBy(0,2200);await new Promise(r=>setTimeout(r,1500));}grab();
(document.querySelectorAll("article").length?"":"EMPTY ")+JSON.stringify([...M.values()].filter(x=>x.ok&&x.d>="2026-10-20"&&K.some(k=>x.t.toLowerCase().includes(k))).slice(0,12).map(x=>x.i+" "+x.t))
