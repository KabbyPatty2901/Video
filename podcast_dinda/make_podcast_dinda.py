#!/usr/bin/env python3
"""TikTok video "Podcast Dinda" (9:16).

Dialogue comes from the user's ElevenLabs recording (vo/rekaman_user.mp3), cut
per line.  Extra voices that were not in the recording (barista, cafe crowd)
are generated with Indonesian neural TTS and cached in vo/gen/.  Visuals are
drawn with pycairo, music and SFX are synthesized with numpy, and mouths are
lip-synced to the loudness of each character's audio.

Usage:  python3 make_podcast_dinda.py            -> podcast_dinda.mp4 (+ .srt)
        python3 make_podcast_dinda.py preview 3 10 -> PNG frames at those times
"""
import math, os, subprocess, sys, wave, hashlib
import numpy as np
import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "podcast_dinda.mp4")
REC = os.path.join(HERE, "vo", "rekaman_user.mp3")
GEN_DIR = os.path.join(HERE, "vo", "gen")
W, H, FPS, SR = 1080, 1920, 30, 44100
FONT = "Inter"

# ------------------------------------------------------------------ palette
WHITE = (1, 1, 1)
INK = (0.12, 0.09, 0.08)
SKIN_S, SKIN_S2 = (0.93, 0.74, 0.58), (0.82, 0.62, 0.47)      # Sasa
SKIN_D, SKIN_D2 = (0.89, 0.68, 0.52), (0.78, 0.57, 0.42)      # Dinda
HAIR_S = (0.16, 0.10, 0.08)
HIJAB = (0.93, 0.47, 0.42)
HIJAB2 = (0.78, 0.33, 0.30)
SASA_SHIRT = (0.35, 0.58, 0.52)
DINDA_SHIRT = (0.98, 0.83, 0.55)
SASA_COL = (0.45, 0.85, 0.75)
DINDA_COL = (1.0, 0.62, 0.55)
YEL = (1.0, 0.84, 0.32)

# ------------------------------------------------------------------ dialogue clips
# (start, end) in the user's recording, found with silence detection and checked
# with Whisper.
CLIPS = {
    "S1": (0.10, 2.99, "Din… aku kemarin diputusin."),
    "S2": (3.40, 5.06, "Din, tapi aku…"),
    "S3": (5.42, 7.34, "Dia gak sadar aku udah pindah."),
    "S4": (7.78, 11.15, "Sudah 40 menit. Aku belum sempat nyebut namanya."),
    "S5": (11.55, 13.26, "Aku bahkan belum sempat cerita."),
    "C1": (13.64, 15.00, "Tag temen yang kayak Dinda."),
    "C2": (15.28, 17.35, "Atau jangan-jangan… itu kamu?"),
    "C3": (17.62, 19.50, "Komen di bawah, aku dengerin kok."),
    "C4": (19.72, 21.03, "Heh, beneran."),
    "D1": (21.36, 22.98, "Ya ampun, Sa…"),
    "D2": (23.19, 24.36, "Aku juga pernah!"),
    "D3": (24.60, 25.92, "Dulu mantanku tuh…"),
    "D4": (26.04, 29.42, "…terus aku bilang gini, dia bilang gitu, terus semua orang pada…"),
    "D5": (29.58, 30.98, "Bentar, belum kelar."),
    "D6": (31.22, 32.58, "Jadi pas itu aku…"),
    "T1": (32.82, 34.66, "Sa, makasih ya udah dengerin."),
    "T2": (34.94, 36.46, "Kamu pendengar terbaik."),
}
# Voices generated here because they are not in the recording.
GEN = {
    "barista": dict(voice="id-ID-ArdiNeural", rate="+6%", pitch="+2Hz",
                    text="Es kopi susu gula aren, atas nama Kak Sasa?"),
}
WALLA = [  # cafe crowd, mixed far away so it reads as murmur
    ("id-ID-GadisNeural", "+0%", "-8Hz", "Eh serius? Terus gimana?"),
    ("id-ID-ArdiNeural", "+5%", "-6Hz", "Mas, gulanya dikit aja ya."),
    ("id-ID-GadisNeural", "+8%", "+12Hz", "Hahaha, ya ampun lucu banget sih."),
    ("id-ID-ArdiNeural", "-4%", "+8Hz", "Besok jadi nggak? Jam berapa?"),
    ("id-ID-GadisNeural", "+4%", "+4Hz", "Aku pesen yang biasa aja deh."),
    ("id-ID-ArdiNeural", "+2%", "-12Hz", "Wifi-nya apa ya kak?"),
    ("id-ID-GadisNeural", "-2%", "-14Hz", "Nanti aku transfer ya, makasih."),
    ("id-ID-ArdiNeural", "+8%", "+0Hz", "Iya iya, aku juga mikir gitu."),
]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def back(t):
    t = clamp(t)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


# ================================================================== audio helpers
def load(path, a=None, b=None):
    cmd = ["ffmpeg", "-v", "error"]
    if a is not None:
        cmd += ["-ss", str(a), "-to", str(b)]
    cmd += ["-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"]
    x = np.frombuffer(subprocess.run(cmd, check=True, capture_output=True).stdout,
                      np.int16).astype(np.float64) / 32768
    f = int(0.012 * SR)
    if len(x) > 2 * f:
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
    return x


def tts(voice, rate, pitch, text):
    os.makedirs(GEN_DIR, exist_ok=True)
    key = hashlib.md5(f"{voice}|{rate}|{pitch}|{text}".encode()).hexdigest()[:10]
    path = os.path.join(GEN_DIR, f"{key}.mp3")
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        cmd = ["edge-tts", "--voice", voice, f"--rate={rate}", f"--pitch={pitch}",
               "--text", text, "--write-media", path]
        if os.environ.get("HTTPS_PROXY"):
            cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    x = load(path)
    idx = np.where(np.abs(x) > 0.01)[0]
    return x[max(0, idx[0] - 300): idx[-1] + 1500] if len(idx) else x


def band(x, lo, hi):
    if len(x) == 0:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def reverb(x, decay=0.4, wet=0.12, seed=3):
    rng = np.random.default_rng(seed)
    n = int(decay * 2.2 * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (decay / 3 * SR))
    ir = band(ir, 250, 6000)
    ir /= np.sqrt(np.sum(ir ** 2))
    y = np.convolve(x, ir)
    out = np.zeros(len(y))
    out[: len(x)] += x * (1 - wet)
    out += y * wet
    return out


def fx(x, kind):
    """Acoustic treatment per situation."""
    if kind == "cafe":      # talking across a cafe table
        return reverb(band(x, 90, 11000), 0.45, 0.10)
    if kind == "narrator":  # documentary voice over: close, dry, warm
        return reverb(band(x, 60, 12000), 0.15, 0.03)
    if kind == "whisper":   # leaning into the camera
        return reverb(band(x, 120, 12000), 0.15, 0.03) * 0.9
    if kind == "small":     # tiny voice, a bit swallowed by the room
        return reverb(band(x, 150, 9000), 0.45, 0.14) * 0.75
    if kind == "text":      # reading a chat message in your head
        y = band(x, 200, 8000)
        e = np.zeros(len(y) + int(0.5 * SR))
        e[: len(y)] += y
        for d, g in ((0.11, 0.22), (0.22, 0.1)):
            i = int(d * SR)
            e[i: i + len(y)] += y * g
        return reverb(e, 0.6, 0.15)
    if kind == "street":
        return reverb(band(x, 80, 12000), 0.3, 0.05)
    if kind == "far":       # Dinda still talking, a bit away
        return reverb(band(x, 220, 4200), 0.6, 0.30) * 0.42
    if kind == "veryfar":
        return reverb(band(x, 300, 2800), 0.8, 0.45) * 0.32
    if kind == "barista":
        return reverb(band(x, 100, 10000), 0.4, 0.09) * 0.95
    return x


def env100(x):
    """Loudness envelope at 100 Hz (for lip sync)."""
    h = SR // 100
    n = len(x) // h
    if n == 0:
        return np.zeros(0)
    e = np.sqrt(np.mean(x[: n * h].reshape(n, h) ** 2, axis=1))
    return e


def add(buf, sig, at):
    i = int(round(at * SR))
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(len(buf), i + len(sig))
    if i < len(buf) and j > i:
        buf[i:j] += sig[: j - i]


# ================================================================== timeline
# Each scene: base duration and spoken events.  Events start at `at` (local s)
# or `gap` seconds after the previous event; scene length follows the audio.
SCENES = [
    dict(name="hook", base=3.4, ev=[]),
    dict(name="awal", base=5.0, tail=0.45, ev=[
        dict(id="S1", who="sasa", fx="cafe", at=0.55, label="SASA"),
        dict(id="D1", who="dinda", fx="cafe", gap=0.35, label="DINDA")]),
    dict(name="ambil", base=6.0, tail=0.35, ev=[
        dict(id="D2", who="dinda", fx="cafe", at=0.25, label="DINDA", ding=True),
        dict(id="D3", who="dinda", fx="cafe", gap=0.12, label="DINDA"),
        dict(id="D4", who="dinda", fx="cafe", gap=0.75, label="DINDA", ding=True)]),
    dict(name="keluar_jiwa", base=11.0, tail=0.35, ev=[
        dict(id="S4", who="sasa", fx="narrator", at=0.35),
        dict(id="barista", who="barista", fx="barista", gap=0.45, label="BARISTA"),
        dict(id="S2", who="sasa", fx="small", gap=0.55, label="SASA"),
        dict(id="D5", who="dinda", fx="cafe", gap=0.05, label="DINDA", ding=True),
        dict(id="D6", who="dinda", fx="cafe", gap=0.2, label="DINDA")]),
    dict(name="klimaks", base=5.4, tail=0.6, ev=[
        dict(id="S3", who="sasa", fx="whisper", at=3.1, label="SASA (bisik)")]),
    dict(name="twist", base=7.0, tail=2.1, ev=[
        dict(id="T1", who="dinda_text", fx="text", at=1.7),
        dict(id="T2", who="dinda_text", fx="text", gap=0.2),
        dict(id="S5", who="sasa", fx="street", gap=0.75, label="SASA")]),
    dict(name="cta", base=6.0, tail=1.5, ev=[
        dict(id="C1", who="sasa", fx="narrator", at=0.45),
        dict(id="C2", who="sasa", fx="narrator", gap=0.25),
        dict(id="C3", who="sasa", fx="narrator", gap=0.3),
        dict(id="C4", who="sasa", fx="narrator", gap=0.15)]),
]


def plan():
    t0 = 0.0
    for sc in SCENES:
        prev = 0.0
        for ev in sc["ev"]:
            if ev["id"] in CLIPS:
                a, b, txt = CLIPS[ev["id"]]
                ev["raw"] = load(REC, a, b)
                ev["text"] = txt
            else:
                g = GEN[ev["id"]]
                ev["raw"] = tts(g["voice"], g["rate"], g["pitch"], g["text"])
                ev["text"] = g["text"]
            ev["dur"] = len(ev["raw"]) / SR
            ev["start"] = max(ev.get("at", 0.0), prev + ev.get("gap", 0.3))
            ev["end"] = ev["start"] + ev["dur"]
            prev = ev["end"]
        sc["dur"] = max(sc["base"], prev + sc.get("tail", 0.4))
        sc["t0"] = t0
        t0 += sc["dur"]
    return t0


