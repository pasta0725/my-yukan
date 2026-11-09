// PNGTuber 星餓りな (tools/shorts_rules.md 「りなの動かし方」, 2026-11-09).
// One still picture per pose; only the mouth and eyes change, so the body never jumps.
// Pictures and their eye/mouth positions: channel/rina_puppet/ (made by tools/rina_puppet_prep.py).
// Page setup:
//   <script src="../../channel/rina_puppet/index.js"></script><script src="../_template/puppet.js"></script>
//   await Puppet.load('../../channel/rina_puppet/');
//   Puppet.chibi(g, x, y, w, h, t, mouth)            small presenter (lower-left)
//   Puppet.big(g, name, x, y, w, h, t, mouth)          big presenter, name = big_base / big_finger1 / ...
//   Puppet.mouthAt(PLAN.voices[lineIndex], secondsIntoLine)  -> [shape, openness] from the narration
//   Puppet.transition('base_to_finger1', secondsUntilEnd) -> picture name while moving into a pose
(function () {
  const IDX = window.PUPPET_INDEX || { assets: {}, transitions: {} };
  const A = IDX.assets, IM = {};
  const SHAPE = { a: [0.95, 0.78], i: [1.05, 0.34], u: [0.52, 0.48], e: [0.92, 0.52], o: [0.64, 0.72], small: [0.46, 0.3] };
  function load(base) {
    return Promise.all(Object.keys(A).map(k => new Promise(r => {
      const i = new Image(); i.onload = () => { IM[k] = i; r(); }; i.onerror = () => r(); i.src = base + k + '.webp';
    })));
  }
  function mouthAt(voice, u) {
    if (!voice || !voice.mouth) return null;
    const f = Math.floor(u * (voice.fps || 30));
    return voice.mouth[f] || null;
  }
  const rgb = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  // open mouth: skin patch over the drawn closed mouth, then a simple anime mouth
  function drawMouth(g, a, ox, oy, sc, m, chibi) {
    if (!m || !a.mouth) return;
    const [shape, open] = m; const sh = SHAPE[shape];
    if (!sh || open < 0.12) return;
    const mx = ox + a.mouth[0] * sc, my = oy + a.mouth[1] * sc, mw = a.mouth_w * sc;
    const w = mw * sh[0] * (0.75 + 0.25 * open), h = Math.max(mw * 0.08, mw * sh[1] * open);
    const skin = a.skin || [250, 220, 220];
    const gr = g.createRadialGradient(mx, my, 0, mx, my, mw * 0.75);
    gr.addColorStop(0, rgb(skin)); gr.addColorStop(0.75, rgb(skin)); gr.addColorStop(1, rgb(skin, 0));
    g.fillStyle = gr; g.beginPath(); g.ellipse(mx, my, mw * 0.75, mw * 0.5, 0, 0, Math.PI * 2); g.fill();
    const top = my - h * 0.35, bot = my + h * 0.65;
    g.save();
    g.beginPath();
    g.moveTo(mx - w / 2, top + h * 0.12);
    g.quadraticCurveTo(mx, top - h * 0.12, mx + w / 2, top + h * 0.12);   // upper lip, almost flat
    g.quadraticCurveTo(mx + w / 2, bot, mx, bot);                          // round lower side
    g.quadraticCurveTo(mx - w / 2, bot, mx - w / 2, top + h * 0.12);
    g.closePath();
    g.fillStyle = chibi ? '#8E2337' : '#A3384B'; g.fill();
    g.clip();
    g.fillStyle = chibi ? '#F27B8E' : '#F28C9B';                           // tongue
    g.beginPath(); g.ellipse(mx, bot, w * 0.36, h * 0.42, 0, 0, Math.PI * 2); g.fill();
    g.restore();
    g.beginPath();
    g.moveTo(mx - w / 2, top + h * 0.12);
    g.quadraticCurveTo(mx, top - h * 0.12, mx + w / 2, top + h * 0.12);
    g.quadraticCurveTo(mx + w / 2, bot, mx, bot);
    g.quadraticCurveTo(mx - w / 2, bot, mx - w / 2, top + h * 0.12);
    g.closePath();
    g.lineJoin = 'round'; g.lineWidth = Math.max(1.2, mw * (chibi ? 0.07 : 0.05)); g.strokeStyle = chibi ? '#3A141C' : '#6B2F3A'; g.stroke();
  }
  // blink: deterministic times (every 2.6-4.8 s), eyes shut for ~0.11 s
  function blinking(t) {
    let s = 1.3, k = 0;
    while (s < t + 1) { const d = 2.6 + ((Math.sin(++k * 12.9898) * 43758.5453) % 1 + 1) % 1 * 2.2; if (t >= s && t < s + 0.11) return true; s += d; }
    return false;
  }
  function closedEyes(g, a, ox, oy, sc) {
    const [bw, bh] = a.eye_box, skin = a.skin;
    for (const [ex, ey] of a.eyes) {
      const x = ox + ex * sc, y = oy + ey * sc, rw = bw * sc * 0.56, rh = bh * sc * 0.5;
      g.fillStyle = rgb(skin); g.beginPath(); g.ellipse(x, y + rh * 0.05, rw, rh, 0, 0, Math.PI * 2); g.fill();
      g.strokeStyle = '#2A1418'; g.lineWidth = Math.max(1.5, bw * sc * 0.07); g.lineCap = 'round';
      g.beginPath(); g.moveTo(x - rw * 0.85, y + rh * 0.1); g.quadraticCurveTo(x, y + rh * 0.62, x + rw * 0.85, y + rh * 0.1); g.stroke();
    }
  }
  // small presenter (lower-left). name: 'small_sticker' (normal proportions, sticker style, 2026-11-09) or 'chibi' (old)
  function chibi(g, x, y, w, h, t, m, name) {
    name = name || 'chibi'; const a = A[name], im = IM[name]; if (!im) return;
    // keep the picture's shape: fit inside the box, standing on its bottom, centred
    const sc = Math.min(w / a.size[0], h / a.size[1]);
    x += (w - a.size[0] * sc) / 2; y += h - a.size[1] * sc; w = a.size[0] * sc; h = a.size[1] * sc;
    // only a slow breathing move (no bounce that follows the mouth: frame-by-frame mouth changes made her twitch, user 2026-11-09)
    const bob = Math.sin(t * 2.0) * 1.2;
    const rot = Math.sin(t * 1.3) * 0.006;                    // gentle sway around the feet
    g.save(); g.translate(x + w / 2, y + h); g.rotate(rot); g.translate(-(x + w / 2), -(y + h) + bob);
    g.drawImage(im, x, y, w, h);
    if (blinking(t)) closedEyes(g, a, x, y, sc);
    drawMouth(g, a, x, y, sc, m, name === 'chibi');
    g.restore();
  }
  function big(g, name, x, y, w, h, t, m) {
    const a = A[name], im = IM[name]; if (!im) return;
    const sc = w / a.size[0], bob = Math.sin(t * 1.9) * 1.6;
    g.save(); g.translate(0, bob);
    g.drawImage(im, x, y, w, h);
    if (a.eyes && blinking(t)) closedEyes(g, Object.assign({ eye_box: [62, 40] }, a), x, y, sc);  // blink (big still used as a puppet, 2026-11-09)
    if (a.mouth) drawMouth(g, a, x, y, sc, m, false);
    g.restore();
  }
  // moving into a pose: 3 frames per in-between drawing, ending exactly when the pose is reached
  function transition(key, before) {
    const seq = (IDX.transitions || {})[key]; if (!seq) return null;
    const n = seq.length - 2, step = 0.1;
    if (before <= 0) return seq[seq.length - 1];
    if (before > n * step) return seq[0];
    return seq[1 + Math.floor((n * step - before) / step)];
  }
  window.Puppet = { load, mouthAt, chibi, big, transition, assets: A };
})();
