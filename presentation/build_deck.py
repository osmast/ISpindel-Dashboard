#!/usr/bin/env python3
"""Build the final-presentation deck (D4) for the iSpindel project.

Run:  python presentation/build_deck.py
Out:  presentation/iSpindel_Final_Presentation.pptx

The deck has 20 slides and is written for TWO speakers who alternate.
Every slide says which speaker owns it and every content line is a
placeholder inside [ ... ] so the owners only replace the text.

NOTE: this script is a *build tool*, not part of the runtime stack - it is
not imported by the app and is not needed to run the system (NFR-08 is
unaffected: no setting is hard-coded anywhere; the deck is a document).
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

import os

# ---------------------------------------------------------------------------
# Themes / templates. Each entry is a self-contained palette + font, so the
# same 20 slides render in several presentation templates. Colours are
# literals on purpose: this is a document generator, not the web UI.
# ---------------------------------------------------------------------------
def _hex(value):
    """'#RRGGBB' -> RGBColor."""
    v = value.lstrip("#")
    return RGBColor(int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


# Five+ reusable presentation templates. `classic` is the app's brand palette.
THEMES = {
    "classic": {
        "label": "Classic - brand blue + beer amber",
        "ink": "#111827", "muted": "#64748B", "brand": "#0057B7",
        "accent": "#D97706", "accent_dark": "#92400E",
        "paper": "#FFFFFF", "card": "#F1F5F9",
        "card_a": "#FEF3C7", "card_b": "#DBEAFE",
        "font": "Calibri",
    },
    "nordic": {
        "label": "Nordic - deep teal + copper",
        "ink": "#0F2E2E", "muted": "#5B7373", "brand": "#0E7490",
        "accent": "#B45309", "accent_dark": "#7C2D12",
        "paper": "#F8FAF9", "card": "#E8F0EE",
        "card_a": "#FCE7D6", "card_b": "#D5EBEB",
        "font": "Segoe UI",
    },
    "midnight": {
        "label": "Midnight - dark navy + cyan + amber",
        "ink": "#E5EAF2", "muted": "#8B9BB4", "brand": "#22D3EE",
        "accent": "#F59E0B", "accent_dark": "#FCD34D",
        "paper": "#0B1220", "card": "#162033",
        "card_a": "#1E2A3B", "card_b": "#12303A",
        "font": "Segoe UI",
    },
    "mono": {
        "label": "Mono - charcoal + grey, minimal",
        "ink": "#1F2937", "muted": "#6B7280", "brand": "#374151",
        "accent": "#6B7280", "accent_dark": "#4B5563",
        "paper": "#FAFAFA", "card": "#F3F4F6",
        "card_a": "#EDEDED", "card_b": "#E5E7EB",
        "font": "Segoe UI",
    },
    "warm": {
        "label": "Warm - burgundy + gold, serif",
        "ink": "#2B1B1B", "muted": "#7A5C5C", "brand": "#7F1D1D",
        "accent": "#B7791F", "accent_dark": "#78350F",
        "paper": "#FFFBF5", "card": "#F7EDE2",
        "card_a": "#FBEFD8", "card_b": "#F3E1E1",
        "font": "Georgia",
    },
    "ocean": {
        "label": "Ocean - royal blue + coral",
        "ink": "#0B2545", "muted": "#5B6B85", "brand": "#1D4ED8",
        "accent": "#F97316", "accent_dark": "#9A3412",
        "paper": "#F5F9FF", "card": "#E7EFFA",
        "card_a": "#FFE9D6", "card_b": "#DBEAFE",
        "font": "Segoe UI",
    },
}

DEFAULT_THEME = "classic"

# The active palette (reassigned by apply_theme before each build).
INK = _hex("#111827")
MUTED = _hex("#64748B")
BRAND = _hex("#0057B7")
AMBER = _hex("#D97706")
AMBER_DARK = _hex("#92400E")
PAPER = _hex("#FFFFFF")
CARD = _hex("#F1F5F9")
CARD_A = _hex("#FEF3C7")
CARD_B = _hex("#DBEAFE")
FONT = "Calibri"


def apply_theme(name=DEFAULT_THEME):
    """Switch the active palette to one of THEMES (module-level globals)."""
    global INK, MUTED, BRAND, AMBER, AMBER_DARK, PAPER, CARD, CARD_A, CARD_B, FONT
    t = THEMES[name]
    INK = _hex(t["ink"])
    MUTED = _hex(t["muted"])
    BRAND = _hex(t["brand"])
    AMBER = _hex(t["accent"])
    AMBER_DARK = _hex(t["accent_dark"])
    PAPER = _hex(t["paper"])
    CARD = _hex(t["card"])
    CARD_A = _hex(t["card_a"])
    CARD_B = _hex(t["card_b"])
    FONT = t["font"]

SW, SH = Inches(13.333), Inches(7.5)      # 16:9 default for pptx

SPEAKER_A = "SPEAKER A - THE BREWER / BUILDER"
SPEAKER_B = "SPEAKER B - THE BREWMASTER'S VOICE (newcomer)"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def _add_box(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE,
             line_w=Pt(1)):
    box = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        box.fill.background()
    else:
        box.fill.solid()
        box.fill.fore_color.rgb = fill
    if line is None:
        box.line.fill.background()
    else:
        box.line.color.rgb = line
        box.line.width = line_w
    box.shadow.inherit = False
    return box


def _text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
          wrap=True):
    """runs = list of paragraphs; each paragraph = list of (text, size, bold, color, italic)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        for (txt, size, bold, color, *rest) in para:
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.name = FONT
            r.font.color.rgb = color
            if rest and rest[0]:
                r.font.italic = True
    return tb