TOTAL = plan()
SC = {sc["name"]: sc for sc in SCENES}


def E(scene, eid):
    for ev in SC[scene]["ev"]:
        if ev["id"] == eid:
            return ev["start"], ev["end"]
    raise KeyError(eid)


# Dinda keeps talking in the background (hook, jump cuts, empty-chair scene):
# her own recorded lines strung together.
BABBLE_ORDER = ["D4", "D3", "D6", "D2", "D4", "D3", "D6", "D4", "D2", "D3"]


def babble(dur, offset=0):
    """Returns (audio, [(offset_s, clip_id), ...]) so the mouth can follow it."""
    parts, n, place = [], 0, []
    k = offset
    while n < dur * SR:
        cid = BABBLE_ORDER[k % len(BABBLE_ORDER)]
        a, b, _ = CLIPS[cid]
        x = load(REC, a, b)
        place.append((n / SR, cid))
        parts += [x, np.zeros(int(0.16 * SR))]
        n += len(x) + int(0.16 * SR)
        k += 1
    y = np.concatenate(parts)[: int(dur * SR)]
    f = int(0.3 * SR)
    y[-f:] *= np.linspace(1, 0, f)
    return y, place


BABBLE = []  # (global_start, raw, fx, placements)
_s = SC["keluar_jiwa"]
for _at, _dur, _off, _kind in ((SC["hook"]["t0"] + 0.2, SC["hook"]["dur"] - 0.2, 4, "veryfar"),
                               (_s["t0"] + 0.1, E("keluar_jiwa", "S2")[0] - 0.35, 0, "far"),
                               (SC["klimaks"]["t0"] + 0.5, SC["klimaks"]["dur"] - 0.5, 2, "far")):
    _y, _pl = babble(_dur, _off)
    BABBLE.append((_at, _y, _kind, _pl))

# ------------------------------------------------------------------ lip sync (visemes)
# Whisper gives the timing of every word in each clip (cached in vo/visemes.json).
# Indonesian is written the way it is spoken, so each letter maps to a mouth shape.
# Shape = (open, width, round, teeth).  Loudness still scales how wide it opens,
# and the mouth closes in silences.
VISEME = {
    "A": (1.00, 1.00, 0.0, 0.25),   # a        jaw dropped
    "E": (0.58, 1.14, 0.0, 0.70),   # e        mid, spread
    "I": (0.34, 1.24, 0.0, 1.00),   # i y      spread, teeth
    "O": (0.74, 0.70, 1.0, 0.10),   # o        rounded
    "U": (0.42, 0.52, 1.0, 0.00),   # u w      small round
    "M": (0.00, 0.94, 0.0, 0.00),   # m b p    lips pressed
    "F": (0.14, 1.00, 0.0, 1.00),   # f v      teeth on lower lip
    "C": (0.28, 1.06, 0.0, 0.85),   # other consonants
}
VIS_JSON = os.path.join(HERE, "vo", "visemes.json")
_NUM = ["nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan"]


def num_id(n):
    n = int(n)
    if n < 10:
        return _NUM[n]
    if n < 20:
        return "sepuluh" if n == 10 else "sebelas" if n == 11 else _NUM[n - 10] + " belas"
    return _NUM[n // 10] + " puluh" + ("" if n % 10 == 0 else " " + _NUM[n % 10])


def letters_to_visemes(word):
    import re
    w = re.sub(r"\d+", lambda m: num_id(m.group()), word.lower())
    w = re.sub(r"[^a-z]", "", w)
    out, i = [], 0
    while i < len(w):
        two = w[i:i + 2]
        if two in ("ng", "ny", "kh", "sy"):
            out.append(("C", 1.0))
            i += 2
            continue
        ch = w[i]
        v = {"a": "A", "e": "E", "i": "I", "y": "I", "o": "O", "u": "U", "w": "U",
             "m": "M", "b": "M", "p": "M", "f": "F", "v": "F"}.get(ch, "C")
        weight = 2.0 if v in "AEIOU" and ch not in "yw" else 1.0
        if ch == "h" and i == len(w) - 1:
            weight = 0.4
        out.append((v, weight))
        i += 1
    return out


def align_clips():
    """Word timestamps for every clip, cached so rendering does not need Whisper."""
    import json
    cache = json.load(open(VIS_JSON)) if os.path.exists(VIS_JSON) else {}
    todo = {}
    for sc in SCENES:
        for ev in sc["ev"]:
            todo[ev["id"]] = (ev["raw"], ev["text"])
    for cid in CLIPS:
        if cid not in todo:
            a, b, txt = CLIPS[cid]
            todo[cid] = (load(REC, a, b), txt)
    missing = [k for k, (x, _) in todo.items() if cache.get(k, {}).get("n") != len(x)]
    if missing:
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="cpu", compute_type="int8")
        for k in missing:
            x, txt = todo[k]
            x16 = np.interp(np.arange(0, len(x), SR / 16000), np.arange(len(x)), x).astype(np.float32)
            segs, _ = model.transcribe(x16, language="id", word_timestamps=True, beam_size=5,
                                       initial_prompt=txt)
            words = [(w.word.strip(), w.start, w.end) for sg in segs for w in sg.words]
            cache[k] = {"n": len(x), "words": words}
        json.dump(cache, open(VIS_JSON, "w"), indent=1, ensure_ascii=False)
    return cache


ALIGN = align_clips()


def viseme_track(cid, x):
    """(open, width, round, teeth) at 100 Hz for one clip."""
    n = len(x) // (SR // 100) + 1
    key = np.zeros((n, 4))
    key[:, 1] = 1.0
    frames, targets = [], []
    for word, ws, we in ALIGN[cid]["words"]:
        vs = letters_to_visemes(word)
        if not vs:
            continue
        tot = sum(wt for _, wt in vs)
        t = ws
        for v, wt in vs:
            d = (we - ws) * wt / tot
            frames.append(t + d * 0.5)
            targets.append(VISEME[v])
            t += d
        frames.append(we + 0.03)
        targets.append((0.0, 1.0, 0.0, 0.0))
    if frames:
        tt = np.arange(n) / 100
        fr = np.array(frames)
        tg = np.array(targets)
        for j in range(4):  # coarticulation: glide between letter targets
            key[:, j] = np.interp(tt, fr, tg[:, j], left=(0 if j != 1 else 1), right=(0 if j != 1 else 1))
    # loudness: open wider on stressed/loud parts, close in silences
    e = env100(x)
    e = e / (np.percentile(e, 95) + 1e-9)
    amp = np.clip((e - 0.06) / 0.5, 0, 1)
    amp = np.concatenate([amp, np.zeros(max(0, n - len(amp)))])[:n]
    key[:, 0] *= (0.6 + 0.55 * amp) * np.clip(amp / 0.1, 0, 1)
    k = np.ones(3) / 3
    key[:, 0] = np.convolve(key[:, 0], k, mode="same")
    return key


NENV = int(TOTAL * 100) + 400
VIS = {k: np.zeros((NENV, 4)) for k in ("sasa", "dinda", "barista", "dinda_text")}
ACTIVE = {k: np.zeros(NENV, bool) for k in VIS}
for k in VIS:
    VIS[k][:, 1] = 1.0


def _vis_add(who, cid, x, at):
    tr = viseme_track(cid, x)
    i = int(round(at * 100))
    j = min(NENV, i + len(tr))
    if j > i:
        seg = tr[: j - i]
        better = seg[:, 0] >= VIS[who][i:j, 0]
        VIS[who][i:j][better] = seg[better]
        ACTIVE[who][i:j] = True


for sc in SCENES:
    for ev in sc["ev"]:
        _vis_add(ev["who"], ev["id"], ev["raw"], sc["t0"] + ev["start"])
for at, raw, kind, place in BABBLE:
    for off, cid in place:
        a, b, _ = CLIPS[cid]
        _vis_add("dinda", cid, load(REC, a, b), at + off)
        # babble is cut at the end of its segment
    end = at + len(raw) / SR
    ie = int(end * 100)
    VIS["dinda"][ie: ie + 300, 0] = 0.0
    ACTIVE["dinda"][ie: ie + 300] = False


class Vis(float):
    """Mouth openness (float, so old code keeps working) + shape details."""
    def __new__(cls, h, w=1.0, rnd=0.0, teeth=0.0, active=False):
        o = float.__new__(cls, h)
        o.w, o.rnd, o.teeth, o.active = w, rnd, teeth, active
        return o


SCENE_T0 = [0.0]  # start of the scene being drawn (scene code passes local time)


def mouth(who, t):
    T = t + SCENE_T0[0]
    i = int(T * 100)
    if 0 <= i < NENV - 1:
        f = T * 100 - i
        v = VIS[who][i] * (1 - f) + VIS[who][i + 1] * f
        return Vis(float(v[0]), float(v[1]), float(v[2]), float(v[3]), bool(ACTIVE[who][i]))
    return Vis(0.0)


# ================================================================== drawing helpers
def rrect(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()


def rgb(c, col, a=1.0):
    c.set_source_rgba(col[0], col[1], col[2], a)


def font(c, size, bold=True):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)


def wrap(c, text, maxw):
    lines, cur = [], ""
    for w_ in text.split(" "):
        test = (cur + " " + w_).strip()
        if c.text_extents(test).x_advance > maxw and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = test
    lines.append(cur)
    return lines


def text_c(c, text, cx, y, size, col=WHITE, a=1.0, bold=True, maxw=920, stroke=0,
           stroke_col=(0, 0, 0), lh=1.2):
    if a <= 0:
        return y
    font(c, size, bold)
    lines = wrap(c, text, maxw)
    for i, ln in enumerate(lines):
        x = cx - c.text_extents(ln).x_advance / 2
        yy = y + i * size * lh
        if stroke:
            c.move_to(x, yy)
            c.text_path(ln)
            rgb(c, stroke_col, a)
            c.set_line_width(stroke)
            c.set_line_join(cairo.LINE_JOIN_ROUND)
            c.stroke()
        c.move_to(x, yy)
        rgb(c, col, a)
        c.show_text(ln)
    return y + len(lines) * size * lh


def glow(c, x, y, r, col, a):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, col[0], col[1], col[2], a)
    g.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
    c.set_source(g)
    c.arc(x, y, r, 0, 2 * math.pi)
    c.fill()


def vgrad(c, top, bot, y0=0, y1=H):
    g = cairo.LinearGradient(0, y0, 0, y1)
    g.add_color_stop_rgb(0, *top)
    g.add_color_stop_rgb(1, *bot)
    c.set_source(g)
    c.rectangle(0, y0, W, y1 - y0)
    c.fill()


def ellipse(c, x, y, rx, ry):
    c.save()
    c.translate(x, y)
    c.scale(rx, ry)
    c.arc(0, 0, 1, 0, 2 * math.pi)
    c.restore()


