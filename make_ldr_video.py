#!/usr/bin/env python3
"""Generate the TikTok video "LDR Nggak Mati Karena Jarak" (9:16, ~52s).

Renders animated vector frames with pycairo, synthesizes SFX/music with numpy,
and muxes everything with ffmpeg.  Usage:  python3 make_ldr_video.py
"""
import math, subprocess, wave, os, sys
import numpy as np
import cairo

W, H, FPS = 1080, 1920, 30
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(OUT_DIR, "ldr_tiktok.mp4")
FONT = "Inter"

# ---------------------------------------------------------------- palette
NIGHT = (0.06, 0.07, 0.13)
NIGHT2 = (0.10, 0.11, 0.20)
BLUE = (0.20, 0.62, 1.0)
PINK = (1.0, 0.42, 0.58)
YEL = (1.0, 0.83, 0.30)
WHITE = (1, 1, 1)
SKIN = (0.96, 0.78, 0.64)
SKIN2 = (0.86, 0.66, 0.50)
HAIR_D = (0.13, 0.09, 0.08)
HAIR_R = (0.20, 0.14, 0.10)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def back(t):
    t = clamp(t)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


# ---------------------------------------------------------------- drawing helpers
def rrect(c, x, y, w, h, r):
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
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w_ in words:
            test = (cur + " " + w_).strip()
            if c.text_extents(test).x_advance > maxw and cur:
                lines.append(cur)
                cur = w_
            else:
                cur = test
        lines.append(cur)
    return lines


def text_c(c, text, cx, y, size, col=WHITE, a=1.0, bold=True, maxw=900,
           stroke=0, stroke_col=(0, 0, 0), lh=1.22):
    """Centered, wrapped text. y = baseline of first line. Returns bottom y."""
    font(c, size, bold)
    lines = wrap(c, text, maxw)
    for i, ln in enumerate(lines):
        ext = c.text_extents(ln)
        x = cx - ext.x_advance / 2
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


def text_l(c, text, x, y, size, col=WHITE, a=1.0, bold=False, maxw=700, lh=1.25):
    font(c, size, bold)
    lines = wrap(c, text, maxw)
    for i, ln in enumerate(lines):
        c.move_to(x, y + i * size * lh)
        rgb(c, col, a)
        c.show_text(ln)
    return lines


def bg_grad(c, top, bot):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *top)
    g.add_color_stop_rgb(1, *bot)
    c.set_source(g)
    c.paint()


def glow(c, x, y, r, col, a):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, col[0], col[1], col[2], a)
    g.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
    c.set_source(g)
    c.arc(x, y, r, 0, 2 * math.pi)
    c.fill()


def subtitle(c, text, a=1.0, y=1560, who=None, who_col=PINK):
    """Big TikTok-style caption box."""
    if a <= 0:
        return
    font(c, 58, True)
    lines = wrap(c, text, 900)
    lh = 58 * 1.25
    bh = len(lines) * lh + 50 + (56 if who else 0)
    top = y - bh / 2
    rrect(c, 60, top, W - 120, bh, 34)
    rgb(c, (0, 0, 0), 0.62 * a)
    c.fill()
    yy = top + 25
    if who:
        font(c, 38, True)
        ext = c.text_extents(who)
        rgb(c, who_col, a)
        c.move_to(W / 2 - ext.x_advance / 2, yy + 38)
        c.show_text(who)
        yy += 56
    font(c, 58, True)
    for i, ln in enumerate(lines):
        ext = c.text_extents(ln)
        c.move_to(W / 2 - ext.x_advance / 2, yy + 52 + i * lh)
        rgb(c, WHITE, a)
        c.show_text(ln)


def popup_card(c, text, t, col=YEL, txt=(0.08, 0.08, 0.12), y=900, size=74):
    """Bouncy pop-up text card. t = local time since appear."""
    s = back(t / 0.35)
    if s <= 0:
        return
    font(c, size, True)
    lines = wrap(c, text, 820)
    lh = size * 1.22
    bh = len(lines) * lh + 90
    c.save()
    c.translate(W / 2, y)
    c.rotate(-0.035)
    c.scale(s, s)
    rrect(c, -470, -bh / 2 + 14, 940, bh, 40)
    rgb(c, (0, 0, 0), 0.35)
    c.fill()
    rrect(c, -470, -bh / 2, 940, bh, 40)
    rgb(c, col)
    c.fill()
    for i, ln in enumerate(lines):
        ext = c.text_extents(ln)
        c.move_to(-ext.x_advance / 2, -bh / 2 + 45 + size * 0.85 + i * lh)
        rgb(c, txt)
        c.show_text(ln)
    c.restore()


def check_marks(c, x, y, col, s=1.0):
    c.save()
    c.translate(x, y)
    c.scale(s, s)
    c.set_line_width(4)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    rgb(c, col)
    for dx in (0, 12):
        c.move_to(dx + 0, 0)
        c.line_to(dx + 7, 8)
        c.line_to(dx + 20, -9)
    c.stroke()
    c.restore()


