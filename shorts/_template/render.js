// render the Short: node render.js            -> whole video with audio (OUT, default short.mp4)
//                   node render.js 1.5,8,20     -> still frames snap_<t>.png
//                   PART=i/n node render.js     -> only part i of n (video only), used by render_par.js
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const D = process.cwd() + '/';
process.on('uncaughtException', e => { if (e.code !== 'EPIPE') throw e; });
(async () => {
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  p.on('pageerror', e => console.log('PAGE ERROR', e.message));
  await p.goto('file://' + D + (process.env.PAGE || 'short.html')); await p.evaluate(() => window.ready);
  const T = await p.evaluate(() => PLAN.T), fps = 30, N = Math.floor(T * fps);
  const only = process.argv[2] ? process.argv[2].split(',').map(Number) : null;
  if (only) { for (const t of only) { await p.evaluate(t => window.render(t), t); await p.screenshot({ path: D + `snap_${t}.png` }); } await b.close(); return; }
  let f0 = 0, f1 = N; const part = process.env.PART;
  if (part) { const [i, n] = part.split('/').map(Number); f0 = Math.floor(N * i / n); f1 = Math.floor(N * (i + 1) / n); }
  if (process.env.RANGE) { const [a, b2] = process.env.RANGE.split(',').map(Number); f0 = Math.round(a * fps); f1 = Math.round(b2 * fps); }  // only seconds a..b (video only)
  const args = ['-y', '-f', 'image2pipe', '-framerate', '30', '-i', '-'];
  if (!part && !process.env.RANGE) args.push('-i', D + 'work/audio.wav');
  args.push('-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p');
  if (!part && !process.env.RANGE) args.push('-c:a', 'aac', '-b:a', '192k', '-shortest');
  args.push(D + (process.env.OUT || 'short.mp4'));
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'ignore', 'ignore'] });
  for (let i = f0; i < f1; i++) {
    await p.evaluate(t => window.render(t), i / fps);
    const buf = await p.screenshot({ type: 'jpeg', quality: 90 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close(); console.log('done', f0, f1);
})();
