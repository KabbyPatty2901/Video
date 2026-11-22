#!/usr/bin/env python3
"""TikTok video "Remarried Empress" - versi reveal judul di akhir (9:16).

Narration: the user's ElevenLabs recording (vo/narasi.mp3).  Word timings were
found with Whisper (faster-whisper "small") and are stored below, so rendering
does not need Whisper.  Characters are cut out of the user's character sheet
(karakter.png); backgrounds, effects, music and SFX are generated here.

Usage:  python3 make_remarried_empress.py              -> remarried_empress.mp4 (+ .srt)
        python3 make_remarried_empress.py preview 3 34 -> preview_*.png at those times
"""
import math, os, subprocess, sys, wave
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "remarried_empress.mp4")
NARASI = os.path.join(HERE, "vo", "narasi.mp3")
SHEET = os.path.join(HERE, "karakter.png")
FONTS = os.path.join(HERE, "fonts")
W, H, FPS, SR = 1080, 1920, 30, 44100
DUR = 74.0

CINZEL = os.path.join(FONTS, "cinzel-700-normal.ttf")
CINZEL6 = os.path.join(FONTS, "cinzel-600-normal.ttf")
GARA_I = os.path.join(FONTS, "cormorant-garamond-600-italic.ttf")
INTER_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
INTER_B = "/usr/share/fonts/opentype/inter/Inter-Black.otf"

GOLD = (255, 211, 110)
RED = (226, 38, 48)
WHITE = (255, 255, 255)

# ------------------------------------------------------------------ narration words
# (word, start, end) from Whisper, spelling fixed to match the script.
WORDS_RAW = """
Dia 0.00 0.32|permaisuri 0.32 0.96|paling 0.96 1.60|sempurna, 1.60 2.26|tapi 2.50 3.20|suaminya 3.20 4.00|malah 4.00 4.30|membawa 4.30 4.66|wanita 4.66 5.06|lain 5.06 5.54|ke 5.54 5.70|istana. 5.70 6.08
Selama 6.58 7.04|bertahun-tahun, 7.04 7.98|dia 8.24 8.44|mengurus 8.44 8.96|negara, 8.96 9.46|menyelamatkan 9.46 10.52|kerajaan, 10.52 11.42|dan 11.42 11.66|setia 11.66 12.22|pada 12.22 12.46|suaminya. 12.46 13.12
Lalu 13.58 14.00|suatu 14.00 14.30|hari, 14.30 14.72|sang 15.16 15.42|kaisar 15.42 15.82|pulang 15.82 16.30|membawa 16.30 16.78|seorang 16.78 17.16|wanita. 17.16 17.64
Seorang 18.22 18.52|mantan 18.52 19.02|budak 19.02 19.44|yang 19.44 19.92|langsung 19.92 20.42|dijadikan 20.42 20.92|kesayangan 20.92 21.60|istana. 21.60 22.06
Dia 22.50 22.80|disuruh 22.80 23.34|menerimanya 23.34 24.00|dan 24.00 24.54|harus 24.54 25.02|tetap 25.02 25.44|tersenyum. 25.44 25.92
Tiap 25.92 26.58|hari, 26.58 26.96|dia 27.08 27.20|melihat 27.20 27.62|suaminya 27.62 28.12|tertawa 28.12 28.74|untuk 28.74 29.06|wanita 29.06 29.40|lain. 29.40 29.82
Lalu 30.18 30.52|datang 30.52 31.00|kalimat 31.00 31.40|yang 31.40 31.64|menghancurkan 31.64 32.54|semuanya. 32.54 33.02
Ayo 33.58 33.88|bercerai. 33.88 34.32
Semua 34.90 35.22|orang 35.22 35.52|mengira 35.52 35.90|dia 35.90 36.22|akan 36.22 36.52|hancur. 36.52 37.18
Tapi 37.50 37.90|dia 37.90 38.48|justru 38.48 39.02|mengangkat 39.02 39.40|kepala 39.40 39.84|dan 39.84 40.36|menerima 40.36 40.88|perceraian 40.88 41.52|itu. 41.52 41.76
Lebih 42.20 42.60|gila 42.60 42.84|lagi, 42.84 43.34|tak 43.80 43.90|lama 43.90 44.08|kemudian 44.08 44.62|dia 44.62 44.88|menikah 44.88 45.54|dengan 45.54 45.74|raja 45.74 46.20|dari 46.20 46.66|negeri 46.66 47.00|lain. 47.00 47.26
Seorang 47.66 48.04|pria 48.04 48.58|yang 48.58 48.88|diam-diam 48.88 49.54|sudah 49.54 49.94|lama 49.94 50.44|menunggunya. 50.44 51.10
Sekarang 51.60 52.20|giliran 52.20 52.56|sang 52.56 52.90|kaisar 52.90 53.38|yang 53.38 53.56|gelisah. 53.56 54.14
Dia 54.14 54.62|baru 54.62 54.86|sadar, 54.86 55.48|wanita 55.70 56.22|yang 56.22 56.44|dia 56.44 56.60|buang 56.60 57.10|ternyata 57.10 57.78|penopang 57.78 58.46|seluruh 58.46 59.06|kerajaannya. 59.06 59.70
Dan 59.98 60.30|istana 60.30 60.78|yang 60.78 61.02|dulu 61.02 61.24|megah 61.24 61.86|mulai 61.86 62.36|retak 62.36 62.84|dari 62.84 63.04|dalam. 63.04 63.36
Judulnya… 63.88 64.54|Remarried 64.98 65.66|Empress. 65.66 66.24
Baca 66.68 67.06|sampai 67.06 67.30|habis, 67.30 67.84|dijamin 68.06 68.64|kamu 68.64 69.00|gak 69.00 69.16|bisa 69.16 69.34|berhenti. 69.34 69.80
Kamu 70.22 70.52|tim 70.52 70.64|siapa? 70.64 71.02|Tulis 71.34 71.72|di 71.72 71.82|komen! 71.82 72.04
"""
LINES = []
for ln in WORDS_RAW.strip().splitlines():
    ws = []
    for item in ln.split("|"):
        w, a, b = item.rsplit(" ", 2)
        ws.append((w, float(a), float(b)))
    LINES.append(ws)


def chunks():
    """Caption chunks: at most ~16 characters per chunk, broken at punctuation."""
    out = []
    for ws in LINES:
        cur = []
        for w in ws:
            cur.append(w)
            text = " ".join(x[0] for x in cur)
            if len(text) >= 15 or w[0][-1] in ",.?!…":
                out.append(cur); cur = []
        if cur:
            out.append(cur)
    # merge a trailing single short word into the previous chunk of the same line
    return out


CHUNKS = chunks()
# words that are shown as big titles instead of captions
NO_CAPTION = [(33.45, 34.9), (64.9, 66.5), (70.1, 99.0)]