# ---------------------------------------------------------------- characters
def face(c, cx, cy, r, who, mood="neutral", t=0.0, look=(0, 0), brow=0.0,
         blink=True, tears=0.0, glow_col=None):
    """Flat cartoon head. who: 'dina' | 'raka'. mood: neutral/worried/sad/smile/laugh/sleep."""
    c.save()
    # hair back
    if who == "dina":
        rgb(c, HAIR_D)
        c.move_to(cx - r * 1.08, cy - r * 0.1)
        c.curve_to(cx - r * 1.25, cy + r * 1.3, cx - r * 0.9, cy + r * 1.7, cx - r * 0.5, cy + r * 1.75)
        c.line_to(cx + r * 0.5, cy + r * 1.75)
        c.curve_to(cx + r * 0.9, cy + r * 1.7, cx + r * 1.25, cy + r * 1.3, cx + r * 1.08, cy - r * 0.1)
        c.close_path()
        c.fill()
    # neck + shoulders
    rgb(c, SKIN2)
    c.rectangle(cx - r * 0.28, cy + r * 0.7, r * 0.56, r * 0.6)
    c.fill()
    shirt = PINK if who == "dina" else (0.25, 0.45, 0.75)
    rgb(c, shirt)
    c.move_to(cx - r * 1.5, cy + r * 2.4)
    c.curve_to(cx - r * 1.5, cy + r * 1.35, cx - r * 0.8, cy + r * 1.15, cx, cy + r * 1.15)
    c.curve_to(cx + r * 0.8, cy + r * 1.15, cx + r * 1.5, cy + r * 1.35, cx + r * 1.5, cy + r * 2.4)
    c.close_path()
    c.fill()
    # head
    rgb(c, SKIN)
    c.save()
    c.translate(cx, cy)
    c.scale(1, 1.1)
    c.arc(0, 0, r, 0, 2 * math.pi)
    c.restore()
    c.fill()
    # ears
    for sx in (-1, 1):
        c.arc(cx + sx * r * 0.98, cy + r * 0.05, r * 0.16, 0, 2 * math.pi)
        c.fill()
    # hair front
    hc = HAIR_D if who == "dina" else HAIR_R
    rgb(c, hc)
    c.save()
    c.translate(cx, cy)
    c.scale(1, 1.12)
    side = 0.25 if who == "dina" else -0.05
    c.move_to(-r * 1.08, r * side)
    c.arc(0, 0, r * 1.09, math.pi + (0.0 if who == "dina" else 0.05), 2 * math.pi - (0.0 if who == "dina" else 0.05))
    c.line_to(r * 1.08, r * side)
    if who == "dina":
        c.curve_to(r * 0.9, -r * 0.45, r * 0.2, -r * 0.5, -r * 0.1, -r * 0.7)
        c.curve_to(-r * 0.4, -r * 0.35, -r * 0.9, -r * 0.3, -r * 1.08, r * side)
    else:
        c.curve_to(r * 0.85, -r * 0.5, r * 0.3, -r * 0.5, -r * 0.2, -r * 0.58)
        c.curve_to(-r * 0.6, -r * 0.45, -r * 0.9, -r * 0.45, -r * 1.04, r * side)
    c.close_path()
    c.fill()
    c.restore()
    # cheeks
    if mood in ("smile", "laugh"):
        for sx in (-1, 1):
            rgb(c, (1, 0.5, 0.5), 0.35)
            c.arc(cx + sx * r * 0.55, cy + r * 0.38, r * 0.16, 0, 2 * math.pi)
            c.fill()
    ex, ey = cx + look[0] * r * 0.08, cy + r * 0.08 + look[1] * r * 0.06
    eye_dx = r * 0.38
    # blinking
    bl = 1.0
    if blink and mood not in ("sleep", "laugh"):
        ph = (t * 0.37 + (0.3 if who == "raka" else 0)) % 1.0
        if ph < 0.05:
            bl = 0.12
    # eyes
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for sx in (-1, 1):
        x = ex + sx * eye_dx
        if mood == "sleep":
            rgb(c, (0.15, 0.1, 0.1))
            c.set_line_width(r * 0.06)
            c.arc(x, ey, r * 0.12, 0.15 * math.pi, 0.85 * math.pi)
            c.stroke()
        elif mood == "laugh":
            rgb(c, (0.15, 0.1, 0.1))
            c.set_line_width(r * 0.07)
            c.arc(x, ey + r * 0.06, r * 0.13, 1.15 * math.pi, 1.85 * math.pi)
            c.stroke()
        else:
            rgb(c, (0.12, 0.08, 0.08))
            c.save()
            c.translate(x, ey)
            c.scale(1, bl)
            c.arc(0, 0, r * 0.11, 0, 2 * math.pi)
            c.restore()
            c.fill()
            if bl > 0.5:
                rgb(c, WHITE)
                c.arc(x + r * 0.035, ey - r * 0.04, r * 0.035, 0, 2 * math.pi)
                c.fill()
            if glow_col:
                rgb(c, glow_col, 0.5)
                c.arc(x - r * 0.03, ey + r * 0.03, r * 0.025, 0, 2 * math.pi)
                c.fill()
    # brows
    rgb(c, HAIR_D if who == "dina" else HAIR_R)
    c.set_line_width(r * 0.07)
    for sx in (-1, 1):
        x = ex + sx * eye_dx
        by = ey - r * 0.32 - brow * r * 0.18
        if mood in ("worried", "sad"):
            c.move_to(x - sx * r * 0.18, by - r * 0.07)  # inner up
            c.line_to(x + sx * r * 0.16, by + r * 0.04)
        else:
            c.move_to(x - r * 0.17, by + r * 0.02)
            c.curve_to(x - r * 0.05, by - r * 0.05, x + r * 0.05, by - r * 0.05, x + r * 0.17, by + r * 0.02)
        c.stroke()
    # mouth
    my = cy + r * 0.55
    rgb(c, (0.45, 0.15, 0.15))
    c.set_line_width(r * 0.06)
    if mood == "smile":
        c.arc(cx, my - r * 0.18, r * 0.25, 0.2 * math.pi, 0.8 * math.pi)
        c.stroke()
    elif mood == "laugh":
        c.move_to(cx - r * 0.3, my - r * 0.08)
        c.curve_to(cx - r * 0.25, my + r * 0.3, cx + r * 0.25, my + r * 0.3, cx + r * 0.3, my - r * 0.08)
        c.close_path()
        c.fill()
    elif mood in ("worried", "sad"):
        c.arc(cx, my + r * 0.2, r * 0.2, 1.2 * math.pi, 1.8 * math.pi)
        c.stroke()
    elif mood == "sleep":
        c.arc(cx + r * 0.05, my, r * 0.08, 0, 2 * math.pi)
        c.stroke()
    else:
        c.move_to(cx - r * 0.15, my)
        c.line_to(cx + r * 0.15, my)
        c.stroke()
    # tears
    if tears > 0:
        for sx in (-1, 1):
            x = ex + sx * eye_dx
            ty = ey + r * 0.15 + tears * r * 0.35
            rgb(c, (0.55, 0.8, 1.0), 0.85)
            c.move_to(x, ty - r * 0.12)
            c.curve_to(x + r * 0.07, ty, x + r * 0.06, ty + r * 0.07, x, ty + r * 0.07)
            c.curve_to(x - r * 0.06, ty + r * 0.07, x - r * 0.07, ty, x, ty - r * 0.12)
            c.fill()
    c.restore()


# ---------------------------------------------------------------- phone UI
def phone_chat(c, x, y, w, h, msgs, t, header="Raka", status="last seen today at 21.14",
               draft="", typing_cursor=True, scale=1.0, dark_glow=True):
    """Phone with a chat. msgs: list of (side, text, appear_time, checks_color)."""
    c.save()
    c.translate(x, y)
    c.scale(scale, scale)
    if dark_glow:
        glow(c, w / 2, h / 2, w * 1.0, BLUE, 0.18)
    # body
    rrect(c, -18, -18, w + 36, h + 36, 70)
    rgb(c, (0.03, 0.03, 0.05))
    c.fill()
    rrect(c, 0, 0, w, h, 56)
    rgb(c, (0.07, 0.09, 0.12))
    c.fill()
    c.save()
    rrect(c, 0, 0, w, h, 56)
    c.clip()
    # wallpaper pattern
    rgb(c, (1, 1, 1), 0.025)
    for i in range(0, int(w), 60):
        for j in range(0, int(h), 60):
            c.arc(i + 30, j + 30, 3, 0, 2 * math.pi)
            c.fill()
    # header
    rgb(c, (0.11, 0.14, 0.18))
    c.rectangle(0, 0, w, 190)
    c.fill()
    # notch
    rrect(c, w / 2 - 90, 16, 180, 40, 20)
    rgb(c, (0, 0, 0))
    c.fill()
    # avatar
    rgb(c, (0.25, 0.45, 0.75))
    c.arc(80, 125, 40, 0, 2 * math.pi)
    c.fill()
    text_c(c, header[0], 80, 140, 40, WHITE)
    text_l(c, header, 140, 120, 38, WHITE, bold=True)
    text_l(c, status, 140, 162, 26, (0.65, 0.7, 0.75))
    # messages
    yy = 250
    for side, txt, at, ck in msgs:
        if t < at:
            continue
        k = back((t - at) / 0.3)
        font(c, 36, False)
        lines = wrap(c, txt, w * 0.62)
        bw = max(c.text_extents(l).x_advance for l in lines) + 60
        bw = max(bw, 200)
        bh = len(lines) * 46 + 64
        bx = w - bw - 30 if side == "me" else 30
        c.save()
        c.translate(bx + (bw if side == "me" else 0), yy + bh)
        c.scale(k, k)
        c.translate(-(bx + (bw if side == "me" else 0)), -(yy + bh))
        rrect(c, bx, yy, bw, bh, 26)
        rgb(c, (0.0, 0.36, 0.3) if side == "me" else (0.15, 0.18, 0.22))
        c.fill()
        for i, ln in enumerate(lines):
            c.move_to(bx + 28, yy + 50 + i * 46)
            rgb(c, WHITE)
            c.show_text(ln)
        font(c, 22, False)
        rgb(c, (0.75, 0.8, 0.8))
        c.move_to(bx + bw - (120 if side == "me" else 80), yy + bh - 16)
        c.show_text("21.0%d" % (len(txt) % 10) if side == "me" else "21.10")
        if side == "me" and ck:
            check_marks(c, bx + bw - 50, yy + bh - 24, ck, 0.9)
        c.restore()
        yy += bh + 22
    # input bar
    rgb(c, (0.11, 0.14, 0.18))
    c.rectangle(0, h - 140, w, 140)
    c.fill()
    rrect(c, 24, h - 118, w - 150, 84, 42)
    rgb(c, (0.18, 0.21, 0.26))
    c.fill()
    font(c, 34, False)
    shown = draft
    lines = wrap(c, shown, w - 230) if shown else [""]
    last = lines[-1] if shown else ""
    if not shown:
        rgb(c, (0.5, 0.55, 0.6))
        c.move_to(60, h - 64)
        c.show_text("Ketik pesan")
    else:
        rgb(c, WHITE)
        c.move_to(60, h - 64)
        c.show_text(last)
    if typing_cursor and (t * 2) % 1 < 0.5 and shown:
        ext = c.text_extents(last).x_advance
        c.rectangle(62 + ext, h - 96, 3, 42)
        rgb(c, BLUE)
        c.fill()
    rgb(c, (0.0, 0.55, 0.45))
    c.arc(w - 70, h - 76, 42, 0, 2 * math.pi)
    c.fill()
    c.restore()
    c.restore()


# ---------------------------------------------------------------- voice over
# Each line: at = earliest local start (s), gap = min pause after previous line,
# v = voice preset, say = spoken text, sub = on-screen subtitle (None = scene draws
# its own text), who = speaker label (dialogue only), srt = text for the .srt file.
VOICE_SET = "multi" if "--multi" in sys.argv else "native"
VOICE_NAMES = {
    "native": {"D": "id-ID-GadisNeural", "R": "id-ID-ArdiNeural"},
    # conversational multilingual voices: speak Indonesian, pronounce English natively
    "multi": {"D": "en-US-EmmaMultilingualNeural", "R": "en-US-BrianMultilingualNeural"},
}[VOICE_SET]
if VOICE_SET == "multi":
    OUT = os.path.join(OUT_DIR, "ldr_tiktok_multilingual.mp4")