# ------------------------------------------------------------------ characters
def person(c, cx, cy, r, who, mood="neutral", T=0.0, talk=0.0, look=(0, 0), brow=0.0,
           tears=0.0, shirt=True, nod=0.0):
    """Cartoon head + shoulders.  who: 'sasa' (bob hair) or 'dinda' (hijab).
    mood: neutral sad blank smile excited smirk flat whisper open."""
    skin, skin2 = (SKIN_S, SKIN_S2) if who == "sasa" else (SKIN_D, SKIN_D2)
    c.save()
    cy = cy + nod * r * 0.08
    # shoulders / body
    if shirt:
        col = SASA_SHIRT if who == "sasa" else DINDA_SHIRT
        rgb(c, col)
        c.move_to(cx - r * 1.55, cy + r * 2.7)
        c.curve_to(cx - r * 1.55, cy + r * 1.45, cx - r * 0.85, cy + r * 1.2, cx, cy + r * 1.2)
        c.curve_to(cx + r * 0.85, cy + r * 1.2, cx + r * 1.55, cy + r * 1.45, cx + r * 1.55, cy + r * 2.7)
        c.close_path()
        c.fill()
        if who == "sasa":  # cardigan opening
            rgb(c, (0.95, 0.93, 0.86))
            c.move_to(cx - r * 0.35, cy + r * 1.2)
            c.line_to(cx, cy + r * 2.7)
            c.line_to(cx + r * 0.35, cy + r * 1.2)
            c.close_path()
            c.fill()
    if who == "dinda":
        # hijab drape (behind face) down onto the shoulders
        rgb(c, HIJAB)
        c.move_to(cx - r * 1.25, cy - r * 0.1)
        c.curve_to(cx - r * 1.4, cy - r * 1.55, cx + r * 1.4, cy - r * 1.55, cx + r * 1.25, cy - r * 0.1)
        c.curve_to(cx + r * 1.3, cy + r * 0.9, cx + r * 1.2, cy + r * 1.6, cx + r * 0.9, cy + r * 1.9)
        c.curve_to(cx + r * 0.3, cy + r * 2.15, cx - r * 0.3, cy + r * 2.15, cx - r * 0.9, cy + r * 1.9)
        c.curve_to(cx - r * 1.2, cy + r * 1.6, cx - r * 1.3, cy + r * 0.9, cx - r * 1.25, cy - r * 0.1)
        c.close_path()
        c.fill()
        rgb(c, HIJAB2, 0.5)  # fold
        c.set_line_width(r * 0.05)
        c.move_to(cx - r * 0.8, cy + r * 1.6)
        c.curve_to(cx - r * 0.3, cy + r * 1.85, cx + r * 0.3, cy + r * 1.85, cx + r * 0.8, cy + r * 1.6)
        c.stroke()
    else:
        # bob hair (back)
        rgb(c, HAIR_S)
        c.move_to(cx - r * 1.12, cy - r * 0.2)
        c.curve_to(cx - r * 1.3, cy + r * 0.6, cx - r * 1.2, cy + r * 0.95, cx - r * 0.95, cy + r * 1.0)
        c.line_to(cx + r * 0.95, cy + r * 1.0)
        c.curve_to(cx + r * 1.2, cy + r * 0.95, cx + r * 1.3, cy + r * 0.6, cx + r * 1.12, cy - r * 0.2)
        c.close_path()
        c.fill()
        # neck
        rgb(c, skin2)
        c.rectangle(cx - r * 0.25, cy + r * 0.75, r * 0.5, r * 0.5)
        c.fill()
    # face
    rgb(c, skin)
    ellipse(c, cx, cy, r * 0.92 if who == "dinda" else r, r * 1.08)
    c.fill()
    if who == "dinda":
        # inner cap line (ciput) framing the forehead
        rgb(c, HIJAB2)
        c.save()
        c.translate(cx, cy)
        c.scale(1, 1.1)
        c.arc(0, 0, r * 0.98, math.pi * 1.0, math.pi * 2.0)
        c.arc_negative(0, -r * 0.05, r * 0.86, math.pi * 2.0 - 0.05, math.pi * 1.0 + 0.05)
        c.close_path()
        c.restore()
        c.fill()
        rgb(c, HIJAB)
        c.save()
        c.translate(cx, cy)
        c.scale(1, 1.12)
        c.arc(0, 0, r * 1.16, math.pi * 0.97, math.pi * 2.03)
        c.arc_negative(0, 0, r * 0.97, math.pi * 2.03, math.pi * 0.97)
        c.close_path()
        c.restore()
        c.fill()
        # sides of hijab along the cheeks
        for sx in (-1, 1):
            c.move_to(cx + sx * r * 0.93, cy - r * 0.1)
            c.curve_to(cx + sx * r * 0.98, cy + r * 0.5, cx + sx * r * 0.75, cy + r * 0.95, cx + sx * r * 0.35, cy + r * 1.12)
            c.line_to(cx + sx * r * 1.2, cy + r * 1.1)
            c.line_to(cx + sx * r * 1.22, cy - r * 0.1)
            c.close_path()
            c.fill()
    else:
        for sx in (-1, 1):  # ears
            rgb(c, skin)
            c.arc(cx + sx * r * 0.98, cy + r * 0.1, r * 0.15, 0, 2 * math.pi)
            c.fill()
        # bob fringe + top
        rgb(c, HAIR_S)
        c.save()
        c.translate(cx, cy)
        c.scale(1, 1.1)
        c.move_to(-r * 1.12, r * 0.05)
        c.arc(0, -r * 0.02, r * 1.12, math.pi, 2 * math.pi)
        c.line_to(r * 1.12, r * 0.05)
        c.line_to(r * 0.95, r * 0.05)
        c.curve_to(r * 0.9, -r * 0.35, r * 0.6, -r * 0.42, r * 0.2, -r * 0.4)
        c.line_to(-r * 0.75, -r * 0.42)
        c.curve_to(-r * 0.9, -r * 0.3, -r * 0.95, -r * 0.1, -r * 0.95, r * 0.05)
        c.close_path()
        c.restore()
        c.fill()
        # side curtains
        for sx in (-1, 1):
            c.move_to(cx + sx * r * 0.95, cy - r * 0.1)
            c.curve_to(cx + sx * r * 1.0, cy + r * 0.4, cx + sx * r * 1.05, cy + r * 0.8, cx + sx * r * 0.98, cy + r * 1.02)
            c.line_to(cx + sx * r * 1.25, cy + r * 1.0)
            c.curve_to(cx + sx * r * 1.3, cy + r * 0.6, cx + sx * r * 1.25, cy + r * 0.1, cx + sx * r * 1.12, cy - r * 0.1)
            c.close_path()
            c.fill()
    # cheeks
    if mood in ("smile", "excited", "smirk"):
        for sx in (-1, 1):
            rgb(c, (1, 0.45, 0.45), 0.28)
            c.arc(cx + sx * r * 0.52, cy + r * 0.4, r * 0.15, 0, 2 * math.pi)
            c.fill()
    # eyes
    ex, ey = cx + look[0] * r * 0.09, cy + r * 0.1 + look[1] * r * 0.07
    dx = r * 0.37
    ph = (T * 0.31 + (0.5 if who == "dinda" else 0)) % 1.0
    blink = ph < 0.045 and mood not in ("blank", "flat")
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for sx in (-1, 1):
        x = ex + sx * dx
        if blink:
            rgb(c, INK)
            c.set_line_width(r * 0.05)
            c.move_to(x - r * 0.1, ey)
            c.line_to(x + r * 0.1, ey)
            c.stroke()
            continue
        if mood == "excited":
            rgb(c, INK)
            ellipse(c, x, ey, r * 0.12, r * 0.14)
            c.fill()
            rgb(c, WHITE)
            c.arc(x + r * 0.04, ey - r * 0.05, r * 0.04, 0, 2 * math.pi)
            c.fill()
        elif mood in ("blank", "flat"):
            # half-lidded, empty stare
            rgb(c, WHITE)
            ellipse(c, x, ey, r * 0.15, r * 0.11)
            c.fill()
            rgb(c, INK)
            c.arc(x + look[0] * r * 0.03, ey + r * 0.02, r * 0.045, 0, 2 * math.pi)
            c.fill()
            rgb(c, skin2)
            c.rectangle(x - r * 0.17, ey - r * 0.13, r * 0.34, r * 0.1 if mood == "flat" else r * 0.08)
            c.fill()
            rgb(c, INK)
            c.set_line_width(r * 0.035)
            c.move_to(x - r * 0.16, ey - (r * 0.03 if mood == "flat" else r * 0.05))
            c.line_to(x + r * 0.16, ey - (r * 0.03 if mood == "flat" else r * 0.05))
            c.stroke()
        elif mood == "smirk":
            rgb(c, INK)
            c.set_line_width(r * 0.06)
            if sx < 0:
                c.arc(x, ey + r * 0.04, r * 0.1, 1.15 * math.pi, 1.85 * math.pi)
                c.stroke()
            else:
                ellipse(c, x, ey, r * 0.1, r * 0.08)
                c.fill()
        else:
            rgb(c, INK)
            ellipse(c, x, ey, r * 0.1, r * 0.12)
            c.fill()
            rgb(c, WHITE)
            c.arc(x + r * 0.035, ey - r * 0.045, r * 0.035, 0, 2 * math.pi)
            c.fill()
            if mood in ("sad",) or tears > 0:
                rgb(c, (0.7, 0.88, 1.0), 0.7)  # watery shine
                c.arc(x - r * 0.03, ey + r * 0.05, r * 0.03, 0, 2 * math.pi)
                c.fill()
    # brows
    rgb(c, HAIR_S if who == "sasa" else (0.25, 0.15, 0.12))
    c.set_line_width(r * 0.065)
    for sx in (-1, 1):
        x = ex + sx * dx
        by = ey - r * 0.3 - brow * r * 0.17
        if mood in ("sad",):
            c.move_to(x - sx * r * 0.16, by - r * 0.06)
            c.line_to(x + sx * r * 0.15, by + r * 0.04)
        elif mood in ("blank", "flat"):
            c.move_to(x - r * 0.16, by + r * 0.03)
            c.line_to(x + r * 0.16, by + r * 0.03)
        elif mood == "smirk" and sx > 0:
            c.move_to(x - r * 0.16, by - r * 0.02)
            c.line_to(x + r * 0.16, by - r * 0.1)
        else:
            c.move_to(x - r * 0.16, by + r * 0.02)
            c.curve_to(x - r * 0.05, by - r * 0.05, x + r * 0.05, by - r * 0.05, x + r * 0.16, by + r * 0.02)
        c.stroke()
    # mouth: viseme-driven (open, width, round, teeth) or a mood shape at rest
    my = cy + r * 0.58
    h = float(talk)
    wv = getattr(talk, "w", 1.0)
    rnd = getattr(talk, "rnd", 0.0)
    teeth = getattr(talk, "teeth", 0.0)
    active = getattr(talk, "active", h > 0.05)
    if mood == "whisper":
        h, wv = h * 0.55, wv * 0.85
    lift = r * 0.045 if mood in ("smile", "excited", "smirk") else (-r * 0.03 if mood == "sad" else 0)
    if active and h > 0.04:
        draw_mouth(c, cx, my, r, h, wv, rnd, teeth, lift, mood == "smirk")
    elif active:
        # lips pressed together (m / b / p, or a tiny pause inside a word)
        hw = r * 0.17 * wv
        rgb(c, (0.62, 0.25, 0.26))
        c.set_line_width(r * 0.075)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.move_to(cx - hw, my - lift)
        c.curve_to(cx - hw * 0.4, my + r * 0.015, cx + hw * 0.4, my + r * 0.015, cx + hw, my - lift)
        c.stroke()
    else:
        rgb(c, (0.42, 0.13, 0.14))
        c.set_line_width(r * 0.055)
        if mood in ("smile", "excited"):
            c.arc(cx, my - r * 0.16, r * 0.22, 0.2 * math.pi, 0.8 * math.pi)
            c.stroke()
        elif mood == "smirk":
            c.move_to(cx - r * 0.18, my + r * 0.02)
            c.curve_to(cx, my + r * 0.06, cx + r * 0.12, my, cx + r * 0.22, my - r * 0.1)
            c.stroke()
        elif mood == "sad":
            c.arc(cx, my + r * 0.18, r * 0.17, 1.2 * math.pi, 1.8 * math.pi)
            c.stroke()
        elif mood == "open":
            draw_mouth(c, cx, my, r, 0.55, 0.75, 0.8, 0.2, 0, False)
        elif mood in ("blank", "flat"):
            c.move_to(cx - r * 0.14, my)
            c.line_to(cx + r * 0.14, my)
            c.stroke()
        else:
            c.move_to(cx - r * 0.13, my)
            c.curve_to(cx - r * 0.05, my + r * 0.03, cx + r * 0.05, my + r * 0.03, cx + r * 0.13, my)
            c.stroke()
    if tears > 0:
        for sx in (-1, 1):
            x = ex + sx * dx + sx * r * 0.04
            ty = ey + r * 0.14 + tears * r * 0.3
            rgb(c, (0.6, 0.83, 1.0), 0.85)
            c.move_to(x, ty - r * 0.1)
            c.curve_to(x + r * 0.06, ty, x + r * 0.05, ty + r * 0.06, x, ty + r * 0.06)
            c.curve_to(x - r * 0.05, ty + r * 0.06, x - r * 0.06, ty, x, ty - r * 0.1)
            c.fill()
    c.restore()


