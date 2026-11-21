#!/usr/bin/env python3
"""Aldorra mountain-guide passport spread (make.fun r3 rebuild).

Pure Python standard library only. Deterministic: no randomness, no
timestamps, fixed float formatting. Renders a 1024x1024 two-page passport
spread to /output/entry.png (when MAKEFUN_OUTPUT_DIR is set) or ./entry.png.

Invented world: Republic of ALDORRA, holder JOREN HALD, passport ALD730518,
guide licence G-0730. All numbers cross-checked in code (MRZ check digits
computed per ICAO 9303 and asserted against the design spec).
"""
import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
TEAL = (31, 77, 58)        # deep teal-green frame / headers
DTEAL = (20, 52, 38)       # darker teal
MTEAL = (46, 99, 76)       # mid teal
CREAM = (245, 239, 224)    # paper
PAPER2 = (249, 244, 231)   # lighter paper
INK = (26, 34, 30)         # near-black ink
GREY = (96, 110, 100)      # label grey
LGREY = (214, 219, 206)    # faint guilloche
WML = (226, 231, 214)      # watermark
WHITE = (255, 255, 255)
BLACK = (16, 16, 16)
RED = (158, 44, 40)        # Aldorra stamps / toll
BLUE = (44, 86, 150)       # Tarnovia stamps
GREEN = (42, 116, 70)      # Kaldoria stamps
PURPLE = (102, 70, 152)    # Veskara stamps
DRED = (138, 38, 34)
SIGBLUE = (32, 52, 112)    # signature ink
# portrait skin tones
SKIN = (227, 185, 140)
SKIN_HI = (239, 201, 160)
SKIN_SH = (201, 143, 102)
SKIN_DK = (168, 122, 82)
HAIR = (58, 42, 28)
HAIR_DK = (40, 28, 16)
HAIR_LT = (106, 74, 46)
JACKET = (46, 74, 60)
JACKET_DK = (30, 52, 42)
JACKET_LT = (62, 96, 78)
PHOTO_BG0 = (213, 218, 222)
PHOTO_BG1 = (183, 192, 199)

# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)


def _off(x, y):
    return (y * W + x) * 3


def px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        o = _off(x, y)
        buf[o] = c[0]
        buf[o + 1] = c[1]
        buf[o + 2] = c[2]