VO_DIR = os.path.join(OUT_DIR, "vo")
RAKA_COL = (0.6, 0.75, 1.0)


def P(text, v="D", r=15, p=0, vol=0, pause=0.18, en=None):
    """One spoken phrase with its own direction: rate %, pitch Hz, volume %, pause after (s).
    English words are respelled phonetically for the Indonesian voice
    (checked with Whisper: e.g. 'atetsmen engsaieti' -> 'attachment anxiety')."""
    if VOICE_SET == "multi":
        text = en or text
    return dict(text=text, v=v, r=r, p=p, vol=vol, pause=pause)


# Each line: at = earliest local start (s), gap = min pause after previous line,
# parts = directed phrases, sub = on-screen subtitle (None/absent = scene draws its
# own text), who = speaker label (dialogue only), srt = text for the .srt file.
SPEC = {
    "sc_hook": dict(base=3.0, y=None, lines=[
        dict(at=0.7, srt="Dia nggak selingkuh. Otakmu yang bikin kamu mikir gitu.", parts=[
            P("Dia nggak selingkuh.", r=10, p=-2, pause=0.3),
            P("Otakmu, yang bikin kamu mikir gitu.", r=14, p=1)])]),
    "sc_room": dict(base=4.5, y=1700, lines=[
        dict(at=0.4, sub="\u201cLast seen 21.14. Sekarang 00.30.\u201d", srt="Last seen 21.14. Sekarang 00.30.", parts=[
            P("Les siin, jam sembilan malam.", en="Last seen, jam sembilan malam.", r=4, p=-3, vol=-8, pause=0.45),
            P("Sekarang... setengah satu pagi.", r=0, p=-4, vol=-8)]),
        dict(gap=0.5, sub="\u201cDia ke mana?\u201d", srt="Dia ke mana?", parts=[
            P("Dia ke mana?", r=-8, p=-6, vol=-20)])]),
    "sc_popup1": dict(base=1.8, y=None, lines=[
        dict(at=0.3, srt="Otakmu lagi ngisi kekosongan.", parts=[
            P("Otakmu lagi ngisi kekosongan.", r=10, p=0)])]),
    "sc_brain": dict(base=5.0, y=1660, lines=[
        dict(at=0.3, sub="Otak nggak suka blank. Kalau nggak ada info, dia bikin cerita sendiri.", parts=[
            P("Otak nggak suka blenk.", en="Otak nggak suka blank.", r=12, p=1, pause=0.3),
            P("Kalau nggak ada info, dia bikin cerita sendiri.", r=20, p=1)]),
        dict(gap=0.35, sub="Dan biasanya, ceritanya yang paling buruk.", parts=[
            P("Dan biasanya...", r=2, p=-3, pause=0.25),
            P("ceritanya yang paling buruk.", r=4, p=-5, vol=-5)])]),
    "sc_raka": dict(base=3.5, y=None, lines=[
        dict(at=0.5, srt="Sementara itu, Raka ketiduran. HP-nya mati.", parts=[
            P("Sementara itu, Raka ketiduran.", r=16, p=1, pause=0.15),
            P("Hapenya mati.", r=12, p=-2)])]),
    "sc_typing": dict(base=6.0, y=1660, lines=[
        dict(at=0.3, sub="Ini namanya attachment anxiety.", parts=[
            P("Ini namanya,", r=18, pause=0.05),
            P("atetsmen engsaieti.", en="attachment anxiety.", r=4, p=2)]),
        dict(gap=0.45, sub="Makin sedikit kabar, makin keras alarm di kepala bunyi.", parts=[
            P("Makin sedikit kabar, makin keras alarm di kepala bunyi.", r=22, p=3, vol=5)])]),
    "sc_call": dict(base=9.0, y=1770, lines=[
        dict(at=1.9, who="RAKA", sub="\u201cMaaf, aku ketiduran. Kamu udah makan?\u201d", parts=[
            P("Hmm...", v="R", r=-20, p=-10, vol=-12, pause=0.3),
            P("Maaf...", v="R", r=-12, p=-8, vol=-5, pause=0.35),
            P("aku ketiduran.", v="R", r=-6, p=-8, pause=0.4),
            P("Kamu udah makan?", v="R", r=0, p=-4)]),
        dict(gap=0.55, who="DINA", sub="\u201cAku kira kamu mulai bosan.\u201d", parts=[
            P("Aku kira...", r=-14, p=-5, vol=-15, pause=0.55),
            P("kamu mulai bosan.", r=-18, p=-8, vol=-18)]),
        dict(gap=0.7, who="RAKA", sub="\u201cKita bikin aturan kecil aja ya. Kabar singkat pun cukup, asal ada.\u201d", parts=[
            P("Kita bikin aturan kecil aja ya.", v="R", r=4, p=-4, pause=0.35),
            P("Kabar singkat pun cukup...", v="R", r=0, p=-4, pause=0.2),
            P("asal ada.", v="R", r=-10, p=-6, vol=-5)])]),
    "sc_truth": dict(base=3.0, y=None, lines=[
        dict(at=0.3, srt="Kamu nggak ditinggalkan. Kamu cuma kekurangan kepastian.", parts=[
            P("Kamu nggak ditinggalkan.", r=0, p=-2, pause=0.45),
            P("Kamu cuma kekurangan...", r=6, p=-1, pause=0.15),
            P("kepastian.", r=-4, p=-2)])]),
    "sc_montage": dict(base=5.0, y=1560, lines=[
        dict(at=0.3, sub="Studi bilang: pasangan LDR yang punya ritual kecil rutin justru sering lebih puas dibanding pasangan yang dekat.", parts=[
            P("Studi bilang, pasangan LDR yang punya ritual kecil rutin,", r=17, p=1, pause=0.08),
            P("justru sering lebih puas dibanding yang dekat.", r=20, p=2)]),
        dict(gap=0.35, srt="Bukan sering ngobrol, tapi konsisten.", parts=[
            P("Bukan sering ngobrol,", r=10, pause=0.3),
            P("tapi konsisten.", r=-2, p=3, vol=5)])]),
    "sc_cta": dict(base=4.0, y=1240, tail=1.4, lines=[
        dict(at=0.4, sub="\u201cKamu tipe yang mana, overthinking atau ketiduran?\u201d", parts=[
            P("Kamu tipe yang mana?", r=14, p=4, pause=0.25),
            P("Overthingking...", en="Overthinking...", r=6, p=3, pause=0.15),
            P("atau ketiduran?", r=10, p=5)]),
        dict(gap=0.3, sub="\u201cTag pasanganmu, kasih tahu dia.\u201d",
             srt="Tag pasanganmu, kasih tahu dia. Komen: tim Dina atau tim Raka?", parts=[
            P("Teg pasanganmu,", en="Tag pasanganmu,", r=16, p=3, pause=0.08),
            P("kasih tahu dia!", r=14, p=5)])]),
}


def vo_file(part):
    import hashlib
    key = f"{VOICE_NAMES[part['v']]}|{part['r']}|{part['p']}|{part['vol']}|{part['text']}"
    return os.path.join(VO_DIR, f"{part['v']}_{hashlib.md5(key.encode()).hexdigest()[:10]}.mp3")


def vo_generate(part):
    path = vo_file(part)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(VO_DIR, exist_ok=True)
    cmd = ["edge-tts", "--voice", VOICE_NAMES[part["v"]], f"--rate={part['r']:+d}%",
           f"--pitch={part['p']:+d}Hz", f"--volume={part['vol']:+d}%",
           "--text", part["text"], "--write-media", path]
    if os.environ.get("HTTPS_PROXY"):
        cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]
    for attempt in range(4):
        if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 \
                and os.path.getsize(path) > 0:
            return path
    raise RuntimeError("TTS failed for: " + part["text"])


def load_audio(path, sr=44100):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1",
                          "-ar", str(sr), "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0