def draw_mouth(c, cx, my, r, h, w, rnd, teeth, lift=0.0, smirk=False):
    """Articulated cartoon mouth.  h: jaw opening 0..1, w: width factor,
    rnd: lip rounding 0..1 (o/u), teeth: how much teeth show 0..1."""
    h = clamp(h, 0, 1.1)
    hw = r * 0.23 * w * (1 - 0.3 * rnd)                 # half width
    up = r * (0.045 + 0.11 * h) * (1 + 0.35 * rnd)       # upper lip rise
    dn = r * (0.04 + 0.36 * h) * (1 + 0.1 * rnd)         # jaw drop
    sk = r * 0.04 if smirk else 0.0
    k = 0.55 + 0.35 * rnd                                # rounder controls for o/u
    lx, rx = cx - hw, cx + hw
    ly, ry = my - lift + sk, my - lift - sk
    def outline():
        c.new_path()
        c.move_to(lx, ly)
        c.curve_to(cx - hw * k, my - up, cx + hw * k, my - up, rx, ry)
        c.curve_to(cx + hw * k, my + dn, cx - hw * k, my + dn, lx, ly)
        c.close_path()
    outline()
    rgb(c, (0.32, 0.07, 0.1))
    c.fill_preserve()
    c.save()
    c.clip()
    if teeth > 0.05:                                     # upper teeth
        th = (up + dn) * (0.22 + 0.25 * teeth)
        rgb(c, (0.98, 0.97, 0.94))
        c.rectangle(lx, my - up - 2, hw * 2, th + 2)
        c.fill()
        if teeth > 0.6 and h < 0.5:                      # lower teeth for i / e
            rgb(c, (0.93, 0.92, 0.9))
            c.rectangle(lx, my + dn - th * 0.7, hw * 2, th)
            c.fill()
    if h > 0.35:                                         # tongue
        rgb(c, (0.86, 0.42, 0.45))
        ellipse(c, cx, my + dn * 0.95, hw * 0.62, dn * 0.5)
        c.fill()
    c.restore()
    outline()
    rgb(c, (0.70, 0.30, 0.31))
    c.set_line_width(r * (0.04 + 0.02 * rnd))
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.stroke()


def hand(c, x, y, r, skin, kind="palm", rot=0.0):
    c.save()
    c.translate(x, y)
    c.rotate(rot)
    rgb(c, skin)
    if kind == "palm":       # "bentar" — open palm facing out
        rrect(c, -r * 0.55, -r * 0.4, r * 1.1, r * 1.0, r * 0.35)
        c.fill()
        for i, (fx_, fl) in enumerate(((-0.42, 0.75), (-0.14, 0.95), (0.14, 0.9), (0.4, 0.7))):
            rrect(c, fx_ * r - r * 0.12, -r * 0.4 - fl * r, r * 0.24, fl * r + r * 0.2, r * 0.12)
            c.fill()
        rrect(c, -r * 0.95, -r * 0.05, r * 0.5, r * 0.22, r * 0.11)  # thumb
        c.fill()
    elif kind == "point":    # pointing at the viewer (foreshortened index finger)
        rrect(c, -r * 0.6, -r * 0.1, r * 1.2, r * 0.95, r * 0.4)  # fist
        c.fill()
        rgb(c, (0, 0, 0), 0.12)
        for i in range(3):
            c.rectangle(-r * 0.45 + i * r * 0.32, r * 0.25, r * 0.04, r * 0.5)
            c.fill()
        rgb(c, skin)
        c.arc(0, -r * 0.15, r * 0.42, 0, 2 * math.pi)  # finger coming at us
        c.fill()
        rgb(c, (0.97, 0.86, 0.8))
        ellipse(c, 0, -r * 0.2, r * 0.22, r * 0.18)  # fingernail
        c.fill()
        rgb(c, (0, 0, 0), 0.15)
        c.set_line_width(r * 0.04)
        c.arc(0, -r * 0.15, r * 0.42, 0, 2 * math.pi)
        c.stroke()
    elif kind == "fist":
        c.arc(0, 0, r * 0.45, 0, 2 * math.pi)
        c.fill()
    c.restore()


def arm(c, x0, y0, x1, y1, col, w):
    c.save()
    rgb(c, col)
    c.set_line_width(w)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(x0, y0)
    c.curve_to(x0 + (x1 - x0) * 0.2, y0 + (y1 - y0) * 0.7, x0 + (x1 - x0) * 0.6, y1, x1, y1)
    c.stroke()
    c.restore()


# ------------------------------------------------------------------ props & places
def cup(c, x, y, s, fill=1.0, iced=True, tilt=0.0):
    c.save()
    c.translate(x, y)
    c.rotate(tilt)
    c.scale(s, s)
    # plastic cup
    rgb(c, (1, 1, 1), 0.35)
    c.move_to(-48, -120)
    c.line_to(48, -120)
    c.line_to(38, 0)
    c.line_to(-38, 0)
    c.close_path()
    c.fill()
    if fill > 0:
        top = -10 - 100 * fill
        rgb(c, (0.62, 0.42, 0.26))
        k = (top + 120) / 120
        c.move_to(-48 + 10 * k, top)
        c.line_to(48 - 10 * k, top)
        c.line_to(38, 0)
        c.line_to(-38, 0)
        c.close_path()
        c.fill()
        rgb(c, (0.95, 0.9, 0.82), 0.9)  # milk layer
        c.rectangle(-44 + 10 * k, top, 88 - 20 * k, 14)
        c.fill()
        if iced:
            for (ix, iy) in ((-15, top + 30), (14, top + 45)):
                if iy < -10:
                    rgb(c, (1, 1, 1), 0.5)
                    rrect(c, ix - 12, iy - 12, 24, 24, 5)
                    c.fill()
    rgb(c, (1, 1, 1), 0.7)
    c.set_line_width(3)
    c.move_to(-48, -120)
    c.line_to(-38, 0)
    c.line_to(38, 0)
    c.line_to(48, -120)
    c.stroke()
    rgb(c, (0.15, 0.15, 0.15))  # straw
    c.set_line_width(9)
    c.move_to(12, -60)
    c.line_to(28, -175)
    c.stroke()
    c.restore()


def cafe_bg(c, T, warm=1.0, crowd=True):
    # warm wall
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, 0.55 * warm + 0.1, 0.33 * warm + 0.08, 0.2 * warm + 0.06)
    g.add_color_stop_rgb(1, 0.27, 0.16, 0.1)
    c.set_source(g)
    c.paint()
    # wood panelling
    for i in range(0, W, 90):
        rgb(c, (0, 0, 0), 0.05)
        c.rectangle(i, 1000, 3, 600)
        c.fill()
    rgb(c, (0.36, 0.22, 0.13))
    c.rectangle(0, 1000, W, 14)
    c.fill()
    # sunset window
    rrect(c, 90, 230, 400, 520, 18)
    g = cairo.LinearGradient(0, 230, 0, 750)
    g.add_color_stop_rgb(0, 1.0, 0.72, 0.45)
    g.add_color_stop_rgb(1, 0.95, 0.5, 0.35)
    c.set_source(g)
    c.fill()
    rgb(c, (1.0, 0.92, 0.7))
    c.arc(330, 600, 60, 0, 2 * math.pi)
    c.fill()
    rgb(c, (0.3, 0.18, 0.12))
    c.set_line_width(14)
    rrect(c, 90, 230, 400, 520, 18)
    c.stroke()
    c.move_to(290, 230)
    c.line_to(290, 750)
    c.stroke()
    # shelf + plants + jars
    rgb(c, (0.3, 0.18, 0.11))
    c.rectangle(600, 520, 400, 18)
    c.fill()
    for i, (px, col) in enumerate(((650, (0.35, 0.6, 0.35)), (900, (0.3, 0.55, 0.4)))):
        rgb(c, (0.75, 0.45, 0.3))
        rrect(c, px - 35, 450, 70, 70, 10)
        c.fill()
        rgb(c, col)
        for k in range(5):
            a = -math.pi / 2 + (k - 2) * 0.45 + 0.05 * math.sin(T * 1.5 + k)
            c.save()
            c.translate(px, 455)
            c.rotate(a + math.pi / 2)
            ellipse(c, 0, -40, 14, 42)
            c.restore()
            c.fill()
    for jx in (750, 800):
        rgb(c, (1, 1, 1), 0.25)
        rrect(c, jx - 20, 460, 40, 60, 8)
        c.fill()
        rgb(c, (0.4, 0.25, 0.15), 0.8)
        c.rectangle(jx - 18, 490, 36, 28)
        c.fill()
    # menu board
    rrect(c, 640, 620, 320, 260, 14)
    rgb(c, (0.15, 0.15, 0.14))
    c.fill()
    text_c(c, "MENU", 800, 680, 40, (0.95, 0.9, 0.8))
    for i, it in enumerate(("Kopi Susu", "Es Teh", "Matcha")):
        font(c, 28, False)
        rgb(c, (0.9, 0.88, 0.8))
        c.move_to(680, 735 + i * 44)
        c.show_text(it)
        c.move_to(880, 735 + i * 44)
        c.show_text("%dk" % (18 + i * 4))
    # pendant lamps
    for lx in (270, 810):
        rgb(c, (0.1, 0.08, 0.06))
        c.set_line_width(4)
        c.move_to(lx, 0)
        c.line_to(lx, 150)
        c.stroke()
        glow(c, lx, 200, 330, (1.0, 0.8, 0.45), 0.28)
        rgb(c, (0.15, 0.12, 0.1))
        c.move_to(lx - 70, 205)
        c.curve_to(lx - 60, 140, lx + 60, 140, lx + 70, 205)
        c.close_path()
        c.fill()
        rgb(c, (1.0, 0.9, 0.6))
        ellipse(c, lx, 208, 32, 12)
        c.fill()
    # background customers (silhouettes) for life
    if crowd:
        for i, (bx, by, s) in enumerate(((590, 930, 0.55), (1000, 950, 0.5))):
            rgb(c, (0.2, 0.12, 0.08), 0.55)
            bob = 4 * math.sin(T * 2 + i)
            c.arc(bx, by - 90 * s + bob, 55 * s, 0, 2 * math.pi)
            c.fill()
            c.move_to(bx - 90 * s, by + 80 * s)
            c.curve_to(bx - 90 * s, by - 20 * s, bx + 90 * s, by - 20 * s, bx + 90 * s, by + 80 * s)
            c.fill()


