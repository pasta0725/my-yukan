const { chromium } = require('playwright');
const { spawn } = require('child_process');
const D = __dirname + '/';
process.on('uncaughtException', e => { if (e.code !== 'EPIPE') throw e; });
(async () => {
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  p.on('pageerror', e => console.log('PAGE ERROR', e.message));
  await p.goto('file://' + D + 'puppet.html');
  await p.evaluate(() => window.ready); await p.evaluate(() => document.fonts.ready);
  const dur = await p.evaluate(() => VOICE.dur), fps = 30;
  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', '30', '-i', '-', '-i', D + 'voice.wav',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-af', 'apad', '-shortest', D + 'puppet.mp4'], { stdio: ['pipe', 'ignore', 'ignore'] });
  for (let i = 0; i < Math.floor(dur * fps); i++) {
    await p.evaluate(t => window.render(t), i / fps);
    const buf = await p.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r));
  for (const t of [0.6, 1.25, 2.4, 3.6, 5.0, 6.6]) { await p.evaluate(t => window.render(t), t); await p.screenshot({ path: D + `pf${t}.png`, clip: { x: 160, y: 760, width: 760, height: 760 } }); }
  await b.close(); console.log('done');
})();