def trim_silence(x, thr=0.012, max_pause=0.26, sr=44100):
    """Trim edges and shorten long internal pauses (TikTok pacing)."""
    hop = int(0.01 * sr)
    nfr = len(x) // hop
    rms = np.sqrt(np.mean(x[: nfr * hop].reshape(nfr, hop) ** 2, axis=1))
    loud = rms > thr
    if not loud.any():
        return x
    first, last = np.argmax(loud), nfr - 1 - np.argmax(loud[::-1])
    keep = np.zeros(nfr, bool)
    keep[max(0, first - 2): last + 3] = True
    run = 0
    maxf = int(max_pause / 0.01)
    for i in range(first, last):
        run = run + 1 if not loud[i] else 0
        if run > maxf:
            keep[i] = False
    out = [x[i * hop:(i + 1) * hop] for i in range(nfr) if keep[i]]
    y = np.concatenate(out)
    f = int(0.004 * sr)  # tiny fades to avoid clicks at joins
    y[:f] *= np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)
    return y


def room_verb(x, sr=44100, wet=0.07):
    """Very small room reverb so the voice sits in the scene instead of sounding dry."""
    rng = np.random.default_rng(3)
    n = int(0.25 * sr)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (0.05 * sr))
    ir /= np.sqrt(np.sum(ir ** 2))
    y = np.convolve(x, ir)[: len(x) + n // 2]
    out = np.zeros_like(y)
    out[: len(x)] = x
    return out * (1 - wet) + y * wet


# Per-line acoustic treatment and human sounds before the line.
#   close = intimate close-mic narration, inner = thought / inner-voice echo,
#   phone = heard through the phone, room = normal room.
FX = {
    ("sc_hook", 0): ("close", "in"), ("sc_room", 0): ("close", "in"), ("sc_room", 1): ("close", "in_soft"),
    ("sc_popup1", 0): ("inner", None), ("sc_brain", 0): ("inner", "in"), ("sc_brain", 1): ("inner", "in_soft"),
    ("sc_raka", 0): ("close", "in"), ("sc_typing", 0): ("close", "in"), ("sc_typing", 1): ("inner", "in_fast"),
    ("sc_call", 0): ("phone", "yawn"), ("sc_call", 1): ("close", "sniff"), ("sc_call", 2): ("phone", "in"),
    ("sc_truth", 0): ("close", "in_soft"), ("sc_montage", 0): ("room", "in"), ("sc_montage", 1): ("room", "in"),
    ("sc_cta", 0): ("room", "in"), ("sc_cta", 1): ("room", "in_fast"),
}
_rng_fx = np.random.default_rng(11)


def band(x, lo, hi, sr=44100):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def reverb(x, decay=0.3, wet=0.1, pre=0.0, sr=44100, seed=3):
    rng = np.random.default_rng(seed)
    n = int(decay * 2.5 * sr)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (decay / 3 * sr))
    ir = band(ir, 200, 6000)
    ir /= np.sqrt(np.sum(ir ** 2))
    pad = int(pre * sr)
    y = np.convolve(np.concatenate([np.zeros(pad), x]), ir)
    out = np.zeros(len(x) + n // 2)
    out[: len(x)] += x * (1 - wet)
    k = min(len(out), len(y))
    out[:k] += y[:k] * wet
    return out


def breath(kind, sr=44100):
    """Synthesized human sounds: inhale, soft inhale, sniffle, sleepy yawn-breath."""
    if kind is None:
        return np.zeros(0)
    dur, lo, hi, amp = {"in": (0.34, 500, 2600, 0.05), "in_soft": (0.42, 400, 2000, 0.035),
                        "in_fast": (0.2, 600, 3000, 0.045), "yawn": (0.9, 250, 1500, 0.06),
                        "sniff": (0.14, 1500, 6500, 0.10)}[kind]
    n = int(dur * sr)
    nz = band(_rng_fx.standard_normal(n), lo, hi)
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t ** 0.7) ** 1.5
    if kind == "yawn":  # inhale then a low voiced sigh
        env = np.sin(np.pi * t) ** 1.2
        tt = np.arange(n) / sr
        sigh = np.sin(2 * np.pi * (140 - 40 * t) * tt) * np.exp(-((t - 0.65) / 0.18) ** 2) * 0.25
        nz = nz / (np.max(np.abs(nz)) + 1e-9) + sigh
    y = nz / (np.max(np.abs(nz)) + 1e-9) * env * amp
    if kind == "sniff":  # two quick sniffs
        y = np.concatenate([y, np.zeros(int(0.09 * sr)), y * 0.8, np.zeros(int(0.25 * sr))])
    else:
        y = np.concatenate([y, np.zeros(int(0.06 * sr))])
    return y


def apply_fx(x, kind):
    if kind == "close":
        return reverb(band(x, 70, 11000), decay=0.18, wet=0.05)
    if kind == "inner":
        y = band(x, 120, 8000)
        e = np.zeros(len(y) + int(0.9 * 44100))
        e[: len(y)] += y
        for d, g in ((0.16, 0.28), (0.32, 0.14), (0.48, 0.07)):
            i = int(d * 44100)
            e[i: i + len(y)] += band(y, 300, 4000) * g
        return reverb(e, decay=0.9, wet=0.22, pre=0.02)
    if kind == "phone":
        y = band(x, 320, 3400)
        y = y / (np.max(np.abs(y)) + 1e-9)
        y = np.tanh(y * 2.2) / np.tanh(2.2)
        y = y + band(_rng_fx.standard_normal(len(y)), 400, 3000) * 0.012
        return y * np.max(np.abs(x)) * 0.95
    return reverb(x, decay=0.3, wet=0.08)


def plan_vo():
    """Generate VO phrases, assemble lines and lay them out; returns scene durations."""
    durs = {}
    for name, sp in SPEC.items():
        prev_end = 0.0
        for ln in sp["lines"]:
            chunks = []
            for part in ln["parts"]:
                chunks.append(trim_silence(load_audio(vo_generate(part)), max_pause=0.32))
                gap = np.zeros(int(part["pause"] * 44100))
                if part["pause"] >= 0.3 and part is not ln["parts"][-1]:
                    b = breath("in_soft") * 0.7  # breathe in during longer pauses
                    if len(b) < len(gap):
                        gap[len(gap) - len(b):] += b
                chunks.append(gap)
            chunks.pop()
            idx = sp["lines"].index(ln)
            fx, pre = FX.get((name, idx), ("room", None))
            dry = np.concatenate(chunks)
            ln["audio"] = apply_fx(dry, fx)
            ln["pre"] = breath(pre)
            ln["fx"] = fx
            ln["dur"] = len(dry) / 44100  # echo/reverb tails may ring past the line
            start = max(ln.get("at", 0.0), prev_end + ln.get("gap", 0.25))
            ln["start"], ln["end"] = start, start + ln["dur"]
            ln["say"] = ln.get("srt") or ln.get("sub") or ""
            prev_end = ln["end"]
        durs[name] = max(sp["base"], prev_end + sp.get("tail", 0.35))
    return durs


def L(name, i):
    ln = SPEC[name]["lines"][i]
    return ln["start"], ln["end"]


def draw_sub(c, name, t, d):
    sp = SPEC[name]
    if sp["y"] is None:
        return
    lines = sp["lines"]
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["start"] - 0.05 if i + 1 < len(lines) else d
        if ln.get("sub") and ln["start"] - 0.1 <= t < nxt:
            subtitle(c, ln["sub"], ease((t - ln["start"] + 0.1) / 0.25), y=sp["y"],
                     who=ln.get("who"), who_col=RAKA_COL if ln.get("who") == "RAKA" else PINK)


# ---------------------------------------------------------------- scenes
def sc_hook(c, t, T):
    bg_grad(c, (0.02, 0.02, 0.04), NIGHT)
    zoom = 1.0 + 0.06 * ease(t / 4)
    msgs = [("me", "Kamu udah sampai kos?", -1, BLUE),
            ("me", "Sayang?", -1, BLUE),
            ("me", "Halo??", 0.6, BLUE)]
    pw, ph = 720, 1180
    c.save()
    c.translate(W / 2, 880)
    c.scale(zoom, zoom)
    c.translate(-W / 2, -880)
    phone_chat(c, (W - pw) / 2, 230, pw, ph, msgs, t)
    c.restore()
    # flash of "read" — highlight the blue ticks
    if 1.0 < t < 1.8:
        glow(c, W / 2 + 300, 760, 120, BLUE, 0.4 * math.sin((t - 1) / 0.8 * math.pi))
    # hook text
    s0, e0 = L("sc_hook", 0)
    t2 = s0 + (e0 - s0) * 0.42
    if t > s0:
        a = ease((t - s0) / 0.3)
        text_c(c, "Dia nggak selingkuh.", W / 2, 1640, 76, WHITE, a, stroke=10)
    if t > t2:
        a = ease((t - t2) / 0.3)
        text_c(c, "Otakmu yang bikin kamu mikir gitu.", W / 2, 1745, 58, YEL, a, stroke=9, maxw=980)
    # top label
    text_c(c, "Dibaca. Nggak dibalas.", W / 2, 150, 46, (0.75, 0.8, 0.9), ease(t / 0.4))


