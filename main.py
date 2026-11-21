#!/usr/bin/env python3
"""
THE DAILY DISPATCH — Saturday, 21 November 2026 in one image.

Deterministic newspaper front-page generator for the make.fun bounty
"Sum up 21 November's world news in one image" (news-image-20261121).

- No network, no randomness, no timestamps, no input files except fonts.
- All news content is embedded below as data (compiled from Reuters, AP,
  BBC, NYT and wire reports dated 21 November 2026; summaries condensed
  from the full list in stories.md).
- Writes exactly one PNG to /output/entry.png (<=1024x1024, <=1 MiB).
- Two runs produce byte-identical output (fixed layout algorithm below:
  the column packer picks the first size preset that fits, deterministically).
"""

import os
from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Fonts (system fonts only)
# --------------------------------------------------------------------------
SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
SERIF_B = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
SANS_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
PAPER = (250, 247, 238)
INK = (18, 18, 18)
GREY = (70, 70, 70)
DARK = (40, 40, 40)
ACCENT = (150, 30, 20)      # deep red for kickers / thermometer
GLOBE_LAND = (96, 128, 92)
GLOBE_SEA = (196, 214, 222)
WHITE = (255, 255, 255)

W, H = 1024, 1024
M = 26                      # page margin
CW = W - 2 * M              # content width = 972
COL_W = 316
COL_X = [M, M + COL_W + 12, M + 2 * (COL_W + 12)]
COL_BOTTOM = H - 36

# --------------------------------------------------------------------------
# News data — every story dated Saturday, 21 November 2026
# (headline, one-line summary with source)
# --------------------------------------------------------------------------
HERO_KICKER = "CLIMATE SUMMIT \u00b7 ANTALYA, TURKEY"
HERO_HEADLINE = "COP31 TALKS RUN DEEP INTO OVERTIME OVER FOSSIL FUELS"
HERO_SUMMARY = (
    "ANTALYA \u2014 Negotiators from nearly 200 countries worked through Saturday with no final "
    "deal, after a draft text dropped every mention of the fossil fuels driving global warming. "
    "Crews were already boxing up the venue as delegations shuttled between rooms; the EU's "
    "climate chief Wopke Hoekstra warned it would be \u201ca good deal or no deal.\u201d"
)
HERO_BYLINE = "Reuters / AP \u2014 Antalya"
HERO_CAPTION = (
    "A feverish planet: October ran 1.8\u00b0C above pre-industrial levels, Berkeley Earth says, "
    "in a year of heatwaves and floods."
)

# markets strip is built from segments; trailing segments are dropped
# (deterministically) until the line fits the bar
STRIP_SEGMENTS = [
    "MARKETS \u2014 AI SELL-OFF RATTLES THE WORLD:",
    "S&P 500 \u22123.7%", "NIKKEI \u22125.1%", "FTSE \u22121.0%", "GOLD \u22124.6%",
    "BITCOIN $57,850", "BRENT $89.95 \u25b2", "SENSEX +2.3%",
]