def table(c, y=1250, x0=-40, x1=W + 40):
    rgb(c, (0.42, 0.26, 0.15))
    rrect(c, x0, y, x1 - x0, 60, 14)
    c.fill()
    rgb(c, (0.34, 0.2, 0.11))
    c.rectangle(x0 + 20, y + 60, x1 - x0 - 40, H - y)
    c.fill()
    rgb(c, (1, 1, 1), 0.08)
    c.rectangle(x0, y + 4, x1 - x0, 6)
    c.fill()


def chair_back(c, x, y, s=1.0):
    rgb(c, (0.3, 0.17, 0.09))
    rrect(c, x - 150 * s, y, 300 * s, 360 * s, 40 * s)
    c.fill()
    rgb(c, (0.38, 0.22, 0.12))
    rrect(c, x - 120 * s, y + 30 * s, 240 * s, 140 * s, 30 * s)
    c.fill()


def two_shot(c, T, sasa_mood="neutral", dinda_mood="neutral", sasa_talk=None, dinda_talk=None,
             sasa_x=330, sasa_present=True, sasa_scale=1.0, tears=0.0, dinda_look=(-1, 0),
             sasa_look=(1, 0), cups=(1.0, 0.7), touch=0.0, palm=0.0, sasa_nod=0.0):
    st = mouth("sasa", T) if sasa_talk is None else sasa_talk
    dt = mouth("dinda", T) if dinda_talk is None else dinda_talk
    # chairs behind
    chair_back(c, 330, 1000)
    chair_back(c, 760, 990)
    # Dinda
    bounce = 6 * dt * math.sin(T * 9)
    person(c, 760, 860 + bounce, 135, "dinda", dinda_mood, T, dt, look=dinda_look,
           brow=0.6 if dinda_mood == "excited" else 0.0)
    if sasa_present:
        c.save()
        c.translate(sasa_x, 880)
        c.scale(sasa_scale, sasa_scale)
        person(c, 0, 0, 135, "sasa", sasa_mood, T, st, look=sasa_look, tears=tears, nod=sasa_nod)
        c.restore()
    if touch > 0 and sasa_present:  # Dinda's hand on Sasa's shoulder
        ex = 760 + (430 - 760) * ease(touch)
        arm(c, 640, 1110, ex, 1060, DINDA_SHIRT, 70)
        hand(c, ex, 1060, 55, SKIN_D, "fist")
    table(c)
    cup(c, 330, 1300, 1.0, fill=cups[0])
    cup(c, 760, 1300, 1.0, fill=cups[1], iced=False)
    if palm > 0:  # "bentar" — palm up at Sasa
        k = back(palm)
        arm(c, 650, 1160, 560, 1040 - 60 * k, DINDA_SHIRT, 72)
        hand(c, 545, 960 - 60 * k, 95 * k, SKIN_D, "palm", rot=-0.15)


def podcast_badge(c, T, minutes, a=1.0):
    if a <= 0:
        return
    rrect(c, 60, 110, 700, 92, 46)
    rgb(c, (0, 0, 0), 0.55 * a)
    c.fill()
    rgb(c, (1, 0.25, 0.25), a * (0.6 + 0.4 * (math.sin(T * 6) > 0)))
    c.arc(108, 156, 14, 0, 2 * math.pi)
    c.fill()
    font(c, 34, True)
    rgb(c, WHITE, a)
    c.move_to(136, 168)
    c.show_text("LIVE  ·  PODCAST DINDA")
    font(c, 30, False)
    rgb(c, (0.85, 0.85, 0.85), a)
    c.move_to(615, 168)
    m = int(minutes)
    c.show_text("%02d:%02d" % (m, int((minutes - m) * 60)))
    # mic icon
    c.save()
    c.translate(1000, 156)
    rgb(c, WHITE, a * 0.9)
    rrect(c, -16, -40, 32, 52, 16)
    c.fill()
    c.set_line_width(5)
    c.arc(0, -6, 26, 0.1 * math.pi, 0.9 * math.pi)
    c.stroke()
    c.move_to(0, 20)
    c.line_to(0, 36)
    c.stroke()
    c.restore()


def subtitle(c, text, a=1.0, y=1640, who=None, who_col=YEL, size=56):
    if a <= 0 or not text:
        return
    font(c, size, True)
    lines = wrap(c, text, 900)
    lh = size * 1.24
    bh = len(lines) * lh + 46 + (52 if who else 0)
    top = y - bh / 2
    rrect(c, 60, top, W - 120, bh, 32)
    rgb(c, (0, 0, 0), 0.62 * a)
    c.fill()
    yy = top + 23
    if who:
        font(c, 36, True)
        ext = c.text_extents(who)
        rgb(c, who_col, a)
        c.move_to(W / 2 - ext.x_advance / 2, yy + 36)
        c.show_text(who)
        yy += 52
    font(c, size, True)
    for i, ln in enumerate(lines):
        ext = c.text_extents(ln)
        c.move_to(W / 2 - ext.x_advance / 2, yy + size * 0.9 + i * lh)
        rgb(c, WHITE, a)
        c.show_text(ln)