def room_bg(c, t, lamp=0.0):
    bg_grad(c, (0.03, 0.03, 0.07), (0.07, 0.07, 0.14))
    # window with moon
    rrect(c, 640, 180, 340, 420, 16)
    rgb(c, (0.09, 0.12, 0.25))
    c.fill()
    glow(c, 860, 300, 130, (0.9, 0.9, 1.0), 0.25)
    rgb(c, (0.92, 0.92, 0.85))
    c.arc(860, 300, 42, 0, 2 * math.pi)
    c.fill()
    rgb(c, (0.09, 0.12, 0.25))
    c.arc(878, 288, 38, 0, 2 * math.pi)
    c.fill()
    for (sx, sy) in [(700, 230), (760, 520), (930, 470), (690, 400)]:
        rgb(c, WHITE, 0.5 + 0.5 * math.sin(t * 3 + sx))
        c.arc(sx, sy, 3, 0, 2 * math.pi)
        c.fill()
    c.set_line_width(12)
    rgb(c, (0.03, 0.03, 0.06))
    c.move_to(810, 180); c.line_to(810, 600)
    c.move_to(640, 390); c.line_to(980, 390)
    c.stroke()
    # bed
    rgb(c, (0.12, 0.12, 0.22))
    rrect(c, -40, 1250, W + 80, 800, 60)
    c.fill()
    rgb(c, (0.16, 0.16, 0.3))
    rrect(c, 40, 1150, 420, 170, 70)
    c.fill()


def clock(c, x, y, txt, a=1.0, size=80):
    rrect(c, x - 190, y - 80, 380, 120, 24)
    rgb(c, (0, 0, 0), 0.55 * a)
    c.fill()
    text_c(c, txt, x, y + 8, size, (1.0, 0.35, 0.35), a)


def sc_room(c, t, T):
    room_bg(c, t)
    # Dina in bed with phone glow
    glow(c, 540, 1060, 420, BLUE, 0.22 + 0.03 * math.sin(t * 5))
    face(c, 540, 930, 150, "dina", "worried", t, look=(0, 1), glow_col=BLUE)
    # blanket
    rgb(c, (0.25, 0.28, 0.5))
    c.move_to(-20, 1260)
    c.curve_to(300, 1180, 780, 1180, W + 20, 1260)
    c.line_to(W + 20, H)
    c.line_to(-20, H)
    c.close_path()
    c.fill()
    # phone in hand
    rrect(c, 470, 1140, 140, 230, 22)
    rgb(c, (0.05, 0.05, 0.08))
    c.fill()
    rrect(c, 480, 1150, 120, 210, 16)
    rgb(c, (0.55, 0.78, 1.0))
    c.fill()
    # scroll lines
    for i in range(5):
        yy = 1165 + ((i * 40 + t * 120) % 190)
        rrect(c, 492, yy, 70 + (i % 2) * 25, 16, 8)
        rgb(c, WHITE, 0.8)
        c.fill()
    # labels
    a1 = ease(t / 0.3)
    rrect(c, 80, 170, 440, 90, 22)
    rgb(c, (0, 0, 0), 0.55 * a1)
    c.fill()
    text_c(c, "last seen 21.14", 300, 230, 44, (0.7, 0.8, 0.9), a1)
    if t > 1.6:
        clock(c, 300, 380, "00.30", ease((t - 1.6) / 0.3))
    q0 = L("sc_room", 1)[0]
    if t > q0:
        a = ease((t - q0) / 0.3)
        for i, q in enumerate("???"):
            text_c(c, q, 720 + i * 70 + 8 * math.sin(t * 6 + i), 760 - i * 30, 110, YEL, a)


def sc_popup1(c, t, T):
    sc_room(c, 6.0 + t, 999)
    c.set_source_rgba(0, 0, 0, 0.45 * ease(t / 0.2))
    c.paint()
    popup_card(c, "Otakmu lagi ngisi kekosongan.", t, YEL, y=880)


def sc_brain(c, t, T):
    bg_grad(c, (0.09, 0.05, 0.16), (0.03, 0.03, 0.08))
    # head silhouette with brain
    cx, cy = 540, 860
    rgb(c, (0.18, 0.12, 0.28))
    c.arc(cx, cy, 300, 0, 2 * math.pi)
    c.fill()
    pulse = 1 + 0.04 * math.sin(t * 8)
    c.save()
    c.translate(cx, cy)
    c.scale(pulse, pulse)
    rgb(c, (1.0, 0.55, 0.7))
    for (bx, by, br) in [(-90, -60, 95), (0, -100, 100), (90, -60, 95), (-110, 40, 85),
                         (0, 10, 105), (110, 40, 85), (-40, 100, 70), (50, 100, 70)]:
        c.arc(bx, by, br, 0, 2 * math.pi)
        c.fill()
    rgb(c, (0.8, 0.3, 0.45))
    c.set_line_width(9)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(0, -190); c.curve_to(-30, -100, 30, -40, 0, 50); c.curve_to(-20, 100, 20, 140, 0, 170)
    c.move_to(-170, -40); c.curve_to(-110, -20, -100, 30, -60, 40)
    c.move_to(170, -40); c.curve_to(110, -20, 100, 30, 60, 40)
    c.stroke()
    c.restore()
    # worst-case stories popping out
    stories = [("Dia bosan sama aku?", 1.0, (-260, -420)),
               ("Ada orang lain?", 2.2, (250, -330)),
               ("Aku salah ngomong?", 3.4, (-240, 360)),
               ("Dia mau putus?!", 4.4, (240, 440))]
    sc = SCENE_DUR["sc_brain"] / 6.0
    for txt, at, (dx, dy) in stories:
        at *= sc
        if t < at:
            continue
        k = back((t - at) / 0.3)
        c.save()
        c.translate(cx + dx, cy + dy)
        c.scale(k, k)
        c.rotate(0.04 * math.sin(at * 7))
        font(c, 44, True)
        tw = c.text_extents(txt).x_advance
        rrect(c, -tw / 2 - 34, -50, tw + 68, 96, 48)
        rgb(c, WHITE)
        c.fill()
        c.arc(-dx * 0.18, -dy * 0.12 + (40 if dy < 0 else -40), 14, 0, 2 * math.pi)
        c.fill()
        rgb(c, (0.85, 0.1, 0.25))
        c.move_to(-tw / 2, 14)
        c.show_text(txt)
        c.restore()


def sc_raka(c, t, T):
    bg_grad(c, (0.10, 0.09, 0.08), (0.05, 0.05, 0.06))
    # desk lamp light
    glow(c, 300, 600, 520, (1.0, 0.85, 0.55), 0.22)
    # lamp
    rgb(c, (0.3, 0.3, 0.32))
    c.set_line_width(14)
    c.move_to(160, 1180); c.line_to(220, 760); c.line_to(330, 560)
    c.stroke()
    c.move_to(260, 520); c.line_to(420, 600); c.line_to(360, 660); c.close_path()
    c.fill()
    # desk
    rgb(c, (0.38, 0.25, 0.16))
    c.rectangle(0, 1180, W, 90)
    c.fill()
    rgb(c, (0.25, 0.16, 0.1))
    c.rectangle(0, 1270, W, H)
    c.fill()
    # laptop
    rgb(c, (0.6, 0.62, 0.66))
    c.move_to(560, 1180); c.line_to(1000, 1180); c.line_to(1040, 1195); c.line_to(520, 1195); c.close_path()
    c.fill()
    rgb(c, (0.25, 0.26, 0.3))
    c.move_to(600, 1180); c.line_to(660, 860); c.line_to(1000, 860); c.line_to(960, 1180); c.close_path()
    c.fill()
    rgb(c, (0.35, 0.6, 0.9), 0.6)
    c.move_to(620, 1165); c.line_to(672, 880); c.line_to(980, 880); c.line_to(940, 1165); c.close_path()
    c.fill()
    for i in range(6):
        rgb(c, WHITE, 0.6)
        c.rectangle(700 + i * 4, 920 + i * 38, 180 - i * 12, 14)
        c.fill()
    # Raka head down on arms
    c.save()
    bob = 6 * math.sin(t * 2.2)
    c.translate(0, bob)
    rgb(c, (0.25, 0.45, 0.75))
    rrect(c, 150, 1080, 440, 130, 65)
    c.fill()
    c.restore()
    c.save()
    c.translate(360, 1010 + bob)
    c.rotate(-0.35)
    face(c, 0, 0, 110, "raka", "sleep", t)
    c.restore()
    # zzz
    for i in range(3):
        ph = (t * 0.6 + i / 3) % 1
        text_c(c, "z", 520 + ph * 140 + i * 10, 880 - ph * 260, 50 + ph * 40, WHITE, 1 - ph)
    # phone on desk with dead battery
    rrect(c, 250, 1200, 200, 50, 12)
    rgb(c, (0.08, 0.08, 0.1))
    c.fill()
    # battery icon above phone
    bx, by = 300, 1380
    rrect(c, bx, by, 170, 80, 14)
    rgb(c, (1, 1, 1))
    c.set_line_width(6)
    c.stroke()
    c.rectangle(bx + 170, by + 24, 12, 32)
    c.fill()
    if (t * 2) % 1 < 0.6:
        rrect(c, bx + 10, by + 10, 18, 60, 6)
        rgb(c, (1, 0.25, 0.25))
        c.fill()
    text_c(c, "0%", bx + 85, by + 140, 46, (1, 0.35, 0.35))
    # unplugged charger
    rgb(c, (0.9, 0.9, 0.9))
    c.set_line_width(8)
    c.move_to(900, 1500); c.curve_to(820, 1420, 720, 1560, 640, 1450)
    c.stroke()
    rrect(c, 620, 1420, 40, 60, 8)
    c.fill()
    text_c(c, "charger belum dicolok", 780, 1580, 34, (0.8, 0.8, 0.8), ease(t / 0.4))
    # caption
    a = ease(t / 0.3)
    rrect(c, 290, 140, 500, 96, 48)
    rgb(c, YEL, a)
    c.fill()
    text_c(c, "Sementara itu…", W / 2, 205, 50, (0.1, 0.1, 0.1), a)
    text_c(c, "Raka: ketiduran, HP mati.", W / 2, 1760, 54, WHITE, ease((t - 0.6) / 0.3), stroke=8)