def _blank(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    _add_box(s, 0, 0, SW, SH, fill=PAPER)
    return s


def _speaker_tag(slide, speaker):
    """Coloured pill in the top-right corner that names the speaker."""
    if speaker == "A":
        fill, txt = CARD_A, AMBER_DARK
        label = SPEAKER_A
    elif speaker == "B":
        fill, txt = CARD_B, BRAND
        label = SPEAKER_B
    else:  # both
        fill, txt = CARD, MUTED
        label = "BOTH SPEAKERS"
    pill = _add_box(slide, SW - Inches(4.9), Inches(0.28), Inches(4.6),
                    Inches(0.46), fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    tf = pill.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.name = FONT
    r.font.color.rgb = txt


def _title(slide, text, speaker=None, kicker=None):
    if kicker:
        _text(slide, Inches(0.6), Inches(0.35), Inches(8), Inches(0.4),
              [[(kicker, 12, True, AMBER)]])
        ty = Inches(0.72)
    else:
        ty = Inches(0.45)
    _text(slide, Inches(0.6), ty, Inches(8), Inches(0.8),
          [[(text, 30, True, INK)]])
    if speaker:
        _speaker_tag(slide, speaker)
    _add_box(slide, Inches(0.63), ty + Inches(0.86), Inches(1.4),
             Pt(3), fill=AMBER)


def _footer(slide, n):
    # thin rule + a rounded slide-number badge (theme-aware)
    _add_box(slide, Inches(0.6), SH - Inches(0.66), Inches(12.13), Pt(1), fill=CARD)
    _text(slide, Inches(0.6), SH - Inches(0.52), Inches(9), Inches(0.35),
          [[("iSpindel Fermentation Monitor - ZHAW Digital Food Processing HS26 - D4",
             10, False, MUTED)]])
    badge = _add_box(slide, SW - Inches(1.2), SH - Inches(0.72), Inches(0.5),
                     Inches(0.38), fill=BRAND, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    tf = badge.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.name = FONT
    r.font.color.rgb = PAPER


def _card(slide, x, y, w, h, heading, bullets, fill=CARD, head_color=INK):
    _add_box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    runs = [[(heading, 15, True, head_color)]]
    for b in bullets:
        runs.append([(b, 13, False, INK)])
    _text(slide, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5),
          h - Inches(0.35), runs)


# ---------------------------------------------------------------------------
# Slide builders
# ---------------------------------------------------------------------------
def slide_title(prs, n):
    s = _blank(prs)
    _add_box(s, 0, 0, SW, Inches(0.35), fill=AMBER)
    _add_box(s, 0, Inches(0.35), SW, Inches(0.15), fill=BRAND)
    _text(s, Inches(1.0), Inches(1.6), SW - Inches(2), Inches(1.4),
          [[("[ Title of your presentation ]", 44, True, INK)]])
    _text(s, Inches(1.0), Inches(2.95), SW - Inches(2), Inches(1.2),
          [[("[ Subtitle - beer + fermentation monitoring with the iSpindel ]",
             20, False, MUTED)]])
    _text(s, Inches(1.0), Inches(4.4), SW - Inches(2), Inches(1.8),
          [[("Speaker A - [ name ]  |  Brewer / Builder", 15, True, AMBER_DARK)],
           [("Speaker B - [ name ]  |  Brewmaster's voice", 15, True, BRAND)],
           [("ZHAW - Digital Food Processing HS26 / AD24 - Final Presentation (D4)",
             13, False, MUTED)],
           [("Date: [ 12.11.2026 ] - 15 minutes plus questions - with live demo",
             13, False, MUTED)]])
    _footer(s, n)
    return s


def slide_agenda(prs, n):
    s = _blank(prs)
    _title(s, "Agenda & who presents what", speaker=None, kicker="OVERVIEW")
    _card(s, Inches(0.6), Inches(1.9), Inches(6.0), Inches(4.6),
          "Speaker A - Brewer / Builder (beer + system)",
          ["1. [ Our two beers: recipe, grain, hops, yeast ]",
           "2. [ Brew day + fermentation process ]",
           "3. [ Architecture, data model, technology ]",
           "4. [ Live demo of the running system ]",
           "5. [ Outlook / next iteration ]"], fill=CARD_A,
          head_color=AMBER_DARK)
    _card(s, Inches(6.9), Inches(1.9), Inches(5.8), Inches(4.6),
          "Speaker B - Brewmaster's voice (user + concept)",
          ["1. [ What a brewmaster needs from the data ]",
           "2. [ The two brewmaster questions ]",
           "3. [ How the concept / recipes were structured ]",
           "4. [ Reading the fermentation curve as a user ]",
           "5. [ Requirement checklist: does it hold up? ]"],
          fill=CARD_B, head_color=BRAND)
    _footer(s, n)
    return s


def two_col(prs, n, title, kicker, speaker, left_head, left_rows,
            right_head, right_rows, fill_l=CARD_A, fill_r=CARD_B,
            hc_l=AMBER_DARK, hc_r=BRAND, note=None):
    s = _blank(prs)
    _title(s, title, speaker=speaker, kicker=kicker)
    _card(s, Inches(0.6), Inches(1.95), Inches(5.95), Inches(4.6),
          left_head, left_rows, fill=fill_l, head_color=hc_l)
    _card(s, Inches(6.75), Inches(1.95), Inches(5.95), Inches(4.6),
          right_head, right_rows, fill=fill_r, head_color=hc_r)
    if note:
        _text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.4),
              [[(note, 12, True, AMBER_DARK)]])
    _footer(s, n)
    return s


