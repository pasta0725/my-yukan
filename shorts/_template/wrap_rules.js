// The caption line-break rules of tools/shorts_rules.md「画面と字幕」, checked on finished lines (2026-11-18).
// check_fit.js and preview.js use it on every speech bubble / giant caption / chest caption before the video is rendered.
// It is written apart from wrapJa() in short.html on purpose: a mistake in wrapJa is still caught here.
//   const { check } = require('./wrap_rules'); check(['およそ259億', 'キロです'])  ->  ['数字と単位の間で改行（259億｜キロで）']
//   opt: maxLines (bubble 3, giant caption and chest caption 2), size/base/minRatio (the letters shrank below base*minRatio = no place to break)
const NOSTART = '、。，．,.・…」』）)】〕!！?？をにはがでとのもへやかよねっゃゅょぁぃぅぇぉゎッャュョァィゥェォヮヵヶーんてただ';
const NOSTART_W = ['から', 'まで', 'より', 'だけ', 'しか', 'ほど', 'など', 'くらい', 'ぐらい', 'ので', 'のに', 'けど', 'ます', 'ません'];
// words that may start a line although their first letter is in NOSTART (ただし・ただ・だから …), when the line before ends with 、 or a particle
const HEAD_OK = ['ただし', 'ただ', 'だから', 'だけど', 'だが', 'だって', 'たとえば', 'たった', 'たくさん', 'たぶん', 'でも', 'では', 'ところが', 'ところで',
  'とても', 'とくに', 'とりあえず', 'もう', 'もし', 'もっと', 'もちろん', 'しかし', 'しかも'];
const HEAD_OK_AFTER = '、。」』）!！?？ 　はがをにでともへやよねばす';
const HEAD_FREE = ['かか', 'かけ', 'かなり', 'かつて', 'かわり', 'でき', 'とき', 'ところ'];   // verbs / nouns that look like a particle: may start a line anywhere
const UNITS = ['時間', '年間', '日間', '週間', '分間', '秒間', 'カ月', 'ヶ月', 'か月', 'ヵ月', '言語', '光年', '光日', '万円', '億円', '千円', '兆円', '万人', '億人', '万台', 'パーセント'];
const PUNCT = '、。，．,!！?？ 　」』）';
const DIG = /[0-9０-９]/, HIRA = /[ぁ-ゟ]/, KATA = /[ァ-ヺーヽヾ]/, AN = /[A-Za-z0-9Ａ-Ｚａ-ｚ０-９.\-+_'’&]/;
const SOFT = 'をにはがでとのもへやよねばて';
const letters = t => t.replace(/[\s、。，．,.!！?？「」『』（）()・…〜~]/g, '').length;

function check(lines, opt = {}) {
  const out = [], L = lines.filter(l => l.length);
  const maxLines = opt.maxLines || 3;
  if (L.length > maxLines) out.push(`${L.length}行になっている（${maxLines}行まで）`);
  if (L.length > 1) for (const l of L) if (letters(l) < 3) out.push(`3文字未満の行（${l}）`);
  for (let k = 1; k < L.length; k++) {
    const prev = L.slice(0, k).join(''), last = L[k - 1], cur = L[k], a = last[last.length - 1], b = cur[0], at = `${last.slice(-4)}｜${cur.slice(0, 4)}`;
    const headOK = HEAD_FREE.some(w => cur.startsWith(w)) || HEAD_OK.some(w => cur.startsWith(w)) && HEAD_OK_AFTER.includes(a);
    if (!headOK) {
      const w = NOSTART_W.find(x => cur.startsWith(x));
      if (w || NOSTART.includes(b)) out.push(`行頭が「${w || b}」（${at}）`);
    }
    if (prev.split(/[「『（(【]/).length > prev.split(/[」』）)】]/).length || '「『（(【'.includes(a)) out.push(`かっこの中で改行（${at}）`);
    const before = last[last.length - 2] || '';
    if (DIG.test(a) && !PUNCT.includes(b)) out.push(DIG.test(b) || '.,'.includes(b) ? `数字の途中で改行（${at}）` : `数字と単位の間で改行（${at}）`);
    else if ('億万千百十兆'.includes(a) && DIG.test(before) && !PUNCT.includes(b)) out.push(DIG.test(b) ? `数字の途中で改行（${at}）` : `数字と単位の間で改行（${at}）`);
    else if (DIG.test(b) && ('.,，．約第$¥＄￥#＃+＋'.includes(a) || DIG.test(before) || /[0-9０-９]分の$/.test(last))) out.push(`数字の途中で改行（${at}）`);
    else if (DIG.test(b) && (AN.test(a) || KATA.test(a) || a === ' ')) out.push(`名前と数字の間で改行（${at}）`);
    const m = last.match(/[0-9０-９][0-9０-９.,，．億万千百十兆]*([^0-9０-９]{1,4})$/);
    if (m && UNITS.some(u => u.length > m[1].length && u.startsWith(m[1]) && (m[1] + cur).startsWith(u))) out.push(`単位の途中で改行（${at}）`);
    if (KATA.test(a) && KATA.test(b)) out.push(`カタカナ語の途中で改行（${at}）`);
    if (AN.test(a) && AN.test(b) && !(DIG.test(a) || DIG.test(b))) out.push(`英単語の途中で改行（${at}）`);
    if (b === ' ' || b === '　') out.push(`行頭が空白（${at}）`);
    if (HIRA.test(a) && HIRA.test(b) && !SOFT.includes(a) && !headOK) out.push(`ひらがなの単語の途中で改行（${at}）`);
  }
  if (opt.size && opt.base && opt.size < opt.base * (opt.minRatio || 0.7)) out.push(`改行できる所がなく字が小さい（${opt.size}px、ふつう${opt.base}px）`);
  return out;
}
module.exports = { check };