def sc_typing(c, t, T):
    bg_grad(c, (0.02, 0.02, 0.05), NIGHT2)
    seq = [  # (start, end_type, end_hold, text, delete_after)
        (0.2, 2.2, 2.6, "Kalau kamu udah nggak serius bilang aja, aku capek nungguin kamu terus", True),
        (3.4, 4.4, 9.9, "Kamu baik-baik aja?", False),
    ]
    draft = ""
    sent = False
    for st, te, th, txt, dele in seq:
        if t < st:
            break
        if t < te:
            n = int(len(txt) * (t - st) / (te - st))
            draft = txt[:n]
        elif t < th:
            draft = txt
        elif dele and t < th + 0.6:
            n = int(len(txt) * (1 - (t - th) / 0.6))
            draft = txt[:max(0, n)]
        elif dele:
            draft = ""
        else:
            draft = txt
    msgs = [("me", "Kamu udah sampai kos?", -1, BLUE),
            ("me", "Sayang?", -1, BLUE),
            ("me", "Halo??", -1, BLUE)]
    pw, ph = 640, 1000
    phone_chat(c, (W - pw) / 2, 180, pw, ph, msgs, t, draft=draft, status="last seen today at 21.14")
    # typed text overlay (bigger, readable)
    if draft:
        font(c, 46, False)
        lines = wrap(c, draft, W - 260)
        bh = len(lines) * 58 + 50
        rrect(c, 90, 1390 - bh - 60, W - 180, bh, 28)
        rgb(c, WHITE, 0.95)
        c.fill()
        for i, ln in enumerate(lines):
            c.move_to(130, 1390 - bh - 60 + 62 + i * 58)
            rgb(c, (0.1, 0.1, 0.15))
            c.show_text(ln)
    # anxiety meter
    lvl = clamp(0.25 + t / 6.0 * 0.75)
    mx, my, mw, mh = 120, 1440, W - 240, 44
    text_l(c, "ALARM DI KEPALA", mx, my - 18, 34, (1, 0.6, 0.6), bold=True)
    rrect(c, mx, my, mw, mh, 22)
    rgb(c, (1, 1, 1), 0.15)
    c.fill()
    g = cairo.LinearGradient(mx, 0, mx + mw, 0)
    g.add_color_stop_rgb(0, 1.0, 0.85, 0.3)
    g.add_color_stop_rgb(1, 1.0, 0.2, 0.25)
    rrect(c, mx, my, max(44, mw * lvl), mh, 22)
    c.set_source(g)
    c.fill()
    if lvl > 0.85 and (t * 4) % 1 < 0.5:
        glow(c, W / 2, H / 2, 1100, (1, 0.1, 0.1), 0.18)
    # deleted stamp
    if 2.6 < t < 3.4:
        text_c(c, "*dihapus*", W / 2, 1300, 54, (1, 0.5, 0.5), 1.0)


def sc_call(c, t, T):
    # incoming call screen -> accepted call with both faces
    ring_end = 1.7
    if t < ring_end:
        bg_grad(c, (0.08, 0.15, 0.28), (0.02, 0.04, 0.1))
        for i in range(3):
            ph = (t * 1.2 + i / 3) % 1
            c.set_line_width(4)
            rgb(c, WHITE, 0.4 * (1 - ph))
            c.arc(W / 2, 640, 170 + ph * 260, 0, 2 * math.pi)
            c.stroke()
        shake = 6 * math.sin(t * 60) if (t % 0.8) < 0.4 else 0
        face(c, W / 2 + shake, 600, 140, "raka", "neutral", t)
        text_c(c, "Raka", W / 2, 1000, 90, WHITE)
        text_c(c, "Panggilan suara masuk…", W / 2, 1070, 42, (0.75, 0.8, 0.9), bold=False)
        # buttons
        for bx, col in ((300, (0.95, 0.25, 0.3)), (780, (0.2, 0.8, 0.4))):
            rgb(c, col)
            c.arc(bx, 1450, 80, 0, 2 * math.pi)
            c.fill()
        # pulse on accept
        if t > 1.3:
            c.set_line_width(6)
            rgb(c, WHITE, 1 - (t - 1.3) / 0.7)
            c.arc(780, 1450, 80 + (t - 1.3) * 120, 0, 2 * math.pi)
            c.stroke()
        text_c(c, "Dina diam sebentar…", W / 2, 1750, 48, YEL, ease((t - 0.4) / 0.3), stroke=8)
        return
    lt = t - ring_end
    bg_grad(c, (0.07, 0.08, 0.16), (0.03, 0.03, 0.06))
    # split screen
    rgb(c, (0.12, 0.14, 0.24))
    c.rectangle(0, 0, W, 820)
    c.fill()
    rgb(c, (0.18, 0.12, 0.22))
    c.rectangle(0, 830, W, 820)
    c.fill()
    text_l(c, "RAKA", 50, 90, 40, (0.6, 0.75, 1.0), bold=True)
    text_l(c, "DINA", 50, 920, 40, PINK, bold=True)
    # timer
    text_c(c, "00:%02d" % int(lt), W / 2, 90, 40, (0.7, 0.75, 0.8), bold=False)
    (r1s, r1e), (d1s, d1e), (r2s, r2e) = L("sc_call", 0), L("sc_call", 1), L("sc_call", 2)
    raka_talk = r1s <= t < r1e or r2s <= t < r2e
    dina_talk = d1s <= t < d1e
    dina_smile = r2s + (r2e - r2s) * 0.6
    tears = clamp((t - d1s) / 1.2) if d1s < t < dina_smile else 0
    face(c, W / 2, 420, 150, "raka", "smile" if t > r2s else "worried", t,
         brow=0.3 if t < r1e else 0)
    face(c, W / 2, 1230, 150, "dina", "smile" if t > dina_smile else "sad", t, look=(0, 0.6),
         tears=tears)
    # sound bars
    for i in range(5):
        if raka_talk:
            hh = 20 + 40 * abs(math.sin(t * 11 + i * 1.3))
            rgb(c, (0.6, 0.75, 1.0))
            rrect(c, 900 + i * 22, 760 - hh, 12, hh, 6)
            c.fill()
        if dina_talk:
            hh = 20 + 30 * abs(math.sin(t * 9 + i * 1.7))
            rgb(c, PINK)
            rrect(c, 900 + i * 22, 1580 - hh, 12, hh, 6)
            c.fill()