def full_card(prs, n, title, kicker, speaker, heading, bullets, fill=CARD,
              head_color=INK, note=None):
    s = _blank(prs)
    _title(s, title, speaker=speaker, kicker=kicker)
    _card(s, Inches(0.6), Inches(1.95), Inches(12.1), Inches(4.6),
          heading, bullets, fill=fill, head_color=head_color)
    if note:
        _text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.4),
              [[(note, 12, True, AMBER_DARK)]])
    _footer(s, n)
    return s


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build(path, theme=DEFAULT_THEME):
    apply_theme(theme)
    prs = Presentation()
    prs.slide_width = SW
    prs.slide_height = SH
    n = 0

    # 1 - Title
    slide_title(prs, n + 1); n += 1

    # 2 - Agenda + speaker split
    slide_agenda(prs, n + 1); n += 1

    # 3 - Why this project exists (both)
    full_card(prs, n + 1, "Why this project exists", "MOTIVATION", None,
              "The gap the system closes",
              ["- [ Today gravity is measured by hand: a few spot values, every sample opens the",
               "  fermenter and adds a contamination risk ]",
               "- [ 'Measured values are only valuable if they are stored reliably, assigned to the",
               "  correct batch and remain accessible later' - exactly this gap is our project ]",
               "- [ Four benefits: process control, quality & traceability, learning from comparisons,",
               "  transfer to industrial food production ]",
               "- [ Non-goals: no actuators, no temperature control, no internet exposure ]"],
              note="Both speak - A ~20 s on brewing reality, B ~20 s on the assignment sentence.")
    n += 1

    # 4 - The two beers (Speaker A + B, one column each)
    two_col(prs, n + 1, "Our two beers - one per presenter", "THE BEER", "A",
            "Beer 1 - [ name ] - Speaker A",
            ["- Style: [ e.g. IPA ]",
             "- Original gravity: [ e.g. 15.9 °P ]",
             "- Malt: [ ... ]",
             "- Hops: [ ... ]",
             "- Yeast: [ ... ]",
             "- Fermentation T: [ e.g. 19-21 °C ]",
             "- Expected FG: [ ~3.2 °P ]"],
            "Beer 2 - [ name ] - Speaker B",
            ["- Style: [ e.g. Weissbier ]",
             "- Original gravity: [ ... °P ]",
             "- Malt: [ ... ]",
             "- Hops: [ ... ]",
             "- Yeast: [ ... ]",
             "- Fermentation T: [ ... °C ]",
             "- Expected FG: [ ... °P ]"],
            hc_l=AMBER_DARK, hc_r=AMBER_DARK)
    n += 1

    # 5 - Recipe construction (Speaker A)
    full_card(prs, n + 1, "How the recipe is built", "RECIPES", "A",
              "Grain -> water -> hops -> yeast",
              ["- [ Water: profile / treatment ]",
               "- [ Mashing: temperature steps and why (e.g. 63 °C for fermentability) ]",
               "- [ Boil: duration, hop schedule for bitterness / aroma ]",
               "- [ Fermentation: yeast strain, pitch rate, temperature window ]",
               "- [ Conditioning / dry hopping: what we plan and when ]"],
              fill=CARD_A, head_color=AMBER_DARK,
              note="Keep it short - this is the 'why'; the numbers sit in the recipes table.")
    n += 1

    # 6 - Brew day + the two brews (both)
    two_col(prs, n + 1, "Brew day and fermentation plan", "PROCESS", None,
            "Brew day - [ 29.10.2026 ]",
            ["- [ Beer 1 brewed ]",
             "- [ Beer 2 brewed ]",
             "- [ iSpindel sanitised and placed in the fermenter ]",
             "- [ Experiment started in the dashboard ]"],
            "Fermentation plan",
            ["- Lag phase: [ ~ hrs, nothing happens yet ]",
             "- Main fermentation: [ gravity falls, temperature rises ]",
             "- End: [ stable gravity over ~2-3 days ]",
             "- [ Expected 7-10 days ]"],
            fill_l=CARD_A, fill_r=CARD_B, hc_l=AMBER_DARK, hc_r=BRAND)
    n += 1

    # 7 - Architecture (Speaker A)
    full_card(prs, n + 1, "Architecture on the automation pyramid", "CONCEPT (D1)", "A",
              "iSpindel -> MQTT -> ingest -> PostgreSQL -> Dash",
              ["- Field level: [ iSpindel - sensor in the fermenter ]",
               "- Control level: [ Raspberry Pi - mosquitto + ingest (data acquisition only) ]",
               "- Supervisory level (MES): [ PostgreSQL - device / experiment / measurement ]",
               "- Enterprise level (ERP): [ out of scope ]",
               "- [ Replace this text with a screenshot of the concept diagram ]"],
              note="Point at the concept diagram (docs/concept.md section 1).")
    n += 1

    # 8 - Data model (Speaker A)
    full_card(prs, n + 1, "Data model", "CONCEPT (D1)", "A",
              "Separated, linked entities (FR-12)",
              ["- device - [ mqtt_name, display_name, first_seen ]",
               "- experiment - [ name (unique), device_id, started_at, ended_at, beer_style, og_plato ]",
               "- measurement - [ device_id, experiment_id (nullable), recorded_at (UTC), tilt, temp,",
               "  gravity, battery, interval, rssi ]",
               "- experiment_event - [ occurred_at, note (dry hopping, temperature raised) ]",
               "- [ One measurement = one row; no schema change for a new iSpindel or experiment ]"],
              note="Insert the ER diagram screenshot from docs/concept.md section 2.")
    n += 1

    # 9 - Technology choice (Speaker A)
    full_card(prs, n + 1, "Technology choice - and why", "CONCEPT (D1)", "A",
              "What we picked and what we rejected",
              ["- MQTT [ prescribed by the assignment as the data interface ]",
               "- PostgreSQL 16 [ relational, timestamptz, constraints = data integrity ]",
               "- Python ingest [ paho-mqtt, one row per transmission ]",
               "- Plotly Dash + gunicorn [ interactive charts, pure Python, no JS build ]",
               "- Podman/Docker Compose [ one stack on laptop and Pi - the same four containers ]",
               "- [ Rejected: e.g. InfluxDB, Node-RED, a spreadsheet - and why ]"],
              note="Justification is part of D1; keep alternatives visible.")
    n += 1

    # 10 - Live demo (Speaker A)
    full_card(prs, n + 1, "Live demo of the running system", "LIVE SYSTEM (D4)", "A",
              "On http://[ hostname ]:8080",
              ["- [ Live device cards: latest gravity, temperature, tilt, battery (FR-13) ]",
               "- [ Chart updates itself within 60 s (FR-14) ]",
               "- [ Start a new experiment - required fields only (FR-01) ]",
               "- [ End the experiment (FR-04), try a duplicate name (FR-02) ]",
               "- [ Compare two experiments in one chart (FR-17) ]",
               "- [ Export the batch as CSV and open it in Excel (FR-21) ]"],
              fill=CARD_A, head_color=AMBER_DARK,
              note="Keep a backup screenshot for every step in case the network fails.")
    n += 1

    # 11 - The two brewmaster questions (Speaker B)
    two_col(prs, n + 1, "The two brewmaster questions", "INTERPRETATION", "B",
            "Question 1 - needs historical data",
            ["- [ e.g. 'Is the fermentation finished - is the gravity stable over 2-3 days?' ]",
             "- [ Why historical: you compare today's value with the last days ]",
             "- [ How the dashboard answers it: batch zones + rate °P/24h (FR-16, FR-20) ]"],
            "Question 2 - needs a comparison",
            ["- [ e.g. 'Which batch fermented faster - this year's or last year's?' ]",
             "- [ Why comparison: two experiments overlaid (FR-17 / FR-18) ]",
             "- [ How the dashboard answers it: overlay + relative time axis ]"],
            fill_l=CARD_B, fill_r=CARD_B, hc_l=BRAND, hc_r=BRAND)
    n += 1

    # 12 - Reading the curve (Speaker B)
    full_card(prs, n + 1, "Reading the fermentation curve", "INTERPRETATION", "B",
              "Lag phase - main fermentation - end",
              ["- Lag phase: [ gravity nearly flat, temperature follows ambient ]",
               "- Main fermentation: [ gravity falls steeply, temperature rises (exothermic) ]",
               "- End: [ gravity stable -> beer ready for the next step ]",
               "- [ This is the hand sketch from the self-study - put it here as a picture ]",
               "- [ Compare: what the sketch predicted vs. what our data actually shows ]"],
              fill=CARD_B, head_color=BRAND,
              note="Speaker B interprets as a user here - no code, just the meaning of the curve.")
    n += 1

    # 13 - Interpreting OUR beer (Speaker B)
    two_col(prs, n + 1, "What our beer actually did", "INTERPRETATION", "B",
            "Beer 1 - [ name ]",
            ["- [ OG ... °P -> current ... °P ]",
             "- [ Attenuation ... %, ABV ... % ]",
             "- [ Rate ~... °P/24h ]",
             "- [ Temperature stayed in / left the window ]",
             "- [ Any anomaly and what it meant ]"],
            "Beer 2 - [ name ]",
            ["- [ OG ... °P -> current ... °P ]",
             "- [ Attenuation ... %, ABV ... % ]",
             "- [ Rate ~... °P/24h ]",
             "- [ Temperature stayed in / left the window ]",
             "- [ Any anomaly and what it meant ]"],
            fill_l=CARD_B, fill_r=CARD_B, hc_l=BRAND, hc_r=BRAND)
    n += 1

    # 14 - Requirement checklist intro (Speaker B)
    full_card(prs, n + 1, "Does it hold up? The requirement checklist", "REQUIREMENTS", "B",
              "31 requirements: 22 Must, 8 Should, 1 Could",
              ["- Experiment management: FR-01 - FR-06",
               "- Data acquisition & storage: FR-07 - FR-12",
               "- Dashboard & visualisation: FR-13 - FR-20",
               "- Data access & export: FR-21 - FR-22",
               "- Non-functional: NFR-01 - NFR-09",
               "- [ Full checklist: presentation/requirements-checklist.md ]"],
              fill=CARD_B, head_color=BRAND,
              note="B is the non-developer voice: she/he checks the system the way a client would.")
    n += 1

    # 15 - Requirements part 1 (Must, experiment + data) (Speaker B)
    two_col(prs, n + 1, "Checklist - experiment & data (Must)", "REQUIREMENTS", "B",
            "Experiment management",
            ["- FR-01 create + start [ MET ]",
             "- FR-02 unique name [ MET ]",
             "- FR-03 one iSpindel per experiment [ MET ]",
             "- FR-04 end experiment [ MET ]",
             "- FR-05 overview list [ MET ]"],
            "Data acquisition",
            ["- FR-07 all iSpindels via MQTT [ MET ]",
             "- FR-08 all fields stored [ MET ]",
             "- FR-09 auto-assign to active batch [ MET ]",
             "- FR-11 no duplicates [ MET ]",
             "- FR-12 separated data model [ MET ]"],
            fill_l=CARD_B, fill_r=CARD_B, hc_l=BRAND, hc_r=BRAND)
    n += 1

    # 16 - Requirements part 2 (Must, dashboard + export + NFR) (Speaker B)
    two_col(prs, n + 1, "Checklist - dashboard, export, NFR (Must)", "REQUIREMENTS", "B",
            "Dashboard & export",
            ["- FR-13 latest values per device [ MET ]",
             "- FR-14 chart auto-update < 60 s [ MET ]",
             "- FR-15 all iSpindels at once [ MET ]",
             "- FR-16 any experiment, any range [ MET ]",
             "- FR-17 two experiments overlaid [ MET ]",
             "- FR-21 CSV export [ MET ]"],
            "Non-functional Must",
            ["- NFR-01 app + DB on the Pi [ MET ]",
             "- NFR-02 LAN only, no internet [ MET ]",
             "- NFR-03 auto start after power loss [ MET ]",
             "- NFR-04 no data loss + backup [ MET ]",
             "- NFR-05 non-programmer, English UI [ MET ]",
             "- NFR-08 README + config file [ MET ]"],
            fill_l=CARD_B, fill_r=CARD_B, hc_l=BRAND, hc_r=BRAND)
    n += 1

    # 17 - Should / Could (Speaker B)
    full_card(prs, n + 1, "Checklist - Should and Could", "REQUIREMENTS", "B",
              "What is expected on top of the Must core",
              ["- FR-06 edit fields + record events [ Should ]",
               "- FR-10 measurements without an active experiment are kept [ Should ]",
               "- FR-18 relative time axis for comparison [ Should ]",
               "- FR-19 stale device / low battery warning [ Should ]",
               "- FR-22 export several experiments / a time range [ Should ]",
               "- FR-20 derived values: attenuation, ABV, rate [ Could - done ]",
               "- NFR-06 smartphone, NFR-07 < 5 s render, NFR-09 UTC + Europe/Zurich [ Should ]"],
              fill=CARD_B, head_color=BRAND,
              note="Mark each one honestly - Must first, then Should, then the one Could.")
    n += 1

    # 18 - Acceptance test T-01..T-08 (Speaker B)
    two_col(prs, n + 1, "Acceptance test - the client's checklist", "REQUIREMENTS", "B",
            "Tests T-01 - T-04",
            ["- T-01 start/duplicate/in use/end [ FR-01-05 ]",
             "- T-02 all iSpindels at once [ FR-07-09, FR-15 ]",
             "- T-03 interval 1 min then 30 min [ FR-11 ]",
             "- T-04 new measurement in < 60 s [ FR-13, FR-14 ]"],
            "Tests T-05 - T-08",
            ["- T-05 completed vs running experiment [ FR-16, FR-17 ]",
             "- T-06 export -> Excel [ FR-21 ]",
             "- T-07 pull the power, reconnect [ NFR-03, NFR-04 ]",
             "- T-08 open from another device [ NFR-02 ]"],
            fill_l=CARD_B, fill_r=CARD_B, hc_l=BRAND, hc_r=BRAND)
    n += 1

    # 19 - Outlook (both)
    full_card(prs, n + 1, "Outlook - what we would improve next", "OUTLOOK", None,
              "Honest gaps and the next iteration",
              ["- [ e.g. MQTT authentication / a device allow-list to stop injection ]",
               "- [ e.g. a shared naming convention across all course batches ]",
               "- [ e.g. a push notification when a fermentation stalls ]",
               "- [ e.g. calibration per device instead of trusting the polynomial ]",
               "- [ e.g. an ERP/MES hand-off - batch records into quality assurance ]"],
              note="A closes the technical wish list, B closes the user wish list.")
    n += 1

    # 20 - Thank you / questions (both)
    s = _blank(prs)
    _add_box(s, 0, 0, SW, Inches(0.35), fill=AMBER)
    _text(s, Inches(1.0), Inches(2.2), SW - Inches(2), Inches(1.4),
          [[("Thank you - questions?", 40, True, INK)]])
    _text(s, Inches(1.0), Inches(3.4), SW - Inches(2), Inches(2.0),
          [[("Speaker A - [ name ]  |  Brewing & build", 16, True, AMBER_DARK)],
           [("Speaker B - [ name ]  |  Brewmaster's voice & requirements", 16, True, BRAND)],
           [("Live dashboard: http://[ hostname ]:8080", 15, False, MUTED)],
           [("Repository: [ link ] - concept (D1), README (NFR-08), self-tests", 15, False, MUTED)]])
    _speaker_tag(s, None)
    _footer(s, n + 1)
    n += 1

    prs.save(path)
    return n


if __name__ == "__main__":
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    theme = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in THEMES else DEFAULT_THEME

    # the deck that is actually presented, built with the default template
    out = os.path.join(here, "iSpindel_Final_Presentation.pptx")
    count = build(out, theme=theme)
    print(f"Wrote {count} slides -> {out}  (theme: {theme})")

    # the template gallery: one full deck per theme, so a different look is
    # one file away and needs no code change
    tdir = os.path.join(here, "templates")
    os.makedirs(tdir, exist_ok=True)
    for name, spec in THEMES.items():
        path = os.path.join(tdir, f"ispindel_template_{name}.pptx")
        slides = build(path, theme=name)
        print(f"  template {name:9s} [{spec['label']}] -> {path}  ({slides} slides)")






