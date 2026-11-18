// Preview of the key frames before the whole render (2026-11-18): the whole render takes ~15 min, and it was redone 4-5 times a video
// because the screen check found the mistakes only afterwards. This draws only the frames that matter, in a minute or two:
//   0-8 s every 0.5 s (the giant caption and the hook), each line's start + 0.3 s, the middle of every caption chunk, the last 2 s every 0.5 s.
// Each frame is drawn by render.js's one-frame mode (node render.js 1.6,9,51 -> snap_<t>.png), split over the CPUs.
// The parts YouTube covers (left/right 50 px, the search icon y180-280) are tinted light pink, and the frames are put on
// contact sheets with their time, scene and caption: preview/sheet_NN.png (12 a sheet). check_fit.js (overflow + line breaks) runs at the
// same time and writes preview/fit.txt.
// usage (in the short's folder): node ../_template/preview.js      env: N=<processes> (default: CPUs), PER=<frames a sheet> (default 12)
// exit code = check_fit.js's (0 = nothing to fix, 5 = fix the OVERFLOW / BREAK lines in preview/fit.txt first, 6 = palette only)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');
const D = process.cwd() + '/', OUT = D + 'preview/', t0 = Date.now();
const sec = () => ((Date.now() - t0) / 1000).toFixed(1);
const run = (args, logFile) => new Promise(ok => {
  const c = spawn('node', args, { cwd: D, stdio: ['ignore', 'pipe', 'pipe'] }); let out = '';
  c.stdout.on('data', d => out += d); c.stderr.on('data', d => out += d);
  c.on('close', code => { if (logFile) fs.writeFileSync(logFile, out); ok({ code, out }); });
});
(async () => {
  fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT + 'frames', { recursive: true });
  global.window = {}; eval(fs.readFileSync(D + 'plan.js', 'utf8')); const P = window.PLAN;
  const T = P.T || P.voice_end, lines = P.lines || [], tel = P.tel || [];
  // which frames, and why
  const want = [];
  for (let t = 0; t <= Math.min(8, T - 0.05); t += 0.5) want.push([t, '0〜8秒']);
  for (const L of lines) want.push([L.start + 0.3, 'セリフの頭']);
  for (const x of tel) want.push([(x.start + (x.end || x.start + 0.4)) / 2, '字幕']);
  for (let t = Math.max(0, T - 2); t < T; t += 0.5) want.push([t, '最後']);
  want.push([Math.max(0, T - 0.05), '最後']);
  want.sort((a, b) => a[0] - b[0]);
  const frames = [];
  for (const [t, why] of want) {
    const r = Math.round(Math.min(Math.max(t, 0), T - 0.02) * 100) / 100;
    const near = frames.find(f => Math.abs(f.t - r) < 0.15);
    if (near) { if (!near.why.includes(why)) near.why.push(why); } else frames.push({ t: r, why: [why] });
  }
  const n = Math.max(1, Math.min(+(process.env.N || os.cpus().length), frames.length));
  console.log(`${frames.length} frames, ${n} processes`);
  // check_fit.js alongside the frames
  const fit = run([path.join(__dirname, 'check_fit.js')], OUT + 'fit.txt');
  const parts = [...Array(n)].map((_, i) => frames.filter((_, k) => k % n === i).map(f => f.t));
  const res = await Promise.all(parts.map(ts => run([path.join(__dirname, 'render.js'), ts.join(',')])));
  for (const r of res) if (r.code) { console.log('render.js failed:\n' + r.out.slice(-2000)); process.exit(3); }
  for (const f of frames) { const src = D + `snap_${f.t}.png`; f.file = OUT + `frames/t_${f.t.toFixed(2)}.png`; if (fs.existsSync(src)) fs.renameSync(src, f.file); else f.file = null; }
  console.log(`frames drawn: ${sec()} s`);
  // label each frame: time, scene, caption chunk on screen
  const sceneAt = t => { let s = lines[0] ? lines[0].scene : ''; for (const L of lines) if (L.start <= t) s = L.scene; return s; };
  const capAt = t => { let c = tel[0] ? tel[0].text : ''; for (const x of tel) if (x.start <= t) c = x.text; return c; };
  const mmss = t => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;
  const per = +(process.env.PER || 12), cols = 4, tw = 360, th = 640, lab = 74, gap = 10;
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const rows = Math.ceil(per / cols), SW = cols * tw + (cols - 1) * gap, SH = rows * (th + lab) + (rows - 1) * gap;
  const p = await b.newPage({ viewport: { width: SW, height: SH } });
  await p.goto('file://' + OUT); await p.setContent(`<html><body style="margin:0;background:#555"><canvas id="c" width="${SW}" height="${SH}"></canvas></body></html>`);
  const sheets = [];
  for (let s = 0; s * per < frames.length; s++) {
    const items = frames.slice(s * per, (s + 1) * per).map((f, k) => ({ k: s * per + k + 1, img: f.file ? 'data:image/png;base64,' + fs.readFileSync(f.file).toString('base64') : null,
      head: `#${s * per + k + 1}  ${mmss(f.t)}  ${sceneAt(f.t)}`, why: f.why.join('・'), cap: capAt(f.t) }));
    await p.evaluate(async ({ items, cols, tw, th, lab, gap, SW, SH }) => {
      const c = document.getElementById('c'), g = c.getContext('2d'); g.fillStyle = '#555'; g.fillRect(0, 0, SW, SH);
      const sc = tw / 1080;
      for (let i = 0; i < items.length; i++) {
        const it = items[i], x = (i % cols) * (tw + gap), y = Math.floor(i / cols) * (th + lab + gap);
        g.fillStyle = '#111'; g.fillRect(x, y, tw, lab);
        g.fillStyle = '#FFE14D'; g.font = '700 22px "Noto Sans CJK JP",sans-serif'; g.textBaseline = 'top'; g.fillText(it.head, x + 8, y + 6, tw - 16);
        g.fillStyle = '#FFFFFF'; g.font = '700 19px "Noto Sans CJK JP",sans-serif'; g.fillText(`${it.why}｜${it.cap}`, x + 8, y + 40, tw - 16);
        if (it.img) { const im = new Image(); await new Promise(r => { im.onload = r; im.onerror = r; im.src = it.img; }); g.drawImage(im, x, y + lab, tw, th); }
        else { g.fillStyle = '#933'; g.fillRect(x, y + lab, tw, th); g.fillStyle = '#fff'; g.fillText('描けなかった', x + 20, y + lab + 20); }
        // what YouTube covers: left/right 50 px, the search icon y180-280 (the tint is not in the video)
        g.fillStyle = 'rgba(255,105,180,0.33)'; g.fillRect(x, y + lab, 50 * sc, th); g.fillRect(x + tw - 50 * sc, y + lab, 50 * sc, th);
        g.fillRect(x + 50 * sc, y + lab + 180 * sc, tw - 100 * sc, 100 * sc);
      }
    }, { items, cols, tw, th, lab, gap, SW, SH });
    const f = OUT + `sheet_${String(s + 1).padStart(2, '0')}.png`; await p.screenshot({ path: f }); sheets.push(path.basename(f));
  }
  await b.close();
  const fr = await fit;
  console.log(`sheets: ${sheets.join(' ')}  (${sec()} s)`);
  console.log(`check_fit.js (exit ${fr.code}) -> preview/fit.txt`); process.stdout.write(fr.out.split('\n').filter(l => /^(OVERFLOW|BREAK|PALETTE|fit:|breaks:)/.test(l)).map(l => '  ' + l + '\n').join(''));
  console.log(`total ${sec()} s`);
  process.exit(fr.code === 0 || fr.code === 5 || fr.code === 6 ? fr.code : 4);
})();