def emoji_surface(ch, size=109):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
    im = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox()).resize((size, size))
    arr = np.array(im).astype(np.float64)
    a = arr[..., 3:4] / 255.0
    bgra = np.dstack([arr[..., 2:3] * a, arr[..., 1:2] * a, arr[..., 0:1] * a, arr[..., 3:4]]).astype(np.uint8)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    stride = surf.get_stride()
    buf = surf.get_data()
    data = np.ndarray((size, stride // 4, 4), np.uint8, buf)
    data[:, :size, :] = bgra
    surf.mark_dirty()
    return surf


EMOJI = {}


def draw_emoji(c, ch, x, y, size):
    if (ch, size) not in EMOJI:
        EMOJI[(ch, size)] = emoji_surface(ch, size)
    c.set_source_surface(EMOJI[(ch, size)], x, y)
    c.paint()


# ================================================================== scenes
def sc_hook(c, t, sc):
    cafe_bg(c, t, crowd=False)
    c.save()
    c.translate(W / 2, 980)
    z = 1.0 + 0.04 * t
    c.scale(z, z)
    c.translate(-W / 2, -980)
    nod = abs(math.sin(t * 2.4)) * 1.0  # slow, hopeless nodding
    person(c, W / 2, 900, 300, "sasa", "blank", t, 0, look=(0.6, 0), nod=nod)
    c.restore()
    # vignette
    g = cairo.RadialGradient(W / 2, 900, 300, W / 2, 900, 1200)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.6)
    c.set_source(g)
    c.paint()
    # off-screen Dinda: speech marks from the right edge
    for i in range(3):
        ph = (t * 0.9 + i / 3) % 1
        text_c(c, "bla bla bla", W - 110 - ph * 120, 540 + i * 90 - ph * 40, 34, WHITE, 0.35 * (1 - ph), bold=False)
    a = ease((t - 0.4) / 0.4)
    text_c(c, "Cerita 5 detik,", W / 2, 1600, 82, WHITE, a, stroke=12)
    a2 = ease((t - 1.2) / 0.4)
    text_c(c, "diambil alih 2 jam.", W / 2, 1705, 82, YEL, a2, stroke=12)


def sc_awal(c, t, sc):
    s1, e1 = E("awal", "S1")
    d1, de1 = E("awal", "D1")
    cafe_bg(c, t)
    tears = clamp((t - 1.2) / 1.0) if t < de1 + 0.3 else 1
    touch = clamp((t - d1 + 0.2) / 0.45)
    two_shot(c, t, sasa_mood="sad", dinda_mood="sad" if t > d1 - 0.3 else "neutral",
             tears=tears * 0.8, touch=touch, cups=(0.8, 0.8), dinda_look=(-1, 0.3), sasa_look=(0.6, 0.5))


def sc_ambil(c, t, sc):
    d2, _ = E("ambil", "D2")
    d3, e3 = E("ambil", "D3")
    d4, _ = E("ambil", "D4")
    cafe_bg(c, t)
    # slow push-in towards Dinda
    z = 1.0 + 0.28 * ease(t / sc["dur"])
    c.save()
    c.translate(760, 900)
    c.scale(z, z)
    c.translate(-760, -900)
    sasa_mood = "sad"
    if e3 + 0.05 < t < d4 + 0.1:
        sasa_mood = "open"  # tries to say something
    elif t > d4 + 0.1:
        sasa_mood = "blank"
    two_shot(c, t, sasa_mood=sasa_mood, dinda_mood="excited" if t > d2 - 0.1 else "sad",
             cups=(0.55, 0.6), tears=0.5 if t < d2 + 1 else 0, sasa_look=(0.8, 0))
    c.restore()
    # "AKU JUGA PERNAH!" burst
    if d2 - 0.05 < t < d2 + 1.4:
        k = back((t - d2 + 0.05) / 0.25)
        c.save()
        c.translate(600, 560)
        c.rotate(0.06)
        c.scale(k, k)
        font(c, 70, True)
        tw = c.text_extents("AKU JUGA PERNAH!").x_advance
        rrect(c, -tw / 2 - 30, -70, tw + 60, 100, 26)
        rgb(c, YEL)
        c.fill()
        c.move_to(-tw / 2, 4)
        rgb(c, INK)
        c.show_text("AKU JUGA PERNAH!")
        c.restore()
    podcast_badge(c, t, 0.05 + t * 0.4, ease((t - d2 - 0.3) / 0.4))
    # Sasa's attempt bubble
    if e3 + 0.05 < t < d4 + 0.15:
        text_c(c, "eh—", 300, 640, 60, WHITE, 0.9, stroke=8)


def sc_keluar_jiwa(c, t, sc):
    s4, e4 = E("keluar_jiwa", "S4")
    b0, b1 = E("keluar_jiwa", "barista")
    s2, e2 = E("keluar_jiwa", "S2")
    d5, e5 = E("keluar_jiwa", "D5")
    d6, e6 = E("keluar_jiwa", "D6")
    cut1 = s4 + (e4 - s4) * 0.45
    shots = [(0, "cup_empty"), (cut1, "clock"), (b0 - 0.25, "barista"), (b1 + 0.15, "blabla"),
             (s2 - 0.2, "try"), (d5 - 0.05, "palm"), (d6 - 0.05, "dinda_go")]
    shot = shots[0][1]
    st0 = 0
    for at, nm in shots:
        if t >= at:
            shot, st0 = nm, at
    lt = t - st0
    if shot == "cup_empty":
        cafe_bg(c, t)
        person(c, W / 2, 820, 270, "sasa", "blank", t, mouth("sasa", t) * 0, look=(0.3, 0.3))
        # sucking the empty straw
        cup(c, W / 2 + 40, 1420, 2.0, fill=0.0, tilt=-0.12 + 0.03 * math.sin(lt * 10))
        text_c(c, "*sluuurp*", 760, 1180, 50, WHITE, 0.85 * ease(lt / 0.3), stroke=8)
    elif shot == "clock":
        rgb(c, (0.5, 0.31, 0.19))
        c.paint()
        cx, cy, r = W / 2, 720, 330
        rgb(c, (0.25, 0.15, 0.09))
        c.arc(cx, cy, r + 26, 0, 2 * math.pi)
        c.fill()
        rgb(c, (0.98, 0.95, 0.88))
        c.arc(cx, cy, r, 0, 2 * math.pi)
        c.fill()
        rgb(c, INK)
        for i in range(12):
            a = i / 12 * 2 * math.pi
            c.set_line_width(10 if i % 3 == 0 else 5)
            c.move_to(cx + math.sin(a) * r * 0.85, cy - math.cos(a) * r * 0.85)
            c.line_to(cx + math.sin(a) * r * 0.95, cy - math.cos(a) * r * 0.95)
            c.stroke()
        mins = 10 + 40 * ease(lt / max(0.5, (b0 - 0.25) - cut1))
        am = mins / 60 * 2 * math.pi
        ah = (4 + mins / 60) / 12 * 2 * math.pi
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.set_line_width(22)
        c.move_to(cx, cy)
        c.line_to(cx + math.sin(ah) * r * 0.5, cy - math.cos(ah) * r * 0.5)
        c.stroke()
        c.set_line_width(12)
        c.move_to(cx, cy)
        c.line_to(cx + math.sin(am) * r * 0.78, cy - math.cos(am) * r * 0.78)
        c.stroke()
        rgb(c, (0.9, 0.3, 0.3))
        c.arc(cx, cy, 18, 0, 2 * math.pi)
        c.fill()
        text_c(c, "16.%02d" % int(mins), cx, cy + r + 120, 80, WHITE, 1.0, stroke=10)
        person(c, 820, 1500, 170, "sasa", "blank", t, 0, look=(-1, -1))
    elif shot == "barista":
        cafe_bg(c, t)
        person(c, W / 2, 820, 270, "sasa", "blank", t, 0, look=(0.6, 0.2))
        k = ease(lt / 0.5)
        bx = W + 300 - 520 * k
        arm(c, W + 200, 1600, bx, 1330, (0.15, 0.15, 0.15), 110)  # barista apron sleeve
        hand(c, bx - 20, 1320, 70, (0.82, 0.6, 0.44), "fist")
        cup(c, bx - 120, 1460, 2.0, fill=1.0)
        cup(c, 300, 1460, 2.0, fill=0.0)
        if lt > 0.5:
            text_c(c, "+1 kopi", 760, 1000, 54, YEL, ease((lt - 0.5) / 0.3), stroke=8)
    elif shot == "blabla":
        cafe_bg(c, t)
        two_shot(c, t, sasa_mood="blank", dinda_mood="excited", cups=(0.0, 0.3), sasa_nod=abs(math.sin(t * 2.4)))
        for i in range(6):
            ph = (lt * 0.8 + i / 6) % 1
            x = 700 - ph * 520 + 40 * math.sin(i * 3)
            y = 520 - ph * 60 + (i % 3) * 70
            a = 1 - ph
            font(c, 44, True)
            tw = c.text_extents("bla bla").x_advance
            rrect(c, x - tw / 2 - 22, y - 46, tw + 44, 66, 33)
            rgb(c, WHITE, 0.9 * a)
            c.fill()
            c.move_to(x - tw / 2, y)
            rgb(c, (0.8, 0.3, 0.3), a)
            c.show_text("bla bla")
    elif shot in ("try", "palm"):
        cafe_bg(c, t)
        palm = clamp((t - d5 + 0.05) / 0.25) if shot == "palm" else 0
        sasa_scale = 1.0 - 0.12 * palm
        two_shot(c, t, sasa_mood="open" if shot == "try" else "blank", dinda_mood="excited",
                 cups=(0.0, 0.2), palm=palm, sasa_scale=sasa_scale, dinda_look=(-1, 0))
        if shot == "try":
            k = back(lt / 0.25)
            c.save()
            c.translate(330, 600)
            c.scale(k, k)
            hand(c, 0, 0, 40, SKIN_S, "fist")
            rgb(c, SKIN_S)
            rrect(c, -8, -70, 16, 60, 8)  # raised index finger
            c.fill()
            c.restore()
    elif shot == "dinda_go":
        cafe_bg(c, t)
        dt = mouth("dinda", t)
        person(c, W / 2, 820, 280, "dinda", "excited", t, dt, look=(-0.5, 0), brow=0.7)
        # gesturing hands
        hand(c, 220 + 30 * math.sin(t * 7), 1350, 80, SKIN_D, "fist")
        hand(c, 860 + 30 * math.sin(t * 6 + 1), 1330, 80, SKIN_D, "fist")
    podcast_badge(c, t, 5 + 35 * clamp(t / (d6 - 0.1)), 1.0)


def sc_klimaks(c, t, sc):
    s3, e3 = E("klimaks", "S3")
    move0, move1 = 0.7, 2.3
    if t < s3 - 0.25:
        cafe_bg(c, t, warm=0.85)
        c.save()
        c.translate(W / 2, 1100)
        c.scale(0.92, 0.92)
        c.translate(-W / 2, -1100)
        k = ease((t - move0) / (move1 - move0))
        # Sasa slides away to the edge of the frame, Dinda keeps talking
        sx = 330 - 330 * k
        two_shot(c, t, sasa_mood="blank", dinda_mood="excited", cups=(0.0, 0.2),
                 sasa_x=sx, sasa_scale=1.0 - 0.35 * k, dinda_look=(-1, 0))
        c.restore()
        if k >= 1:
            text_c(c, "(kursi kosong)", 330, 1180, 40, WHITE, 0.8 * ease((t - move1) / 0.4), bold=False, stroke=6)
        podcast_badge(c, t, 41 + t * 0.2, 1.0)
    else:
        # close-up whisper to camera, Dinda tiny and blurred in the background
        lt = t - (s3 - 0.25)
        cafe_bg(c, t, warm=0.7)
        person(c, 860, 900, 70, "dinda", "excited", t, mouth("dinda", t), look=(-1, 0))
        rgb(c, (0, 0, 0), 0.35)
        c.paint()
        z = 1.0 + 0.03 * lt
        c.save()
        c.translate(W / 2, 900)
        c.scale(z, z)
        c.translate(-W / 2, -900)
        person(c, 470, 880, 300, "sasa", "whisper", t, mouth("sasa", t), look=(0, 0))
        hand(c, 760, 1060, 110, SKIN_S, "palm", rot=-0.25)  # hand cupped at mouth
        c.restore()
        if lt < 0.6:
            rgb(c, WHITE, 0.4 * (1 - lt / 0.6))
            c.paint()


def street_bg(c, t):
    vgrad(c, (0.06, 0.07, 0.17), (0.12, 0.1, 0.2))
    # buildings with lit windows
    rng = np.random.default_rng(5)
    for i in range(7):
        bx = i * 170 - 40
        bh = 420 + (i * 97) % 300
        rgb(c, (0.09, 0.09, 0.16))
        c.rectangle(bx, 1150 - bh, 160, bh)
        c.fill()
        for wy in range(int(1150 - bh + 30), 1120, 70):
            for wx in (bx + 25, bx + 95):
                if rng.random() < 0.45:
                    rgb(c, (1.0, 0.82, 0.45), 0.75)
                    c.rectangle(wx, wy, 34, 40)
                    c.fill()
    # road + sidewalk
    rgb(c, (0.16, 0.15, 0.2))
    c.rectangle(0, 1150, W, 200)
    c.fill()
    rgb(c, (0.24, 0.22, 0.26))
    c.rectangle(0, 1350, W, H - 1350)
    c.fill()
    for i in range(0, W + 200, 220):  # moving lane marks
        x = (i - t * 120) % (W + 200) - 100
        rgb(c, (0.9, 0.85, 0.6), 0.7)
        c.rectangle(x, 1245, 110, 12)
        c.fill()
    # street lamp
    rgb(c, (0.12, 0.12, 0.15))
    c.rectangle(860, 420, 18, 940)
    c.fill()
    c.move_to(869, 430)
    c.curve_to(869, 380, 800, 370, 760, 400)
    c.set_line_width(14)
    c.stroke()
    glow(c, 750, 420, 520, (1.0, 0.8, 0.45), 0.35)
    rgb(c, (1.0, 0.9, 0.6))
    ellipse(c, 750, 415, 38, 14)
    c.fill()


def phone_chat(c, x, y, w, h, t, show2):
    rrect(c, x - 16, y - 16, w + 32, h + 32, 60)
    rgb(c, (0.03, 0.03, 0.05))
    c.fill()
    rrect(c, x, y, w, h, 48)
    rgb(c, (0.92, 0.9, 0.86))
    c.fill()
    c.save()
    rrect(c, x, y, w, h, 48)
    c.clip()
    rgb(c, (0.98, 0.55, 0.5))
    c.rectangle(x, y, w, 150)
    c.fill()
    rgb(c, HIJAB2)
    c.arc(x + 80, y + 95, 38, 0, 2 * math.pi)
    c.fill()
    text_c(c, "D", x + 80, y + 110, 40, WHITE)
    font(c, 38, True)
    rgb(c, WHITE)
    c.move_to(x + 140, y + 92)
    c.show_text("Dinda")
    font(c, 24, False)
    c.move_to(x + 140, y + 126)
    c.show_text("online")
    # message bubble
    k = back(t / 0.3)
    if k > 0:
        c.save()
        c.translate(x + 40, y + 380)
        c.scale(k, k)
        rrect(c, 0, -170, w - 120, 230, 30)
        rgb(c, WHITE)
        c.fill()
        font(c, 36, False)
        rgb(c, INK)
        for i, ln in enumerate(wrap(c, "Makasih ya Sa udah dengerin. Kamu pendengar terbaik", w - 190)):
            c.move_to(28, -110 + i * 46)
            c.show_text(ln)
        c.restore()
        if show2:
            draw_emoji(c, "\U0001F979", int(x + w - 200), int(y + 300), 74)
    c.restore()


def sc_twist(c, t, sc):
    t1, e1 = E("twist", "T1")
    t2, e2 = E("twist", "T2")
    s5, e5 = E("twist", "S5")
    if t < s5 - 0.35:
        street_bg(c, t)
        walk = math.sin(t * 6) * 10
        person(c, 380, 1000 + abs(walk), 150, "sasa", "flat", t, 0, look=(0.5, 0.6))
        if t > 0.9:  # phone buzz then the chat
            k = ease((t - 1.0) / 0.35)
            c.save()
            c.translate(0, 300 * (1 - k))
            phone_chat(c, 290, 520, 620, 900, t - 1.2, t > e1)
            c.restore()
            if t < 1.6:
                text_c(c, "bzzt bzzt", 820, 470, 44, WHITE, 0.9, stroke=6)
    else:
        lt = t - (s5 - 0.35)
        street_bg(c, t)
        rgb(c, (0, 0, 0), 0.3)
        c.paint()
        glow(c, W / 2, 500, 700, (1.0, 0.8, 0.45), 0.25)
        person(c, W / 2, 860, 300, "sasa", "flat", t, mouth("sasa", t), look=(0, 0))


def sc_cta(c, t, sc):
    vgrad(c, (1.0, 0.88, 0.72), (0.98, 0.72, 0.62))
    for i in range(10):
        x = (i * 157 + 60) % W
        y = (i * 311 + t * 60) % H
        rgb(c, WHITE, 0.25)
        c.arc(x, y, 10 + (i % 3) * 6, 0, 2 * math.pi)
        c.fill()
    person(c, W / 2, 760, 250, "sasa", "smirk", t, mouth("sasa", t), look=(0, 0))
    c1, _ = E("cta", "C1")
    k = back((t - c1) / 0.35)
    if k > 0:
        arm(c, 900, 1500, 800, 1260, SASA_SHIRT, 120)
        hand(c, 790, 1200, 170 * k, SKIN_S, "point")
    text_c(c, "Kamu tim Sasa atau tim Dinda?", W / 2, 190, 56, (0.35, 0.15, 0.1), ease(t / 0.4))
    kb = back((t - 1.2) / 0.35)
    if kb > 0:
        for i, (lbl, col) in enumerate((("TIM SASA", (0.25, 0.6, 0.52)), ("TIM DINDA", (0.9, 0.42, 0.38)))):
            x = W / 2 + (-240 if i == 0 else 240)
            c.save()
            c.translate(x, 1820)
            pul = 1 + 0.04 * math.sin(t * 6 + i * 3)
            c.scale(kb * pul, kb * pul)
            rrect(c, -210, -62, 420, 124, 62)
            rgb(c, col)
            c.fill()
            text_c(c, lbl, 0, 18, 52, WHITE)
            c.restore()


DRAW = {"hook": sc_hook, "awal": sc_awal, "ambil": sc_ambil, "keluar_jiwa": sc_keluar_jiwa,
        "klimaks": sc_klimaks, "twist": sc_twist, "cta": sc_cta}
SUB_Y = {"awal": 1650, "ambil": 1650, "keluar_jiwa": 1680, "klimaks": 1640, "twist": 1640, "cta": 1560}


def draw_subs(c, sc, t):
    if sc["name"] == "hook":
        return
    evs = sc["ev"]
    for i, ev in enumerate(evs):
        if ev["who"] == "dinda_text":
            continue  # shown as a chat bubble
        nxt = evs[i + 1]["start"] - 0.05 if i + 1 < len(evs) else sc["dur"]
        if ev["start"] - 0.08 <= t < max(nxt, ev["end"] + 0.25) and (i + 1 >= len(evs) or t < evs[i + 1]["start"] - 0.05):
            lab = ev.get("label")
            col = SASA_COL if lab and lab.startswith("SASA") else DINDA_COL if lab == "DINDA" else YEL
            text = ev["text"] if ev["id"] != "barista" else "Es kopi susu gula aren, atas nama Kak Sasa?"
            subtitle(c, "“" + text + "”" if lab else text, ease((t - ev["start"] + 0.08) / 0.2),
                     y=SUB_Y[sc["name"]], who=lab, who_col=col)


# ================================================================== audio
def tone(freq, dur, amp=0.3, decay=6.0, harm=(1.0,), att=0.004):
    t = np.arange(int(SR * dur)) / SR
    sig = sum(h * np.sin(2 * np.pi * freq * (i + 1) * t) for i, h in enumerate(harm))
    return amp * sig * np.exp(-decay * t) * np.minimum(1, t / att)


def note_hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def rhodes(f, dur, amp):
    t = np.arange(int(SR * dur)) / SR
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-6 * t)
         + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-9 * t))
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)
    return amp * s * trem * np.exp(-1.8 * t) * np.minimum(1, t / 0.006)


