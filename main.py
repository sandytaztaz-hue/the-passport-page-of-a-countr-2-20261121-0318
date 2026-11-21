#!/usr/bin/env python3
"""Meridia passport spread generator.

Writes one image, /output/entry.png: an open passport spread for the
invented Republic of Meridia -- data page on the left, visa and stamp
page on the right. Pure standard library: the picture is drawn pixel
by pixel (no fonts, no image libraries, no network) so it runs in the
sandbox exactly as it runs here. Every date is consistent: the
passport was issued 02 JUN 2023 and every stamp falls after that date,
in ascending order, each arrival matched by a later departure.
"""

import math
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------- font
# A hand-drawn 5x7 bitmap font. Each glyph is 7 rows of 5 cells,
# '#' ink, '.' blank. One size only; callers scale it.
FONT = {
    'A': ("..#..", ".#.#.", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    '-': (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    '/': ("....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."),
    '(': ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ')': (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    ':': (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '&': (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
    '+': (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    '<': ("...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."),
    '>': (".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."),
    '=': (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    '!': ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '?': (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    '*': (".....", ".#.#.", "..#..", "#####", "..#..", ".#.#.", "....."),
    '%': ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "#..##"),
}

GLYPH_W = 5
GLYPH_H = 7


def text_width(text, scale, spacing=None):
    """Pixel width of text rendered at the given scale."""
    if spacing is None:
        spacing = scale
    if not text:
        return 0
    return len(text) * (GLYPH_W * scale + spacing) - spacing


# ------------------------------------------------------------- canvas
class Canvas:
    """An RGB raster with small drawing primitives."""

    def __init__(self, width, height, fill=(255, 255, 255)):
        self.w = width
        self.h = height
        self.px = bytearray(fill[0:1] * 0)  # placeholder, replaced below
        self.px = bytearray(width * height * 3)
        for i in range(width * height):
            self.px[3 * i:3 * i + 3] = bytes(fill)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = 3 * (y * self.w + x)
            self.px[i:i + 3] = bytes(color)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = 3 * (y * self.w + x)
            return tuple(self.px[i:i + 3])
        return (0, 0, 0)

    def fill_rect(self, x0, y0, x1, y1, color):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        row = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            i = 3 * (y * self.w + x0)
            self.px[i:i + len(row)] = row

    def rect(self, x0, y0, x1, y1, color, thick=1):
        self.fill_rect(x0, y0, x1, y0 + thick, color)
        self.fill_rect(x0, y1 - thick, x1, y1, color)
        self.fill_rect(x0, y0, x0 + thick, y1, color)
        self.fill_rect(x1 - thick, y0, x1, y1, color)

    def hline(self, x0, x1, y, color, thick=1):
        self.fill_rect(x0, y, x1, y + thick, color)

    def vline(self, x, y0, y1, color, thick=1):
        self.fill_rect(x, y0, x + thick, y1, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        """Bresenham line with a square brush."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = int(x0), int(y0)
        r = thick // 2
        while True:
            self.fill_rect(x - r, y - r, x - r + thick, y - r + thick, color)
            if x == int(x1) and y == int(y1):
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, color, thick=1):
        for a in range(0, 360):
            t = math.radians(a)
            for k in range(thick):
                self.set(int(cx + (r - k) * math.cos(t)),
                         int(cy + (r - k) * math.sin(t)), color)

    def disc(self, cx, cy, r, color):
        r = int(r)
        for y in range(int(cy) - r, int(cy) + r + 1):
            half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            self.fill_rect(int(cx) - half, y, int(cx) + half + 1, y + 1, color)

    def ellipse(self, cx, cy, rx, ry, color, thick=1):
        for a in range(0, 360):
            t = math.radians(a)
            for k in range(thick):
                self.set(int(cx + (rx - k) * math.cos(t)),
                         int(cy + (ry - k) * math.sin(t)), color)

    def ellipse_fill(self, cx, cy, rx, ry, color):
        for y in range(int(cy) - int(ry), int(cy) + int(ry) + 1):
            v = (y - cy) / max(1, ry)
            half = int(rx * math.sqrt(max(0.0, 1.0 - v * v)))
            self.fill_rect(int(cx) - half, y, int(cx) + half + 1, y + 1, color)

    def poly_fill(self, points, color):
        """Scanline fill of a simple polygon."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[j]), y, int(xs[j + 1]) + 1, y + 1, color)

    def round_rect(self, x0, y0, x1, y1, r, color, thick=1):
        self.hline(x0 + r, x1 - r, y0, color, thick)
        self.hline(x0 + r, x1 - r, y1 - thick, color, thick)
        self.vline(x0, y0 + r, y1 - r, color, thick)
        self.vline(x1 - thick, y0 + r, y1 - r, color, thick)
        for cx, cy, sx, sy in ((x0 + r, y0 + r, -1, -1), (x1 - r, y0 + r, 1, -1),
                               (x0 + r, y1 - r, -1, 1), (x1 - r, y1 - r, 1, 1)):
            for a in range(0, 91):
                t = math.radians(a)
                px = cx + sx * r * math.cos(t)
                py = cy + sy * r * math.sin(t)
                self.fill_rect(int(px), int(py), int(px) + thick,
                               int(py) + thick, color)

    def round_rect_fill(self, x0, y0, x1, y1, r, color):
        self.fill_rect(x0 + r, y0, x1 - r, y1, color)
        self.fill_rect(x0, y0 + r, x1, y1 - r, color)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                       (x0 + r, y1 - r), (x1 - r, y1 - r)):
            self.disc(cx, cy, r, color)

    # ------------------------------------------------------------ text
    def glyph(self, x, y, ch, scale, color, bold=False):
        rows = FONT.get(ch, FONT['?'])
        for ry, row in enumerate(rows):
            for rx, cell in enumerate(row):
                if cell == '#':
                    self.fill_rect(x + rx * scale, y + ry * scale,
                                   x + rx * scale + scale,
                                   y + ry * scale + scale, color)
                    if bold:
                        self.fill_rect(x + rx * scale + 1, y + ry * scale,
                                       x + rx * scale + scale + 1,
                                       y + ry * scale + scale, color)

    def text(self, x, y, s, scale, color, spacing=None, bold=False):
        if spacing is None:
            spacing = scale
        cx = int(x)
        for ch in s:
            self.glyph(cx, int(y), ch.upper() if ch.isalpha() else ch,
                       scale, color, bold=bold)
            cx += GLYPH_W * scale + spacing
        return cx

    def text_center(self, cx, y, s, scale, color, spacing=None, bold=False):
        w = text_width(s, scale, spacing)
        return self.text(cx - w // 2, y, s, scale, color, spacing, bold)

    def text_right(self, x, y, s, scale, color, spacing=None, bold=False):
        w = text_width(s, scale, spacing)
        return self.text(x - w, y, s, scale, color, spacing, bold)

    def blit(self, src, dx, dy, transparent=None):
        for y in range(src.h):
            ty = dy + y
            if ty < 0 or ty >= self.h:
                continue
            for x in range(src.w):
                tx = dx + x
                if tx < 0 or tx >= self.w:
                    continue
                i = 3 * (y * src.w + x)
                c = tuple(src.px[i:i + 3])
                if transparent is not None and c == transparent:
                    continue
                j = 3 * (ty * self.w + tx)
                self.px[j:j + 3] = bytes(c)

    def blit_rotated(self, src, cx, cy, angle_deg, transparent):
        """Blit src centred at (cx, cy), rotated by angle_deg."""
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
                    i = 3 * (iy * src.w + ix)
                    c = tuple(src.px[i:i + 3])
                    if c == transparent:
                        continue
                    self.set(tx, ty, c)


# -------------------------------------------------------------- png out
def _chunk(kind, data):
    out = struct.pack('>I', len(data)) + kind + data
    out += struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(canvas, path):
    ihdr = struct.pack('>IIBBBBB', canvas.w, canvas.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[3 * y * canvas.w:3 * (y + 1) * canvas.w]
    data = (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + _chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


# ------------------------------------------------------------ palette
TEAL = (15, 76, 76)        # cover, headings
TEAL_DK = (9, 52, 52)
TEAL_LT = (38, 110, 108)
CREAM = (245, 238, 221)    # page paper
CREAM_DK = (233, 224, 198)
INK = (30, 42, 38)         # document ink
GOLD = (176, 141, 62)
GOLD_LT = (201, 170, 96)
WHITE = (252, 250, 244)
STAMP_BLUE = (38, 84, 138)
STAMP_RED = (146, 58, 44)
STAMP_PURPLE = (104, 74, 138)
STAMP_GREEN = (46, 110, 74)
SKIN = (198, 148, 108)
SKIN_DK = (176, 124, 86)
HAIR = (46, 32, 24)
BLOUSE = (22, 96, 104)
FAINT = (238, 231, 206)

W, H = 1024, 724


def mrz_check(text):
    """ICAO 9303 check digit for a field (A=10 .. Z=35, '<'=0)."""
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(text):
        if ch.isdigit():
            v = int(ch)
        elif ch == '<':
            v = 0
        else:
            v = ord(ch) - ord('A') + 10
        total += v * weights[i % 3]
    return str(total % 10)


def mrz_lines():
    """The data page's two machine-readable lines, check digits real.

    TD3 layout, 44 columns: document number (9) + check, nationality
    (3), birth date (6) + check, sex (1), expiry (6) + check,
    optional data (14) + check, composite check (1).
    """
    surname = 'VOSS'
    given = 'ELENA<MAR'
    line1 = 'P<MER' + surname + '<<' + given
    line1 = line1 + '<' * (44 - len(line1))
    doc = 'MD4718820'
    doc_c = mrz_check(doc)
    dob = '880314'
    dob_c = mrz_check(dob)
    sex = 'F'
    exp = '330602'
    exp_c = mrz_check(exp)
    personal = '<' * 14
    personal_c = mrz_check(personal)
    line2 = (doc + doc_c + 'MER' + dob + dob_c + sex + exp + exp_c
             + personal + personal_c)
    final_c = mrz_check(line2)
    line2 = line2 + final_c
    assert len(line1) == 44 and len(line2) == 44
    return line1, line2


def guilloche(canvas, x0, y0, x1, y1, color, step=7, amp=3):
    """Fine wavy security lines across a rectangle."""
    for y in range(y0, y1, step):
        for x in range(x0, x1):
            yy = y + int(amp * math.sin((x - x0) / 26.0 + y / 31.0))
            canvas.set(x, yy, color)


def watermark(canvas, x0, y0, x1, y1, word, color):
    """One huge faint diagonal word across a page."""
    scale = 9
    w = text_width(word, scale, spacing=10)
    tmp = Canvas(w + 40, 90, fill=(255, 0, 255))
    tmp.text(20, 12, word, scale, color, spacing=10, bold=True)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    canvas.blit_rotated(tmp, cx, cy, -24, (255, 0, 255))


def emblem(canvas, cx, cy, r, color):
    """Meridia's arms: a ring, three waves and a star."""
    canvas.circle(cx, cy, r, color, thick=2)
    canvas.circle(cx, cy, r - 4, color, thick=1)
    for k, yy in enumerate((cy - 4, cy + 2, cy + 8)):
        wave_r = r - 7 - k
        for a in range(200, 341):
            t = math.radians(a)
            canvas.set(int(cx + wave_r * math.cos(t)),
                       int(yy + 3 * math.sin(t * 2)), color)
    # five-point star above the waves
    sx, sy, sr = cx, cy - 10, 7
    pts = []
    for i in range(10):
        ang = math.radians(-90 + i * 36)
        rr = sr if i % 2 == 0 else sr * 0.45
        pts.append((sx + rr * math.cos(ang), sy + rr * math.sin(ang)))
    canvas.poly_fill([(int(px), int(py)) for px, py in pts], color)


# ------------------------------------------------------------ portrait
def draw_portrait(canvas, x0, y0, x1, y1):
    """The holder's photograph: a drawn portrait in document colours.

    Elena Mar Voss, 38, of Port Selene: dark hair in a low knot, teal
    blouse, plain light ground -- the same palette as the rest of the
    spread, so the portrait belongs to the document, not pasted on it.
    """
    cx = (x0 + x1) // 2
    canvas.fill_rect(x0, y0, x1, y1, (226, 232, 222))
    for i in range(0, y1 - y0, 6):
        shade = 226 - (i % 12)
        canvas.fill_rect(x0, y0 + i, x1, y0 + i + 3, (shade, 234, 228))
    # hair behind the head, falling to the shoulders
    canvas.ellipse_fill(cx, y0 + 62, 42, 50, HAIR)
    canvas.ellipse_fill(cx - 30, y0 + 118, 16, 34, HAIR)
    canvas.ellipse_fill(cx + 30, y0 + 118, 16, 34, HAIR)
    canvas.disc(cx, y0 + 34, 15, HAIR)
    # shoulders and blouse
    canvas.poly_fill([(x0 + 8, y1), (x1 - 8, y1), (x1 - 22, y0 + 148),
                      (cx + 26, y0 + 132), (cx - 26, y0 + 132),
                      (x0 + 22, y0 + 148)], BLOUSE)
    canvas.poly_fill([(cx - 26, y0 + 132), (cx + 26, y0 + 132),
                      (cx, y0 + 158)], WHITE)
    canvas.line(cx - 26, y0 + 132, cx, y0 + 158, TEAL_DK, 1)
    canvas.line(cx + 26, y0 + 132, cx, y0 + 158, TEAL_DK, 1)
    # neck and ears
    canvas.fill_rect(cx - 12, y0 + 104, cx + 12, y0 + 136, SKIN_DK)
    canvas.disc(cx - 33, y0 + 76, 6, SKIN)
    canvas.disc(cx + 33, y0 + 76, 6, SKIN)
    # face
    canvas.ellipse_fill(cx, y0 + 72, 33, 42, SKIN)
    # front hair: swept fringe and side locks over the face edge
    canvas.poly_fill([(cx - 34, y0 + 78), (cx - 34, y0 + 34),
                      (cx - 10, y0 + 22), (cx + 12, y0 + 22),
                      (cx + 34, y0 + 34), (cx + 34, y0 + 78),
                      (cx + 26, y0 + 52), (cx + 8, y0 + 38),
                      (cx - 12, y0 + 38), (cx - 26, y0 + 52)], HAIR)
    canvas.ellipse_fill(cx - 30, y0 + 96, 9, 26, HAIR)
    canvas.ellipse_fill(cx + 30, y0 + 96, 9, 26, HAIR)
    # brows, eyes, nose, mouth, blush
    canvas.line(cx - 20, y0 + 62, cx - 7, y0 + 60, HAIR, 2)
    canvas.line(cx + 7, y0 + 60, cx + 20, y0 + 62, HAIR, 2)
    canvas.ellipse_fill(cx - 13, y0 + 70, 7, 4, WHITE)
    canvas.ellipse_fill(cx + 13, y0 + 70, 7, 4, WHITE)
    canvas.disc(cx - 13, y0 + 70, 3, HAIR)
    canvas.disc(cx + 13, y0 + 70, 3, HAIR)
    canvas.line(cx, y0 + 72, cx - 2, y0 + 86, SKIN_DK, 2)
    canvas.line(cx - 2, y0 + 86, cx + 3, y0 + 87, SKIN_DK, 1)
    canvas.poly_fill([(cx - 10, y0 + 98), (cx, y0 + 102),
                      (cx + 10, y0 + 98), (cx, y0 + 106)],
                     (168, 90, 80))
    canvas.disc(cx - 21, y0 + 86, 4, (214, 150, 130))
    canvas.disc(cx + 21, y0 + 86, 4, (214, 150, 130))
    # earrings
    canvas.disc(cx - 33, y0 + 90, 2, GOLD)
    canvas.disc(cx + 33, y0 + 90, 2, GOLD)
    # frame and caption
    canvas.rect(x0, y0, x1, y1, INK, 2)
    canvas.fill_rect(x0, y1 - 18, x1, y1, INK)
    canvas.text_center(cx, y1 - 14, 'PHOTOGRAPH', 1, WHITE, spacing=1)


# -------------------------------------------------------------- stamps
def draw_stamp(canvas, cx, cy, angle, kind, place, date, color):
    """One border stamp, drawn on a tile and rotated onto the page.

    kind is ARR or DEP; place is the port; date is DD MON YYYY.
    Every stamp here is dated after the passport's issue, 02 JUN 2023,
    and the dates run in ascending order across the page.
    """
    tile = Canvas(150, 92, fill=(255, 0, 255))
    tile.ellipse(cx=75, cy=46, rx=72, ry=43, color=color, thick=2)
    tile.ellipse(cx=75, cy=46, rx=65, ry=37, color=color, thick=1)
    tile.text_center(75, 8, place, 2, color, bold=True)
    tile.text_center(75, 30, kind, 2, color, bold=True)
    tile.text_center(75, 52, date, 2, color, bold=True)
    tile.text_center(75, 74, 'MERIDIA', 1, color, spacing=1)
    canvas.blit_rotated(tile, cx, cy, angle, (255, 0, 255))


def draw_fee_stamp(canvas, cx, cy, angle):
    """The small rectangular fee stamp overlapping the Kestrel arrival."""
    tile = Canvas(150, 64, fill=(255, 0, 255))
    tile.rect(2, 2, 148, 62, STAMP_RED, 2)
    tile.text_center(75, 10, 'FERRY LEVY PAID', 1, STAMP_RED, spacing=1)
    tile.text_center(75, 26, '12.00 MER', 2, STAMP_RED, bold=True)
    tile.text_center(75, 46, '10 MAY 2024', 1, STAMP_RED, spacing=1)
    canvas.blit_rotated(tile, cx, cy, angle, (255, 0, 255))


def draw_visa(canvas, x0, y0, x1, y1, angle):
    """The Kestrel Isles ferry visa: a sticker pasted on the visa page."""
    tile = Canvas(x1 - x0, y1 - y0, fill=(255, 0, 255))
    w, h = tile.w, tile.h
    tile.round_rect_fill(2, 2, w - 2, h - 2, 10, (250, 246, 232))
    tile.round_rect(2, 2, w - 2, h - 2, 10, STAMP_PURPLE, 2)
    tile.fill_rect(4, 4, w - 4, 34, STAMP_PURPLE)
    tile.text_center(w // 2, 11, 'KESTREL ISLES', 2, WHITE, bold=True)
    tile.text_center(w // 2, 40, 'FERRY VISA', 2, STAMP_PURPLE, bold=True)
    tile.text_center(w // 2, 58, 'FERRY ZONE ONLY', 1, STAMP_PURPLE,
                     spacing=1)
    rows = [
        ('VALID', '10 MAY 2024 - 09 JUN 2024'),
        ('ENTRIES', 'MULTIPLE'),
        ('STAY', 'UP TO 30 DAYS'),
        ('SERIAL', 'KI-22914'),
    ]
    y = 76
    for label, value in rows:
        tile.text(14, y, label, 1, INK, spacing=1)
        tile.text(72, y, value, 1, INK, spacing=1, bold=True)
        y += 16
    tile.hline(14, w - 14, y + 2, GOLD, 1)
    tile.text_center(w // 2, y + 8, 'ISSUED AT FERRY TERMINAL', 1,
                     STAMP_PURPLE, spacing=1)
    tile.text_center(w // 2, y + 20, 'PORT SELENE, 10 MAY 2024', 1,
                     STAMP_PURPLE, spacing=1)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    canvas.blit_rotated(tile, cx, cy, angle, (255, 0, 255))


# ---------------------------------------------------------- data page
def draw_data_page(c):
    """Left page: the holder's data, portrait, condition, MRZ."""
    x0, x1 = 16, 510
    # header
    emblem(c, 58, 62, 24, TEAL)
    c.text(92, 40, 'REPUBLIC OF MERIDIA', 2, TEAL, bold=True)
    c.text_right(496, 40, 'NO. MD4718820', 1, TEAL, spacing=1, bold=True)
    c.text(92, 64, 'PASSPORT - DATA PAGE', 1, GOLD, spacing=1)
    c.hline(34, 496, 84, GOLD, 2)
    watermark(c, x0, 120, x1, 700, 'MERIDIA', (228, 216, 186))
    # portrait
    draw_portrait(c, 40, 104, 192, 314)
    # data fields: (label, value, value-scale, second column or None)
    fields = [
        ('TYPE', 'P', 2, ('CODE', 'MER', 2)),
        ('SURNAME', 'VOSS', 2, None),
        ('GIVEN NAMES', 'ELENA MAR', 2, None),
        ('NATIONALITY', 'MERIDIAN', 2, None),
        ('DATE OF BIRTH', '14 MAR 1988', 2, ('SEX', 'F', 2)),
        ('PLACE OF BIRTH', 'PORT SELENE', 2, None),
        ('DATE OF ISSUE', '02 JUN 2023', 2, ('DATE OF EXPIRY', '02 JUN 2033', 2)),
        ('AUTHORITY', 'IMMIGRATION OFFICE', 1, None),
    ]
    y = 104
    for label, value, scale, second in fields:
        c.text(208, y, label, 1, TEAL, spacing=1)
        c.text(208, y + 10, value, scale, INK, bold=True)
        if second is not None:
            lab2, val2, sc2 = second
            c.text(360, y, lab2, 1, TEAL, spacing=1)
            c.text(360, y + 10, val2, sc2, INK, bold=True)
        y += 28
    # holder's signature
    c.text(208, y + 2, "HOLDER'S SIGNATURE", 1, TEAL, spacing=1)
    c.text(208, y + 12, 'Elena Mar Voss', 2, INK)
    c.line(208, y + 30, 330, y + 28, INK, 1)
    c.line(330, y + 28, 360, y + 31, INK, 1)
    # condition box: the paperwork detail that reveals the place
    bx0, bx1, by0, by1 = 40, 496, 400, 500
    c.rect(bx0, by0, bx1, by1, TEAL, 2)
    c.fill_rect(bx0, by0, bx1, by0 + 22, TEAL)
    c.text_center((bx0 + bx1) // 2, by0 + 5,
                  'CONDITION 7 - KESTREL ISLES FERRY ZONE', 1, WHITE,
                  spacing=1, bold=True)
    cond = [
        'HOLDER MAY ENTER THE KESTREL ISLES FERRY ZONE',
        'WITHOUT A VISA FOR STAYS OF UP TO 30 DAYS.',
        "SEAFARER'S ENDORSEMENT - VALID FOR INTER-ISLAND",
        'FERRIES ONLY. NOT VALID FOR ONWARD TRAVEL.',
    ]
    cy = by0 + 30
    for line in cond:
        c.text(bx0 + 12, cy, line, 1, INK, spacing=1)
        cy += 12
    c.text(bx0 + 12, cy + 2, 'MERIDIAN: BEZ VIZE DO 30 DANA - TRAJEKTI SAMO.',
           1, GOLD, spacing=1)
    # machine-readable zone
    mx0, mx1, my0, my1 = 40, 496, 528, 606
    c.fill_rect(mx0 + 3, my0 + 3, mx1 + 3, my1 + 3, (200, 190, 160))
    c.fill_rect(mx0, my0, mx1, my1, WHITE)
    c.rect(mx0, my0, mx1, my1, INK, 1)
    line1, line2 = mrz_lines()
    c.text(mx0 + 8, my0 + 12, line1, 2, INK, spacing=0)
    c.text(mx0 + 8, my0 + 40, line2, 2, INK, spacing=0)
    c.text_center((x0 + x1) // 2, 676, 'MERIDIA', 1, GOLD, spacing=2)
    c.text_right(496, 676, '1', 1, INK, spacing=1)


# ---------------------------------------------------------- visa page
def draw_visa_page(c):
    """Right page: ferry visa, arrival card, nine stamps."""
    x0, x1 = 514, 1008
    c.text_center(761, 40, 'VISAS', 3, TEAL, bold=True)
    c.text_center(761, 66, 'VISA - PAGE 2', 1, GOLD, spacing=1)
    c.hline(532, 992, 86, GOLD, 2)
    watermark(c, x0, 100, x1, 700, 'MERIDIA', (228, 216, 186))
    # ferry visa sticker, slightly askew as pasted
    draw_visa(c, 540, 104, 820, 288, -2)
    # arrival card for the latest trip, matching the last stamp
    ax0, ax1, ay0, ay1 = 836, 992, 104, 288
    card = Canvas(ax1 - ax0, ay1 - ay0, fill=(255, 0, 255))
    card.round_rect_fill(2, 2, card.w - 2, card.h - 2, 8, WHITE)
    card.round_rect(2, 2, card.w - 2, card.h - 2, 8, STAMP_BLUE, 2)
    card.fill_rect(4, 4, card.w - 4, 30, STAMP_BLUE)
    card.text_center(card.w // 2, 10, 'ARRIVAL CARD', 1, WHITE, spacing=1,
                     bold=True)
    rows = [
        ('PORT', 'HARBOURGATE'),
        ('DATE', '12 OCT 2026'),
        ('PURPOSE', 'VISIT'),
        ('STAY', '14 DAYS'),
        ('NAME', 'VOSS, ELENA M.'),
    ]
    y = 40
    for label, value in rows:
        card.text(12, y, label, 1, INK, spacing=1)
        card.text(12, y + 10, value, 1, INK, spacing=1, bold=True)
        y += 26
    c.blit_rotated(card, (ax0 + ax1) // 2, (ay0 + ay1) // 2, 1,
                   (255, 0, 255))
    # nine stamps, dates ascending, each arrival matched by a departure
    stamps = [
        ('DEPARTURE', 'PORT SELENE', '14 SEP 2023', TEAL, -4),
        ('ARRIVAL', 'DURNHOLM', '15 SEP 2023', STAMP_BLUE, 3),
        ('DEPARTURE', 'DURNHOLM', '28 SEP 2023', STAMP_RED, -3),
        ('ARRIVAL', 'PORT SELENE', '28 SEP 2023', TEAL, 5),
        ('ARRIVAL', 'KESTREL', '10 MAY 2024', STAMP_PURPLE, -5),
        ('DEPARTURE', 'KESTREL', '22 MAY 2024', STAMP_PURPLE, 4),
        ('ARRIVAL', 'PORTO VERDE', '04 FEB 2025', STAMP_GREEN, -3),
        ('DEPARTURE', 'PORTO VERDE', '17 FEB 2025', STAMP_GREEN, 3),
        ('ARRIVAL', 'DURNHOLM', '12 OCT 2026', STAMP_BLUE, -4),
    ]
    xs = (608, 761, 914)
    ys = (368, 492, 616)
    for i, (kind, place, date, color, angle) in enumerate(stamps):
        draw_stamp(c, xs[i % 3], ys[i // 3], angle, kind, place, date,
                   color)
    # fee stamp in the band between the visa and the stamp rows
    draw_fee_stamp(c, 700, 312, -6)
    c.text_center((x0 + x1) // 2, 676, 'MERIDIA', 1, GOLD, spacing=2)
    c.text_right(992, 676, '2', 1, INK, spacing=1)


# -------------------------------------------------------------- spread
def build():
    c = Canvas(W, H, fill=TEAL_DK)
    # the open book: two cream pages inside a dark cover edge
    c.fill_rect(16, 16, 1008, 708, CREAM)
    guilloche(c, 20, 20, 1004, 704, FAINT, step=11, amp=2)
    c.rect(16, 16, 1008, 708, GOLD, 2)
    draw_data_page(c)
    draw_visa_page(c)
    # centre gutter shadow
    for i, shade in enumerate(((0, 0, 0), (30, 42, 38), (60, 70, 64))):
        c.vline(508 + i, 18, 706, shade, 1)
        c.vline(515 - i, 18, 706, shade, 1)
    c.fill_rect(511, 18, 514, 706, (20, 30, 28))
    return c


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        'OUTPUT', '/output/entry.png')
    canvas = build()
    size = write_png(canvas, out)
    print('wrote %s (%dx%d, %d bytes)' % (out, canvas.w, canvas.h, size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