def blend_px(x, y, c, a):
    """Blend colour c over existing pixel with alpha a (0..1)."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        o = _off(x, y)
        buf[o] = int(buf[o] * (1.0 - a) + c[0] * a)
        buf[o + 1] = int(buf[o + 1] * (1.0 - a) + c[1] * a)
        buf[o + 2] = int(buf[o + 2] * (1.0 - a) + c[2] * a)


def mix(c1, c2, t):
    return (int(c1[0] * (1.0 - t) + c2[0] * t),
            int(c1[1] * (1.0 - t) + c2[1] * t),
            int(c1[2] * (1.0 - t) + c2[2] * t))


def fill_rect(x0, y0, x1, y1, c):
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W, x1)
    y1 = min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(c) * (x1 - x0)
    for y in range(y0, y1):
        o = _off(x, y0) if False else _off(x0, y)
        buf[o:o + len(row)] = row


def vgrad_rect(x0, y0, x1, y1, c0, c1):
    h = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / float(h)
        fill_rect(x0, y, x1, y + 1, mix(c0, c1, t))


def hline(x0, x1, y, c, w=1):
    if x0 > x1:
        x0, x1 = x1, x0
    for yy in range(y, y + w):
        fill_rect(x0, yy, x1 + 1, yy + 1, c)


def vline(x, y0, y1, c, w=1):
    if y0 > y1:
        y0, y1 = y1, y0
    for xx in range(x, x + w):
        fill_rect(xx, y0, xx + 1, y1 + 1, c)


def line(x0, y0, x1, y1, c, w=1):
    """Bresenham line (with optional thickness)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if w == 1:
            px(x0, y0, c)
        else:
            fill_rect(x0 - w // 2, y0 - w // 2, x0 + w // 2 + 1,
                      y0 + w // 2 + 1, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def poly_fill(points, c):
    """Scanline fill for a simple polygon (convex or concave)."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0, y1 = max(0, min(ys)), min(H - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, yy1 = points[i]
            x2, yy2 = points[(i + 1) % n]
            if (yy1 <= y < yy2) or (yy2 <= y < yy1):
                if yy2 != yy1:
                    xs.append(x1 + (y - yy1) * (x2 - x1) / float(yy2 - yy1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            fill_rect(int(math.ceil(xs[i])), y,
                      int(math.floor(xs[i + 1])) + 1, y + 1, c)


def circle(cx, cy, r, c, w=1):
    for k in range(w):
        rr = r - k
        if rr <= 0:
            break
        x = 0
        y = rr
        d = 3 - 2 * rr
        while x <= y:
            for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                           (x, -y), (y, -x), (-x, -y), (-y, -x)):
                px(cx + sx, cy + sy, c)
            if d < 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1


def fill_ellipse(cx, cy, rx, ry, c, a=1.0):
    if rx <= 0 or ry <= 0:
        return
    for y in range(cy - ry, cy + ry + 1):
        t = (y - cy) / float(ry)
        if abs(t) > 1.0:
            continue
        dx = int(rx * math.sqrt(1.0 - t * t))
        if a >= 1.0:
            fill_rect(cx - dx, y, cx + dx + 1, y + 1, c)
        else:
            for x in range(cx - dx, cx + dx + 1):
                blend_px(x, y, c, a)


def ellipse_outline(cx, cy, rx, ry, c):
    steps = max(24, int(2 * math.pi * max(rx, ry)))
    prev = None
    for i in range(steps + 1):
        a = 2 * math.pi * i / steps
        p = (int(round(cx + rx * math.cos(a))),
             int(round(cy + ry * math.sin(a))))
        if prev is not None:
            line(prev[0], prev[1], p[0], p[1], c)
        prev = p


# ------------------------------------------------------- rotation transform
_rot = None  # (cx, cy, cos, sin)


def set_rot(cx, cy, deg):
    global _rot
    a = math.radians(deg)
    _rot = (cx, cy, math.cos(a), math.sin(a))


def clear_rot():
    global _rot
    _rot = None


def tx(x, y):
    if _rot is None:
        return x, y
    cx, cy, co, si = _rot
    dx, dy = x - cx, y - cy
    return (int(round(cx + dx * co - dy * si)),
            int(round(cy + dx * si + dy * co)))


def rline(x0, y0, x1, y1, c, w=1):
    ax, ay = tx(x0, y0)
    bx, by = tx(x1, y1)
    line(ax, ay, bx, by, c, w)


def rrect(x0, y0, x1, y1, c, w=1):
    pts = [tx(x0, y0), tx(x1, y0), tx(x1, y1), tx(x0, y1)]
    for i in range(4):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % 4]
        line(ax, ay, bx, by, c, w)


def rfill_rect(x0, y0, x1, y1, c):
    pts = [tx(x0, y0), tx(x1, y0), tx(x1, y1), tx(x0, y1)]
    poly_fill(pts, c)


def rcircle(cx, cy, r, c, w=1):
    ax, ay = tx(cx, cy)
    circle(ax, ay, r, c, w)


# ------------------------------------------------------------------- font
# 5x7 bitmap font: each glyph is 7 rows, bit 4 = leftmost column.
FONT = {
    'A': (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'B': (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    'C': (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    'D': (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    'E': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    'F': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    'G': (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    'H': (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'I': (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    'J': (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    'K': (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    'L': (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    'M': (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    'N': (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    'O': (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    'P': (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    'Q': (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    'R': (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    'S': (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    'T': (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    'U': (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    'V': (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'W': (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    'X': (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    'Y': (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    'Z': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    '0': (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    '1': (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    '2': (0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F),
    '3': (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    '4': (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    '5': (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    '6': (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    '7': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    '8': (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    '9': (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    ' ': (0, 0, 0, 0, 0, 0, 0),
    '.': (0, 0, 0, 0, 0, 0x0C, 0x0C),
    ',': (0, 0, 0, 0, 0x0C, 0x04, 0x08),
    '-': (0, 0, 0, 0x1F, 0, 0, 0),
    '\u2013': (0, 0, 0, 0x1F, 0, 0, 0),
    '\u2014': (0, 0, 0, 0x1F, 0x1F, 0, 0),
    '/': (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    '(': (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ')': (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    '<': (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02),
    '>': (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08),
    ':': (0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0),
    ';': (0, 0x0C, 0x0C, 0, 0x0C, 0x04, 0x08),
    "'": (0x04, 0x04, 0x08, 0, 0, 0, 0),
    '"': (0x0A, 0x0A, 0x0A, 0, 0, 0, 0),
    '+': (0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0),
    '=': (0, 0, 0x1F, 0, 0x1F, 0, 0),
    '&': (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D),
    '!': (0x04, 0x04, 0x04, 0x04, 0x04, 0, 0x04),
    '?': (0x0E, 0x11, 0x01, 0x02, 0x04, 0, 0x04),
    '%': (0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13),
    '*': (0, 0x04, 0x15, 0x0E, 0x15, 0x04, 0),
    '_': (0, 0, 0, 0, 0, 0, 0x1F),
    '\u2022': (0, 0x04, 0x0E, 0x0E, 0x0E, 0x04, 0),   # bullet
    '\u00b7': (0, 0, 0, 0x0C, 0x0C, 0, 0),            # middle dot
    'a': (0, 0, 0x0E, 0x01, 0x0F, 0x11, 0x0F),
    'b': (0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x1E),
    'c': (0, 0, 0x0E, 0x10, 0x10, 0x11, 0x0E),
    'd': (0x01, 0x01, 0x0F, 0x11, 0x11, 0x11, 0x0F),
    'e': (0, 0, 0x0E, 0x11, 0x1F, 0x10, 0x0E),
    'f': (0x06, 0x08, 0x08, 0x1E, 0x08, 0x08, 0x08),
    'g': (0, 0x0F, 0x11, 0x11, 0x0F, 0x01, 0x0E),
    'h': (0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x11),
    'i': (0x04, 0, 0x0C, 0x04, 0x04, 0x04, 0x0E),
    'j': (0x02, 0, 0x06, 0x02, 0x02, 0x12, 0x0C),
    'k': (0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12),
    'l': (0x0C, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    'm': (0, 0, 0x1A, 0x15, 0x15, 0x15, 0x15),
    'n': (0, 0, 0x1E, 0x11, 0x11, 0x11, 0x11),
    'o': (0, 0, 0x0E, 0x11, 0x11, 0x11, 0x0E),
    'p': (0, 0, 0x1E, 0x11, 0x11, 0x1E, 0x10),
    'q': (0, 0, 0x0F, 0x11, 0x11, 0x0F, 0x01),
    'r': (0, 0, 0x16, 0x19, 0x10, 0x10, 0x10),
    's': (0, 0, 0x0F, 0x10, 0x0E, 0x01, 0x1E),
    't': (0x04, 0x04, 0x1F, 0x04, 0x04, 0x04, 0x03),
    'u': (0, 0, 0x11, 0x11, 0x11, 0x13, 0x0D),
    'v': (0, 0, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'w': (0, 0, 0x11, 0x15, 0x15, 0x15, 0x0A),
    'x': (0, 0, 0x11, 0x0A, 0x04, 0x0A, 0x11),
    'y': (0, 0, 0x11, 0x11, 0x0F, 0x01, 0x0E),
    'z': (0, 0, 0x1F, 0x02, 0x04, 0x08, 0x1F),
}


def text_w(s, scale=1, adv=None):
    a = adv if adv is not None else 6 * scale
    return len(s) * a


def draw_char(x, y, ch, c, scale=1, bold=False):
    g = FONT.get(ch)
    if g is None:
        return
    off = max(1, scale // 2) if bold else 0
    for r in range(7):
        row = g[r]
        if row == 0:
            continue
        for col in range(5):
            if (row >> (4 - col)) & 1:
                fill_rect(x + col * scale, y + r * scale,
                          x + col * scale + scale, y + r * scale + scale, c)
                if off:
                    fill_rect(x + col * scale + off, y + r * scale,
                              x + col * scale + scale + off,
                              y + r * scale + scale, c)


def text(x, y, s, c, scale=1, bold=False, adv=None, align='l', slope=0.0,
         rot=False):
    """Draw text. align: 'l'/'c'/'r' relative to x. slope: dy per char
    (diagonal text). rot: if True, apply the current rotation transform
    to each character origin (glyph pixels stay upright)."""
    a = adv if adv is not None else 6 * scale
    w = len(s) * a
    if align == 'c':
        x -= w // 2
    elif align == 'r':
        x -= w
    for i, ch in enumerate(s):
        cx = x + i * a
        cy = y + int(round(i * slope))
        if rot:
            cx, cy = tx(cx, cy)
        draw_char(cx, cy, ch, c, scale, bold)


def wrap(s, max_w, scale=1, adv=None):
    """Greedy word wrap; returns list of lines."""
    a = adv if adv is not None else 6 * scale
    max_chars = max(1, max_w // a)
    lines = []
    for para in s.split('\n'):
        words = para.split(' ')
        cur = ''
        for wd in words:
            trial = wd if not cur else cur + ' ' + wd
            if len(trial) <= max_chars:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                while len(wd) > max_chars:
                    lines.append(wd[:max_chars])
                    wd = wd[max_chars:]
                cur = wd
        if cur or not lines:
            lines.append(cur)
    return lines

# --------------------------------------------------------------------- MRZ
# ICAO 9303 check digits: value A=10..Z=35, '<'=0, digits as-is;
# weights 7,3,1 cycling from the first character of the field.
def _cd_val(ch):
    if ch == '<':
        return 0
    if ch.isdigit():
        return int(ch)
    return ord(ch) - 55


def check_digit(field):
    w = (7, 3, 1)
    return sum(_cd_val(ch) * w[i % 3] for i, ch in enumerate(field)) % 10


PASSPORT_NO = 'ALD730518'
CODE = 'ALD'
SURNAME = 'HALD'
GIVEN = 'JOREN'
DOB = '881003'          # 03 OCT 1988
EXPIRY = '340421'       # 21 APR 2034
SEX = 'M'
PERSONAL = '0310100388'  # personal no, display "0310 1003 88"

DOC_CD = check_digit(PASSPORT_NO)
DOB_CD = check_digit(DOB)
EXP_CD = check_digit(EXPIRY)
OPT_FIELD = PERSONAL + '<<<<'      # optional data field, positions 29-42
OPT_CD = check_digit(OPT_FIELD)
COMPOSITE_SRC = (PASSPORT_NO + str(DOC_CD) + DOB + str(DOB_CD) +
                 EXPIRY + str(EXP_CD) + OPT_FIELD + str(OPT_CD))
COMP_CD = check_digit(COMPOSITE_SRC)

# Spec assertions — if any fails the program stops, nothing is rendered.
assert DOC_CD == 0, 'passport check digit %d != 0' % DOC_CD
assert DOB_CD == 4, 'DOB check digit %d != 4' % DOB_CD
assert EXP_CD == 8, 'expiry check digit %d != 8' % EXP_CD
assert OPT_CD == 6, 'personal check digit %d != 6' % OPT_CD
assert COMP_CD == 4, 'composite check digit %d != 4' % COMP_CD

MRZ1 = 'P<' + CODE + SURNAME + '<<' + GIVEN
MRZ1 = MRZ1 + '<' * (44 - len(MRZ1))
MRZ2 = (PASSPORT_NO + str(DOC_CD) + CODE + DOB + str(DOB_CD) + SEX +
        EXPIRY + str(EXP_CD) + OPT_FIELD + str(OPT_CD) + str(COMP_CD))
assert len(MRZ1) == 44, 'MRZ line 1 len %d' % len(MRZ1)
assert len(MRZ2) == 44, 'MRZ line 2 len %d' % len(MRZ2)
assert MRZ1 == 'P<ALDHALD<<JOREN<<<<<<<<<<<<<<<<<<<<<<<<<<<<', MRZ1
assert MRZ2 == 'ALD7305180ALD8810034M34042180310100388<<<<64', MRZ2


# ----------------------------------------------------------------- guilloche
def guilloche(x0, x1, y0, y1, color, step=13, amp=3):
    for yb in range(y0, y1, step):
        for x in range(x0, x1, 2):
            y = yb + int(round(amp * math.sin(x * 0.021 + yb * 0.37)))
            px(x, y, color)
            px(x, y + 1, color)


def watermark(page_x0, page_x1, y, s, color, slope=0.22):
    text(page_x0 + 20, y, s, color, scale=3, slope=slope)


# ------------------------------------------------------------------- emblem
def emblem(cx, cy, r, color):
    circle(cx, cy, r, color, 2)
    circle(cx, cy, r - 4, color, 1)
    # mountain peaks inside the ring
    poly_fill([(cx - 16, cy + 10), (cx - 6, cy - 8), (cx + 2, cy + 10)],
              color)
    poly_fill([(cx - 2, cy + 10), (cx + 8, cy - 12), (cx + 17, cy + 10)],
              color)
    fill_rect(cx - 17, cy + 10, cx + 18, cy + 12, color)


# ------------------------------------------------------------------ portrait
def portrait(x0, y0, x1, y1):
    """Realistic male portrait, built from layered shapes + gradients.
    Photo box roughly 152x196."""
    cx = (x0 + x1) // 2
    # background: light grey studio gradient
    vgrad_rect(x0, y0, x1, y1, PHOTO_BG0, PHOTO_BG1)
    # soft backdrop shadow behind the head
    fill_ellipse(cx, y0 + 96, 66, 84, (168, 176, 184), a=0.20)

    # ---- jacket / shoulders
    poly_fill([(x0 + 6, y1), (x0 + 14, y0 + 158), (x0 + 46, y0 + 140),
               (cx, y0 + 136), (x1 - 46, y0 + 140), (x1 - 14, y0 + 158),
               (x1 - 6, y1)], JACKET)
    # jacket folds
    line(cx - 34, y0 + 152, cx - 26, y1 - 4, JACKET_DK, 2)
    line(cx + 34, y0 + 152, cx + 26, y1 - 4, JACKET_DK, 2)
    line(cx - 52, y0 + 164, cx - 48, y1 - 4, JACKET_DK, 1)
    line(cx + 52, y0 + 164, cx + 48, y1 - 4, JACKET_DK, 1)
    # collar
    poly_fill([(cx - 24, y0 + 136), (cx, y0 + 158), (cx - 12, y0 + 168),
               (cx - 30, y0 + 150)], JACKET_LT)
    poly_fill([(cx + 24, y0 + 136), (cx, y0 + 158), (cx + 12, y0 + 168),
               (cx + 30, y0 + 150)], JACKET_LT)
    line(cx - 24, y0 + 136, cx, y0 + 158, JACKET_DK, 1)
    line(cx + 24, y0 + 136, cx, y0 + 158, JACKET_DK, 1)
    # zipper
    line(cx, y0 + 160, cx, y1 - 2, JACKET_DK, 2)
    # shirt glimpse
    poly_fill([(cx - 8, y0 + 158), (cx + 8, y0 + 158), (cx + 4, y0 + 176),
               (cx - 4, y0 + 176)], (214, 206, 190))

    # ---- neck
    poly_fill([(cx - 13, y0 + 108), (cx + 13, y0 + 108), (cx + 11, y0 + 140),
               (cx - 11, y0 + 140)], SKIN_SH)
    fill_ellipse(cx, y0 + 112, 12, 7, SKIN_DK, a=0.45)

    # ---- ears (tucked, small)
    fill_ellipse(cx - 44, y0 + 92, 5, 10, SKIN_SH)
    fill_ellipse(cx + 44, y0 + 92, 5, 10, SKIN_SH)
    fill_ellipse(cx - 44, y0 + 92, 2, 6, SKIN_DK, a=0.6)
    fill_ellipse(cx + 44, y0 + 92, 2, 6, SKIN_DK, a=0.6)

    # ---- face base (forehead wide, jaw narrower)
    face = [(cx - 32, y0 + 26), (cx + 32, y0 + 26), (cx + 40, y0 + 48),
            (cx + 44, y0 + 88), (cx + 36, y0 + 122), (cx + 18, y0 + 144),
            (cx - 18, y0 + 144), (cx - 36, y0 + 122), (cx - 44, y0 + 88),
            (cx - 40, y0 + 48)]
    poly_fill(face, SKIN)
    # vertical skin gradient: lighter forehead, warmer jaw
    for yy in range(y0 + 26, y0 + 145):
        t = (yy - (y0 + 26)) / 119.0
        tone = mix(SKIN_HI, SKIN_SH, t * 0.55)
        # re-tint only pixels already skin-coloured: approximate by
        # blending a horizontal span across the face width at this height
        half = 44 - int(14 * max(0.0, (yy - (y0 + 88)) / 56.0))
        for xx in range(cx - half, cx + half + 1):
            blend_px(xx, yy, tone, 0.28)
    # forehead highlight
    fill_ellipse(cx, y0 + 48, 26, 13, SKIN_HI, a=0.5)
    # cheek shading
    fill_ellipse(cx - 28, y0 + 98, 13, 10, (214, 154, 110), a=0.45)
    fill_ellipse(cx + 28, y0 + 98, 13, 10, (214, 154, 110), a=0.45)
    # right-side shadow (light from the left)
    fill_ellipse(cx + 38, y0 + 82, 10, 42, SKIN_SH, a=0.30)
    # jaw + chin shadow
    fill_ellipse(cx, y0 + 138, 24, 9, SKIN_SH, a=0.45)

    # ---- hair: short dark-brown cap with a low hairline
    hair = [(cx - 44, y0 + 56), (cx - 42, y0 + 28), (cx - 26, y0 + 8),
            (cx, y0 + 2), (cx + 26, y0 + 8), (cx + 42, y0 + 28),
            (cx + 44, y0 + 56), (cx + 36, y0 + 44), (cx + 30, y0 + 32),
            (cx + 14, y0 + 24), (cx, y0 + 22), (cx - 14, y0 + 24),
            (cx - 30, y0 + 32), (cx - 36, y0 + 44)]
    poly_fill(hair, HAIR)
    # sideburns
    fill_rect(cx - 45, y0 + 52, cx - 39, y0 + 86, HAIR)
    fill_rect(cx + 39, y0 + 52, cx + 45, y0 + 86, HAIR)
    # hairline height as a function of horizontal offset from centre:
    # low in the middle (y0+22), rising to the temples (y0+44)
    def hairline_y(dx):
        t = min(1.0, abs(dx) / 44.0)
        return y0 + 22 + int(round(22 * t * t))

    # top of the hair cap as a function of offset (for strand bounds)
    def cap_top_y(dx):
        t = min(1.0, abs(dx) / 44.0)
        return y0 + 2 + int(round(26 * t * t))

    # hair strands: deterministic short strokes, kept strictly INSIDE the
    # hair cap (above the hairline, below the cap top) so none land on
    # the forehead or poke out of the silhouette
    strand_cols = [HAIR_DK, HAIR, HAIR_LT, (80, 58, 36)]
    for i in range(130):
        sx = cx - 40 + (i * 37) % 80
        sy = y0 + 5 + (i * 11) % 32
        if sy < cap_top_y(sx - cx) + 2:
            continue
        if sy > hairline_y(sx - cx) - 3:
            continue
        dx = int(round(2 * math.sin(i * 2.399)))
        dy = 2 + (i % 3)
        line(sx, sy, sx + dx, sy + dy, strand_cols[i % 4], 1)
    # fringe: short downward strokes along the hairline edge
    for dx in range(-38, 39, 4):
        hx = cx + dx
        hy = hairline_y(dx)
        line(hx, hy - 2, hx + (1 if dx > 0 else -1), hy + 3, HAIR_DK, 1)
    # hairline edge highlight
    line(cx - 30, y0 + 32, cx - 14, y0 + 24, HAIR_LT, 1)
    line(cx + 14, y0 + 24, cx + 30, y0 + 32, HAIR_LT, 1)

    # ---- eyebrows (thicker, closer to the eyes)
    line(cx - 26, y0 + 75, cx - 8, y0 + 72, HAIR_DK, 3)
    line(cx + 8, y0 + 72, cx + 26, y0 + 75, HAIR_DK, 3)

    # ---- eyes (larger, with lid crease)
    for ex in (cx - 17, cx + 17):
        ey = y0 + 86
        fill_ellipse(ex, ey, 10, 6, (242, 238, 230))
        # upper lid crease
        line(ex - 10, ey - 6, ex + 10, ey - 6, SKIN_DK, 1)
        # upper lid line
        line(ex - 10, ey - 3, ex + 10, ey - 3, (90, 60, 40), 1)
        # iris + pupil + highlight
        fill_ellipse(ex, ey, 5, 5, (74, 46, 20))
        fill_ellipse(ex, ey, 2, 2, (10, 10, 10))
        fill_ellipse(ex - 2, ey - 2, 1, 1, WHITE)
        # lower lid
        line(ex - 8, ey + 6, ex + 8, ey + 6, (196, 160, 124), 1)

    # ---- nose: bridge highlight, side shadows, nostrils, under-nose shade
    line(cx - 1, y0 + 90, cx - 1, y0 + 116, SKIN_HI, 2)
    line(cx - 5, y0 + 92, cx - 5, y0 + 114, SKIN_SH, 1)
    line(cx + 4, y0 + 92, cx + 5, y0 + 116, SKIN_SH, 2)
    fill_ellipse(cx, y0 + 124, 9, 3, SKIN_SH, a=0.45)
    fill_ellipse(cx - 6, y0 + 120, 3, 2, SKIN_DK, a=0.8)
    fill_ellipse(cx + 6, y0 + 120, 3, 2, SKIN_DK, a=0.8)
    line(cx - 7, y0 + 122, cx + 7, y0 + 122, SKIN_DK, 1)

    # ---- mouth
    my = y0 + 134
    poly_fill([(cx - 12, my - 2), (cx, my - 4), (cx + 12, my - 2),
               (cx + 8, my + 3), (cx, my + 4), (cx - 8, my + 3)],
              (176, 106, 82))
    line(cx - 12, my - 2, cx + 12, my - 2, (122, 58, 46), 2)
    fill_ellipse(cx, my + 6, 8, 2, SKIN_SH, a=0.5)

    # ---- stubble: sparse deterministic dots, chin only (below the mouth)
    # + a denser moustache above the lip
    for yy in range(my + 8, y0 + 145, 3):
        half = 44 - int(14 * max(0.0, (yy - (y0 + 88)) / 56.0))
        for xx in range(cx - half, cx + half + 1, 3):
            if (xx * 31 + yy * 17) % 11 in (0, 1):
                blend_px(xx, yy, (90, 58, 38), 0.35)
    for yy in range(my - 9, my - 3, 2):  # moustache, denser
        for xx in range(cx - 13, cx + 14, 2):
            if (xx * 13 + yy * 7) % 5 in (0, 1):
                blend_px(xx, yy, (90, 58, 38), 0.5)

    # ---- frame
    line(x0, y0, x1, y0, TEAL, 2)
    line(x0, y1, x1, y1, TEAL, 2)
    line(x0, y0, x0, y1, TEAL, 2)
    line(x1, y0, x1, y1, TEAL, 2)


def ghost_photo(x0, y0, x1, y1):
    """Small faded ghost image (bottom-right of the data area)."""
    cx = (x0 + x1) // 2
    a = 0.30
    g = (150, 148, 142)
    gd = (110, 108, 102)
    # backdrop
    for y in range(y0, y1):
        for x in range(x0, x1):
            blend_px(x, y, (226, 224, 218), 0.5)
    fill_ellipse(cx, y0 + 34, 22, 30, g, a)
    fill_ellipse(cx, y0 + 14, 20, 14, gd, a)          # hair
    fill_ellipse(cx - 9, y0 + 32, 2, 2, gd, a)        # eyes
    fill_ellipse(cx + 9, y0 + 32, 2, 2, gd, a)
    line(cx - 12, y0 + 48, cx + 12, y0 + 48, gd, 1)   # mouth hint
    poly_fill([(x0 + 4, y1), (cx - 20, y0 + 62), (cx + 20, y0 + 62),
               (x1 - 4, y1)], g)                      # shoulders
    line(x0, y0, x1, y0, gd, 1)
    line(x0, y1, x1, y1, gd, 1)
    line(x0, y0, x0, y1, gd, 1)
    line(x1, y0, x1, y1, gd, 1)


# ------------------------------------------------------------------- stamps
def draw_stamp(x0, y0, w, h, color, country, subtitle, kind, date, post,
               rot_deg):
    """Rounded-rectangle border stamp, slight rotation, hand-stamped feel."""
    cx, cy = x0 + w // 2, y0 + h // 2
    set_rot(cx, cy, rot_deg)
    # double border
    rrect(x0 + 3, y0 + 3, x0 + w - 3, y0 + h - 3, color, 2)
    rrect(x0 + 7, y0 + 7, x0 + w - 7, y0 + h - 7, color, 1)
    arrow = '-->' if kind == 'ARRIVAL' else '<--'
    text(cx, y0 + 11, country, color, scale=2, bold=True, align='c',
         rot=True)
    text(cx, y0 + 29, subtitle, color, scale=1, align='c', rot=True)
    text(cx, y0 + 41, kind + ' ' + arrow, color, scale=1, bold=True,
         align='c', rot=True)
    text(cx, y0 + 54, date, color, scale=2, bold=True, align='c', rot=True)
    text(cx, y0 + 70, post, color, scale=1, align='c', rot=True)
    clear_rot()


def toll_stamp(cx, cy, r, color):
    """Circular red toll stamp overlapping the endorsement box corner."""
    circle(cx, cy, r, color, 2)
    circle(cx, cy, r - 6, color, 1)
    text(cx, cy - 30, 'PASS TOLL', color, scale=1, bold=True, align='c',
         slope=-0.06)
    text(cx, cy - 13, '18 KR', color, scale=2, bold=True, align='c',
         slope=-0.06)
    text(cx, cy + 6, 'PAID \u2022 HALD 03', color, scale=1, bold=True,
         align='c', slope=-0.06)
    text(cx, cy + 20, '08 MAY 2024', color, scale=1, bold=True, align='c',
         slope=-0.06)


def field_label(x, y, label):
    text(x, y, label, GREY, scale=1)


def field_value(x, y, value, scale=2, color=INK, bold=True):
    text(x, y, value, color, scale=scale, bold=bold)

# ---------------------------------------------------------------- left page
def draw_left_page():
    # paper
    fill_rect(12, 12, 500, 1012, CREAM)
    guilloche(16, 496, 20, 1004, LGREY)
    # faint large circles, like a security print
    ellipse_outline(120, 700, 150, 150, WML)
    ellipse_outline(120, 700, 120, 120, WML)
    ellipse_outline(420, 320, 130, 130, WML)
    # diagonal watermark
    watermark(16, 496, 300, 'ALDORRA', WML)
    watermark(16, 496, 640, 'ALDORRA', WML)

    # header
    emblem(256, 62, 26, TEAL)
    text(256, 100, 'REPUBLIC OF ALDORRA', TEAL, scale=3, bold=True,
         align='c')
    text(256, 126, 'REPUBLIKA ALDORRA', TEAL, scale=2, align='c')
    text(256, 148, 'PASAR \u2022 PASSPORT', DTEAL, scale=2, align='c')
    text(488, 44, 'ALD730518', DRED, scale=2, bold=True, align='r')
    hline(30, 482, 172, TEAL, 2)

    # ---- portrait (left) + data fields (right)
    portrait(30, 188, 182, 384)
    text(106, 390, 'FOTOGRAF / PHOTOGRAPH', GREY, scale=1, align='c')

    fx = 200
    # row 1: type / code / passport no (three columns)
    field_label(fx, 192, 'TIP / TYPE')
    field_value(fx, 206, 'P')
    field_label(fx + 92, 192, 'KOD / CODE')
    field_value(fx + 92, 206, 'ALD')
    field_label(fx + 188, 192, 'PAS NR. / PASSPORT NO.')
    field_value(fx + 188, 206, 'ALD730518')
    # surname / given names
    field_label(fx, 240, 'FAMAR / SURNAME')
    field_value(fx, 254, 'HALD')
    field_label(fx, 284, 'ANVAR / GIVEN NAMES')
    field_value(fx, 298, 'JOREN')
    # nationality
    field_label(fx, 328, 'VATENAR / NATIONALITY')
    field_value(fx, 342, 'ALDORRAN')
    # dob / sex
    field_label(fx, 372, 'DUNVAR / DATE OF BIRTH')
    field_value(fx, 386, '03 OCT 1988')
    field_label(fx + 200, 372, 'KESH / SEX')
    field_value(fx + 200, 386, 'M')

    # ---- lower data block (full width)
    field_label(30, 416, 'DUNVAR-ESH / PLACE OF BIRTH')
    field_value(30, 430, 'HALD VALLEY')
    field_label(30, 460, 'ISHAR / DATE OF ISSUE')
    field_value(30, 474, '22 APR 2024')
    field_label(290, 460, 'ISHDAL / DATE OF EXPIRY')
    field_value(290, 474, '21 APR 2034')
    field_label(30, 504, 'DAFTAR / AUTHORITY')
    field_value(30, 518, 'PASS REGISTRY, HALD VALLEY')
    field_label(30, 548, 'SHAKH NR. / PERSONAL NO.')
    field_value(30, 562, '0310 1003 88')

    # ---- signature (left) + ghost photo (right)
    text(40, 606, 'Joren Hald', SIGBLUE, scale=3, bold=False, slope=-0.10)
    hline(30, 330, 636, INK, 1)
    field_label(30, 644, "IMZAR / HOLDER'S SIGNATURE")
    ghost_photo(400, 592, 480, 687)
    text(440, 692, 'GHOST IMAGE', GREY, scale=1, align='c')

    # ---- observations
    field_label(30, 668, 'MERKAR / OBSERVATIONS')
    obs = ('Holder is a licensed mountain guide, licence G-0730. '
           'High-pass transit endorsement on page 5.')
    for i, ln in enumerate(wrap(obs, 452, scale=1)):
        text(30, 684 + i * 13, ln, INK, scale=1)

    # ---- ruled notes
    field_label(30, 724, 'NOTES / ANTECKNINGAR')
    for yy in (744, 766, 788):
        hline(30, 482, yy, (190, 196, 184), 1)
    text(30, 750, 'Entries recorded by the Pass Registry, Hald Valley.',
         GREY, scale=1)

    # ---- repeating band
    text(256, 806, 'ALDORRA \u2022 REPUBLIKA ALDORRA \u2022 ALDORRA \u2022 '
         'REPUBLIKA ALDORRA', GREY, scale=1, align='c')

    # ---- MRZ box
    fill_rect(24, 828, 488, 952, WHITE)
    line(24, 828, 488, 828, INK, 2)
    line(24, 952, 488, 952, INK, 2)
    line(24, 828, 24, 952, INK, 2)
    line(488, 828, 488, 952, INK, 2)
    text(30, 848, MRZ1, BLACK, scale=2, adv=10)
    text(30, 892, MRZ2, BLACK, scale=2, adv=10)

    # ---- footer
    text(256, 968, 'THIS PASSPORT REMAINS THE PROPERTY OF THE '
         'REPUBLIC OF ALDORRA', GREY, scale=1, align='c')
    text(30, 990, '2', GREY, scale=1)


# --------------------------------------------------------------- right page
STAMPS = [
    # (country, subtitle, kind, date, post, colour)
    ('ALDORRA', 'Republika Aldorra', 'DEPARTURE', '08 MAY 2024',
     'HALD PASS 03', RED),
    ('TARNOVIA', 'Tarnovian Republic', 'ARRIVAL', '08 MAY 2024',
     'VEYL GATE', BLUE),
    ('TARNOVIA', 'Tarnovian Republic', 'DEPARTURE', '24 MAY 2024',
     'VEYL GATE', BLUE),
    ('ALDORRA', 'Republika Aldorra', 'ARRIVAL', '24 MAY 2024',
     'HALD PASS 03', RED),
    ('ALDORRA', 'Republika Aldorra', 'DEPARTURE', '19 JUL 2024',
     'DRAKKEN PASS', RED),
    ('KALDORIA', 'Kaldorian Tasavald', 'ARRIVAL', '19 JUL 2024',
     'VARN KELD', GREEN),
    ('KALDORIA', 'Kaldorian Tasavald', 'DEPARTURE', '02 AUG 2024',
     'VARN KELD', GREEN),
    ('ALDORRA', 'Republika Aldorra', 'ARRIVAL', '02 AUG 2024',
     'DRAKKEN PASS', RED),
    ('VESKARA', 'Veskaran Republic', 'ARRIVAL', '11 OCT 2024',
     'THARN CROSSING', PURPLE),
    ('VESKARA', 'Veskaran Republic', 'DEPARTURE', '25 OCT 2024',
     'THARN CROSSING', PURPLE),
]


def draw_right_page():
    fill_rect(524, 12, 1012, 1012, CREAM)
    guilloche(528, 1008, 20, 1004, LGREY)
    ellipse_outline(768, 480, 170, 170, WML)
    ellipse_outline(768, 480, 140, 140, WML)
    watermark(528, 1008, 420, 'ALDORRA', WML)

    # header
    text(540, 40, 'VIZAR \u2022 VISAS', TEAL, scale=3, bold=True)
    text(996, 40, '5', TEAL, scale=2, bold=True, align='r')
    hline(540, 996, 72, TEAL, 2)

    # ---- high-pass transit endorsement box
    fill_rect(540, 86, 996, 232, WHITE)
    line(540, 86, 996, 86, BLUE, 2)
    line(540, 232, 996, 232, BLUE, 2)
    line(540, 86, 540, 232, BLUE, 2)
    line(996, 86, 996, 232, BLUE, 2)
    text(556, 96, 'HIGH-PASS TRANSIT ENDORSEMENT', BLUE, scale=2,
         bold=True)
    endorse = ('HALD PASS \u2014 ISSUED ALDORRA 22 APR 2024. HALD AND '
               'DRAKKEN PASSES ARE CLOSED 1 NOV \u2013 30 APR. BEARER MAY '
               'CROSS ONLY 1 MAY \u2013 31 OCT, AND SHALL REPORT TO THE '
               'PASS WARDEN. VALID WITH GUIDE LICENCE G-0730.')
    for i, ln in enumerate(wrap(endorse, 340, scale=1)):
        text(556, 122 + i * 13, ln, INK, scale=1)
    # circular toll stamp overlapping the box corner
    toll_stamp(936, 204, 50, RED)

    # ---- ten stamps, 2 columns x 5 rows
    for idx, (country, subtitle, kind, date, post, color) in enumerate(
            STAMPS):
        col = idx % 2
        row = idx // 2
        x0 = 540 + col * 240
        y0 = 256 + row * 90
        rot = 1.5 if idx % 2 == 0 else -1.5
        draw_stamp(x0, y0, 216, 86, color, country, subtitle, kind, date,
                   post, rot)

    # ---- Kaldoria visitor visa box
    fill_rect(540, 720, 996, 860, (232, 240, 224))
    line(540, 720, 996, 720, GREEN, 2)
    line(540, 860, 996, 860, GREEN, 2)
    line(540, 720, 540, 860, GREEN, 2)
    line(996, 720, 996, 860, GREEN, 2)
    text(556, 730, 'KALDORIA \u2022 VISITOR VISA', GREEN, scale=2,
         bold=True)
    text(980, 734, 'KALDORIAN TASAVALD', GREEN, scale=1, align='r')
    visa_rows = [
        ('TYPE:', 'C \u2022 SINGLE ENTRY', 'DURATION OF STAY:', '30 DAYS'),
        ('VALID FROM:', '01 JUL 2024', 'UNTIL:', '30 AUG 2024'),
        ('ISSUED AT:', 'HALD VALLEY, 15 JUN 2024', 'FEE:', '45 ALD'),
    ]
    for i, (l1, v1, l2, v2) in enumerate(visa_rows):
        yy = 760 + i * 32
        text(556, yy, l1, GREY, scale=1)
        text(556, yy + 13, v1, INK, scale=1, bold=True)
        text(800, yy, l2, GREY, scale=1)
        text(800, yy + 13, v2, INK, scale=1, bold=True)

    # ---- mountain guide licence box
    fill_rect(540, 874, 996, 950, WHITE)
    line(540, 874, 996, 874, DTEAL, 2)
    line(540, 950, 996, 950, DTEAL, 2)
    line(540, 874, 540, 950, DTEAL, 2)
    line(996, 874, 996, 950, DTEAL, 2)
    text(556, 884, 'MOUNTAIN GUIDE LICENCE', DTEAL, scale=2, bold=True)
    lic = ('No. G-0730 \u00b7 Holder JOREN HALD \u00b7 Valid 22 APR 2024 '
           '\u2013 21 APR 2029 \u00b7 Issued by ALDORRA MOUNTAIN GUILD, '
           'HALD VALLEY.')
    for i, ln in enumerate(wrap(lic, 424, scale=1)):
        text(556, 908 + i * 13, ln, INK, scale=1)

    # ---- footer
    text(540, 972, 'VIZAR', GREY, scale=1)
    text(996, 972, 'ALD730518', GREY, scale=1, align='r')


# -------------------------------------------------------------------- render
def render():
    fill_rect(0, 0, W, H, TEAL)
    draw_left_page()
    draw_right_page()
    # centre spine
    fill_rect(500, 12, 524, 1012, DTEAL)
    vline(511, 12, 1012, (12, 30, 22), 2)


def png_bytes():
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += buf[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack('>I', len(data)) + typ + data
        c += struct.pack('>I', zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
            chunk(b'IDAT', comp) + chunk(b'IEND', b''))


def main():
    render()
    data = png_bytes()
    out_dir = os.environ.get('MAKEFUN_OUTPUT_DIR') or '.'
    path = os.path.join(out_dir, 'entry.png')
    with open(path, 'wb') as f:
        f.write(data)
    print('wrote %s (%d bytes)' % (path, len(data)))
    print('MRZ1: %s' % MRZ1)
    print('MRZ2: %s' % MRZ2)
    print('check digits: doc=%d dob=%d exp=%d personal=%d composite=%d' % (
        DOC_CD, DOB_CD, EXP_CD, OPT_CD, COMP_CD))


if __name__ == '__main__':
    main()