SECTIONS = [
    ("EUROPE", [
        ("Russia fires 400 drones and 110 missiles at Ukraine",
         "Projectiles land in Poland; at least 8 killed in Kyiv, power cut in 10 regions. (BBC)"),
        ("Trump tells Europe to defund Ukraine after Putin summit",
         "Angry call after the summit; Zelensky calls Putin a \u201ckiller.\u201d (Telegraph)"),
        ("UK and EU sign three post-Brexit agreements",
         "Burnham signs youth mobility, trade and energy deals in Brussels. (Wires)"),
        ("Denmark expels Russian diplomat over plot to kill rapper",
         "Two arrested over plot against a US-Ukrainian rapper. (Wires)"),
        ("Cost-of-living protests spread across Europe",
         "Students in 25 countries walk out over costs, tuition, military spending. (Wires)"),
        ("Spain heads to snap election on Nov. 29",
         "Banking tax to be extended to fund housing, PM says. (Wires)"),
        ("Activists brand COP31 among worst ever",
         "100 groups warn hosts Turkey and Australia of a historic low point. (AP)"),
    ]),
    ("MIDDLE EAST", [
        ("Saudi defences destroy three Houthi missiles over Riyadh",
         "Interceptions confirmed after 2am; emergency alerts issued, then lifted. (Reuters)"),
        ("Tankers hit near Hormuz as US\u2013Iran talks stall",
         "Iran's Guards say they downed a US drone over the strait. (Wires)"),
        ("Trump weighs new strikes on Iran; Israel presses for action",
         "New intelligence on Iranian capabilities drives the talks. (NYT)"),
        ("Israeli fire kills Palestinians in Gaza",
         "Seven reported killed across the Strip despite the ceasefire. (Wires)"),
        ("Saudi Arabia, Japan agree oil stockpile deal",
         "Riyadh to triple crude stored in Japan amid tensions. (Arab News)"),
    ]),
    ("ASIA-PACIFIC", [
        ("Japan sidelined by China as ties hit record low",
         "Beijing: Japan must change its \u201cattitude\u201d after Xi snubs PM Takaichi at APEC. (Wires)"),
        ("India, Japan deepen defence ties at Tokyo 2+2",
         "Japanese forces to train at Indian ranges; ISRO\u2013JAXA space pact signed. (Wires)"),
        ("UN court: Myanmar responsible for Rohingya genocide",
         "ICJ ruling draws protests from Myanmar and China. (Wires)"),
        ("Japan core inflation rises to 2.2% in October",
         "Figure keeps pressure on Tokyo policymakers. (Wires)"),
        ("Pilotless air taxi carries passenger in Japan",
         "Uncrewed first in Yamanashi Prefecture. (Wires)"),
        ("Nepal PM Balendra Shah to visit India",
         "Trip to anchor a reset in Kathmandu\u2013Delhi ties. (Wires)"),
    ]),
    ("AMERICAS", [
        ("Magnitude 6.7 earthquake shakes Peru's Andes",
         "Struck near Jun\u00edn, felt in Lima; residents fled to streets; no deaths reported. (AP)"),
        ("Anthropic lists on Wall Street at $2 trillion value",
         "AI firm's debut makes it one of the world's most valuable firms. (NYT)"),
        ("FBI criminal database and USDA reportedly hacked",
         "Intruders hit the FBI crime database and a USDA payment system. (Wires)"),
        ("Man convicted of starting deadly Palisades fire",
         "Los Angeles jury finds defendant guilty over the blaze. (Wires)"),
        ("Salvadoran troops fight gangs in Haiti, lose soldiers",
         "Casualties in clashes around Port-au-Prince. (Wires)"),
        ("Bolsonaro hospitalized in Bras\u00edlia",
         "Former president admitted with intestinal obstruction. (Wires)"),
    ]),
    ("AFRICA", [
        ("Phumzile Mlambo-Ngcuka, SA's first woman deputy president, dies at 71",
         "Death of the former UN Women chief announced by the Presidency. (Wires)"),
        ("WHO keeps Congo Ebola outbreak a global emergency",
         "Cases hit 11,613 with 5,678 deaths; children hit hardest. (WHO)"),
        ("Uganda restricts gatherings, travel over Ebola",
         "Kampala tightens measures as the outbreak grows. (Wires)"),
        ("Boat of funeral mourners capsizes in Nigeria",
         "Four dead in Bayelsa State; search continues. (Wires)"),
        ("Kenya begins onshore crude drilling in Turkana",
         "First onshore campaign opens a new energy frontier. (Wires)"),
        ("Somalia orders UAE ambassador out in 72 hours",
         "Expulsion amid a widening diplomatic row. (Wires)"),
    ]),
    ("SCIENCE & HEALTH", [
        ("Pill makes pancreatic tumours vanish in some patients",
         "Daily pill daraxonrasib left cancer undetectable in 1 in 12 trial patients. (Wires)"),
        ("BepiColombo reaches Mercury orbit after eight years",
         "European-Japanese probe ends its long cruise. (Wires)"),
        ("Voyager 1 now 24 light-hours from Earth",
         "NASA's farthest probe widens its record. (Wires)"),
        ("CERN finds first evidence of ultra-rare decay",
         "Milestone observation reported in Geneva. (Wires)"),
        ("US loses measles elimination status",
         "Designation withdrawn after sustained outbreaks. (Wires)"),
        ("Nations to draft rules for AI \u201ckiller robots\u201d by 2028",
         "States agree controls on autonomous weapons. (Wires)"),
    ]),
]

