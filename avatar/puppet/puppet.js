// Live2D-like puppet from layered PNGs (made by tools/avatar_build.py).
// Puppet.load(dir, rig) once, then Puppet.draw(ctx, t, voice, {cx, bottom, scale}) every frame.
// voice = {fps, mouth:[[shape, open],...], env:[...]} or null (idle, mouth closed).
(function () {
  const NAMES = ['back', 'under', 'side', 'bangs', 'ribbon', 'eye_whites', 'iris', 'eyes_half', 'eyes_closed',
    'mouth_closed', 'mouth_small', 'mouth_a', 'mouth_i', 'mouth_u', 'mouth_e', 'mouth_o'];
  const SHAPES = ['small', 'a', 'i', 'u', 'e', 'o', 'closed'];
  const L = {}; let R, IW, IH, headC, hg, bodyC, bg, irisC, ig;
  const mk = (w, h) => { const k = document.createElement('canvas'); k.width = w; k.height = h; return k; };
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  let rnd = 7; const rand = () => { rnd = (rnd * 16807) % 2147483647; return rnd / 2147483647; };
  const blinks = [], glances = [[0, 0, 0]];
  for (let t = 1.2; t < 300; t += 2.2 + rand() * 2.8) blinks.push(t);
  for (let t = 0; t < 300;) { t += 1.0 + rand() * 2.0; glances.push([t, (rand() - .5) * 1.6, (rand() - .5) * 0.8]); }

  function talk(V, t) { if (!V) return 0; let s = 0; for (let d = -8; d <= 8; d++) s += V.env[clamp(Math.round(t * V.fps) + d, 0, V.env.length - 1)] || 0; return s / 17; }
  function headAt(V, t) {
    const k = talk(V, t);
    return { x: 0.55 * Math.sin(2 * Math.PI * 0.09 * t) + 0.25 * Math.sin(2 * Math.PI * 0.23 * t + 1),
      y: 0.25 * Math.sin(2 * Math.PI * 0.17 * t + 2) + 0.6 * k * Math.sin(2 * Math.PI * 1.4 * t),
      z: 0.6 * Math.sin(2 * Math.PI * 0.11 * t + .5) + 0.25 * Math.sin(2 * Math.PI * 0.31 * t) };
  }
  function springs(V, t) {
    const p = { s: 0, v: 0, r: 0, rv: 0, b: 0, bv: 0 }; const dt = 1 / 60; let prev = headAt(V, Math.max(0, t - 3));
    for (let u = Math.max(0, t - 3); u <= t; u += dt) {  // the last 3 s are enough for the springs to settle
      const h = headAt(V, u); const ax = (h.x - prev.x) / dt * 14 + (h.z - prev.z) / dt * 10; prev = h;
      p.v += (-70 * p.s - 6 * p.v - ax) * dt; p.s += p.v * dt; p.rv += (-45 * p.r - 4 * p.rv - ax * 1.3) * dt; p.r += p.rv * dt;
      p.bv += (-110 * p.b - 9 * p.bv - ax * 0.5) * dt; p.b += p.bv * dt;
    }
    return p;
  }
  function blinkAt(t) { for (const b of blinks) { const d = t - b; if (d >= 0 && d < 0.2) return d < 0.05 || d > 0.15 ? 1 : 2; } return 0; }
  function glanceAt(t) { let a = glances[0]; for (const gl of glances) { if (gl[0] <= t) a = gl; else break; } return [a[1], a[2]]; }
  // one shape at a time (no double exposure); openness eases between frames
  function mouthAt(V, t) {
    if (!V) return ['closed', 0];
    const f = Math.round(t * V.fps), cur = V.mouth[clamp(f, 0, V.mouth.length - 1)] || ['closed', 0];
    const prev = V.mouth[clamp(f - 1, 0, V.mouth.length - 1)] || ['closed', 0];
    const open = prev[0] === cur[0] ? 0.4 * prev[1] + 0.6 * cur[1] : cur[1];
    return [cur[0], open];
  }
  function bend(ctx, img, dx, box, power = 1.6, sx = 0, sy = 0) {
    const tot = dx + sx;
    if (!box || Math.abs(tot) < 0.02 && Math.abs(sy) < 0.02) { ctx.drawImage(img, 0, 0); return; }
    const [x0, y0, x1, y1] = box, h = y1 - y0;
    ctx.drawImage(img, 0, 0, IW, y0, 0, 0, IW, y0);
    for (let y = y0; y < y1; y++) { const k = Math.pow((y - y0) / h, power); ctx.drawImage(img, 0, y, IW, 1, tot * k, y + sy * k, IW, 1.6); }
    ctx.drawImage(img, 0, y1, IW, IH - y1, tot, y1 + sy, IW, IH - y1);
  }
  window.Puppet = {
    async load(dir, rig) {
      R = rig; IW = R.size[0]; IH = R.size[1];
      headC = mk(IW, IH); hg = headC.getContext('2d'); bodyC = mk(IW, IH); bg = bodyC.getContext('2d');
      irisC = mk(400, 300); ig = irisC.getContext('2d');
      await Promise.all(NAMES.map(n => new Promise(r => { const i = new Image(); i.onload = () => { L[n] = i; r(); }; i.src = dir + '/' + n + '.png'; })));
      // body = under layer below the neck (fixed), prepared once
      const [nx, ny] = R.neck; bg.drawImage(L.under, 0, 0); bg.globalCompositeOperation = 'destination-out';
      const gr = bg.createLinearGradient(0, ny - 40, 0, ny + 40); gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      bg.fillStyle = gr; bg.fillRect(0, 0, IW, IH); bg.globalCompositeOperation = 'source-over';
    },
    draw(g, t, V, o = {}) {
      const cx = o.cx ?? 540, bottom = o.bottom ?? 1960, S = o.scale ?? 1.02, cut = o.cut ?? 1127;
      const h = headAt(V, t), sp = springs(V, t), k = talk(V, t), px = 10, [nx, ny] = R.neck;
      hg.clearRect(0, 0, IW, IH);
      hg.drawImage(L.under, 0, 0); hg.globalCompositeOperation = 'destination-in';
      const gr = hg.createLinearGradient(0, ny - 40, 0, ny + 40); gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
      hg.fillStyle = gr; hg.fillRect(0, 0, IW, IH); hg.globalCompositeOperation = 'source-over';
      const [ex, ey] = R.eyes, fx = h.x * px * 0.5, fy = h.y * px * 0.3;
      hg.drawImage(L.eye_whites, ex + fx, ey + fy);
      const [gx, gy] = glanceAt(t);
      ig.clearRect(0, 0, irisC.width, irisC.height);
      ig.drawImage(L.iris, gx * 4 + h.x * 2.5, gy * 3); ig.globalCompositeOperation = 'destination-in'; ig.drawImage(L.eye_whites, 0, 0); ig.globalCompositeOperation = 'source-over';
      hg.drawImage(irisC, ex + fx, ey + fy);
      const bl = blinkAt(t); if (bl) hg.drawImage(bl === 1 ? L.eyes_half : L.eyes_closed, ex + fx, ey + fy);
      const [mx, my] = R.mouth, [shape, open] = mouthAt(V, t);
      hg.drawImage(L.mouth_closed, mx + fx, my + fy);
      if (shape !== 'closed' && open > 0.02) { hg.globalAlpha = clamp(open * 1.2); hg.drawImage(L['mouth_' + shape], mx + fx, my + fy); hg.globalAlpha = 1; }
      bend(hg, L.side, sp.s * 9, R.side_box, 1.8, h.x * px * 0.25, 0);
      bend(hg, L.bangs, sp.b * 4, R.bangs_box, 1.2, h.x * px * 0.7, h.y * px * 0.2);
      bend(hg, L.ribbon, sp.r * 12, R.ribbon_box, 1.7, -h.x * px * 0.15, 0);
      const sway = 0.008 * Math.sin(2 * Math.PI * 0.19 * t) + 0.004 * Math.sin(2 * Math.PI * 0.41 * t + 1);
      const breath = 1 + 0.007 * Math.sin(2 * Math.PI * 0.26 * t), bob = -6 * k * Math.abs(Math.sin(2 * Math.PI * 1.4 * t));
      g.save(); g.translate(cx, bottom + bob); g.rotate(sway); g.scale(S, S * breath); g.translate(-IW / 2, -cut);
      const headT = () => { g.translate(nx, ny); g.rotate(h.z * 0.035); g.translate(h.x * px * 0.15, h.y * px * 0.35); g.translate(-nx, -ny); };
      g.save(); headT(); bend(g, L.back, -sp.s * 5, R.back_box, 1.5, -h.x * px * 0.6, 0); g.restore();
      g.drawImage(bodyC, 0, 0);
      g.save(); headT(); g.drawImage(headC, 0, 0); g.restore();
      g.restore();
    },
  };
})();