def kick(amp=0.5):
    t = np.arange(int(SR * 0.3)) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


def noise_hit(rng, dur, lo, hi, amp, dec):
    n = int(SR * dur)
    return band(rng.standard_normal(n), lo, hi) * np.exp(-np.arange(n) / (dec * SR)) * amp


def beat_times(t0, t1, bpm0, bpm1, sub=2):
    """Grid of subdivisions with tempo ramping linearly from bpm0 to bpm1."""
    out, t, k = [], t0, 0
    while t < t1:
        out.append((t, k))
        frac = (t - t0) / max(1e-6, t1 - t0)
        bpm = bpm0 + (bpm1 - bpm0) * frac
        t += 60 / bpm / sub
        k += 1
    return out


def music_lofi(buf, t0, t1, bpm0, bpm1, rng, amp=1.0):
    chords = [[65, 69, 72, 76], [64, 67, 71, 74], [62, 65, 69, 72], [60, 64, 67, 71]]  # Fmaj7 Em7 Dm7 Cmaj7
    for t, k in beat_times(t0, t1, bpm0, bpm1, sub=2):
        beat = k // 2
        bar = beat // 4
        ch = chords[bar % 4]
        off = k % 2 == 1
        swing = 0.035 if off else 0
        if k % 8 == 0:
            for j, n in enumerate(ch):
                add(buf, rhodes(note_hz(n), 2.4, 0.045 * amp), t + j * 0.012)
            add(buf, tone(note_hz(ch[0] - 24), 1.6, 0.14 * amp, 1.6, (1, 0.3)), t)
        if k % 8 == 4:
            add(buf, tone(note_hz(ch[0] - 24 + 7), 0.9, 0.1 * amp, 2.5, (1, 0.3)), t)
        if k % 4 == 0:
            add(buf, kick(0.32 * amp), t)
        if k % 8 == 4:
            add(buf, noise_hit(rng, 0.2, 900, 5000, 0.12 * amp, 0.05), t)
        add(buf, noise_hit(rng, 0.05, 6000, 12000, (0.03 if off else 0.045) * amp, 0.012), t + swing)
        if k % 16 == 6:  # little melody
            add(buf, rhodes(note_hz(ch[2] + 12), 0.8, 0.03 * amp), t)


