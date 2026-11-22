#!/usr/bin/env python3
"""THE DAILY DISPATCH - front page of Saturday, 21 November 2026.

A single-file, pure-standard-library program that draws a complete
newspaper front page (masthead, COP31 lead story, markets strip,
six regional sections, an In Brief column and a footer) and writes
it as a 1024x1024 PNG to $MAKEFUN_OUTPUT_DIR/entry.png
(default /output/entry.png).

The grader machine has no Pillow and no font files, so all text is
drawn with a small bitmap font defined below (5x7 pixel glyphs,
stored as seven integer bit-rows per character) and the PNG is
encoded by hand with zlib + struct.  The program reads no files,
uses no randomness and no clock, so two runs produce byte-identical
output.
"""

import math
import os
import struct
import zlib

# ------------------------------------------------------------------
# Page geometry and palette
# ------------------------------------------------------------------

W = 1024                      # page width in pixels
H = 1024                      # page height in pixels

PAPER = (246, 243, 233)       # warm off-white newsprint
INK = (17, 17, 17)            # near-black ink
RED = (148, 26, 20)           # the single accent colour
FAINT = (96, 94, 86)          # grey for credits and rules

MARGIN = 36                   # left / right page margin
CONTENT_W = W - 2 * MARGIN    # 952 px of usable width

# The pixel buffer: one bytearray of RGB triples, row major.
PX = bytearray(bytes(PAPER) * (W * H))


def rect(x, y, w, h, colour):
    """Fill an axis-aligned rectangle, clipped to the page."""
    if w <= 0 or h <= 0:
        return
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(colour) * (x1 - x0)
    stride = W * 3
    off = y0 * stride + x0 * 3
    for _ in range(y0, y1):
        PX[off:off + len(row)] = row
        off += stride


def plot(x, y, colour, size=2):
    """Draw one square dot (used for ellipse outlines)."""
    rect(int(x) - size // 2, int(y) - size // 2, size, size, colour)


def disc(cx, cy, r, colour):
    """Draw a filled circle, one horizontal span per row."""
    r = int(r)
    for dy in range(-r, r + 1):
        hw = int(math.sqrt(max(0, r * r - dy * dy)))
        rect(cx - hw, cy + dy, 2 * hw + 1, 1, colour)


def ellipse(cx, cy, rx, ry, colour, size=2):
    """Draw an ellipse outline by stepping the parameter angle."""
    steps = max(24, int(2 * math.pi * max(rx, ry) / 3))
    for i in range(steps + 1):
        t = 2.0 * math.pi * i / steps
        plot(cx + rx * math.cos(t), cy + ry * math.sin(t), colour, size)


# ------------------------------------------------------------------
# PNG encoding (deterministic: filter 0 scanlines, zlib level 9)
# ------------------------------------------------------------------

def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def save_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)                       # filter type 0 (None)
        raw += PX[y * stride:(y + 1) * stride]
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


# ------------------------------------------------------------------
# The built-in bitmap font.
#
# Each glyph is a tuple of 7 integers, one per pixel row, top first.
# Within a row, bit 4 is the leftmost of the 5 pixel columns and
# bit 0 the rightmost, so 0x11 draws pixels at columns 0 and 4.
# Lowercase letters sit on rows 2..6 (x-height), capitals and digits
# use all seven rows.  Glyphs advance proportionally: the advance of
# a character is its inked width plus one blank column.
# ------------------------------------------------------------------

