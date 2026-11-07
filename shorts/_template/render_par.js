// parallel render: splits the video into N parts, renders them at the same time, then joins them and adds the audio.
// usage (in the short's folder): N=4 OUT=short.mp4 node render_par.js
const { spawn, execFileSync } = require('child_process');
const D = process.cwd() + '/', n = +(process.env.N || 4), out = process.env.OUT || 'short.mp4';
const run = i => new Promise((ok, ng) => { const c = spawn('node', [__dirname + '/render.js'], { cwd: D, env: { ...process.env, PART: `${i}/${n}`, OUT: `part_${i}.mp4` }, stdio: 'inherit' });
  c.on('close', code => code === 0 ? ok() : ng(new Error('part ' + i + ' failed'))); });
(async () => {
  const t0 = Date.now();
  await Promise.all([...Array(n).keys()].map(run));
  require('fs').writeFileSync(D + 'parts.txt', [...Array(n).keys()].map(i => `file 'part_${i}.mp4'`).join('\n'));
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', D + 'parts.txt', '-i', D + 'work/audio.wav',
    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', D + out]);
  console.log('joined', out, ((Date.now() - t0) / 1000).toFixed(0) + 's');
})();
