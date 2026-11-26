// Overflow check (2026-11-13): renders the Short every 0.2 s and lists text that sticks out of the card/icon it sits in.
// Line-break check (2026-11-18): the same pass lists every speech bubble / giant caption / chest caption whose line breaks break the rules
// of tools/shorts_rules.md「画面と字幕」(wrap_rules.js): before rendering, not in the screen check after a 15-minute render.
// usage (in the short's folder): node ../_template/check_fit.js      exit 0 = none, 5 = some (fix them before rendering), 6 = only the palette differs
//   OVERFLOW <scene> t=<s>s  "<text>"  <n>px outside its box
//   BREAK <scene> t=<s>s  "<line1／line2>"  <what is wrong>
//   BUBBLE <scene or function>  <what is wrong>   (a speech bubble drawn by hand, not with talkBox)
const { chromium } = require('playwright');
const { check } = require('./wrap_rules');
(async () => {
  const D = process.cwd() + '/';
  // palette check (2026-11-14): pal.js must be the template's (light theme, orange numbers). An empty pal.js fell back to the dark default.
  const fs = require('fs'); const tpl = fs.readFileSync(__dirname + '/pal.js', 'utf8').trim();
  const own = fs.existsSync(D + 'pal.js') ? fs.readFileSync(D + 'pal.js', 'utf8').trim() : '';
  let palBad = false; if (D !== __dirname + '/' && own !== tpl) { palBad = true; console.log('PALETTE pal.js がひな形（shorts/_template/pal.js）と違います。配色が変わるので、ひな形をそのままコピーしてください'); }
  // hand-made speech bubble (2026-11-26, user: 「フキダシが変」): a box (roundRect) and a tail (lineTo) drawn as two shapes leave the box's edge across the tail's root.
  // Speech in a scene must use the template's person() + talkBox() (one outline). Only lines that are not in the template are looked at.
  const tplLines = new Set(fs.readFileSync(__dirname + '/short.html', 'utf8').split('\n').map(x => x.trim()));
  const handBubbles = []; let owner = '';
  if (D !== __dirname + '/') for (const raw of fs.readFileSync(D + 'short.html', 'utf8').split('\n')) {
    const ln = raw.trim(); const m = ln.match(/^(?:function\s+)?(\w+)\s*\([^)]*\)\s*\{/); if (m) owner = m[1];
    if (tplLines.has(ln)) continue;
    for (const seg of ln.split(/beginPath\(\)/)) if (/roundRect\(/.test(seg) && /lineTo\(/.test(seg.slice(seg.indexOf('roundRect(')))) { handBubbles.push(owner || '?'); break; }
  }
  for (const o of new Set(handBubbles)) console.log(`BUBBLE ${o}  四角としっぽを別々に描いた吹き出し。ひな形の person()・talkBox() で描き直す`);
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.goto('file://' + D + 'short.html'); await p.evaluate(() => window.ready);
  // short.html made from the template after 2026-11-18 logs its layouts (window.WRAP_LOG); an older copy only has wrapJa(), which is watched instead
  const newer = await p.evaluate(() => { window.WRAP_LOG = []; if (window.LAYOUT) return true;
    if (typeof window.wrapJa === 'function') { const o = window.wrapJa; window.wrapJa = function (s, size, maxw) { const r = o.apply(this, arguments); window.WRAP_LOG.push({ kind: size >= 120 ? 'telop' : 'bubble', text: s, lines: r }); return r; }; }
    return false; });
  if (!newer) console.log('NOTE この short.html はひな形の 2026-11-18 より前のコピーです。改行は wrapJa の結果で調べます（ひな形の wrapJa・bubbleText・bigTelop に入れ替えると、決まりどおりに組まれます）');
  const P = await p.evaluate(() => ({ T: window.PLAN.voice_end, lines: window.PLAN.lines.map(l => [l.start, l.scene]), tel: (window.PLAN.tel || []).map(x => (x.start + (x.end || x.start + 0.4)) / 2) }));
  const times = new Set(); for (let t = 0; t < P.T; t += 0.2) times.add(+t.toFixed(2)); for (const t of P.tel) if (t < P.T) times.add(+t.toFixed(2));   // also the middle of every caption chunk
  const sceneAt = t => { let s = P.lines[0] ? P.lines[0][1] : ''; for (const [st, sc] of P.lines) if (st <= t) s = sc; return s; };
  const brk = new Map();
  for (const t of [...times].sort((x, y) => x - y)) {
    await p.evaluate(t => window.render(t), t);
    const log = await p.evaluate(() => { const l = window.WRAP_LOG; window.WRAP_LOG = []; return l; });
    for (const x of log) {
      const k = x.kind + '|' + x.text; if (brk.has(k)) continue;
      const base = { bubble: 74, telop: 150, caption: 66 }[x.kind];
      const bad = check(x.lines, { maxLines: x.kind === 'bubble' ? 3 : 2, size: x.size, base, minRatio: x.kind === 'telop' ? 0.6 : 0.7 });
      brk.set(k, { t, scene: sceneAt(t), lines: x.lines, bad });
    }
  }
  const w = await p.evaluate(() => window.FIT_WARN); await b.close();
  const seen = new Map(); for (const x of w) { const k = x.scene + '|' + x.text; if (!seen.has(k) || seen.get(k).over < x.over) seen.set(k, x); }
  const bads = [...brk.values()].filter(x => x.bad.length);
  if (!seen.size) console.log('fit: ok (no text outside its box)');
  for (const x of seen.values()) console.log(`OVERFLOW ${x.scene} t=${x.t}s  "${x.text}"  ${x.over}px outside its box`);
  console.log(`breaks: ${brk.size} captions checked, ${bads.length} break the rules`);
  for (const x of bads) console.log(`BREAK ${x.scene} t=${x.t}s  "${x.lines.join('／')}"  ${x.bad.join('; ')}`);
  if (seen.size || bads.length || handBubbles.length) process.exit(5);
  if (palBad) process.exit(6);
})();