def music_bouncy(buf, t0, t1, bpm, rng, amp=1.0):
    """Comedic fast music: oom-pah bass, staccato plucks, woodblock."""
    prog = [[60, 64, 67], [65, 69, 72], [67, 71, 74], [60, 64, 67]]
    mel = [72, 74, 76, 74, 72, 76, 79, 77, 76, 74, 72, 71, 72, 67, 64, 67]
    for t, k in beat_times(t0, t1, bpm, bpm, sub=2):
        ch = prog[(k // 8) % 4]
        if k % 2 == 0:
            add(buf, tone(note_hz(ch[0] - 24 + (7 if k % 4 == 2 else 0)), 0.25, 0.16 * amp, 10, (1, 0.5, 0.2)), t)
        else:
            for n in ch:
                add(buf, tone(note_hz(n), 0.12, 0.035 * amp, 25, (1, 0.6, 0.3)), t)
            add(buf, tone(1800, 0.05, 0.05 * amp, 80, (1,)), t)  # woodblock
        add(buf, tone(note_hz(mel[k % 16]), 0.14, 0.045 * amp, 18, (1, 0.25, 0.1, 0.05)), t)


def music_sad(buf, t0, t1, rng, amp=1.0):
    """Music box in A minor, sad but a bit silly."""
    notes = [69, 72, 76, 72, 67, 71, 74, 71, 65, 69, 72, 69, 64, 68, 71, 68]
    for t, k in beat_times(t0, t1, 84, 84, sub=2):
        n = notes[k % 16]
        add(buf, tone(note_hz(n + 12), 1.2, 0.05 * amp, 4.0, (1, 0.0, 0.35, 0.0, 0.12)), t)
        if k % 8 == 0:
            add(buf, tone(note_hz(n - 24), 2.0, 0.08 * amp, 1.2, (1, 0.2)), t)


def sad_trombone(buf, at, amp=0.22):
    seq = [(58, 0.32), (57, 0.32), (56, 0.32), (55, 1.1)]
    t = at
    for n, d in seq:
        tt = np.arange(int(SR * d)) / SR
        f = note_hz(n) * (1 + (0.02 * np.sin(2 * np.pi * 6 * tt) if d > 0.5 else 0) - (0.03 * tt / d if d > 0.5 else 0))
        ph = 2 * np.pi * np.cumsum(f) / SR
        s = sum((1 / h) * np.sin(h * ph) for h in range(1, 9))  # brassy saw
        s = band(s, 80, 2200)
        env = np.minimum(1, tt / 0.03) * np.minimum(1, (d - tt) / 0.06)
        add(buf, amp * s * env / 2.5, t)
        t += d


def music_happy(buf, t0, t1, rng, amp=1.0):
    prog = [[60, 64, 67], [67, 71, 74], [69, 72, 76], [65, 69, 72]]  # C G Am F
    for t, k in beat_times(t0, t1, 118, 118, sub=2):
        ch = prog[(k // 8) % 4]
        if k % 2 == 0:
            add(buf, kick(0.3 * amp), t) if k % 4 == 0 else None
            add(buf, tone(note_hz(ch[0] - 24), 0.4, 0.13 * amp, 5, (1, 0.4)), t)
        if k % 4 == 2:
            add(buf, noise_hit(rng, 0.15, 1000, 6000, 0.12 * amp, 0.03), t)  # clap
        for n in ch:
            add(buf, tone(note_hz(n + 12), 0.25, 0.022 * amp, 10, (1, 0.4)), t + 0.01)
        add(buf, noise_hit(rng, 0.04, 7000, 12000, 0.03 * amp, 0.01), t)


def tape_stop(buf, at, src_t0, length=0.7, amp=0.35):
    """Pitch-down 'record stops' effect: a dying chord."""
    tt = np.arange(int(SR * length)) / SR
    f = np.maximum(1, 1 - tt / length) ** 1.5
    for n in (65, 69, 72):
        ph = 2 * np.pi * np.cumsum(note_hz(n) * f) / SR
        add(buf, amp * 0.25 * np.sin(ph) * (1 - tt / length), at)


def ding(buf, at, amp=0.32):
    add(buf, tone(1568, 1.1, amp, 4.5, (1, 0.0, 0.25, 0.0, 0.1)), at)
    add(buf, tone(2093, 0.9, amp * 0.6, 5.5, (1, 0.2)), at + 0.005)


def walla_track(dur, rng):
    """Indonesian cafe murmur from several generated voices."""
    clips = [tts(v, r, p, txt) for v, r, p, txt in WALLA]
    out = np.zeros(int(dur * SR) + SR * 4)
    for voice_layer in range(3):
        t = rng.random() * 1.5
        while t < dur:
            x = clips[rng.integers(len(clips))]
            add(out, x * (0.6 + 0.4 * rng.random()), t)
            t += len(x) / SR + 0.4 + rng.random() * 1.6
    out = reverb(band(out, 250, 3200), 0.9, 0.5)[: len(out)]
    return out / (np.max(np.abs(out)) + 1e-9)


def crickets(dur, rng, amp=0.02):
    L = int(dur * SR)
    tt = np.arange(L) / SR
    out = np.zeros(L)
    for f0, period, ph in ((4300, 0.83, 0.0), (4700, 1.07, 0.4), (3900, 1.31, 0.7)):
        k = ph
        while k < dur:
            for j in range(3):
                i = int((k + j * 0.045) * SR)
                m = int(0.03 * SR)
                if i + m < L:
                    out[i:i + m] += np.sin(2 * np.pi * f0 * tt[:m]) * np.hanning(m) * amp
            k += period * (0.85 + 0.3 * rng.random())
    return out


def motorbike(rng, dur=3.0, amp=0.12):
    """A motorbike passing by (very Indonesian night street)."""
    tt = np.arange(int(dur * SR)) / SR
    pos = (tt - dur / 2) / (dur / 2)
    f = 95 * (1 - 0.12 * np.tanh(pos * 3))  # doppler drop
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = sum((1 / h) * np.sin(h * ph) for h in range(1, 12)) + 0.3 * rng.standard_normal(len(tt))
    s = band(s, 60, 2500)
    env = 1 / (1 + (pos * 2.2) ** 2)
    return amp * s * env / np.max(np.abs(s))


def build_audio(path):
    n = int(SR * (TOTAL + 1.0))
    rng = np.random.default_rng(21)
    mus = np.zeros(n)   # music (ducked under voices)
    amb = np.zeros(n)   # ambience + sfx
    vo = np.zeros(n)
    duck = np.zeros(n)
    T0 = {sc["name"]: sc["t0"] for sc in SCENES}
    D = {sc["name"]: sc["dur"] for sc in SCENES}

    # --- voices
    for sc in SCENES:
        for ev in sc["ev"]:
            at = sc["t0"] + ev["start"]
            x = fx(ev["raw"], ev["fx"])
            add(vo, x, at)
            i0 = int((at - 0.1) * SR)
            duck[max(0, i0): i0 + len(ev["raw"]) + int(0.3 * SR)] = 1
            if ev.get("ding"):
                ding(amb, at - 0.06)
    # background babble steps back whenever Sasa or the barista speaks
    fg = np.zeros(n)
    for sc in SCENES:
        for ev in sc["ev"]:
            if ev["who"] in ("sasa", "barista"):
                i0 = int((sc["t0"] + ev["start"] - 0.25) * SR)
                fg[max(0, i0): i0 + len(ev["raw"]) + int(0.4 * SR)] = 1
    k = int(0.2 * SR)
    fg = np.convolve(fg, np.ones(k) / k, mode="same")
    bab = np.zeros(n)
    for at, raw, kind, _ in BABBLE:
        add(bab, fx(raw, kind), at)
    vo += bab * (1 - 0.82 * fg)

    # --- music per scene
    music_lofi(mus, T0["awal"], T0["ambil"], 78, 80, rng, 1.0)
    music_lofi(mus, T0["ambil"], T0["keluar_jiwa"], 82, 112, rng, 1.1)
    music_bouncy(mus, T0["keluar_jiwa"], T0["klimaks"] - 0.02, 150, rng, 1.0)
    tape_stop(amb, T0["klimaks"], T0["klimaks"])
    music_sad(mus, T0["twist"] + 0.2, T0["twist"] + E("twist", "S5")[0] - 0.4, rng, 1.0)
    sad_trombone(amb, T0["twist"] + E("twist", "S5")[1] + 0.15)
    music_happy(mus, T0["cta"], TOTAL, rng, 1.0)
    # vinyl crackle on the lo-fi part
    L = int((T0["keluar_jiwa"] - T0["awal"]) * SR)
    cr = np.zeros(L)
    idx = rng.integers(0, L, L // 900)
    cr[idx] = rng.standard_normal(len(idx)) * 0.15
    add(mus, band(cr, 1500, 9000), T0["awal"])

    # --- ambience
    cafe0, cafe1 = T0["hook"], T0["twist"]
    w = walla_track(cafe1 - cafe0, rng)
    lvl = np.full(len(w), 0.05)
    k0 = int((T0["klimaks"] - cafe0) * SR)
    lvl[k0:] = 0.075  # music stopped: room noise more noticeable
    lvl[: int((T0["awal"] - cafe0) * SR)] = 0.02  # hook: only crickets matter
    wl = w * lvl
    wl[-int(0.6 * SR):] *= np.linspace(1, 0, int(0.6 * SR))
    add(amb, wl, cafe0)
    add(amb, crickets(D["hook"] + 0.3, rng, 0.06), T0["hook"])
    # cup clinks + espresso steam now and then
    t = cafe0 + 2.0
    while t < cafe1 - 1:
        add(amb, tone(3200 + rng.random() * 800, 0.4, 0.03, 14, (1, 0.6, 0.3)), t)
        t += 2.5 + rng.random() * 3
    add(amb, noise_hit(rng, 1.4, 2500, 9000, 0.03, 0.6), T0["ambil"] + 2.0)
    # barista cup down
    b0, _ = E("keluar_jiwa", "barista")
    add(amb, tone(900, 0.2, 0.15, 30, (1, 0.5)), T0["keluar_jiwa"] + b0 - 0.1)
    # whooshes on jump cuts
    for cut in (0.0,) + tuple(np.linspace(0, 1, 1)):  # placeholder
        pass
    s4, e4 = E("keluar_jiwa", "S4")
    for at in (s4 + (e4 - s4) * 0.45, b0 - 0.25):
        add(amb, noise_hit(rng, 0.25, 800, 6000, 0.06, 0.08), T0["keluar_jiwa"] + at)
    # chair scrape when Sasa moves away
    sc_ = noise_hit(rng, 1.0, 300, 2500, 0.05, 0.4) * (1 + 0.5 * np.sin(np.arange(SR) / SR * 2 * np.pi * 14))
    add(amb, sc_, T0["klimaks"] + 0.8)
    # street: traffic hum, crickets, motorbike, phone buzz
    Ls = int((D["twist"]) * SR)
    hum = np.cumsum(rng.standard_normal(Ls))
    hum = band(hum - hum.mean(), 30, 400)
    add(amb, hum / np.max(np.abs(hum)) * 0.04, T0["twist"])
    add(amb, crickets(D["twist"], rng, 0.012), T0["twist"])
    add(amb, motorbike(rng, 3.2, 0.1), T0["twist"] + 0.3)
    for k in range(2):
        tt = np.arange(int(0.35 * SR)) / SR
        add(amb, 0.12 * np.sin(2 * np.pi * 170 * tt) * (np.sin(2 * np.pi * 30 * tt) > 0), T0["twist"] + 1.0 + k * 0.45)
    # CTA pops for buttons
    add(amb, tone(880, 0.15, 0.15, 20), T0["cta"] + 1.2)
    add(amb, tone(1320, 0.15, 0.12, 20), T0["cta"] + 1.3)

    # --- mix
    k = int(0.15 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same")
    mus = mus / (np.max(np.abs(mus)) + 1e-9) * 0.5
    voice_peak = np.max(np.abs(vo)) + 1e-9
    vo = vo / voice_peak * 0.9
    mix = mus * (1 - 0.6 * duck) + amb + vo
    fo = int(1.2 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)
    mix = np.tanh(mix * 1.1) * 0.95
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


def write_srt(path):
    def ts(x):
        ms = int(round(x * 1000))
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
    i = 0
    with open(path, "w", encoding="utf-8") as f:
        i += 1
        f.write(f"{i}\n{ts(0.4)} --> {ts(SC['hook']['dur'])}\n[Teks] Cerita 5 detik, diambil alih 2 jam.\n\n")
        for sc in SCENES:
            for ev in sc["ev"]:
                i += 1
                lab = {"sasa": "SASA", "dinda": "DINDA", "barista": "BARISTA", "dinda_text": "CHAT DINDA"}[ev["who"]]
                a, b = sc["t0"] + ev["start"], sc["t0"] + ev["end"] + 0.2
                f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{lab}: {ev['text']}\n\n")


# ================================================================== render
def render(preview=None):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)

    def draw(T):
        for sc in SCENES:
            if sc["t0"] <= T < sc["t0"] + sc["dur"] or sc is SCENES[-1]:
                t = T - sc["t0"]
                SCENE_T0[0] = sc["t0"]
                c.save()
                c.set_operator(cairo.OPERATOR_SOURCE)
                c.set_source_rgb(0, 0, 0)
                c.paint()
                c.set_operator(cairo.OPERATOR_OVER)
                DRAW[sc["name"]](c, t, sc)
                c.restore()
                draw_subs(c, sc, t)
                if t < 0.1 and sc["t0"] > 0:
                    c.set_source_rgba(1, 1, 1, 0.45 * (1 - t / 0.1))
                    c.paint()
                break
        c.rectangle(0, 0, W * T / TOTAL, 8)
        c.set_source_rgba(1, 1, 1, 0.6)
        c.fill()

    if preview:
        for T in preview:
            draw(T)
            surf.write_to_png(os.path.join(HERE, "preview_%05.1f.png" % T))
        return
    wav = os.path.join(HERE, "_audio.wav")
    build_audio(wav)
    write_srt(OUT[:-4] + ".srt")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(TOTAL * FPS)
    for f in range(nf):
        draw(f / FPS)
        surf.flush()
        p.stdin.write(bytes(surf.get_data()))
        if f % 300 == 0:
            print(f"frame {f}/{nf}", file=sys.stderr)
    p.stdin.close()
    p.wait()
    os.remove(wav)
    print("wrote", OUT, "duration %.1fs" % TOTAL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        render([float(x) for x in sys.argv[2:]])
    else:
        render()
