"""Make a royalty-free background loop and sound effects with plain math (no samples, no licences).
usage: python3 tools/sfx.py <out_dir> [bgm_seconds]"""
import os, sys, wave
import numpy as np

out = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 60
os.makedirs(out, exist_ok=True)
SR = 48000
rng = np.random.default_rng(7)


def save(name, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], axis=1) if x.ndim == 1 else x
    with wave.open(os.path.join(out, name + ".wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def t_(d): return np.arange(int(SR * d)) / SR


def env(n, a=0.005, r=0.2):
    e = np.ones(n); ai = int(SR * a)
    e[:ai] = np.linspace(0, 1, ai) if ai else 1
    return e * np.exp(-np.arange(n) / (SR * r))


def lowpass(x, k):  # simple one-pole
    y = np.zeros_like(x); a = np.broadcast_to(np.asarray(k, float), x.shape)
    for i in range(1, len(x)): y[i] = y[i - 1] + a[i] * (x[i] - y[i - 1])
    return y


# ---- sound effects ----
t = t_(0.45); f = 120 * np.exp(-t * 6) + 45
save("se_don", 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.002, 0.18))
t = t_(0.35); n = rng.standard_normal(len(t))
sweep = np.sin(np.pi * t / t[-1]) ** 2
save("se_whoosh", 0.35 * lowpass(n, 0.08 + 0.25 * sweep) * sweep / 0.3)
t = t_(0.12); save("se_pop", 0.4 * np.sin(2 * np.pi * (600 + 900 * t / t[-1]) * t) * env(len(t), 0.002, 0.04))
t = t_(1.2)
bell = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((1318, .5), (1975, .25), (2637, .12)))
save("se_ding", 0.45 * bell * env(len(t), 0.002, 0.35))
t = t_(0.9); f = 70 * np.exp(-t * 3) + 32
hit = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.002, 0.35) + 0.25 * lowpass(rng.standard_normal(len(t)), 0.05) * env(len(t), 0.001, 0.08)
save("se_heavy", 0.95 * hit)

# ---- background loop: light "tech news" bed, 100 BPM, Am - F - C - G ----
bpm = 100; beat = 60 / bpm; n = int(SR * secs); x = np.zeros(n)
chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)]
bass = [110.0, 87.31, 65.41, 98.0]
bar = 4 * beat
for k in range(int(secs / bar) + 1):
    s0 = int(k * bar * SR)
    if s0 >= n: break
    c = chords[k % 4]; seg = t_(bar); m = min(len(seg), n - s0)
    pad = sum(np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * 2 * f * seg) for f in c)
    pad *= (0.6 + 0.4 * np.sin(np.pi * seg / bar)) * 0.035
    x[s0:s0 + m] += pad[:m]
    for b in range(8):  # eighth-note bass pulse
        p0 = s0 + int(b * beat / 2 * SR); tb = t_(beat / 2); mm = min(len(tb), n - p0)
        if mm <= 0: continue
        x[p0:p0 + mm] += (0.10 * np.sin(2 * np.pi * bass[k % 4] * tb) * env(len(tb), 0.004, 0.12))[:mm]
    for b in range(8):  # soft hats
        p0 = s0 + int((b + 0.5) * beat / 2 * SR); th = t_(0.05); mm = min(len(th), n - p0)
        if mm <= 0: continue
        x[p0:p0 + mm] += (0.025 * rng.standard_normal(len(th)) * env(len(th), 0.001, 0.012))[:mm]
    for b in (0, 2):  # soft kick on 1 and 3
        p0 = s0 + int(b * beat * SR); tk = t_(0.25); mm = min(len(tk), n - p0)
        if mm <= 0: continue
        fk = 90 * np.exp(-tk * 18) + 45
        x[p0:p0 + mm] += (0.18 * np.sin(2 * np.pi * np.cumsum(fk) / SR) * env(len(tk), 0.002, 0.08))[:mm]
fade = int(SR * 1.5); x[:fade] *= np.linspace(0, 1, fade); x[-fade:] *= np.linspace(1, 0, fade)
save("bgm", x / max(1e-9, np.abs(x).max()) * 0.6)
print("ok")