FONT = {
    'A': (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'B': (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    'C': (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    'D': (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    'E': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    'F': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    'G': (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    'H': (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'I': (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    'J': (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    'K': (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    'L': (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    'M': (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    'N': (0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11),
    'O': (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    'P': (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    'Q': (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    'R': (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    'S': (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    'T': (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    'U': (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    'V': (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'W': (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A),
    'X': (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    'Y': (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    'Z': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    '0': (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    '1': (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    '2': (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    '3': (0x0E, 0x11, 0x01, 0x06, 0x01, 0x11, 0x0E),
    '4': (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    '5': (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    '6': (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    '7': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    '8': (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    '9': (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    'a': (0x00, 0x00, 0x0E, 0x01, 0x0F, 0x11, 0x0F),
    'b': (0x10, 0x10, 0x16, 0x19, 0x11, 0x11, 0x1E),
    'c': (0x00, 0x00, 0x0E, 0x11, 0x10, 0x11, 0x0E),
    'd': (0x01, 0x01, 0x0D, 0x13, 0x11, 0x11, 0x0F),
    'e': (0x00, 0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E),
    'f': (0x06, 0x09, 0x08, 0x1E, 0x08, 0x08, 0x08),
    'g': (0x00, 0x00, 0x0F, 0x11, 0x0F, 0x01, 0x0E),
    'h': (0x10, 0x10, 0x16, 0x19, 0x11, 0x11, 0x11),
    'i': (0x04, 0x00, 0x06, 0x04, 0x04, 0x04, 0x0E),
    'j': (0x02, 0x00, 0x06, 0x02, 0x02, 0x12, 0x0C),
    'k': (0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12),
    'l': (0x06, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    'm': (0x00, 0x00, 0x1A, 0x15, 0x15, 0x15, 0x15),
    'n': (0x00, 0x00, 0x16, 0x19, 0x11, 0x11, 0x11),
    'o': (0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E),
    'p': (0x00, 0x00, 0x16, 0x19, 0x11, 0x1E, 0x10),
    'q': (0x00, 0x00, 0x0D, 0x13, 0x11, 0x0F, 0x01),
    'r': (0x00, 0x00, 0x16, 0x19, 0x10, 0x10, 0x10),
    's': (0x00, 0x00, 0x0F, 0x10, 0x0E, 0x01, 0x1E),
    't': (0x08, 0x08, 0x1C, 0x08, 0x08, 0x09, 0x06),
    'u': (0x00, 0x00, 0x11, 0x11, 0x11, 0x13, 0x0D),
    'v': (0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'w': (0x00, 0x00, 0x11, 0x15, 0x15, 0x15, 0x0A),
    'x': (0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11),
    'y': (0x00, 0x00, 0x11, 0x11, 0x0F, 0x01, 0x0E),
    'z': (0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F),
    ' ': (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    '.': (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    ',': (0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08),
    ':': (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    ';': (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x04, 0x08),
    '!': (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    '?': (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    "'": (0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00),
    '‘': (0x08, 0x08, 0x04, 0x00, 0x00, 0x00, 0x00),
    '’': (0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00),
    '"': (0x0A, 0x0A, 0x0A, 0x00, 0x00, 0x00, 0x00),
    '“': (0x09, 0x09, 0x09, 0x00, 0x00, 0x00, 0x00),
    '”': (0x12, 0x12, 0x12, 0x00, 0x00, 0x00, 0x00),
    '-': (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    '–': (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    '—': (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    '−': (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    '+': (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
    '/': (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    '(': (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ')': (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    '%': (0x18, 0x19, 0x02, 0x04, 0x08, 0x13, 0x03),
    '$': (0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04),
    '€': (0x0F, 0x10, 0x1E, 0x10, 0x1E, 0x10, 0x0F),
    '£': (0x06, 0x09, 0x08, 0x1E, 0x08, 0x08, 0x1F),
    '¥': (0x11, 0x11, 0x0A, 0x04, 0x1F, 0x04, 0x04),
    '&': (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D),
    '@': (0x0E, 0x11, 0x17, 0x15, 0x16, 0x10, 0x0E),
    '#': (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
    '*': (0x00, 0x04, 0x15, 0x0E, 0x15, 0x04, 0x00),
    '•': (0x00, 0x00, 0x00, 0x0E, 0x0E, 0x00, 0x00),
    '·': (0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00),
    '°': (0x04, 0x0A, 0x04, 0x00, 0x00, 0x00, 0x00),
}


# ------------------------------------------------------------------
# Text measurement and drawing
# ------------------------------------------------------------------

def _ink_width(rows):
    """Width in columns of a glyph's ink (0 for a blank glyph)."""
    w = 0
    for v in rows:
        if v:
            lowest = (v & -v).bit_length() - 1   # lowest set bit index
            w = max(w, 5 - lowest)
    return w


_ADV = {}


def advance(ch):
    """Advance of one character, in font columns (unscaled)."""
    if ch == ' ':
        return 3
    if ch not in _ADV:
        _ADV[ch] = _ink_width(FONT.get(ch, FONT[' '])) + 1
    return _ADV[ch]


def text_w(text, scale):
    """Pixel width of a string at the given integer scale."""
    if not text:
        return 0
    return (sum(advance(c) for c in text) - 1) * scale


def draw_text(x, y, text, scale, colour, bold=False):
    """Draw a string with its top-left at (x, y); return its width."""
    cx = x
    extra = max(1, scale // 2) if bold else 0
    for ch in text:
        rows = FONT.get(ch, FONT[' '])
        for r in range(7):
            bits = rows[r]
            if not bits:
                continue
            for c in range(5):
                if bits & (1 << (4 - c)):
                    px = cx + c * scale
                    py = y + r * scale
                    rect(px, py, scale, scale, colour)
                    if extra:
                        rect(px + extra, py, scale, scale, colour)
        cx += advance(ch) * scale
    return cx - x - (scale if text else 0)


def draw_centered(text, y, scale, colour, bold=False, cx=W // 2):
    """Draw a string centred on cx; return its width."""
    w = text_w(text, scale)
    draw_text(cx - w // 2, y, text, scale, colour, bold)
    return w


def wrap(text, max_px, scale):
    """Split text into lines that fit max_px, on word boundaries.

    A single word longer than the line is hard-split so that no
    line can ever overflow its column.
    """
    lines = []
    cur = ''
    for word in text.split(' '):
        trial = word if not cur else cur + ' ' + word
        if text_w(trial, scale) <= max_px:
            cur = trial
            continue
        if cur:
            lines.append(cur)
            cur = ''
        while text_w(word, scale) > max_px and len(word) > 1:
            cut = len(word)
            while cut > 1 and text_w(word[:cut], scale) > max_px:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(x, y, text, max_px, scale, colour, pitch,
                 bold=False, align='left'):
    """Draw wrapped text; return the y just below the last line."""
    for line in wrap(text, max_px, scale):
        if align == 'center':
            draw_centered(line, y, scale, colour, bold, x + max_px // 2)
        else:
            draw_text(x, y, line, scale, colour, bold)
        y += pitch
    return y


# ------------------------------------------------------------------
# The "day in one image" panel: a wireframe globe and a thermometer
# ------------------------------------------------------------------

def draw_globe(cx, cy, r):
    """A simple wireframe globe: rim, equator, latitudes, meridians."""
    ellipse(cx, cy, r, r, INK, 2)
    ellipse(cx, cy, r, max(2, int(r * 0.30)), INK, 2)          # equator
    for lat in (-52, -26, 26, 52):
        fy = math.sin(math.radians(lat))
        fx = math.cos(math.radians(lat))
        ellipse(cx, cy - int(r * fy), int(r * fx),
                max(2, int(r * fx * 0.30)), INK, 2)
    for lon in (24, 48, 72, 96, 120, 156):
        fx = math.sin(math.radians(lon))
        if fx > 0.05:
            ellipse(cx, cy, max(2, int(r * fx)), r, INK, 2)
    rect(cx - 1, cy - r, 2, 2 * r, INK)                        # axis


def draw_thermometer(x, y, h):
    """A thermometer, bulb at the bottom, filled two-thirds in red."""
    tube_w = 14
    rect(x, y, tube_w, h, INK)                                # tube shell
    rect(x + 3, y + 3, tube_w - 6, h - 6, PAPER)              # tube inner
    fill_h = int((h - 10) * 0.68)
    rect(x + 3, y + h - 5 - fill_h, tube_w - 6, fill_h, RED)  # mercury
    disc(x + tube_w // 2, y + h + 12, 15, INK)                # bulb shell
    disc(x + tube_w // 2, y + h + 12, 11, RED)                # bulb
    for i in range(5):                                        # tick marks
        ty = y + 8 + i * (h - 20) // 4
        rect(x + tube_w + 5, ty, 9, 2, INK)


def draw_image_panel(x, y, w, h):
    """Bordered panel beside the lead story: globe, heat, caption."""
    rect(x, y, w, h, INK)
    rect(x + 2, y + 2, w - 4, h - 4, PAPER)
    draw_centered('THE DAY IN ONE IMAGE', y + 12, 2, INK, True,
                  x + w // 2)
    rect(x + 14, y + 34, w - 28, 2, INK)
    draw_globe(x + 92, y + 96, 50)
    draw_thermometer(x + w - 62, y + 50, 72)
    draw_centered('+1.8°C', y + 146, 3, RED, True, x + w // 2)
    draw_wrapped(x + 16, y + h - 48,
                 'A feverish planet: October ran 1.8°C above '
                 'pre-industrial levels.',
                 w - 32, 2, FAINT, 14, align='center')


# ------------------------------------------------------------------
# Newspaper furniture: section bars, story blocks, brief items
# ------------------------------------------------------------------

def section_bar(x, y, w, title):
    """A black section bar with the title in paper colour."""
    rect(x, y, w, 22, INK)
    draw_text(x + 9, y + 4, title, 2, PAPER, True)
    return y + 22


def story(x, y, w, headline, summary):
    """One story: bold headline over a short summary.  Returns new y."""
    y = draw_wrapped(x, y, headline, w, 2, INK, 16, bold=True)
    y += 1
    y = draw_wrapped(x, y, summary, w, 2, INK, 16)
    return y + 8


def brief_item(x, y, w, text):
    """One In Brief line, hung on a bullet.  Returns new y."""
    draw_text(x, y, '•', 2, RED, True)
    y = draw_wrapped(x + 16, y, text, w - 16, 2, INK, 15)
    return y + 3


# ------------------------------------------------------------------
# The day's news, Saturday 21 November 2026 (from the wires)
# ------------------------------------------------------------------

LEAD_KICKER = 'CLIMATE SUMMIT · ANTALYA, TURKEY'
LEAD_HEADLINE = ('COP31 TALKS RUN DEEP INTO OVERTIME '
                 'OVER FOSSIL FUELS')
LEAD_BODY = (
    'ANTALYA — Negotiators from nearly 200 countries worked '
    'through Saturday with no final deal, after a draft text '
    'dropped every mention of the fossil fuels driving global '
    'warming. Crews were already boxing up the venue as '
    'delegations shuttled between rooms; the EU climate chief '
    'Wopke Hoekstra warned it would be “a good deal or no deal.”'
)
LEAD_CREDIT = 'Reuters / AP — Antalya'

MARKETS_TITLE = 'MARKETS — AI SELL-OFF RATTLES THE WORLD'
MARKETS_LINE = ('S&P -3.7% · NIKKEI -5.1% · FTSE -1% · '
                'GOLD -4.6% · BTC $57,850 · BRENT $89.95 · '
                'SENSEX +2.3%')

EUROPE = [
    ('Russia fires 400 drones and 110 missiles at Ukraine',
     'Eight killed in Kyiv; projectiles land in Poland. (BBC)'),
    ('Trump tells Europe to defund Ukraine after Putin summit',
     'Urges Europe to stop funding Kyiv. (Telegraph)'),
    ('UK and EU sign three post-Brexit agreements',
     'Mobility, trade and energy deals signed in Brussels.'),
]

ASIA_PACIFIC = [
    ('Japan sidelined by China as ties hit record low',
     'Beijing demands an attitude change after Xi’s APEC snub.'),
    ('India, Japan deepen defence ties at Tokyo 2+2',
     'Forces deal plus an ISRO-JAXA space pact in Tokyo.'),
    ('UN court: Myanmar responsible for Rohingya genocide',
     'ICJ ruling draws protests from Myanmar and China. (Wires)'),
]

AMERICAS = [
    ('Magnitude 6.7 earthquake shakes Peru’s Andes',
     'Felt in Lima; residents fled into streets, no deaths. (AP)'),
    ('Anthropic lists on Wall Street at $2tn value',
     'One of the world’s most valuable firms after debut. (NYT)'),
    ('FBI criminal database and USDA reportedly hacked',
     'Intruders hit crime records and a USDA payment system.'),
]

MIDDLE_EAST = [
    ('Saudi defences destroy three Houthi missiles over Riyadh',
     'Downed after 2am; emergency alerts later lifted. (Reuters)'),
    ('Israeli fire kills Palestinians in Gaza',
     'Seven reported killed despite the ceasefire. (Wires)'),
]

AFRICA = [
    ('Phumzile Mlambo-Ngcuka, SA’s first woman deputy '
     'president, dies at 71',
     'Death announced by the South African Presidency. (Wires)'),
    ('WHO keeps Congo Ebola outbreak a global emergency',
     'Cases 11,613, deaths 5,678; Uganda curbs travel. (WHO)'),
]

SCIENCE_HEALTH = [
    ('Pill makes pancreatic tumours vanish in some patients',
     'Daraxonrasib left cancer undetectable in 1 in 12 patients.'),
    ('BepiColombo reaches Mercury orbit after eight years',
     'European-Japanese probe ends its long cruise. (Wires)'),
]

BRIEFS_BUSINESS = [
    'GTA 6: $4.9bn first-day sales record',
    'Judge endorses $7.25bn Roundup deal',
    'Egypt IMF deal unlocks $2.3bn',
]

BRIEFS_SPORT = [
    'Verstappen takes Las Vegas GP pole',
    'Kane out months with ankle injury',
    'Harden passes Kobe on 50-point list',
]


# ------------------------------------------------------------------
# Page layout
# ------------------------------------------------------------------

def draw_section(x, y, w, title, stories):
    """A section bar followed by its stories.  Returns new y."""
    y = section_bar(x, y, w, title) + 6
    for head, summ in stories:
        y = story(x, y, w, head, summ)
    return y


def draw_brief_band(y):
    """A full-width In Brief band: business and sport side by side."""
    y = section_bar(MARGIN, y, CONTENT_W, 'IN BRIEF') + 8
    draw_text(MARGIN, y, 'BUSINESS', 2, RED, True)
    draw_text(536, y, 'SPORT', 2, RED, True)
    y += 17
    draw_wrapped(MARGIN, y, ' · '.join(BRIEFS_BUSINESS), 452, 2,
                 INK, 15)
    draw_wrapped(536, y, ' · '.join(BRIEFS_SPORT), 452, 2, INK, 15)


def main():
    # Masthead ------------------------------------------------------------
    rect(MARGIN, 16, CONTENT_W, 3, INK)
    rect(MARGIN, 23, CONTENT_W, 1, INK)
    draw_centered('THE DAILY DISPATCH', 32, 7, INK, True)
    rect(MARGIN, 88, CONTENT_W, 2, INK)
    draw_text(MARGIN, 96, 'Vol. I · No. 325', 2, INK)
    draw_centered('Saturday, 21 November 2026', 96, 2, INK, True)
    right = 'ONE DAY · ONE PAGE'
    draw_text(W - MARGIN - text_w(right, 2), 96, right, 2, INK)
    rect(MARGIN, 118, CONTENT_W, 4, INK)

    # Lead story, with the image panel beside it --------------------------
    ly = 134
    draw_text(MARGIN, ly, LEAD_KICKER, 2, RED, True)
    hy = draw_wrapped(MARGIN, ly + 22, LEAD_HEADLINE, 596, 4, INK, 34,
                      bold=True)
    by = draw_wrapped(MARGIN, hy + 8, LEAD_BODY, 596, 2, INK, 15)
    draw_text(MARGIN, by + 4, LEAD_CREDIT, 2, FAINT)
    draw_image_panel(656, ly, 332, 216)

    # Markets strip ---------------------------------------------------------
    my = 362
    rect(MARGIN, my, CONTENT_W, 40, INK)
    draw_centered(MARKETS_TITLE, my + 4, 2, PAPER, True)
    draw_centered(MARKETS_LINE, my + 22, 2, PAPER)

    # Three news columns ----------------------------------------------------
    top = 418
    rect(346, top, 1, 456, FAINT)
    rect(666, top, 1, 456, FAINT)
    y1 = draw_section(MARGIN, top, 312, 'EUROPE', EUROPE)
    draw_section(MARGIN, y1 + 6, 312, 'MIDDLE EAST', MIDDLE_EAST)
    y2 = draw_section(356, top, 312, 'ASIA-PACIFIC', ASIA_PACIFIC)
    draw_section(356, y2 + 6, 312, 'AFRICA', AFRICA)
    y3 = draw_section(676, top, 312, 'AMERICAS', AMERICAS)
    draw_section(676, y3 + 6, 312, 'SCIENCE & HEALTH', SCIENCE_HEALTH)
    draw_brief_band(882)

    # Footer ------------------------------------------------------------------
    rect(MARGIN, 980, CONTENT_W, 2, INK)
    draw_centered('Compiled from Reuters, AP, BBC, AFP, the New York '
                  'Times and wire reports', 988, 2, FAINT)
    draw_centered('Every story dated 21 November 2026 · One page, '
                  'one day, every story', 1004, 2, FAINT)

    out = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(out, exist_ok=True)
    save_png(os.path.join(out, 'entry.png'))


if __name__ == '__main__':
    main()