def sc_truth(c, t, T):
    bg_grad(c, (0.98, 0.93, 0.86), (0.98, 0.84, 0.80))
    # soft hearts
    for i in range(9):
        x = (i * 137) % W
        y = H - ((t * 120 + i * 260) % (H + 200))
        rgb(c, PINK, 0.18)
        heart(c, x, y, 40 + (i % 3) * 14)
    a1 = ease(t / 0.35)
    text_c(c, "Kamu nggak ditinggalkan.", W / 2, 820, 82, (0.15, 0.12, 0.2), a1, maxw=950)
    ts0, te0 = L("sc_truth", 0)
    t2 = ts0 + (te0 - ts0) * 0.45
    if t > t2:
        a2 = ease((t - t2) / 0.35)
        text_c(c, "Kamu cuma kekurangan", W / 2, 1090, 70, (0.35, 0.3, 0.4), a2, maxw=950)
        s = back((t - t2 - 0.7) / 0.4)
        if s > 0:
            c.save()
            c.translate(W / 2, 1270)
            c.scale(s, s)
            font(c, 120, True)
            tw = c.text_extents("KEPASTIAN.").x_advance
            rrect(c, -tw / 2 - 40, -110, tw + 80, 150, 30)
            rgb(c, PINK)
            c.fill()
            c.move_to(-tw / 2, 0)
            rgb(c, WHITE)
            c.show_text("KEPASTIAN.")
            c.restore()


def heart(c, x, y, s):
    c.save()
    c.translate(x, y)
    c.scale(s / 50, s / 50)
    c.move_to(0, 15)
    c.curve_to(-50, -20, -25, -60, 0, -30)
    c.curve_to(25, -60, 50, -20, 0, 15)
    c.close_path()
    c.fill()
    c.restore()


def sc_montage(c, t, T):
    bg_grad(c, (0.18, 0.12, 0.35), (0.45, 0.20, 0.45))
    # sparkles
    for i in range(18):
        x = (i * 211 + 50) % W
        y = (i * 397 + 80) % 1500
        rgb(c, WHITE, 0.25 + 0.25 * math.sin(t * 4 + i))
        c.arc(x, y, 4, 0, 2 * math.pi)
        c.fill()
    # rapid cuts every ~1.25s: different "ritual" vignettes
    cl = SCENE_DUR["sc_montage"] / 5
    cut = int(t / cl)
    labels = ["Ritual alis naik-turun", "Kabar pagi: “udah bangun!”",
              "Selfie makan siang", "Good night call 5 menit", "Ketawa bareng lagi"]
    # video call frames
    for side, who, x in ((0, "raka", 280), (1, "dina", 800)):
        rrect(c, x - 230, 260, 460, 640, 40)
        rgb(c, (0.08, 0.08, 0.14))
        c.fill()
        c.save()
        rrect(c, x - 230, 260, 460, 640, 40)
        c.clip()
        rgb(c, (0.25, 0.32, 0.55) if who == "raka" else (0.45, 0.25, 0.45))
        c.paint()
        b = abs(math.sin(t * 6 + side)) if cut % 2 == 0 else 0
        mood = "laugh" if cut in (0, 4) and (t * 2 % 1) > 0.5 else "smile"
        face(c, x, 560, 130, who, mood, t, brow=b)
        c.restore()
        text_l(c, "Raka" if who == "raka" else "Dina", x - 200, 870, 34, WHITE, bold=True)
    # heart between
    rgb(c, PINK)
    hs = 50 + 10 * abs(math.sin(t * 5))
    heart(c, W / 2, 600, hs)
    # ritual label (cut-based)
    k = back((t - cut * cl) / 0.25)
    c.save()
    c.translate(W / 2, 1040)
    c.scale(k, k)
    font(c, 50, True)
    lb = labels[min(cut, len(labels) - 1)]
    tw = c.text_extents(lb).x_advance
    rrect(c, -tw / 2 - 36, -62, tw + 72, 96, 48)
    rgb(c, WHITE)
    c.fill()
    c.move_to(-tw / 2, 4)
    rgb(c, (0.4, 0.15, 0.45))
    c.show_text(lb)
    c.restore()
    # stat line
    ms, me = L("sc_montage", 1)
    if t >= ms - 0.1:
        subtitle(c, "Bukan sering ngobrol, tapi", 1.0, y=1480)
        s = back((t - KONSISTEN_AT) / 0.35)
        if s > 0:
            c.save()
            c.translate(W / 2, 1720)
            c.scale(s, s)
            c.rotate(-0.04)
            font(c, 110, True)
            tw = c.text_extents("KONSISTEN.").x_advance
            rrect(c, -tw / 2 - 40, -100, tw + 80, 140, 30)
            rgb(c, YEL)
            c.fill()
            c.move_to(-tw / 2, 4)
            rgb(c, (0.12, 0.08, 0.18))
            c.show_text("KONSISTEN.")
            c.restore()


def sc_cta(c, t, T):
    bg_grad(c, (1.0, 0.86, 0.80), (0.98, 0.70, 0.75))
    glow(c, W / 2, 700, 600, WHITE, 0.4)
    face(c, W / 2, 640, 210, "dina", "smile", t, look=(0, 0))
    # vote buttons
    k = back((t - 0.6) / 0.35)
    if k > 0:
        for i, (lbl, col) in enumerate((("TIM DINA", PINK), ("TIM RAKA", (0.25, 0.45, 0.75)))):
            x = W / 2 + (-235 if i == 0 else 235)
            c.save()
            c.translate(x, 1560)
            pul = 1 + 0.04 * math.sin(t * 6 + i * 3)
            c.scale(k * pul, k * pul)
            rrect(c, -210, -70, 420, 140, 70)
            rgb(c, col)
            c.fill()
            text_c(c, lbl, 0, 18, 54, WHITE)
            c.restore()
        text_c(c, "overthinking", W / 2 - 235, 1680, 34, (0.4, 0.2, 0.3), k, bold=False)
        text_c(c, "ketiduran", W / 2 + 235, 1680, 34, (0.4, 0.2, 0.3), k, bold=False)
    text_c(c, "Komen: tim Dina atau tim Raka?", W / 2, 1810, 52, (0.25, 0.1, 0.2), ease((t - 1.0) / 0.4))
    text_c(c, "LDR nggak mati karena jarak.", W / 2, 180, 52, (0.35, 0.15, 0.25), ease(t / 0.4))


SCENES = [  # (fn, duration)
    (sc_hook, 4.0),
    (sc_room, 6.0),
    (sc_popup1, 2.2),
    (sc_brain, 6.0),
    (sc_raka, 4.2),
    (sc_typing, 6.2),
    (sc_call, 11.6),
    (sc_truth, 3.6),
    (sc_montage, 6.3),
    (sc_cta, 5.0),
]
SCENE_DUR = plan_vo()
SCENES = [(fn, SCENE_DUR[fn.__name__]) for fn, _ in SCENES]
TOTAL = sum(d for _, d in SCENES)
_ms, _me = L("sc_montage", 1)
KONSISTEN_AT = _ms + (_me - _ms) * 0.62


def scene_starts():
    s, out = 0.0, []
    for fn, d in SCENES:
        out.append((fn, s, d))
        s += d
    return out


# ---------------------------------------------------------------- audio
SR = 44100


def tone(freq, dur, amp=0.3, decay=6.0, harm=(1.0,)):
    t = np.arange(int(SR * dur)) / SR
    sig = sum(h * np.sin(2 * np.pi * freq * (i + 1) * t) for i, h in enumerate(harm))
    env = np.exp(-decay * t) * np.minimum(1, t * 400)
    return amp * sig * env


def add(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]


