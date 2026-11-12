// Overflow check (2026-11-13): renders the Short every 0.2 s and lists text that sticks out of the card/icon it sits in.
// usage (in the short's folder): node ../_template/check_fit.js      exit 0 = none, 5 = some (fix them before rendering)
const { chromium } = require('playwright');
(async () => {
  const D = process.cwd() + '/';
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.goto('file://' + D + 'short.html'); await p.evaluate(() => window.ready);
  const T = await p.evaluate(() => window.PLAN.voice_end);
  for (let t = 0; t < T; t += 0.2) await p.evaluate(t => window.render(t), t);
  const w = await p.evaluate(() => window.FIT_WARN); await b.close();
  const seen = new Map(); for (const x of w) { const k = x.scene + '|' + x.text; if (!seen.has(k) || seen.get(k).over < x.over) seen.set(k, x); }
  if (!seen.size) { console.log('fit: ok (no text outside its box)'); return; }
  for (const x of seen.values()) console.log(`OVERFLOW ${x.scene} t=${x.t}s  "${x.text}"  ${x.over}px outside its box`);
  process.exit(5);
})();
