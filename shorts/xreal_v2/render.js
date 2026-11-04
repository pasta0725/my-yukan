const { chromium } = require('playwright');
const { spawn } = require('child_process');
const D = __dirname + '/';
process.on('uncaughtException', e => { if (e.code !== 'EPIPE') throw e; });
(async () => {
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  p.on('pageerror', e => console.log('PAGE ERROR', e.message));
  await p.goto('file://' + D + 'short.html'); await p.evaluate(() => window.ready);
  const T = await p.evaluate(() => PLAN.T), fps = 30;
  const only = process.argv[2] ? process.argv[2].split(',').map(Number) : null;
  if (only) { for (const t of only) { await p.evaluate(t => window.render(t), t); await p.screenshot({ path: D + `snap_${t}.png` }); } await b.close(); return; }
  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', '30', '-i', '-', '-i', D + 'work/audio.wav',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', D + 'short.mp4'], { stdio: ['pipe', 'ignore', 'ignore'] });
  for (let i = 0; i < Math.floor(T * fps); i++) {
    await p.evaluate(t => window.render(t), i / fps);
    const buf = await p.screenshot({ type: 'jpeg', quality: 90 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close(); console.log('done');
})();