def build_audio(path):
    n = int(SR * (TOTAL + 0.5))
    a = np.zeros(n)
    st = {fn.__name__: s for fn, s, d in scene_starts()}
    rng = np.random.default_rng(7)
    # notification ding (hook) - two-note
    def ding(at, amp=0.35):
        add(a, tone(1318.5, 0.6, amp, 7, (1, 0.3, 0.1)), at)
        add(a, tone(1760, 0.8, amp * 0.8, 6, (1, 0.25)), at + 0.12)
    ding(st["sc_hook"] + 0.6)
    # low dark drone during anxious part (hook..typing)
    d0, d1 = st["sc_hook"] + 1.0, st["sc_call"]
    t = np.arange(int(SR * (d1 - d0))) / SR
    drone = 0.06 * (np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 82.4 * t + 0.4 * np.sin(2 * np.pi * 0.2 * t)))
    fade = np.minimum(1, t / 2.0) * np.minimum(1, (t[-1] - t) / 1.0)
    add(a, drone * fade, d0)
    # clock tick in room scene
    for k in range(12):
        add(a, tone(2400, 0.04, 0.12, 120) + 0.05 * rng.standard_normal(int(SR * 0.04)) * np.exp(-np.arange(int(SR * 0.04)) / 200), st["sc_room"] + 0.5 * k + 0.3)
    # popup whoosh/pop
    def pop(at, amp=0.3):
        tt = np.arange(int(SR * 0.18)) / SR
        f = 300 + 900 * tt / 0.18
        add(a, amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 18), at)
    pop(st["sc_popup1"])
    for at in (1.0, 2.2, 3.4, 4.4):
        pop(st["sc_brain"] + at, 0.22)
    # heartbeat in brain + typing
    for k in range(int((st["sc_call"] - st["sc_brain"]) / 0.75)):
        at = st["sc_brain"] + k * 0.75
        add(a, tone(60, 0.18, 0.35, 25, (1, 0.5)), at)
        add(a, tone(55, 0.18, 0.25, 25, (1, 0.5)), at + 0.2)
    # soft snore/zzz in raka scene: filtered noise breaths
    for k in range(3):
        L = int(SR * 1.0)
        nz = rng.standard_normal(L)
        nz = np.convolve(nz, np.ones(60) / 60, mode="same")
        env = np.sin(np.linspace(0, np.pi, L)) ** 2
        add(a, 0.25 * nz * env, st["sc_raka"] + 0.3 + k * 1.4)
    # keyboard taps while typing
    ty = st["sc_typing"]
    for seg in ((0.2, 2.2), (3.4, 4.4)):
        x = seg[0]
        while x < seg[1]:
            L = int(SR * 0.03)
            add(a, 0.18 * rng.standard_normal(L) * np.exp(-np.arange(L) / 180), ty + x)
            x += 0.08 + rng.random() * 0.06
    # delete burst
    for k in range(8):
        L = int(SR * 0.02)
        add(a, 0.12 * rng.standard_normal(L) * np.exp(-np.arange(L) / 120), ty + 2.6 + k * 0.07)
    # phone ring (incoming call)
    cs = st["sc_call"]
    for k in range(2):
        at = cs + k * 0.9
        tt = np.arange(int(SR * 0.4)) / SR
        ring = 0.18 * (np.sin(2 * np.pi * 440 * tt) + np.sin(2 * np.pi * 480 * tt)) * (np.sin(2 * np.pi * 20 * tt) > 0)
        add(a, ring * np.minimum(1, (0.4 - tt) * 40), at)
    # accept blip
    add(a, tone(880, 0.25, 0.25, 10), cs + 1.9)
    add(a, tone(1320, 0.3, 0.2, 10), cs + 2.0)
    # warm music from truth scene to end: soft pluck chords
    m0 = st["sc_truth"]
    chords = [[261.6, 329.6, 392.0], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7]]
    beat = 0.5
    k = 0
    while m0 + k * beat < TOTAL - 0.3:
        ch = chords[(k // 4) % 4]
        at = m0 + k * beat
        amp = 0.08 if at < st["sc_montage"] else 0.11
        for j, f in enumerate(ch):
            add(a, tone(f, 1.2, amp, 3.0, (1, 0.4, 0.15)), at + j * 0.03 * (k % 2))
        if k % 2 == 0:
            add(a, tone(ch[0] / 2, 1.0, amp * 1.2, 2.5, (1, 0.3)), at)
        # melody sparkle in montage/cta
        if at >= st["sc_montage"]:
            mel = ch[(k * 2) % 3] * 2
            add(a, tone(mel, 0.4, 0.05, 6, (1, 0.2)), at + 0.25)
            # light percussion
            L = int(SR * 0.05)
            add(a, 0.05 * rng.standard_normal(L) * np.exp(-np.arange(L) / 150), at + 0.25)
        k += 1
    # big "KONSISTEN" hit + CTA ding
    add(a, tone(523.3, 1.5, 0.15, 2, (1, 0.5, 0.2)), st["sc_montage"] + KONSISTEN_AT)
    ding(st["sc_cta"] + 0.6, 0.25)
    # night ambience: crickets + room tone from the hook until the call is picked up
    n0, n1 = st["sc_hook"], st["sc_call"] + 1.7
    L_ = int((n1 - n0) * SR)
    tt = np.arange(L_) / SR
    amb = np.zeros(L_)
    for f0, period, ph in ((4300, 0.83, 0.0), (4700, 1.07, 0.4), (3900, 1.31, 0.7)):
        k = ph
        while k < tt[-1]:
            for j in range(3):  # 3 pulses per chirp
                i = int((k + j * 0.045) * SR)
                m = int(0.03 * SR)
                if i + m < L_:
                    amb[i:i + m] += np.sin(2 * np.pi * f0 * tt[:m]) * np.hanning(m) * 0.018
            k += period * (0.85 + 0.3 * rng.random())
    brown = np.cumsum(rng.standard_normal(L_))
    brown = band(brown - np.mean(brown), 40, 300)
    amb += brown / (np.max(np.abs(brown)) + 1e-9) * 0.03
    fade = np.minimum(1, tt / 1.0) * np.minimum(1, (tt[-1] - tt) / 0.8)
    add(a, amb * fade, n0)
    # master fade out + normalize
    fo = int(SR * 1.2)
    a[-fo:] *= np.linspace(1, 0, fo)
    a = np.tanh(a * 1.2)
    a = a / (np.max(np.abs(a)) + 1e-9) * 0.85
    # voice over + ducking of music/SFX under the voice
    peak = max(np.max(np.abs(l["audio"])) for sp in SPEC.values() for l in sp["lines"])
    VO_GAIN = 0.92 / peak
    vo = np.zeros(n)
    duck = np.zeros(n)
    for name, sp in SPEC.items():
        for ln in sp["lines"]:
            x = ln["audio"] * VO_GAIN
            add(vo, x, st[name] + ln["start"])
            if len(ln["pre"]):
                add(vo, ln["pre"], max(0, st[name] + ln["start"] - len(ln["pre"]) / SR))
            i0 = int((st[name] + ln["start"] - 0.15) * SR)
            duck[max(0, i0): i0 + len(x) + int(0.35 * SR)] = 1
    k = int(0.12 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same")
    a = a * (0.8 - 0.5 * duck) + vo
    a = np.tanh(a * 1.1) * 0.95
    pcm = (a * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())


# ---------------------------------------------------------------- subtitles (SRT) for editing apps
def write_srt(path):
    def ts(x):
        ms = int(round(x * 1000))
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
    with open(path, "w", encoding="utf-8") as f:
        st = {fn.__name__: s0 for fn, s0, d in scene_starts()}
        i = 0
        for name, sp in SPEC.items():
            for ln in sp["lines"]:
                i += 1
                txt = ln.get("srt") or (ln["sub"].strip("\u201c\u201d") if isinstance(ln.get("sub"), str) else ln["say"])
                if ln.get("who"):
                    txt = ln["who"] + ": " + txt
                a, b = st[name] + ln["start"], st[name] + ln["end"] + 0.3
                f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n\n")


# ---------------------------------------------------------------- render
def render(preview_times=None):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    c.set_antialias(cairo.ANTIALIAS_BEST)
    starts = scene_starts()

    def draw(T):
        for fn, s, d in starts:
            if s <= T < s + d or fn is starts[-1][0]:
                lt = T - s
                c.save()
                c.set_operator(cairo.OPERATOR_SOURCE)
                c.set_source_rgb(0, 0, 0)
                c.paint()
                c.set_operator(cairo.OPERATOR_OVER)
                fn(c, lt, T)
                draw_sub(c, fn.__name__, lt, d)
                c.restore()
                # quick flash-cut transition
                if lt < 0.12 and s > 0:
                    c.set_source_rgba(1, 1, 1, 0.5 * (1 - lt / 0.12))
                    c.paint()
                if lt > d - 0.1 and fn is not starts[-1][0]:
                    pass
                break
        # progress bar on top (TikTok style)
        c.rectangle(0, 0, W * T / TOTAL, 8)
        c.set_source_rgba(1, 1, 1, 0.6)
        c.fill()

    if preview_times:
        for T in preview_times:
            draw(T)
            surf.write_to_png(os.path.join(OUT_DIR, "preview_%05.1f.png" % T))
        return

    wav = os.path.join(OUT_DIR, "_audio.wav")
    build_audio(wav)
    write_srt(OUT[:-4] + ".srt")
    nframes = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nframes):
        draw(f / FPS)
        surf.flush()
        p.stdin.write(bytes(surf.get_data()))
        if f % 150 == 0:
            print(f"frame {f}/{nframes}", file=sys.stderr)
    p.stdin.close()
    p.wait()
    os.remove(wav)
    print("wrote", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        render([float(x) for x in sys.argv[2:]])
    else:
        render()