# ------------------------------------------------------------------ helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def eout(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def back(t):
    t = clamp(t)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def ramp(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def win(t, a, b, fi=0.3, fo=0.3):
    return min(ramp(t, a, a + fi), 1 - ramp(t, b - fo, b))


_FC = {}


def font(path, size):
    k = (path, size)
    if k not in _FC:
        _FC[k] = ImageFont.truetype(path, size)
    return _FC[k]


# ------------------------------------------------------------------ characters
PAD = 60          # native px of transparent padding around every cut-out
HS = 2            # hi-res factor of the stored cut-outs
BOXES = {"navier": (22, 24, 408, 850), "sovieshu": (440, 24, 828, 850),
         "rashta": (856, 24, 1240, 850), "heinley": (1266, 24, 1652, 850)}
# native anchor points (inside each box): face centre, and feet centre
FACE = {"navier": (210, 92), "sovieshu": (183, 48), "rashta": (205, 78), "heinley": (196, 52)}
FEET = {"navier": (193, 826), "sovieshu": (194, 826), "rashta": (192, 826), "heinley": (193, 826)}
GLOWCOL = {"navier": (90, 140, 255), "sovieshu": (220, 40, 50), "rashta": (255, 150, 200),
           "heinley": (170, 90, 255)}


def cutout(box):
    im = Image.open(SHEET).convert("RGB")
    c = im.crop(box)
    m = c.copy()
    w, h = c.size
    bg = (251, 244, 238)
    seeds = [(x, y) for x in range(0, w, 6) for y in (0, h - 1)] + \
            [(x, y) for y in range(0, h, 6) for x in (0, w - 1)]
    for p in seeds:
        px = m.getpixel(p)
        if px != (255, 0, 255) and sum(abs(a - b) for a, b in zip(px, bg)) < 45:
            ImageDraw.floodfill(m, p, (255, 0, 255), thresh=28)
    a = np.asarray(m)
    mask = ~((a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255))
    M = Image.fromarray((mask * 255).astype("uint8")).filter(ImageFilter.MinFilter(5))
    rgba = Image.new("RGBA", (w + 2 * PAD, h + 2 * PAD), (0, 0, 0, 0))
    c2 = c.copy(); c2.putalpha(M)
    rgba.paste(c2, (PAD, PAD))
    big = rgba.resize((rgba.width * HS, rgba.height * HS), Image.LANCZOS)
    rgb = big.convert("RGB").filter(ImageFilter.UnsharpMask(2, 70, 2))
    al = big.getchannel("A").filter(ImageFilter.GaussianBlur(1.6))
    rgb.putalpha(al)
    glow = al.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(40))
    return rgb, glow


CHAR = {k: cutout(b) for k, b in BOXES.items()}


def place(cv, name, scale, anchor, at, alpha=1.0, sat=1.0, bright=1.0, tint=None,
          glow=0.0, glowcol=None, flip=False):
    """Draw a character so that its native point `anchor` lands on screen point
    `at`, at `scale` screen px per native px.  Only the visible part is resized."""
    if alpha <= 0.01:
        return
    img, gl = CHAR[name]
    ax, ay = anchor[0] + PAD, anchor[1] + PAD
    nw, nh = img.width / HS, img.height / HS
    if flip:
        ax = nw - ax
    x0n = max(0.0, ax + (0 - at[0]) / scale); x1n = min(nw, ax + (W - at[0]) / scale)
    y0n = max(0.0, ay + (0 - at[1]) / scale); y1n = min(nh, ay + (H - at[1]) / scale)
    if x1n <= x0n or y1n <= y0n:
        return
    sx = int(round(at[0] + (x0n - ax) * scale)); sy = int(round(at[1] + (y0n - ay) * scale))
    ow = max(1, int(round((x1n - x0n) * scale))); oh = max(1, int(round((y1n - y0n) * scale)))
    box = (int(x0n * HS), int(y0n * HS), int(math.ceil(x1n * HS)), int(math.ceil(y1n * HS)))
    src = img.transpose(Image.FLIP_LEFT_RIGHT) if flip else img
    crop = src.crop(box).resize((ow, oh), Image.BICUBIC if scale < HS else Image.LANCZOS)
    if glow > 0:
        g = (gl.transpose(Image.FLIP_LEFT_RIGHT) if flip else gl).crop(box).resize((ow, oh), Image.BILINEAR)
        g = g.point(lambda v: int(v * glow * alpha))
        cv.paste(Image.new("RGB", (ow, oh), glowcol or GLOWCOL[name]), (sx, sy), g)
    rgb = crop.convert("RGB")
    if sat != 1.0 or bright != 1.0 or tint is not None:
        a = np.asarray(rgb).astype(np.float32)
        if sat != 1.0:
            l = a.mean(2, keepdims=True)
            a = l + (a - l) * sat
        a *= bright
        if tint is not None:
            a *= np.array(tint, np.float32) / 255.0
        rgb = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    m = crop.getchannel("A")
    if alpha < 0.999:
        m = m.point(lambda v: int(v * alpha))
    cv.paste(rgb, (sx, sy), m)


def full(cv, name, height, cx, feet_y, **kw):
    """Full figure: `height` screen px from top of head box to feet."""
    s = height / 826.0
    place(cv, name, s, FEET[name], (cx, feet_y), **kw)


def face(cv, name, scale, fx, fy, **kw):
    place(cv, name, scale, FACE[name], (fx, fy), **kw)


# ------------------------------------------------------------------ backgrounds
BGW, BGH = int(W * 1.12), int(H * 1.12)