BUSINESS_BRIEF = (
    "BUSINESS \u2014 GTA 6 smashes records with nearly $4.9 billion in first-day sales \u2022 "
    "Judge endorses $7.25 billion Roundup settlement \u2022 Egypt reaches IMF staff deal "
    "unlocking about $2.3bn \u2022 Argentina's country risk tops 1,000 points \u2022 Italy gives "
    "Tesla self-driving conditional approval"
)
SPORT_BRIEF = (
    "SPORT \u2014 Verstappen takes Las Vegas GP pole after Antonelli penalty \u2022 Harry Kane "
    "to miss a few months with ankle injury \u2022 Harden passes Kobe Bryant on NBA 50-point "
    "games list \u2022 Alcaraz beats Cobolli at ATP Finals \u2022 BTS wins five MAMA awards in "
    "Osaka \u2022 Choi Min-jeong wins third straight World Tour 1,000m title"
)

FOOTER = ("THE DAILY DISPATCH \u00b7 Saturday, 21 November 2026 \u00b7 Compiled from Reuters, AP, BBC, AFP, "
          "the New York Times and wire reports \u00b7 Every story dated 21 November 2026")

# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------
_probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def wrap(text, font, width):
    """Greedy word wrap; returns list of lines that fit `width` px."""
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if _probe.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(d, x, y, text, font, lh, width, fill=INK, max_lines=None):
    lines = wrap(text, font, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and _probe.textlength(last + "\u2026", font=font) > width:
            last = last[:-1]
        lines[-1] = last + "\u2026"
    for ln in lines:
        d.text((x, y), ln, font=font, fill=fill)
        y += lh
    return y


# --------------------------------------------------------------------------
# Hero visual: a drawn globe with a fever thermometer (abstract, code-drawn)
# --------------------------------------------------------------------------
def draw_globe(img, cx, cy, r):
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GLOBE_SEA)
    # abstract continents on a masked layer so they stay inside the globe
    layer = Image.new("RGBA", (2 * r + 2, 2 * r + 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    land = GLOBE_LAND + (255,)
    s = (2 * r + 2) / 164.0  # scale the sketch (drawn for r=81) to this radius
    def P(pts):
        return [(int(a * s), int(b * s)) for a, b in pts]
    ld.polygon(P([(30, 30), (85, 18), (105, 45), (80, 70), (45, 66), (26, 50)]), fill=land)
    ld.polygon(P([(72, 78), (98, 76), (100, 112), (82, 128), (70, 104)]), fill=land)
    ld.polygon(P([(112, 34), (150, 26), (168, 48), (150, 66), (118, 60)]), fill=land)
    ld.polygon(P([(124, 68), (146, 66), (148, 96), (128, 104), (118, 84)]), fill=land)
    ld.polygon(P([(152, 96), (178, 94), (182, 116), (160, 122)]), fill=land)
    mask = Image.new("L", (2 * r + 2, 2 * r + 2), 0)
    ImageDraw.Draw(mask).ellipse([1, 1, 2 * r, 2 * r], fill=255)
    img.paste(layer, (cx - r - 1, cy - r - 1), Image.composite(
        layer, Image.new("RGBA", layer.size, (0, 0, 0, 0)), mask))
    d = ImageDraw.Draw(img)
    for frac in (0.45, 0.8):
        w2 = int(r * frac)
        d.ellipse([cx - w2, cy - r, cx + w2, cy + r], outline=INK, width=1)
    d.line([cx, cy - r, cx, cy + r], fill=INK, width=1)
    for frac in (-0.55, 0.0, 0.55):
        yy = cy + int(r * frac)
        hw = int(r * (1 - frac * frac) ** 0.5)
        d.line([cx - hw, yy, cx + hw, yy], fill=INK, width=1)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=INK, width=3)


def draw_thermometer(d, x, y, h):
    wdt = 13
    d.rounded_rectangle([x, y, x + wdt, y + h], radius=6, outline=INK, width=2, fill=WHITE)
    bulb_r = 13
    bcx, bcy = x + wdt // 2, y + h + bulb_r - 2
    d.ellipse([bcx - bulb_r, bcy - bulb_r, bcx + bulb_r, bcy + bulb_r], outline=INK, width=2, fill=ACCENT)
    fill_h = int(h * 0.82)
    d.rounded_rectangle([x + 3, y + h - fill_h, x + wdt - 3, y + h], radius=4, fill=ACCENT)
    for i in range(5):
        ty = y + 8 + i * (h - 16) // 4
        d.line([x + wdt + 3, ty, x + wdt + 10, ty], fill=INK, width=1)
    d.text((x - 8, y - 23), "+1.8\u00b0C", font=ImageFont.truetype(SANS_B, 15), fill=ACCENT)


# --------------------------------------------------------------------------
# Column layout with deterministic auto-fit
# --------------------------------------------------------------------------
# (headline px, headline lh, summary px, summary lh, item gap, section height)
PRESETS = [
    (13.0, 16.0, 10.5, 13.0, 5, 26),
    (12.5, 15.0, 10.0, 12.0, 4, 25),
    (12.0, 14.5, 10.0, 12.0, 3, 24),
    (11.5, 14.0, 9.5, 11.5, 3, 23),
    (11.0, 13.0, 9.5, 11.0, 3, 22),
]


def build_blocks():
    blocks = []
    for name, stories in SECTIONS:
        blocks.append(("sect", name))
        for head, summ in stories:
            blocks.append(("story", (head, summ)))
    blocks.append(("sect", "IN BRIEF"))
    blocks.append(("brief", BUSINESS_BRIEF))
    blocks.append(("brief", SPORT_BRIEF))
    return blocks


def preset_fonts(p):
    hs, hlh, ss, slh, gap, sect_h = p
    return {
        "head": ImageFont.truetype(SERIF_B, int(hs)),
        "hlh": hlh,
        "sum": ImageFont.truetype(SERIF, int(ss)),
        "slh": slh,
        "gap": gap,
        "sect_h": sect_h,
        "sect": ImageFont.truetype(SANS_B, 13),
        "brief": ImageFont.truetype(SERIF, int(ss + 0.5)),
        "blh": slh + 1,
    }


def block_height(kind, payload, F):
    if kind == "sect":
        return F["sect_h"]
    if kind == "story":
        head, summ = payload
        return (len(wrap(head, F["head"], COL_W)) * F["hlh"]
                + len(wrap(summ, F["sum"], COL_W)) * F["slh"] + F["gap"])
    return len(wrap(payload, F["brief"], COL_W)) * F["blh"] + F["gap"] + 2


def fits(blocks, F, cols_height):
    """Simulate the 3-column packing; True if every block lands inside.
    A section header is never left orphaned at a column's foot: it moves
    with at least the block that follows it."""
    col, cy = 0, 0
    for i, (kind, payload) in enumerate(blocks):
        bh = block_height(kind, payload, F)
        need = bh
        if kind == "sect" and i + 1 < len(blocks):
            need += block_height(blocks[i + 1][0], blocks[i + 1][1], F)
        if cy + need > cols_height and col < 2:
            col += 1
            cy = 0
        if cy + bh > cols_height:
            return False
        cy += bh
    return True


# --------------------------------------------------------------------------
# Page construction
# --------------------------------------------------------------------------
def build():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    f_mast = ImageFont.truetype(SERIF_B, 58)
    f_date = ImageFont.truetype(SANS_B, 17)
    f_info = ImageFont.truetype(SANS, 11)
    f_kicker = ImageFont.truetype(SANS_B, 13)
    f_hero = ImageFont.truetype(SERIF_B, 33)
    f_hero_sum = ImageFont.truetype(SERIF, 13)
    f_byline = ImageFont.truetype(SERIF_I, 12)
    f_caption = ImageFont.truetype(SERIF_I, 11.5)
    f_strip = ImageFont.truetype(SANS_B, 12.5)
    f_foot = ImageFont.truetype(SANS, 10.5)

    # --- masthead ---------------------------------------------------------
    d.line([M, 14, W - M, 14], fill=INK, width=1)
    title = "THE DAILY DISPATCH"
    tw = d.textlength(title, font=f_mast)
    d.text(((W - tw) / 2, 20), title, font=f_mast, fill=INK)
    d.line([M, 88, W - M, 88], fill=INK, width=3)
    d.line([M, 93, W - M, 93], fill=INK, width=1)

    # --- date / info bar ---------------------------------------------------
    y = 100
    d.text((M, y + 2), "Vol. I \u00b7 No. 325", font=f_info, fill=GREY)
    right = "ONE PAGE \u00b7 ONE DAY \u00b7 EVERY STORY"
    d.text((W - M - d.textlength(right, font=f_info), y + 2), right, font=f_info, fill=GREY)
    date = "Saturday, 21 November 2026"
    dw = d.textlength(date, font=f_date)
    d.text(((W - dw) / 2, y), date, font=f_date, fill=INK)
    y = 126
    d.line([M, y, W - M, y], fill=INK, width=1)

    # --- hero ---------------------------------------------------------------
    hero_top = y + 10
    hero_left_w = 606
    d.text((M, hero_top), HERO_KICKER, font=f_kicker, fill=ACCENT)
    hy = draw_wrapped(d, M, hero_top + 19, HERO_HEADLINE, f_hero, 37, hero_left_w)
    hy += 3
    hy = draw_wrapped(d, M, hy, HERO_SUMMARY, f_hero_sum, 17, hero_left_w)
    hy += 2
    d.text((M, hy), HERO_BYLINE, font=f_byline, fill=GREY)
    hero_text_bottom = hy + 16

    # hero visual box (right)
    vx0, vy0, vx1 = M + hero_left_w + 18, hero_top, W - M
    box_h = 172
    d.rectangle([vx0, vy0, vx1, vy0 + box_h], outline=INK, width=2)
    d.text((vx0 + 10, vy0 + 7), "THE DAY IN ONE IMAGE", font=f_kicker, fill=GREY)
    draw_globe(img, vx0 + 112, vy0 + box_h // 2 + 8, 72)
    d = ImageDraw.Draw(img)
    draw_thermometer(d, vx0 + 262, vy0 + 44, 84)
    cap_y = vy0 + box_h + 6
    cap_bottom = draw_wrapped(d, vx0, cap_y, HERO_CAPTION, f_caption, 15, vx1 - vx0,
                              fill=GREY, max_lines=3)

    hero_bottom = max(hero_text_bottom, cap_bottom)

    # --- markets strip -------------------------------------------------------
    sy = hero_bottom + 6
    d.rectangle([M, sy, W - M, sy + 24], fill=INK)
    segs = list(STRIP_SEGMENTS)
    while len(segs) > 2 and d.textlength("  ".join(segs), font=f_strip) > CW - 16:
        segs.pop()
    strip = "  \u00b7  ".join(segs)
    # rebuild with separators and re-check once (joiner differs)
    strip = " \u00b7 ".join(segs)
    while len(segs) > 2 and d.textlength(strip, font=f_strip) > CW - 16:
        segs.pop()
        strip = " \u00b7 ".join(segs)
    sw = d.textlength(strip, font=f_strip)
    d.text(((W - sw) / 2, sy + 5), strip, font=f_strip, fill=WHITE)
    cols_top = sy + 34
    cols_height = COL_BOTTOM - cols_top

    # --- columns (first preset that fits wins — deterministic) ----------------
    blocks = build_blocks()
    F = None
    for p in PRESETS:
        cand = preset_fonts(p)
        if fits(blocks, cand, cols_height):
            F = cand
            break
    if F is None:
        F = preset_fonts(PRESETS[-1])

    col, cy = 0, cols_top
    for i, (kind, payload) in enumerate(blocks):
        bh = block_height(kind, payload, F)
        need = bh
        if kind == "sect" and i + 1 < len(blocks):
            need += block_height(blocks[i + 1][0], blocks[i + 1][1], F)
        if cy + need > COL_BOTTOM and col < 2:
            col += 1
            cy = cols_top
        x = COL_X[col]
        if kind == "sect":
            d.rectangle([x, cy + 2, x + COL_W, cy + 20], fill=INK)
            d.text((x + 7, cy + 4), payload, font=F["sect"], fill=WHITE)
            cy += F["sect_h"]
        elif kind == "story":
            head, summ = payload
            cy = draw_wrapped(d, x, cy, head, F["head"], F["hlh"], COL_W)
            cy = draw_wrapped(d, x, cy, summ, F["sum"], F["slh"], COL_W, fill=DARK)
            cy += F["gap"]
        else:
            cy = draw_wrapped(d, x, cy, payload, F["brief"], F["blh"], COL_W)
            cy += F["gap"] + 2

    # --- footer ---------------------------------------------------------------
    d.line([M, H - 28, W - M, H - 28], fill=INK, width=1)
    fw = d.textlength(FOOTER, font=f_foot)
    d.text(((W - fw) / 2, H - 22), FOOTER, font=f_foot, fill=GREY)

    return img


def main():
    out_dir = "/output"
    os.makedirs(out_dir, exist_ok=True)
    img = build()
    img.save(os.path.join(out_dir, "entry.png"), format="PNG", optimize=True)


if __name__ == "__main__":
    main()
