#!/usr/bin/env python3
"""Kaldoria mountain-guide passport spread.

Fresh build from the design spec: a dense 2-page passport spread for the
invented Republic of Kaldoria, holder Elin Sara Tharne, licensed mountain
guide, licence G-0913. Pure Python 3 stdlib only (no fonts, no image
libraries, no network). Renders pixel by pixel into an RGB raster and
writes a deterministic PNG.

Usage: python3 main.py [output.png]   (default: $OUTPUT or /output/entry.png)
"""

import math
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------- palette
MAROON = (110, 30, 35)      # headings / borders
CREAM = (245, 238, 221)     # paper
INK = (30, 42, 38)          # body ink
GOLD = (176, 141, 62)       # rules / frames
RED = (146, 58, 44)         # Kaldoria stamps
BLUE = (38, 84, 138)        # Tarnovia stamps / endorsement
GREEN = (46, 110, 74)       # Veskara stamps / visa box
COVER = (58, 14, 18)        # dark cover edge
PAPER_LINE = (226, 214, 190)  # faint guilloche
WATER = (233, 224, 203)     # faint watermark
WHITE = (255, 255, 255)
SKIN = (214, 178, 150)
SKIN_D = (170, 130, 105)
HAIR = (48, 38, 32)
JACKET = (58, 64, 70)
MAGENTA = (255, 0, 255)     # transparent key for sub-canvases

W, H = 1024, 1024

# ------------------------------------------------------- hand-drawn 5x7 font
# Each glyph: 7 rows of 5 bits ('1' = ink). Uppercase, lowercase, digits,
# space and punctuation.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    'a': ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    'b': ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    'c': ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    'd': ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    'e': ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    'f': ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    'g': ("01111", "10001", "10001", "01111", "00001", "00010", "01100"),
    'h': ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    'i': ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    'j': ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    'k': ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    'l': ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    'm': ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    'n': ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    'o': ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    'p': ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    'q': ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    'r': ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    's': ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    't': ("00100", "00100", "11110", "00100", "00100", "00100", "00011"),
    'u': ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    'v': ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    'w': ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    'x': ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    'y': ("00000", "10001", "10001", "01111", "00001", "00010", "01100"),
    'z': ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '/': ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '&': ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '+': ("00000", "00100", "00100", "01110", "00100", "00100", "00000"),
    '<': ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    '>': ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    '*': ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '·': ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
}


def text_width(s, scale, spacing=0):
    """Pixel width of s at the given scale."""
    if not s:
        return 0
    return len(s) * (5 * scale + spacing) - spacing


# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, fill=None):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        if fill is not None:
            self.fill_rect(0, 0, w, h, fill)

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.buf[i], self.buf[i + 1], self.buf[i + 2])

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                self.buf[i] = c[0]
                self.buf[i + 1] = c[1]
                self.buf[i + 2] = c[2]
                i += 3

    def hline(self, x, y, length, c, thick=1):
        for t in range(thick):
            self.fill_rect(x, y + t, length, 1, c)

    def vline(self, x, y, length, c, thick=1):
        for t in range(thick):
            self.fill_rect(x + t, y, 1, length, c)

    def rect(self, x, y, w, h, c, thick=1):
        self.hline(x, y, w, c, thick)
        self.hline(x, y + h - thick, w, c, thick)
        self.vline(x, y, h, c, thick)
        self.vline(x + w - thick, y, h, c, thick)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.px(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def thick_line(self, x0, y0, x1, y1, c, thick=2):
        for k in range(thick):
            self.line(x0, y0 + k, x1, y1 + k, c)

    def circle(self, cx, cy, r, c):
        # Midpoint circle outline.
        x = 0
        y = r
        d = 1 - r
        while x <= y:
            for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                           (x, -y), (y, -x), (-x, -y), (-y, -x)):
                self.px(cx + sx, cy + sy, c)
            if d < 0:
                d += 2 * x + 3
            else:
                d += 2 * (x - y) + 5
                y -= 1
            x += 1

    def circle_arc(self, cx, cy, r, a0, a1, c):
        steps = max(8, int(abs(a1 - a0) * r))
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            self.px(int(round(cx + r * math.cos(a))),
                    int(round(cy + r * math.sin(a))), c)

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.hline(cx - dx, yy, 2 * dx + 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        steps = max(24, int(2 * math.pi * max(rx, ry)))
        for i in range(steps):
            a = 2 * math.pi * i / steps
            self.px(int(round(cx + rx * math.cos(a))),
                    int(round(cy + ry * math.sin(a))), c)

    def ellipse_fill(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            dy = (yy - cy) / float(ry)
            if abs(dy) > 1:
                continue
            dx = int(rx * math.sqrt(1 - dy * dy))
            self.hline(cx - dx, yy, 2 * dx + 1, c)

    def poly_fill(self, pts, c):
        # Scanline polygon fill.
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / float(y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.hline(int(round(xs[k])), y,
                           int(round(xs[k + 1])) - int(round(xs[k])) + 1, c)

    def round_rect(self, x, y, w, h, r, c, thick=1):
        """Rounded-rectangle outline of the given thickness."""
        for t in range(thick):
            self.hline(x + r, y + t, w - 2 * r, c)
            self.hline(x + r, y + h - 1 - t, w - 2 * r, c)
            self.vline(x + t, y + r, h - 2 * r, c)
            self.vline(x + w - 1 - t, y + r, h - 2 * r, c)
        self.circle_arc(x + r, y + r, r, math.pi, 1.5 * math.pi, c)
        self.circle_arc(x + w - r - 1, y + r, r, 1.5 * math.pi, 2 * math.pi, c)
        self.circle_arc(x + w - r - 1, y + h - r - 1, r, 0, 0.5 * math.pi, c)
        self.circle_arc(x + r, y + h - r - 1, r, 0.5 * math.pi, math.pi, c)

    def round_rect_fill(self, x, y, w, h, r, c):
        """Filled rounded rectangle."""
        self.fill_rect(x + r, y, w - 2 * r, h, c)
        self.fill_rect(x, y + r, w, h - 2 * r, c)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.disc(cx, cy, r, c)

    def blit(self, src, dx, dy, fade=None, fade_to=None):
        """Copy src onto self. fade in [0,1]: blend src toward fade_to."""
        for yy in range(src.h):
            ty = dy + yy
            if ty < 0 or ty >= self.h:
                continue
            for xx in range(src.w):
                tx = dx + xx
                if tx < 0 or tx >= self.w:
                    continue
                c = src.get(xx, yy)
                if c == MAGENTA:
                    continue
                if fade is not None:
                    c = tuple(int(round(c[k] * (1 - fade) + fade_to[k] * fade))
                              for k in range(3))
                self.px(tx, ty, c)

    def blit_rotated(self, src, cx, cy, angle_deg):
        """Paste src rotated about its centre onto (cx, cy)."""
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        hw, hh = src.w / 2.0, src.h / 2.0
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        rot = [(x * ca - y * sa, x * sa + y * ca) for x, y in corners]
        minx = int(cx + min(p[0] for p in rot)) - 1
        maxx = int(cx + max(p[0] for p in rot)) + 1
        miny = int(cy + min(p[1] for p in rot)) - 1
        maxy = int(cy + max(p[1] for p in rot)) + 1
        for ty in range(miny, maxy + 1):
            for tx in range(minx, maxx + 1):
                dx, dy = tx - cx, ty - cy
                sx = dx * ca + dy * sa + hw
                sy = -dx * sa + dy * ca + hh
                ix, iy = int(sx), int(sy)
                if 0 <= ix < src.w and 0 <= iy < src.h:
                    c = src.get(ix, iy)
                    if c != MAGENTA:
                        self.px(tx, ty, c)


# --------------------------------------------------------------------- text
def draw_glyph(cv, x, y, ch, scale, color, shear=0):
    glyph = FONT.get(ch)
    if glyph is None:
        return
    for r, row in enumerate(glyph):
        for col, bit in enumerate(row):
            if bit == '1':
                ox = x + col * scale + (r - 3) * shear
                cv.fill_rect(ox, y + r * scale, scale, scale, color)


def draw_text(cv, x, y, s, scale, color, bold=False, spacing=0, shear=0,
              align=None, cx=None):
    """Draw s; align='center' centres on cx."""
    adv = 5 * scale + spacing
    if align == 'center' and cx is not None:
        x = cx - text_width(s, scale, spacing) // 2
    dx = max(1, scale // 2) if bold else 0
    for ch in s:
        draw_glyph(cv, x, y, ch, scale, color, shear=shear)
        if dx:
            draw_glyph(cv, x + dx, y, ch, scale, color, shear=shear)
        x += adv
    return x


def field(cv, x, y, label, value, vscale=2, color=INK, vcolor=None):
    """Small maroon label above a bold value. Returns value bottom y."""
    draw_text(cv, x, y, label, 1, MAROON)
    draw_text(cv, x, y + 11, value, vscale, vcolor or color, bold=True)
    return y + 11 + 7 * vscale


# ------------------------------------------------------- security background
def guilloche(cv, x0, x1, y0, y1):
    """Fine wavy horizontal security lines across a page region."""
    y = y0 + 8
    while y < y1:
        prev = None
        for x in range(x0, x1, 4):
            yy = y + int(round(3 * math.sin(x / 26.0 + y / 9.0)))
            if prev is not None:
                cv.line(prev[0], prev[1], x, yy, PAPER_LINE)
            prev = (x, yy)
        y += 24


def watermark(cv, cx, cy, word, angle=-28):
    """One faint huge diagonal watermark word, pre-blended on cream."""
    scale = 7
    tw = text_width(word, scale, spacing=4)
    th = 7 * scale
    tmp = Canvas(tw + 40, th + 40, fill=MAGENTA)
    draw_text(tmp, 20, 20, word, scale, WATER, bold=True, spacing=4)
    cv.blit_rotated(tmp, cx, cy, angle)


# ------------------------------------------------------------------ portrait
def build_portrait():
    """Drawn portrait: woman mountain guide, dark hair in a low knot,
    outdoor jacket with a high collar, plain light ground. 150 x 210."""
    p = Canvas(150, 210, fill=(198, 208, 214))
    # shoulders / jacket
    p.poly_fill([(8, 210), (28, 168), (55, 152), (95, 152), (122, 168),
                 (142, 210)], JACKET)
    # high collar with maroon band
    p.poly_fill([(52, 168), (58, 148), (92, 148), (98, 168)], (88, 40, 44))
    p.hline(58, 150, 34, GOLD, 2)
    p.vline(74, 168, 42, (40, 44, 48), 2)  # zipper
    # neck
    p.fill_rect(63, 126, 24, 30, SKIN)
    p.fill_rect(63, 126, 24, 6, SKIN_D)
    # hair behind head
    p.ellipse_fill(75, 88, 43, 56, HAIR)
    # low knot (bun) at the nape, right side
    p.disc(112, 152, 13, HAIR)
    p.disc(112, 152, 7, (38, 30, 25))
    # ears
    p.ellipse_fill(34, 96, 5, 9, SKIN)
    p.ellipse_fill(116, 96, 5, 9, SKIN)
    # face
    p.ellipse_fill(75, 94, 36, 46, SKIN)
    # hair cap + side strands framing the face
    p.ellipse_fill(75, 50, 39, 24, HAIR)
    p.poly_fill([(38, 60), (50, 60), (48, 148), (38, 148)], HAIR)
    p.poly_fill([(100, 60), (112, 60), (112, 148), (102, 148)], HAIR)
    # brows
    p.thick_line(52, 80, 67, 77, HAIR, 2)
    p.thick_line(83, 77, 98, 80, HAIR, 2)
    # eyes
    p.ellipse_fill(59, 89, 6, 3, WHITE)
    p.ellipse_fill(91, 89, 6, 3, WHITE)
    p.disc(59, 89, 2, (28, 24, 20))
    p.disc(91, 89, 2, (28, 24, 20))
    # nose
    p.line(75, 92, 73, 105, SKIN_D)
    p.line(73, 105, 78, 107, SKIN_D)
    # mouth
    p.line(66, 119, 75, 121, (140, 60, 55))
    p.line(75, 121, 84, 119, (140, 60, 55))
    # soft cheek shading
    p.ellipse_fill(52, 106, 7, 4, (206, 158, 132))
    p.ellipse_fill(98, 106, 7, 4, (206, 158, 132))
    return p


def ghost_photo(portrait, w, h, fade=0.62):
    """Small faint copy of the portrait, faded toward cream."""
    g = Canvas(w, h)
    for yy in range(h):
        sy = yy * portrait.h // h
        for xx in range(w):
            sx = xx * portrait.w // w
            c = portrait.get(sx, sy)
            g.px(xx, yy, tuple(int(round(c[k] * (1 - fade) + CREAM[k] * fade))
                               for k in range(3)))
    return g


# -------------------------------------------------------------------- stamps
def build_stamp(country, native, action, date, post, color, angle):
    """One rectangular entry/exit stamp, 225 x 100, slightly rotated."""
    s = Canvas(235, 106, fill=MAGENTA)
    x, y, w, h = 5, 5, 225, 96
    s.round_rect(x, y, w, h, 8, color, thick=2)
    s.round_rect(x + 5, y + 5, w - 10, h - 10, 5, color, thick=1)
    arrow = "->" if action == "ARRIVAL" else "<-"
    draw_text(s, 0, y + 10, country, 2, color, bold=True,
              align='center', cx=x + w // 2)
    draw_text(s, 0, y + 29, native, 1, color, align='center', cx=x + w // 2)
    s.hline(x + 14, y + 43, w - 28, color, 1)
    draw_text(s, 0, y + 48, action + " " + arrow, 1, color, bold=True,
              align='center', cx=x + w // 2)
    draw_text(s, 0, y + 62, date, 2, color, bold=True,
              align='center', cx=x + w // 2)
    draw_text(s, 0, y + 82, post, 1, color, align='center', cx=x + w // 2)
    return s


def build_toll_stamp():
    """Circular red pass-toll stamp, 120 x 120."""
    s = Canvas(124, 124, fill=MAGENTA)
    cx, cy = 62, 62
    s.circle(cx, cy, 58, RED)
    s.circle(cx, cy, 57, RED)
    s.circle(cx, cy, 50, RED)
    draw_text(s, 0, 24, "PASS TOLL", 1, RED, bold=True,
              align='center', cx=cx)
    draw_text(s, 0, 40, "15 KR", 3, RED, bold=True, align='center', cx=cx)
    draw_text(s, 0, 72, "PAID · THARN 03", 1, RED, bold=True,
              align='center', cx=cx)
    draw_text(s, 0, 88, "14 MAY 2024", 1, RED, bold=True,
              align='center', cx=cx)
    return s


# ----------------------------------------------------------------------- MRZ
def mrz_check(s):
    """ICAO 9303 check digit: A=10..Z=35, '<'=0, weights 7-3-1."""
    total = 0
    for i, ch in enumerate(s):
        if ch == '<':
            v = 0
        elif ch.isdigit():
            v = int(ch)
        else:
            v = ord(ch) - 55
        total += v * (7, 3, 1)[i % 3]
    return total % 10


def mrz_lines():
    line1 = "P<KLDTHARNE<<ELIN<SARA" + "<" * 22
    doc = "KD2049173"
    dob = "900617"      # 17 JUN 1990
    exp = "340321"      # 21 MAR 2034
    opt = "<" * 14
    body = (doc + str(mrz_check(doc)) + "KLD" + dob + str(mrz_check(dob))
            + "F" + exp + str(mrz_check(exp)) + opt + str(mrz_check(opt)))
    line2 = body + str(mrz_check(body))
    assert len(line1) == 44 and len(line2) == 44, (line1, line2)
    return line1, line2


# -------------------------------------------------------------------- emblem
def draw_emblem(cv, cx, cy, r):
    """Circular emblem: ring + mountain peaks."""
    cv.circle(cx, cy, r, MAROON)
    cv.circle(cx, cy, r - 1, MAROON)
    cv.circle(cx, cy, r - 5, GOLD)
    cv.poly_fill([(cx - 15, cy + 9), (cx - 5, cy - 11), (cx + 2, cy + 2),
                  (cx + 7, cy - 6), (cx + 16, cy + 9)], MAROON)
    cv.poly_fill([(cx - 5, cy - 11), (cx - 2, cy - 4), (cx - 8, cy - 4)],
                 CREAM)
    cv.hline(cx - 16, cy + 12, 32, MAROON, 2)


# -------------------------------------------------------------------- render
def render():
    cv = Canvas(W, H, fill=COVER)
    # two cream pages inside the dark cover edge
    cv.fill_rect(16, 10, 494, 1004, CREAM)    # left page
    cv.fill_rect(514, 10, 494, 1004, CREAM)   # right page
    # gutter shadow where the pages meet
    for i, shade in enumerate(((150, 140, 120), (180, 170, 150),
                               (205, 195, 175), (225, 215, 195))):
        cv.vline(508 + i, 10, 1004, shade)
        cv.vline(515 - i, 10, 1004, shade)
    # gold inner frames
    cv.rect(22, 16, 482, 992, GOLD)
    cv.rect(520, 16, 482, 992, GOLD)
    # guilloche + watermarks on both pages
    guilloche(cv, 26, 504, 20, 1008)
    guilloche(cv, 524, 1002, 20, 1008)
    watermark(cv, 263, 520, "KALDORIA")
    watermark(cv, 761, 520, "KALDORIA")

    # ============================================================ LEFT PAGE
    # page number + passport no
    draw_text(cv, 34, 30, "1", 2, MAROON, bold=True)
    draw_text(cv, 0, 30, "KD2049173", 2, MAROON, bold=True,
              align='center', cx=452)
    # emblem + titles
    draw_emblem(cv, 263, 62, 26)
    draw_text(cv, 0, 98, "REPUBLIC OF KALDORIA", 3, MAROON, bold=True,
              align='center', cx=263)
    draw_text(cv, 0, 126, "RESPUBLIKA KALDORIA", 2, MAROON, spacing=2,
              align='center', cx=263)
    draw_text(cv, 0, 148, "PASAR · PASSPORT", 2, INK, spacing=3,
              align='center', cx=263)
    cv.hline(30, 170, 466, GOLD, 2)
    cv.hline(30, 174, 466, GOLD, 1)

    # photo, framed, with caption strip
    portrait = build_portrait()
    cv.blit(portrait, 30, 188)
    cv.rect(30, 188, 150, 210, INK, 2)
    cv.rect(33, 191, 144, 204, GOLD, 1)
    cv.fill_rect(30, 376, 150, 22, INK)
    draw_text(cv, 0, 383, "PHOTOGRAPH", 1, CREAM, bold=True,
              align='center', cx=105)

    # data fields, right of the photo
    field(cv, 198, 188, "TIP / TYPE", "P")
    field(cv, 258, 188, "KOD / CODE", "KLD")
    field(cv, 340, 188, "PAS NR. / PASSPORT NO.", "KD2049173")
    field(cv, 198, 238, "FAMAR / SURNAME", "THARNE")
    field(cv, 198, 288, "ANVAR / GIVEN NAMES", "ELIN SARA")
    field(cv, 198, 338, "VATENAR / NATIONALITY", "KALDORIAN")
    field(cv, 198, 388, "DUNVAR / DATE OF BIRTH", "17 JUN 1990")
    field(cv, 400, 388, "KESH / SEX", "F")
    # signature
    draw_text(cv, 198, 438, "IMZAR / HOLDER'S SIGNATURE", 1, MAROON)
    draw_text(cv, 198, 452, "Elin Tharne", 2, (38, 64, 120), shear=1)
    cv.hline(198, 478, 220, INK, 1)

    # data fields below the photo
    field(cv, 30, 500, "DUNVAR-ESH / PLACE OF BIRTH", "VARN KELD")
    field(cv, 30, 550, "ISHAR / DATE OF ISSUE", "22 MAR 2024")
    field(cv, 280, 550, "ISHDAL / DATE OF EXPIRY", "21 MAR 2034")
    field(cv, 30, 600, "DAFTAR / AUTHORITY", "PASS REGISTRY, VARN KELD")
    field(cv, 30, 650, "SHAKH NR. / PERSONAL NO.", "3310 0617 82")
    # ghost photo, bottom-right of the data area
    cv.blit(ghost_photo(portrait, 84, 110), 400, 496)
    cv.rect(400, 496, 84, 110, (120, 110, 95), 1)

    # observations
    draw_text(cv, 30, 700, "MERKAR / OBSERVATIONS", 1, MAROON)
    draw_text(cv, 30, 716, "Holder is a licensed mountain", 2, INK)
    draw_text(cv, 30, 734, "guide, licence G-0913. High-pass", 2, INK)
    draw_text(cv, 30, 752, "transit endorsement on page 5.", 2, INK)

    # MRZ strip
    cv.fill_rect(24, 800, 478, 150, WHITE)
    cv.rect(24, 800, 478, 150, INK, 2)
    line1, line2 = mrz_lines()
    draw_text(cv, 32, 824, line1, 2, INK, spacing=0)
    draw_text(cv, 32, 866, line2, 2, INK, spacing=0)
    cv.hline(32, 912, 462, GOLD, 1)
    draw_text(cv, 0, 924, "KALDORIA", 1, MAROON, bold=True,
              align='center', cx=263)

    # =========================================================== RIGHT PAGE
    draw_text(cv, 530, 40, "VIZAR · VISAS", 3, MAROON, bold=True)
    draw_text(cv, 0, 40, "5", 2, MAROON, bold=True, align='center', cx=984)
    cv.hline(530, 72, 462, GOLD, 2)
    cv.hline(530, 76, 462, GOLD, 1)

    # high-pass transit endorsement box
    cv.fill_rect(530, 88, 462, 172, (238, 242, 248))
    cv.rect(530, 88, 462, 172, BLUE, 2)
    draw_text(cv, 544, 100, "HIGH-PASS TRANSIT ENDORSEMENT", 2, BLUE,
              bold=True)
    draw_text(cv, 544, 120, "THARN DAL-VEYL · ISSUED VARN KELD 22 MAR 2024",
              1, INK)
    endorse = [
        "THARN AND DRAKKEN PASSES ARE",
        "CLOSED 1 NOV - 30 APR. BEARER",
        "MAY CROSS ONLY 1 MAY - 31 OCT,",
        "AND SHALL REPORT TO THE PASS",
        "HUT WARDEN. VALID WITH",
        "GUIDE LICENCE G-0913.",
    ]
    for i, ln in enumerate(endorse):
        draw_text(cv, 544, 140 + i * 17, ln, 2, INK)

    # circular pass-toll stamp overlapping the endorsement corner
    cv.blit_rotated(build_toll_stamp(), 936, 258, -8)

    # eight rectangular entry/exit stamps, 2 columns x 4 rows
    stamps = [
        ("KALDORIA", "Respublika Kaldoria", "DEPARTURE", "14 MAY 2024",
         "THARN PASS 03", RED, -2),
        ("TARNOVIA", "Tarnovia", "ARRIVAL", "14 MAY 2024",
         "VEYL BORDER POST", BLUE, 1),
        ("TARNOVIA", "Tarnovia", "DEPARTURE", "28 MAY 2024",
         "VEYL BORDER POST", BLUE, 2),
        ("KALDORIA", "Respublika Kaldoria", "ARRIVAL", "28 MAY 2024",
         "THARN PASS 03", RED, -1),
        ("KALDORIA", "Respublika Kaldoria", "DEPARTURE", "09 SEP 2025",
         "DRAKKEN PASS 01", RED, 1),
        ("VESKARA", "Veskara", "ARRIVAL", "09 SEP 2025",
         "DRAKKEN GATE", GREEN, -2),
        ("VESKARA", "Veskara", "DEPARTURE", "23 SEP 2025",
         "DRAKKEN GATE", GREEN, 2),
        ("KALDORIA", "Respublika Kaldoria", "ARRIVAL", "23 SEP 2025",
         "DRAKKEN PASS 01", RED, -1),
    ]
    rows_y = [320, 430, 714, 826]
    cols_x = [530, 767]
    for idx, st in enumerate(stamps):
        row, col = divmod(idx, 2)
        cx = cols_x[col] + 112
        cy = rows_y[row] + 50
        cv.blit_rotated(build_stamp(*st), cx, cy, st[6])

    # Tarnovia visitor visa box, between the stamp rows
    cv.fill_rect(530, 538, 462, 162, (238, 246, 238))
    cv.rect(530, 538, 462, 162, GREEN, 2)
    draw_text(cv, 544, 550, "TARNOVIA · VISITOR VISA", 2, GREEN, bold=True)
    draw_text(cv, 544, 570, "TARNOVIAN TASAVALD", 1, GREEN, bold=True)
    field(cv, 544, 592, "TYPE", "C · SINGLE ENTRY")
    field(cv, 800, 592, "DURATION OF STAY", "30 DAYS")
    field(cv, 544, 632, "VALID FROM", "01 MAY 2025")
    field(cv, 800, 632, "UNTIL", "30 MAY 2025")
    draw_text(cv, 544, 672, "ISSUED AT", 1, MAROON)
    draw_text(cv, 544, 683, "VARN KELD, 18 APR 2025", 1, INK, bold=True)
    field(cv, 800, 672, "FEE", "45 TVR")

    # footer
    draw_text(cv, 530, 968, "VIZAR", 1, MAROON, bold=True)
    draw_text(cv, 0, 968, "KD2049173", 2, MAROON, bold=True,
              align='center', cx=948)
    return cv


# ---------------------------------------------------------------------- PNG
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(path, cv):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.buf[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "OUTPUT", "/output/entry.png")
    cv = render()
    write_png(out, cv)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