def make_bg(top, bottom, light, light_y=0.42, arches=True, seed=1, bokeh=(255, 220, 150)):
    y = np.linspace(0, 1, BGH)[:, None, None]
    a = np.array(top, np.float32) * (1 - y) + np.array(bottom, np.float32) * y
    a = np.repeat(a, BGW, 1)
    yy, xx = np.mgrid[0:BGH, 0:BGW]
    d = np.sqrt(((xx - BGW / 2) / (BGW * 0.55)) ** 2 + ((yy - BGH * light_y) / (BGH * 0.38)) ** 2)
    a += np.array(light, np.float32) * np.exp(-d ** 2 * 2.2)[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    lay = Image.new("L", (BGW, BGH), 0)
    dr = ImageDraw.Draw(lay)
    if arches:   # palace hall: tall arched windows and columns, very faint
        for i, cx in enumerate([BGW * 0.12, BGW * 0.37, BGW * 0.63, BGW * 0.88]):
            w = 170; top_y = BGH * 0.16
            dr.rounded_rectangle((cx - w / 2, top_y, cx + w / 2, BGH * 0.66), radius=w // 2,
                                 outline=60, width=6)
            dr.rounded_rectangle((cx - w / 2 + 22, top_y + 22, cx + w / 2 - 22, BGH * 0.66 - 10),
                                 radius=w // 2 - 22, fill=22)
            dr.line((cx, top_y + 30, cx, BGH * 0.66), fill=40, width=4)
        for cx in [0, BGW * 0.25, BGW * 0.5, BGW * 0.75, BGW]:
            dr.rectangle((cx - 34, BGH * 0.1, cx + 34, BGH), fill=30)
            dr.rectangle((cx - 50, BGH * 0.1, cx + 50, BGH * 0.12), fill=45)
        dr.rectangle((0, BGH * 0.74, BGW, BGH), fill=18)
        lay = lay.filter(ImageFilter.GaussianBlur(5))
    im = Image.composite(Image.new("RGB", im.size, (255, 235, 200)), im, lay.point(lambda v: v // 2))
    # bokeh (chandelier lights)
    rng = np.random.default_rng(seed)
    bk = Image.new("RGB", im.size, (0, 0, 0))
    bd = ImageDraw.Draw(bk)
    for _ in range(38):
        x, y_ = rng.uniform(0, BGW), rng.uniform(0, BGH * 0.7)
        r = rng.uniform(10, 46); k = rng.uniform(0.15, 0.5)
        bd.ellipse((x - r, y_ - r, x + r, y_ + r), fill=tuple(int(c * k) for c in bokeh))
    bk = bk.filter(ImageFilter.GaussianBlur(7))
    im = ImageChops.add(im, bk)
    return im


BG = {
    "navy": make_bg((8, 12, 40), (4, 4, 14), (60, 70, 130), seed=1),
    "crimson": make_bg((40, 6, 10), (8, 2, 4), (120, 30, 30), seed=2, bokeh=(255, 160, 110)),
    "rose": make_bg((60, 28, 44), (14, 6, 12), (150, 80, 110), seed=3, bokeh=(255, 190, 220)),
    "violet": make_bg((30, 12, 52), (8, 4, 16), (110, 60, 160), seed=4, bokeh=(230, 190, 255)),
    "cold": make_bg((10, 18, 28), (2, 4, 8), (40, 60, 80), seed=5, bokeh=(160, 200, 255)),
    "gold": make_bg((44, 28, 8), (10, 6, 2), (190, 140, 60), seed=6, bokeh=(255, 230, 160)),
    "black": make_bg((6, 4, 6), (0, 0, 0), (26, 10, 12), arches=False, seed=7, bokeh=(120, 30, 30)),
}


def bg(name, t, drift=(0.0, -1.0)):
    im = BG[name]
    ox = int((BGW - W) / 2 + math.sin(t * 0.25) * 30 * drift[0])
    oy = int((BGH - H) / 2 + ((t * 9) % 60 - 30) * drift[1])
    return im.crop((ox, oy, ox + W, oy + H))


# ------------------------------------------------------------------ effects
_yy, _xx = np.mgrid[0:H, 0:W]
VIG = (1 - 0.62 * np.clip(((_xx - W / 2) / (W * 0.75)) ** 2 + ((_yy - H * 0.47) / (H * 0.62)) ** 2, 0, 1)
       ).astype(np.float32)[..., None]
del _yy, _xx
_rng = np.random.default_rng(9)
GRAIN = [(_rng.normal(0, 3, (H // 2, W // 2)).astype(np.float32)) for _ in range(6)]


def dust(cv, t, col=(255, 220, 140), n=46, seed=3, speed=1.0, a=1.0, rise=True):
    """Floating gold dust / embers."""
    rng = np.random.default_rng(seed)
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i in range(n):
        x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
        sp = rng.uniform(25, 90) * speed
        ph = rng.uniform(0, 6.28)
        r = rng.uniform(1.5, 5.5)
        y = (y0 - t * sp) % (H + 40) - 20 if rise else (y0 + t * sp) % (H + 40) - 20
        x = x0 + math.sin(t * 0.8 + ph) * 26
        k = (0.5 + 0.5 * math.sin(t * 3 + ph)) * a
        d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(c * k) for c in col))
    lay = lay.filter(ImageFilter.GaussianBlur(1.5))
    return ImageChops.add(cv, lay)


def petals(cv, t, col=(255, 170, 205), n=26, seed=11, a=1.0):
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(cv, "RGBA")
    for i in range(n):
        x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
        sp = rng.uniform(70, 150); ph = rng.uniform(0, 6.28); s = rng.uniform(9, 18)
        y = (y0 + t * sp) % (H + 60) - 30
        x = x0 + math.sin(t * 1.1 + ph) * 60
        rot = t * 2 + ph
        pts = [(x + math.cos(rot + k * math.pi / 2) * s * (1 if k % 2 == 0 else 0.45),
                y + math.sin(rot + k * math.pi / 2) * s * (1 if k % 2 == 0 else 0.45)) for k in range(4)]
        d.polygon(pts, fill=col + (int(200 * a),))


def crack_paths(seed, origin, n_branch=7, length=900):
    rng = np.random.default_rng(seed)
    paths = []
    for b in range(n_branch):
        ang = rng.uniform(0, 2 * math.pi)
        x, y = origin
        pts = [(x, y)]
        L = length * rng.uniform(0.5, 1.0)
        steps = 14
        for s in range(steps):
            ang += rng.normal(0, 0.45)
            seg = L / steps
            x += math.cos(ang) * seg; y += math.sin(ang) * seg
            pts.append((x, y))
            if rng.random() < 0.25:   # side branch
                bx, by, ba = x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.2)
                sub = [(bx, by)]
                for _ in range(5):
                    ba += rng.normal(0, 0.4)
                    bx += math.cos(ba) * seg * 0.7; by += math.sin(ba) * seg * 0.7
                    sub.append((bx, by))
                paths.append((s / steps, sub))
        paths.append((0.0, pts))
    return paths


CRACK_A = crack_paths(5, (W * 0.5, H * 0.40))
CRACK_B = crack_paths(8, (W * 0.62, H * 0.30), n_branch=9, length=1300)


def draw_crack(cv, paths, prog, col=(255, 255, 255), glowcol=(255, 60, 60), width=5):
    if prog <= 0:
        return cv
    lay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(lay)
    for start, pts in paths:
        p = clamp((prog - start) / max(0.05, 1 - start))
        if p <= 0:
            continue
        k = max(2, int(len(pts) * p))
        d.line(pts[:k], fill=255, width=width, joint="curve")
    glow = lay.filter(ImageFilter.GaussianBlur(9))
    cv.paste(Image.new("RGB", (W, H), glowcol), (0, 0), glow.point(lambda v: min(255, v * 2)))
    cv.paste(Image.new("RGB", (W, H), col), (0, 0), lay)
    return cv


def grade(cv, t, sat=1.0, bright=1.0, tint=None, flash=0.0, shake=0.0, vig=True, contrast=1.0):
    a = np.asarray(cv).astype(np.float32)
    if sat != 1.0:
        l = a.mean(2, keepdims=True); a = l + (a - l) * sat
    if contrast != 1.0:
        a = (a - 128) * contrast + 128
    a *= bright
    if tint is not None:
        a *= np.array(tint, np.float32) / 255.0
    if vig:
        a *= VIG
    g = GRAIN[int(t * FPS) % len(GRAIN)]
    a += np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    if flash > 0:
        a = a + (255 - a) * flash
    a = np.clip(a, 0, 255).astype(np.uint8)
    if shake > 0:
        dx = int(math.sin(t * 91) * shake); dy = int(math.cos(t * 73) * shake)
        a = np.roll(a, (dy, dx), (0, 1))
    return Image.fromarray(a)


# ------------------------------------------------------------------ text
def text_layer(text, path, size, col, stroke=0, stroke_col=(0, 0, 0), spacing=0, glow=0,
               glowcol=None, shadow=True):
    """Render a line of text (optional letter spacing) to an RGBA image."""
    f = font(path, size)
    if spacing:
        ws = [f.getlength(ch) for ch in text]
        tw = int(sum(ws) + spacing * (len(text) - 1))
    else:
        tw = int(f.getlength(text))
    pad = 30 + stroke + glow
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (tw + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def put(dd, fill, sw=0, sc=None, off=(0, 0)):
        x = pad + off[0]
        if spacing:
            for ch, w in zip(text, ws):
                dd.text((x, pad + off[1]), ch, font=f, fill=fill, stroke_width=sw, stroke_fill=sc)
                x += w + spacing
        else:
            dd.text((x, pad + off[1]), text, font=f, fill=fill, stroke_width=sw, stroke_fill=sc)

    if glow:
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        put(ImageDraw.Draw(gl), (glowcol or col) + (255,), sw=max(stroke, 3), sc=(glowcol or col) + (255,))
        gl = gl.filter(ImageFilter.GaussianBlur(glow))
        im = Image.alpha_composite(im, gl); im = Image.alpha_composite(im, gl)
        d = ImageDraw.Draw(im)
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        put(ImageDraw.Draw(sh), (0, 0, 0, 170), sw=stroke, sc=(0, 0, 0, 170), off=(0, 6))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
        im = Image.alpha_composite(sh, im)
        d = ImageDraw.Draw(im)
    put(d, col + (255,), sw=stroke, sc=stroke_col + (255,) if stroke else None)
    return im


_TL = {}


def tl(*a, **k):
    key = (a, tuple(sorted(k.items())))
    if key not in _TL:
        _TL[key] = text_layer(*a, **k)
    return _TL[key]


def put_text(cv, layer, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0.01:
        return
    im = layer
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    cv.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def name_label(cv, t, name, sub, col, t0, y=215):
    a = ramp(t, t0, t0 + 0.5)
    if a <= 0:
        return
    put_text(cv, tl(name, CINZEL, 92, GOLD, spacing=8, glow=14, glowcol=col), W / 2,
             y - 20 * (1 - eout(a)), a)
    # ornament line
    w = int(340 * eout(ramp(t, t0 + 0.15, t0 + 0.8)))
    if w > 2:
        d = ImageDraw.Draw(cv)
        d.line((W / 2 - w, y + 66, W / 2 - 22, y + 66), fill=GOLD, width=3)
        d.line((W / 2 + 22, y + 66, W / 2 + w, y + 66), fill=GOLD, width=3)
        d.regular_polygon((W / 2, y + 66, 10), 4, fill=GOLD)
    put_text(cv, tl(sub, GARA_I, 52, (245, 235, 220)), W / 2, y + 122, ramp(t, t0 + 0.3, t0 + 0.9))


CAP_Y = 1420


def captions(cv, t):
    for a0, a1 in NO_CAPTION:
        if a0 <= t < a1:
            return
    cur = None
    for i, ch in enumerate(CHUNKS):
        s = ch[0][1]
        e = CHUNKS[i + 1][0][1] if i + 1 < len(CHUNKS) else ch[-1][2] + 1.2
        e = min(e, ch[-1][2] + 0.9)
        if s - 0.05 <= t < e:
            cur = ch
            break
    if not cur:
        return
    f = font(INTER_XB, 70)
    words = [w for w, _, _ in cur]
    space = f.getlength(" ")
    widths = [f.getlength(w) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    pop = back(ramp(t, cur[0][1] - 0.05, cur[0][1] + 0.12))
    lay = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x = (W - total) / 2
    for (w, s, e), ww in zip(cur, widths):
        active = s - 0.04 <= t
        col = GOLD + (255,) if (s - 0.04 <= t < e + 0.08) else ((255, 255, 255, 255) if active else (255, 255, 255, 150))
        d.text((x, 60), w, font=f, fill=col, stroke_width=8, stroke_fill=(10, 6, 8, 255))
        x += ww + space
    sh = lay.filter(ImageFilter.GaussianBlur(8))
    sc = 0.86 + 0.14 * pop
    for im in (sh, lay):
        im2 = im.resize((int(W * sc), int(200 * sc)), Image.BICUBIC)
        cv.paste(im2, (int((W - im2.width) / 2), int(CAP_Y - im2.height / 2)), im2)


# ------------------------------------------------------------------ scenes
# Each scene draws on a fresh canvas and returns (canvas, grade-kwargs).
def sc_hook(t):                                     # 0.00 - 2.45
    cv = bg("navy", t)
    a = ease(ramp(t, 0.15, 1.6))
    full(cv, "navier", 1500 + 120 * t, W / 2, 2010 + 30 * t, alpha=a, glow=0.5,
         bright=0.55 + 0.35 * a, sat=0.8)
    cv = dust(cv, t, a=a * 0.7)
    blink = 1.0 if t < 0.12 else (0.75 + 0.25 * math.sin(t * 22)) if t < 0.5 else 1.0
    put_text(cv, tl("DIA DIKHIANATI", CINZEL, 104, RED, glow=22, glowcol=(255, 0, 0), stroke=2,
                    stroke_col=(60, 0, 0)), W / 2, 250, blink, 1.08 - 0.08 * eout(ramp(t, 0, 0.5)))
    put_text(cv, tl("DI HARI ULANG TAHUNNYA", CINZEL6, 56, (255, 120, 120), spacing=4, glow=10,
                    glowcol=(200, 0, 0)), W / 2, 355, ramp(t, 0.45, 0.9))
    return cv, dict(bright=0.25 + 0.75 * ease(ramp(t, 0, 0.5)), contrast=1.05)


def sc_wanita_lain(t):                              # 2.45 - 6.30   (local t)
    cv = bg("crimson", t)
    k = eout(ramp(t, 0.0, 0.9)); k2 = eout(ramp(t, 1.7, 2.6))
    full(cv, "sovieshu", 1480, W * 0.36 - 300 * (1 - k), 1830, alpha=k, glow=0.55)
    full(cv, "rashta", 1340, W * 0.70 + 380 * (1 - k2), 1840, alpha=k2, glow=0.7)
    cv = dust(cv, t, col=(255, 140, 90), seed=5, a=0.8)
    put_text(cv, tl("DIA DIKHIANATI", CINZEL, 104, RED, glow=22, glowcol=(255, 0, 0), stroke=2,
                    stroke_col=(60, 0, 0)), W / 2, 300, 1 - ramp(t, 0.0, 0.6))
    if t > 2.0:
        put_text(cv, tl("wanita lain?!", GARA_I, 92, (255, 200, 215), glow=16, glowcol=(255, 60, 120)),
                 W * 0.70, 420, ramp(t, 2.3, 2.7), 0.9 + 0.1 * back(ramp(t, 2.3, 2.7)))
    return cv, dict(contrast=1.06)


def sc_sempurna(t):                                 # 6.30 - 13.35
    cv = bg("navy", t)
    z = 1 + 0.06 * t / 7
    full(cv, "navier", 1560 * z, W / 2, 2060 + 40 * t / 7, glow=0.75, glowcol=(255, 210, 120))
    cv = dust(cv, t, n=60, a=1.0)
    name_label(cv, t, "NAVIER", "Permaisuri Kekaisaran Timur", (60, 100, 255), 0.25)
    return cv, dict(contrast=1.04)


def sc_kaisar(t):                                   # 13.35 - 17.95
    cv = bg("crimson", t)
    k = eout(ramp(t, 0.1, 1.2))
    z = 1 + 0.05 * t / 4.6
    full(cv, "sovieshu", 1600 * z, W / 2 + 260 * (1 - k), 2080, alpha=k, glow=0.7)
    if t > 2.6:   # the woman he brings home: a silhouette behind him
        a = ramp(t, 2.8, 3.8)
        full(cv, "rashta", 1200, W * 0.80, 1760, alpha=a * 0.9, bright=0.25, sat=0.4, tint=(255, 160, 180))
    cv = dust(cv, t, col=(255, 120, 80), seed=7, a=0.7)
    name_label(cv, t, "SOVIESHU", "Kaisar Kekaisaran Timur", (255, 30, 30), 1.6)
    return cv, dict(contrast=1.06)


def sc_rashta(t):                                   # 17.95 - 22.30
    cv = bg("rose", t)
    k = eout(ramp(t, 0.0, 0.8))
    z = 1 + 0.05 * t / 4.3
    full(cv, "rashta", 1560 * z, W / 2, 2060 + 120 * (1 - k), alpha=k, glow=0.8)
    cv = dust(cv, t, col=(255, 190, 230), seed=9, n=60)
    petals(cv, t, a=0.8)
    name_label(cv, t, "RASHTA", "Mantan budak, kesayangan istana", (255, 80, 160), 0.3)
    return cv, dict(contrast=1.03)


def sc_senyum(t):                                   # 22.30 - 25.92  close-up, forced smile
    cv = bg("cold", t)
    s = 4.2 + 0.5 * t / 3.6
    face(cv, "navier", s, W / 2, 700, glow=0.5, glowcol=(120, 160, 255), sat=0.75)
    cv = dust(cv, t, col=(170, 200, 255), seed=13, a=0.5)
    if t > 1.6:   # tear glint under her eye
        a = win(t, 1.8, 3.6, 0.3, 0.4)
        ex, ey = W / 2 + (232 - 210) * s - 2, 700 + (100 - 92) * s + 30 * ramp(t, 1.8, 3.6)
        d = ImageDraw.Draw(cv, "RGBA")
        for r, al in ((26, 40), (14, 90), (6, 230)):
            d.ellipse((ex - r, ey - r * 1.3, ex + r, ey + r * 1.3), fill=(220, 240, 255, int(al * a)))
    return cv, dict(sat=0.8, contrast=1.05)


def sc_tertawa(t):                                  # 25.92 - 30.00
    cv = bg("gold", t)
    # the happy couple, warm, in the back
    full(cv, "sovieshu", 1250, W * 0.62, 1620, glow=0.5, glowcol=(255, 200, 120))
    full(cv, "rashta", 1120, W * 0.86, 1640, glow=0.6, glowcol=(255, 170, 200))
    cv = dust(cv, t, col=(255, 220, 150), seed=15, a=0.7)
    # Navier in the cold foreground shadow
    s = 3.0 + 0.2 * t / 4
    face(cv, "navier", s, W * 0.20, 820, sat=0.25, bright=0.55, tint=(170, 190, 255), flip=True)
    return cv, dict(contrast=1.05)


def sc_kalimat(t):                                  # 30.00 - 33.45  music stops
    cv = bg("black", t)
    s = 3.6 + 1.6 * ease(t / 3.45)
    face(cv, "sovieshu", s, W / 2, 760, glow=0.35, bright=0.85 - 0.25 * ramp(t, 1.5, 3.4), sat=0.7)
    return cv, dict(tint=(255, 205, 205), contrast=1.1, bright=1 - 0.35 * ramp(t, 2.8, 3.45))


def sc_cerai(t):                                    # 33.45 - 34.90  "Ayo bercerai."
    cv = bg("black", t)
    face(cv, "sovieshu", 5.4, W / 2, 760, bright=0.32, sat=0.3, tint=(255, 120, 120))
    draw_crack(cv, CRACK_A, eout(ramp(t, 0.38, 0.75)))
    a1 = ramp(t, 0.12, 0.2)
    put_text(cv, tl("“AYO", CINZEL, 170, (255, 255, 255), glow=28, glowcol=(255, 0, 0), stroke=3,
                    stroke_col=(80, 0, 0)), W / 2, 820, a1, 1.25 - 0.25 * eout(ramp(t, 0.12, 0.3)))
    a2 = ramp(t, 0.42, 0.5)
    put_text(cv, tl("BERCERAI.”", CINZEL, 150, RED, glow=30, glowcol=(255, 0, 0), stroke=3,
                    stroke_col=(60, 0, 0)), W / 2, 1010, a2, 1.3 - 0.3 * eout(ramp(t, 0.42, 0.62)))
    shake = 16 * (1 - ramp(t, 0.12, 0.5)) + 22 * (1 - ramp(t, 0.42, 0.95)) * (t > 0.42)
    flash = 0.8 * (1 - ramp(t, 0.42, 0.6)) * (t > 0.42)
    return cv, dict(shake=shake, flash=flash, contrast=1.1)


def sc_hancur(t):                                   # 34.90 - 37.35
    cv = bg("cold", t)
    full(cv, "navier", 1500, W / 2, 1850, sat=0.15, bright=0.6, tint=(180, 200, 255))
    draw_crack(cv, CRACK_B, 0.55 + 0.45 * eout(t / 2.4), col=(220, 230, 255), glowcol=(80, 120, 255), width=4)
    return cv, dict(sat=0.6, contrast=1.08)


def sc_bangkit(t):                                  # 37.35 - 42.00
    p = ease(ramp(t, 0.1, 2.0))
    cv = bg("navy" if p < 0.5 else "gold", t) if False else Image.blend(bg("cold", t), bg("gold", t), p)
    # rays of light behind her
    rays = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(rays)
    for i in range(14):
        ang = i * math.pi / 7 + t * 0.15
        d.polygon([(W / 2, 620), (W / 2 + math.cos(ang - 0.07) * 2400, 620 + math.sin(ang - 0.07) * 2400),
                   (W / 2 + math.cos(ang + 0.07) * 2400, 620 + math.sin(ang + 0.07) * 2400)], fill=int(70 * p))
    cv.paste(Image.new("RGB", (W, H), (255, 220, 150)), (0, 0), rays.filter(ImageFilter.GaussianBlur(12)))
    s = 1500 + 260 * ease(ramp(t, 1.4, 4.6))
    full(cv, "navier", s, W / 2, 1880 + 120 * (1 - ease(ramp(t, 1.4, 4.6))),
         sat=0.2 + 0.8 * p, bright=0.65 + 0.4 * p, glow=0.9 * p, glowcol=(255, 210, 120))
    cv = dust(cv, t, n=80, a=p, speed=1.4)
    if t > 1.6:   # crown sparkle at "mengangkat kepala"
        a = win(t, 1.7, 3.2, 0.15, 0.6)
        cx, cy = W / 2 + (205 - 193) * s / 826, 1880 + 120 * (1 - ease(ramp(t, 1.4, 4.6))) - (826 - 12) * s / 826
        d = ImageDraw.Draw(cv, "RGBA")
        L = 120 * a
        d.polygon([(cx, cy - L), (cx + 10, cy), (cx, cy + L), (cx - 10, cy)], fill=(255, 250, 220, int(255 * a)))
        d.polygon([(cx - L, cy), (cx, cy - 10), (cx + L, cy), (cx, cy + 10)], fill=(255, 250, 220, int(255 * a)))
    flash = 0.5 * win(t, 1.6, 2.3, 0.1, 0.6)
    return cv, dict(flash=flash, contrast=1.04)


def sc_plot(t):                                     # 42.00 - 47.45  remarries the western king
    cv = bg("violet", t)
    kh = eout(ramp(t, 1.4, 2.6))
    full(cv, "navier", 1420, W * 0.33, 1960, glow=0.6, glowcol=(255, 210, 120))
    full(cv, "heinley", 1500, W * 0.70 + 420 * (1 - kh), 1990, alpha=kh, glow=0.75)
    cv = dust(cv, t, col=(230, 200, 255), seed=17, n=60)
    if t > 2.8:
        petals(cv, t - 2.8, col=(255, 255, 255), a=0.7 * ramp(t, 2.8, 3.6), seed=21)
    a = ramp(t, 0.1, 0.35)
    put_text(cv, tl("PLOT TWIST", CINZEL, 118, (255, 255, 255), glow=26, glowcol=(190, 90, 255), stroke=2,
                    stroke_col=(60, 10, 90)), W / 2, 300, a * (1 - ramp(t, 1.6, 2.0)),
             1.4 - 0.4 * eout(ramp(t, 0.1, 0.4)))
    if t > 1.7:
        name_label(cv, t, "HEINLEY", "Raja Kerajaan Barat", (170, 80, 255), 2.0)
    return cv, dict(flash=0.6 * (1 - ramp(t, 0.1, 0.4)) * (t > 0.1), contrast=1.04)


def sc_menunggu(t):                                 # 47.45 - 51.35  Heinley close
    cv = bg("violet", t)
    s = 3.6 + 0.5 * t / 3.9
    face(cv, "heinley", s, W / 2 + 40, 700, glow=0.6, glowcol=(255, 210, 160))
    cv = dust(cv, t, col=(255, 225, 180), seed=19, n=70)
    put_text(cv, tl("“Aku sudah lama menunggumu.”", GARA_I, 64, (255, 240, 225), glow=10,
                    glowcol=(160, 80, 255)), W / 2, 300, win(t, 1.6, 3.9, 0.5, 0.4))
    return cv, dict(contrast=1.03)


def sc_gelisah(t):                                  # 51.35 - 55.50
    cv = bg("cold", t)
    s = 3.9 + 0.6 * t / 4.15
    jit = math.sin(t * 7) * 6
    face(cv, "sovieshu", s, W / 2 + jit, 720, sat=0.35, bright=0.8, tint=(190, 210, 255))
    # clock ticks: a thin ring that fills
    d = ImageDraw.Draw(cv, "RGBA")
    d.arc((W / 2 - 90, 190, W / 2 + 90, 370), -90, -90 + 360 * (t / 4.15), fill=(200, 220, 255, 200), width=6)
    d.arc((W / 2 - 90, 190, W / 2 + 90, 370), 0, 360, fill=(200, 220, 255, 60), width=2)
    put_text(cv, tl("GELISAH", CINZEL, 54, (200, 220, 255), spacing=10), W / 2, 280, ramp(t, 1.8, 2.3))
    return cv, dict(sat=0.7, contrast=1.06, shake=2.5 * ramp(t, 1.8, 2.5))


def sc_penopang(t):                                 # 55.50 - 59.85  the woman he threw away
    cv = bg("navy", t)
    a = ease(ramp(t, 0.0, 1.4))
    full(cv, "navier", 2000, W * 0.5, 2300, alpha=0.75 * a, glow=0.9, glowcol=(255, 210, 120))
    cv = dust(cv, t, n=60, a=a)
    full(cv, "sovieshu", 900, W * 0.22, 1880, sat=0.3, bright=0.45, tint=(170, 190, 255), flip=True)
    return cv, dict(contrast=1.05)


def sc_retak(t):                                    # 59.85 - 63.60
    cv = bg("crimson", t)
    full(cv, "sovieshu", 1380, W * 0.36, 1820, sat=0.55, bright=0.7)
    full(cv, "rashta", 1240, W * 0.72, 1830, sat=0.55, bright=0.7)
    prog = eout(ramp(t, 2.45, 3.3))
    draw_crack(cv, CRACK_B, 0.15 * ramp(t, 1.0, 2.4) + 0.85 * prog)
    draw_crack(cv, CRACK_A, prog * 0.9, width=4)
    a = ramp(t, 2.6, 3.0)
    put_text(cv, tl("Penyesalan datang paling akhir", GARA_I, 74, (255, 235, 220), glow=14,
                    glowcol=(255, 40, 40)), W / 2, 300, a)
    shake = 14 * win(t, 2.45, 3.2, 0.02, 0.6)
    return cv, dict(shake=shake, sat=0.85, contrast=1.08, flash=0.4 * win(t, 2.45, 2.8, 0.02, 0.3))


def sc_judul(t):                                    # 63.60 - 66.50
    cv = bg("black", t)
    rev = ramp(t, 1.38, 1.6)         # "Remarried" at 64.98
    if rev > 0:
        cv = Image.blend(cv, bg("gold", t), 0.8 * ease(rev))
        z = 1 + 0.04 * (t - 1.38)
        full(cv, "navier", 1380 * z, W * 0.34, 2090, alpha=ease(rev), glow=0.7, glowcol=(255, 210, 120))
        full(cv, "heinley", 1440 * z, W * 0.70, 2100, alpha=ease(rev), glow=0.6)
        cv = dust(cv, t, n=90, a=rev, speed=1.3)
    put_text(cv, tl("Judulnya…", GARA_I, 96, (255, 240, 220), glow=12, glowcol=(255, 200, 100)),
             W / 2, 820, ramp(t, 0.25, 0.6) * (1 - ramp(t, 1.2, 1.4)))
    if rev > 0:
        sc = 1.5 - 0.5 * eout(ramp(t, 1.38, 1.9))
        put_text(cv, tl("REMARRIED", CINZEL, 132, GOLD, spacing=6, glow=26, glowcol=(255, 160, 40), stroke=2,
                        stroke_col=(90, 50, 0)), W / 2, 330, rev, sc)
        a2 = ramp(t, 2.06, 2.3)
        put_text(cv, tl("EMPRESS", CINZEL, 150, GOLD, spacing=14, glow=26, glowcol=(255, 160, 40), stroke=2,
                        stroke_col=(90, 50, 0)), W / 2, 480, a2, 1.5 - 0.5 * eout(ramp(t, 2.06, 2.5)))
    return cv, dict(flash=0.85 * (1 - ramp(t, 1.38, 1.8)) * (t > 1.38), contrast=1.04)


TEAM = [("navier", "TIM NAVIER"), ("sovieshu", "TIM SOVIESHU"), ("rashta", "TIM RASHTA"),
        ("heinley", "TIM HEINLEY")]


def sc_cta(t):                                      # 66.50 - 74.00
    cv = bg("gold", t)
    cv = Image.blend(cv, bg("violet", t), 0.35)
    put_text(cv, tl("REMARRIED EMPRESS", CINZEL, 78, GOLD, spacing=4, glow=16, glowcol=(255, 160, 40)),
             W / 2, 230, 1.0)
    # 2x2 character cards
    for i, (nm, lab) in enumerate(TEAM):
        a = eout(ramp(t, 0.2 + 0.18 * i, 0.7 + 0.18 * i))
        col, row = i % 2, i // 2
        cx = W * (0.27 if col == 0 else 0.73)
        cy = 600 + row * 490
        cw, ch = 400, 460
        card = Image.new("RGB", (cw, ch), (0, 0, 0))
        g = Image.new("RGB", (cw, ch), tuple(int(c * 0.35) for c in GLOWCOL[nm]))
        card = g
        sub = Image.new("RGB", (W, H), (0, 0, 0))
        place(sub, nm, 2.3, FACE[nm], (cx, cy - 100), glow=0.6)
        tile = sub.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
        tile = ImageChops.add(card, tile)
        hl = 1.0
        if t > 3.7:   # "Kamu tim siapa?" - cards pulse one after another
            k = (t - 3.7) * 2.4
            hl = 1.0 + 0.06 * max(0.0, math.cos((k - i) * math.pi / 2)) ** 8
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), 26, fill=int(255 * a))
        sc = (0.8 + 0.2 * a) * hl
        tile2 = tile.resize((int(cw * sc), int(ch * sc)), Image.BICUBIC)
        m2 = m.resize(tile2.size, Image.BICUBIC)
        x0, y0 = int(cx - tile2.width / 2), int(cy - tile2.height / 2)
        cv.paste(tile2, (x0, y0), m2)
        ImageDraw.Draw(cv).rounded_rectangle((x0, y0, x0 + tile2.width, y0 + tile2.height), 26,
                                             outline=GOLD if a > 0.5 else None, width=4)
        put_text(cv, tl(lab, CINZEL, 44, (255, 255, 255), glow=8, glowcol=(0, 0, 0)), cx,
                 y0 + tile2.height - 46, a)
    if t > 3.6:
        a = ramp(t, 3.7, 4.0)
        put_text(cv, tl("KAMU TIM SIAPA?", INTER_B, 96, (255, 255, 255), stroke=8, stroke_col=(20, 8, 10),
                        glow=14, glowcol=(255, 150, 40)), W / 2, 1420, a, 0.85 + 0.15 * back(ramp(t, 3.7, 4.0)))
    if t > 4.8:
        a = ramp(t, 4.84, 5.1)
        bob = math.sin(t * 6) * 8
        put_text(cv, tl("Tulis di komen  ↓", INTER_XB, 64, GOLD, stroke=6, stroke_col=(20, 8, 10)),
                 W / 2, 1550 + bob, a)
    return cv, dict(contrast=1.03, bright=1 - 0.9 * ramp(t, 7.0, 7.5))


SCENES = [   # (start, end, function, music-cut whoosh)
    (0.00, 2.45, sc_hook), (2.45, 6.30, sc_wanita_lain), (6.30, 13.35, sc_sempurna),
    (13.35, 17.95, sc_kaisar), (17.95, 22.30, sc_rashta), (22.30, 25.92, sc_senyum),
    (25.92, 30.00, sc_tertawa), (30.00, 33.45, sc_kalimat), (33.45, 34.90, sc_cerai),
    (34.90, 37.35, sc_hancur), (37.35, 42.00, sc_bangkit), (42.00, 47.45, sc_plot),
    (47.45, 51.35, sc_menunggu), (51.35, 55.50, sc_gelisah), (55.50, 59.85, sc_penopang),
    (59.85, 63.60, sc_retak), (63.60, 66.50, sc_judul), (66.50, DUR, sc_cta),
]
XF = 0.22   # crossfade length


def scene_at(t):
    for i, (a, b, fn) in enumerate(SCENES):
        if a <= t < b:
            return i
    return len(SCENES) - 1


def render_scene(i, t):
    a, b, fn = SCENES[i]
    cv, g = fn(t - a)
    return grade(cv, t, **g)


def frame(t):
    i = scene_at(t)
    im = render_scene(i, t)
    a, b, _ = SCENES[i]
    hard = {8, 9, 16}   # hard cuts into "Ayo bercerai", out of it, and into the title
    if i > 0 and t - a < XF and i not in hard:
        prev = render_scene(i - 1, t)
        im = Image.blend(prev, im, ease((t - a) / XF))
    captions(im, t)
    return im


# ------------------------------------------------------------------ audio
def load_voice():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", NARASI, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def note(n):          # MIDI -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


def lowpass(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (1 / (1 + (lo / np.maximum(f, 1)) ** 4)) * (1 / (1 + (f / hi) ** 4))
    return np.fft.irfft(X, len(x))


def conv(x, ir):
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]


def reverb(x, secs=2.6, wet=0.35, seed=1):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    ir = lowpass(ir, 5000)
    ir /= np.sqrt((ir ** 2).sum())
    return x * (1 - wet) + conv(x, ir) * wet * 1.2


def add(buf, sig, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    sig = sig[:len(buf) - i]
    buf[i:i + len(sig)] += sig


def env(n, a, r):
    e = np.ones(n)
    ai, ri = min(n, int(a * SR)), min(n, int(r * SR))
    e[:ai] = np.linspace(0, 1, ai) if ai else 1
    if ri:
        e[-ri:] *= np.linspace(1, 0, ri)
    return e


def pad_chord(notes, dur, vol=0.1, bright=6, trem=0.0, seed=0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for m in notes:
        for det in (-0.12, 0.0, 0.11):
            f = note(m + det * 0.1) * (1 + det * 0.004)
            ph = rng.uniform(0, 6.28)
            for k in range(1, bright + 1):
                if f * k > 9000:
                    break
                out += np.sin(2 * np.pi * f * k * tt + ph * k) / k ** 1.4
    out *= vol / (len(notes) * 3)
    if trem:
        out *= 0.75 + 0.25 * np.sin(2 * np.pi * trem * tt)
    return out * env(n, min(1.2, dur * 0.3), min(1.2, dur * 0.4))


def pluck(m, dur=1.6, vol=0.12):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = note(m)
    s = sum(np.sin(2 * np.pi * f * k * tt) / k ** 2 for k in range(1, 6))
    return vol * s * np.exp(-tt * 3.2) * env(n, 0.004, 0.2)


def boom(vol=0.9, f0=90, f1=34, dur=2.2, seed=2):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-tt * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-tt * 1.8)
    rng = np.random.default_rng(seed)
    nz = lowpass(rng.normal(0, 1, n), 900) * np.exp(-tt * 9) * 0.6
    return vol * (s + nz)


def timpani(vol=0.5, m=38):
    n = int(1.4 * SR); tt = np.arange(n) / SR
    f = note(m) * (1 + 0.08 * np.exp(-tt * 20))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.5)
    s += 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * np.exp(-tt * 6)
    return vol * s


def heartbeat(vol=0.5):
    n = int(0.5 * SR); tt = np.arange(n) / SR
    return vol * np.sin(2 * np.pi * 52 * tt) * np.exp(-tt * 14)


def whoosh(dur=0.6, vol=0.22, seed=4, rev=False):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    x = bandpass(rng.normal(0, 1, n), 300, 4000)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    if rev:
        e = np.linspace(0, 1, n) ** 3
    return vol * x * e / (np.abs(x).max() + 1e-9)


def glass(vol=0.5, seed=6):
    rng = np.random.default_rng(seed)
    n = int(1.6 * SR); tt = np.arange(n) / SR
    out = np.zeros(n)
    for _ in range(26):   # many small tinkles
        at = rng.uniform(0, 0.5) ** 2
        f = rng.uniform(2500, 7000)
        i = int(at * SR)
        m = n - i
        tl_ = tt[:m]
        out[i:] += np.sin(2 * np.pi * f * tl_) * np.exp(-tl_ * rng.uniform(12, 30)) * rng.uniform(0.2, 0.6)
    crack = bandpass(rng.normal(0, 1, n), 800, 9000) * np.exp(-tt * 18)
    return vol * (out * 0.5 + crack)


def riser(dur, vol=0.25, seed=8):
    n = int(dur * SR); tt = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    nz = bandpass(rng.normal(0, 1, n), 1500, 9000) * (tt / dur) ** 2
    f = 200 + 900 * (tt / dur) ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / dur) ** 2
    return vol * (0.5 * nz / (np.abs(nz).max() + 1e-9) + 0.4 * tone)


def shimmer(dur=3.0, vol=0.12):
    out = np.zeros(int(dur * SR))
    for i, m in enumerate([77, 81, 84, 89, 93, 96]):
        add(out, pluck(m, 2.2, vol), i * 0.07)
    return out


def tick(vol=0.12):
    n = int(0.05 * SR); tt = np.arange(n) / SR
    return vol * np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 160)


def music():
    total = int((DUR + 1) * SR)
    m = np.zeros(total)
    # A  0 - 30: dark D minor, Dm Bb Gm A
    prog = [[38, 50, 53, 57], [34, 50, 53, 58], [31, 50, 55, 58], [33, 49, 52, 57]]
    t = 0.0
    i = 0
    while t < 30.0:
        d = min(3.75, 30.4 - t)
        v = 0.11 + 0.05 * ramp(t, 20, 29)
        add(m, pad_chord(prog[i % 4], d + 0.6, v, seed=i), t)
        t += 3.75; i += 1
    for b in np.arange(22.0, 30.0, 0.95):   # heartbeat builds tension
        add(m, heartbeat(0.25 + 0.25 * ramp(b, 22, 29.5)), b)
        add(m, heartbeat(0.18 + 0.2 * ramp(b, 22, 29.5)), b + 0.22)
    for b in (31.3, 32.45):                 # silence, just a heartbeat
        add(m, heartbeat(0.35), b); add(m, heartbeat(0.25), b + 0.22)
    # "Ayo bercerai"
    add(m, whoosh(0.5, 0.25, rev=True), 33.08)
    add(m, boom(0.9), 33.58)
    add(m, boom(0.7, 70, 30, 2.6, seed=3), 33.88)
    add(m, glass(0.35), 33.88)
    # B  34.3 - 42: sharp rise, tremolo strings, timpani
    prog2 = [[38, 50, 53, 57, 62], [34, 50, 53, 58, 65], [41, 53, 57, 60, 65], [36, 52, 55, 60, 67]]
    for k, t0 in enumerate([34.4, 36.3, 38.2, 40.1]):
        add(m, pad_chord(prog2[k], 2.3, 0.13 + 0.03 * k, bright=8, trem=11, seed=10 + k), t0)
        add(m, timpani(0.45, prog2[k][0]), t0)
    for b in np.arange(37.4, 39.0, 0.125):   # timpani roll into "mengangkat kepala"
        add(m, timpani(0.06 + 0.25 * ramp(b, 37.4, 39.0), 38), b)
    add(m, boom(0.55, 110, 45, 1.8), 39.0)
    add(m, shimmer(2.5, 0.08), 39.0)
    # C  42 - 51.4: romance in F major, harp arpeggios
    add(m, whoosh(0.7, 0.3), 41.75)
    add(m, boom(0.45, 120, 50, 1.5), 42.2)
    prog3 = [[41, 53, 57, 60], [45, 52, 57, 60], [46, 53, 58, 62], [48, 52, 55, 60]]
    for k in range(5):
        t0 = 42.2 + k * 1.86
        ch = prog3[k % 4]
        add(m, pad_chord(ch, 2.4, 0.1, bright=4, seed=20 + k), t0)
        arp = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 24, ch[3] + 12, ch[2] + 12]
        for j, nn in enumerate(arp):
            add(m, pluck(nn, 1.4, 0.07), t0 + j * 0.31)
    add(m, shimmer(3, 0.07), 47.6)
    # D  51.4 - 63.6: regret, low and cold, clock ticking
    prog4 = [[26, 38, 50, 53], [31, 43, 50, 55], [33, 45, 49, 52], [26, 38, 50, 53], [34, 46, 50, 53],
             [33, 45, 49, 55]]
    for k in range(6):
        add(m, pad_chord(prog4[k], 2.4, 0.12 + 0.02 * (k > 3), bright=5, seed=30 + k), 51.45 + k * 2.03)
    for b in np.arange(51.6, 59.9, 0.5):
        add(m, tick(0.09 if int((b - 51.6) * 2) % 2 == 0 else 0.06), b)
    for b in np.arange(59.9, 62.3, 0.6):
        add(m, timpani(0.15 + 0.2 * ramp(b, 59.9, 62.3), 38), b)
    add(m, glass(0.6, seed=7), 62.3)
    add(m, boom(0.7, 80, 32, 2.0), 62.36)
    # E  title reveal
    add(m, riser(1.3, 0.3), 63.68)
    add(m, boom(0.9, 100, 38, 2.6), 64.98)
    add(m, shimmer(3, 0.11), 64.98)
    add(m, pad_chord([41, 53, 57, 60, 65, 69], 2.2, 0.16, bright=7, seed=40), 64.98)
    add(m, timpani(0.4, 41), 65.66)
    # F  outro: warm
    prog5 = [[41, 53, 57, 60], [36, 52, 55, 60], [38, 50, 53, 57], [34, 50, 53, 58]]
    for k in range(4):
        add(m, pad_chord(prog5[k], 2.4, 0.11, bright=5, seed=50 + k), 66.6 + k * 1.9)
    for k, t0 in enumerate([70.2, 70.5, 70.8, 71.1]):   # card pulses
        add(m, pluck(72 + [0, 4, 7, 12][k], 1.2, 0.06), t0)
    # whooshes on scene cuts
    for a, b, fn in SCENES[1:]:
        if a in (33.45, 34.90, 63.60, 42.00):
            continue
        add(m, whoosh(0.55, 0.12, seed=int(a * 10)), a - 0.3)
    m = reverb(m, 2.8, 0.38)
    m *= env(len(m), 0.01, 1.5)
    return m


def mix():
    v = load_voice()
    total = int(DUR * SR)
    voice = np.zeros(total)
    voice[:min(total, len(v))] = v[:total]
    voice = voice / (np.abs(voice).max() + 1e-9) * 0.9
    mus = music()[:total]
    # sidechain ducking from the voice envelope
    e = np.abs(voice)
    k = int(0.12 * SR)
    e = np.convolve(e, np.ones(k) / k, "same")
    e = e / (e.max() + 1e-9)
    duck = 1 - 0.45 * np.clip(e * 3, 0, 1)
    out = voice + mus * duck * 0.75
    out /= max(1.0, np.abs(out).max() / 0.97)
    path = os.path.join(HERE, "_audio.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return path


# ------------------------------------------------------------------ subtitles
def srt():
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    rows = []
    for i, ws in enumerate(LINES):
        rows.append(f"{i + 1}\n{ts(ws[0][1])} --> {ts(ws[-1][2] + 0.25)}\n" + " ".join(w for w, _, _ in ws) + "\n")
    txt = "\n".join(rows)
    for name in ("remarried_empress.srt", "remarried_empress_subtitle.txt"):
        with open(os.path.join(HERE, name), "w") as f:
            f.write(txt)


# ------------------------------------------------------------------ main
def render_rgb(fi):
    return frame(fi / FPS).tobytes()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        for x in sys.argv[2:]:
            frame(float(x)).save(os.path.join(HERE, f"preview_{x}.png"))
        return
    audio = mix()
    srt()
    n = int(DUR * FPS)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
                           "-af", "loudnorm=I=-14:TP=-1.2:LRA=11", "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT],
                          stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render_rgb, range(n), chunksize=4)):
            ff.stdin.write(buf)
            if k % 150 == 0:
                print(f"frame {k}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    os.remove(audio)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
