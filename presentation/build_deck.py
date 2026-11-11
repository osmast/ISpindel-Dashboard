#!/usr/bin/env python3
"""Build the final-presentation deck (D4) for the iSpindel project.

Run:  python presentation/build_deck.py
Out:  presentation/iSpindel_Final_Presentation.pptx

The deck follows the four parts the assignment asks for (chapter
"5. Deliverables and Presentation"):

    1. Concept              - architecture, data model, technology choice
    2. Live system          - the running dashboard and its main functions
    3. Interpretation       - our beer vs. the hand sketch, the two questions
    4. Outlook              - what we would improve in a next iteration

It is a *build tool*, not part of the runtime stack: nothing in the app
imports it and it is not needed to run the system (NFR-08 is unaffected -
the deck is a document, not a setting).
"""

import os

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------------------------------------------------------------------------
# Palette - the app's brand blue + beer amber
# ---------------------------------------------------------------------------
def _hex(value):
    """'#RRGGBB' -> RGBColor."""
    v = value.lstrip("#")
    return RGBColor(int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


INK = _hex("#111827")
MUTED = _hex("#64748B")
BRAND = _hex("#0057B7")
AMBER = _hex("#D97706")
AMBER_DARK = _hex("#92400E")
PAPER = _hex("#FFFFFF")
CARD = _hex("#F1F5F9")
CARD_A = _hex("#FEF3C7")
CARD_B = _hex("#DBEAFE")
GREEN = _hex("#15803D")
RED = _hex("#B91C1C")
FONT = "Calibri"

SW, SH = Inches(13.333), Inches(7.5)      # 16:9

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "screenshots")


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


def _hanging(paragraph, indent=0.22):
    """Give a bullet paragraph a hanging indent so wrapped lines align."""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(indent))))
    pPr.set("indent", str(int(-Inches(indent))))


def _text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
          wrap=True, space_after=0, line_spacing=None):
    """runs = list of paragraphs; each paragraph = list of
    (text, size, bold, color, italic)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if space_after:
            p.space_after = Pt(space_after)
        if line_spacing:
            p.line_spacing = line_spacing
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


def _badge(slide, label, fill=CARD, color=MUTED, y=Inches(0.30)):
    """Rounded pill in the top-right corner naming the part."""
    pill = _add_box(slide, SW - Inches(3.6), y, Inches(3.0),
                    Inches(0.44), fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
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
    r.font.color.rgb = color


def _title(slide, text, kicker=None, badge=None, badge_fill=CARD,
           badge_color=MUTED, size=30):
    if kicker:
        _text(slide, Inches(0.6), Inches(0.35), Inches(8.5), Inches(0.4),
              [[(kicker, 12, True, AMBER)]])
        ty = Inches(0.72)
    else:
        ty = Inches(0.45)
    _text(slide, Inches(0.6), ty, Inches(8.6), Inches(0.8),
          [[(text, size, True, INK)]])
    if badge:
        _badge(slide, badge, fill=badge_fill, color=badge_color)
    _add_box(slide, Inches(0.63), ty + Inches(0.86), Inches(1.4),
             Pt(3), fill=AMBER)


def _footer(slide, n):
    _add_box(slide, Inches(0.6), SH - Inches(0.66), Inches(12.13), Pt(1),
             fill=CARD)
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


def _card(slide, x, y, w, h, heading, bullets, fill=CARD, head_color=INK,
          body_size=13, head_size=15):
    _add_box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    runs = [[(heading, head_size, True, head_color)]]
    for b in bullets:
        runs.append([(b, body_size, False, INK)])
    tb = _text(slide, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5),
               h - Inches(0.35), runs, space_after=5)
    # hanging indent for every bullet paragraph (skip the heading)
    for p in tb.text_frame.paragraphs[1:]:
        _hanging(p)
    return tb


def _picture_fit(slide, path, x, y, w, h, border=True):
    """Place a picture centred inside the box, preserving its aspect ratio."""
    from PIL import Image
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = int(iw * scale), int(ih * scale)
    px = x + (w - pw) // 2
    py = y + (h - ph) // 2
    pic = slide.shapes.add_picture(path, px, py, width=pw, height=ph)
    if border:
        pic.line.color.rgb = CARD
        pic.line.width = Pt(1)
    return pic


def _table(slide, x, y, w, h, data, col_widths, header_fill=BRAND,
           header_color=PAPER, body_fill=PAPER, alt_fill=CARD, size=11,
           header_size=11, bold_first_col=False):
    rows, cols = len(data), len(data[0])
    shape = slide.shapes.add_table(rows, cols, x, y, w, h)
    table = shape.table
    table.first_row = True
    table.horz_banding = False
    for i, cw in enumerate(col_widths):
        table.columns[i].width = cw
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            cell = table.cell(r, c)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = header_fill
            else:
                cell.fill.fore_color.rgb = alt_fill if (r % 2 == 0) else body_fill
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = str(val)
            run.font.size = Pt(header_size if r == 0 else size)
            run.font.bold = (r == 0) or (bold_first_col and c == 0)
            run.font.name = FONT
            run.font.color.rgb = header_color if r == 0 else INK
    return table


def _arrow_down(slide, x, y, w, h):
    _add_box(slide, x, y, w, h, fill=MUTED, shape=MSO_SHAPE.DOWN_ARROW)


def _notes(slide, text):
    """Speaker notes: timing, cue and the one thing to say out loud."""
    slide.notes_slide.notes_text_frame.text = text


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------
def slide_title(prs, n):
    s = _blank(prs)
    _add_box(s, 0, 0, SW, Inches(0.35), fill=AMBER)
    _add_box(s, 0, Inches(0.35), SW, Inches(0.15), fill=BRAND)

    _text(s, Inches(1.0), Inches(1.35), SW - Inches(2), Inches(0.4),
          [[("ZHAW - DIGITAL FOOD PROCESSING HS26 / AD24", 13, True, AMBER)]])
    _text(s, Inches(1.0), Inches(1.85), SW - Inches(2), Inches(1.3),
          [[("iSpindel Fermentation Monitor", 46, True, INK)]])
    _text(s, Inches(1.0), Inches(3.05), SW - Inches(2), Inches(1.0),
          [[("Two beers, one dashboard - concept, live system, data "
             "interpretation, outlook", 20, False, MUTED)]])

    _add_box(s, Inches(1.0), Inches(4.15), Inches(5.6), Pt(2), fill=CARD)
    _text(s, Inches(1.0), Inches(4.35), SW - Inches(2), Inches(1.8),
          [[("Final presentation (D4)  -  12.11.2026", 15, True, INK)],
           [("15 minutes plus questions  -  with live demo and tasting", 14, False, MUTED)],
           [("Oskar  -  Dark Day (dark stout)   |   Anja  -  Mango Maracuya Dream",
             14, True, BRAND)],
           [("One beer logged with the iSpindel, one assessed the traditional way.",
             13, False, MUTED)],
           [("Live dashboard:  http://[ hostname ]:8080", 13, False, MUTED)]],
          space_after=4)
    _notes(s, "0:00-0:30 | Oskar & Anja. Welcome, name the two beers, one sentence "
              "on what the system does. Mention the live demo and the tasting.")
    _footer(s, n)
    return s


def slide_agenda(prs, n):
    s = _blank(prs)
    _title(s, "The presentation in four parts", kicker="AGENDA",
           badge="D4  -  15 MIN + QUESTIONS")

    parts = [
        ("1", "Concept", "Architecture on the automation pyramid, the data "
         "model, and the technology choice with its justification.", CARD_A,
         AMBER_DARK),
        ("2", "Live system", "The running web app: device cards, live chart, "
         "start/end an experiment, compare batches, CSV export.", CARD_B, BRAND),
        ("3", "Interpretation of the data", "Mango Maracuya Dream (logged) and "
         "Dark Day (traditional), the hand sketch, the two questions - and a "
         "tasting of both beers.", CARD_A, AMBER_DARK),
        ("4", "Outlook", "What we would improve in a next iteration - technical "
         "and user-facing.", CARD_B, BRAND),
    ]
    x0, y0 = Inches(0.6), Inches(1.95)
    cw, ch, gap = Inches(5.95), Inches(2.15), Inches(0.23)
    for i, (num, head, body, fill, hc) in enumerate(parts):
        col, row = i % 2, i // 2
        x = x0 + col * (cw + gap)
        y = y0 + row * (ch + gap)
        _add_box(s, x, y, cw, ch, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        _text(s, x + Inches(0.25), y + Inches(0.18), Inches(0.7), Inches(0.7),
              [[(num, 30, True, hc)]])
        _text(s, x + Inches(0.95), y + Inches(0.2), cw - Inches(1.2),
              Inches(0.5), [[(head, 17, True, hc)]])
        _text(s, x + Inches(0.95), y + Inches(0.72), cw - Inches(1.2),
              ch - Inches(0.9), [[(body, 13, False, INK)]])
    _text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.4),
          [[("Must requirements first - Should and Could only add value on top "
             "of a working core system.", 12, True, AMBER_DARK)]])
    _notes(s, "0:30-1:00 | Both. Walk the four parts; mention the web-app demo "
              "and the tasting so the audience knows the structure.")
    _footer(s, n)
    return s


def slide_architecture(prs, n):
    s = _blank(prs)
    _title(s, "Architecture on the automation pyramid", kicker="1 - CONCEPT",
           badge="1  -  CONCEPT", badge_fill=CARD_A, badge_color=AMBER_DARK)

    # Left: the data flow, one box per level
    x, w = Inches(0.6), Inches(5.7)
    y = Inches(1.95)
    bh, gap = Inches(0.82), Inches(0.22)
    levels = [
        ("FIELD", "iSpindel in the fermenter",
         "tilt -> gravity, temperature, battery", CARD_A, AMBER_DARK),
        ("CONTROL - RASPBERRY PI", "mosquitto + ingest service",
         "7 MQTT messages -> one row per transmission", CARD_B, BRAND),
        ("SUPERVISORY (MES)", "PostgreSQL",
         "device / experiment / measurement", CARD_A, AMBER_DARK),
        ("USER LEVEL", "Plotly Dash + gunicorn",
         "browser in the local network, http://hostname:8080", CARD_B, BRAND),
    ]
    for i, (lvl, comp, detail, fill, hc) in enumerate(levels):
        _add_box(s, x, y, w, bh, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        _text(s, x + Inches(0.2), y + Inches(0.08), w - Inches(0.4),
              Inches(0.3), [[(lvl, 10, True, hc)]])
        _text(s, x + Inches(0.2), y + Inches(0.32), w - Inches(0.4),
              Inches(0.3), [[(comp, 14, True, INK)]])
        _text(s, x + Inches(0.2), y + Inches(0.58), w - Inches(0.4),
              Inches(0.25), [[(detail, 10, False, MUTED)]])
        if i < len(levels) - 1:
            _arrow_down(s, x + w // 2 - Inches(0.12), y + bh + Inches(0.02),
                        Inches(0.24), gap - Inches(0.04))
        y += bh + gap

    # Right: the level table
    data = [
        ["Level", "Component", "Why it belongs there"],
        ["Field", "iSpindel", "raw process data: tilt -> gravity, temperature, battery"],
        ["Control", "Pi: mosquitto + ingest", "receives and processes locally; monitoring only, no actuators"],
        ["Supervisory (MES)", "PostgreSQL", "structured storage and assignment of measurements to batches"],
        ["Enterprise (ERP)", "-", "out of scope; a later batch-management / QA hand-off"],
    ]
    _table(s, Inches(6.55), Inches(1.95), Inches(6.18), Inches(3.9), data,
           [Inches(1.35), Inches(1.75), Inches(3.08)], size=10.5,
           header_size=10.5, bold_first_col=True)
    _text(s, Inches(6.55), Inches(6.0), Inches(6.18), Inches(0.5),
          [[("Monitoring only: the control level acquires data, it does not "
             "control the fermenter.", 11, True, AMBER_DARK)]])
    _notes(s, "1:00-2:00 | Concept. Point at the four levels; stress monitoring "
              "only, no actuators. The broker may run off the Pi.")
    _footer(s, n)
    return s


def slide_data_model(prs, n):
    s = _blank(prs)
    _title(s, "Data model: separated, linked entities", kicker="1 - CONCEPT",
           badge="1  -  CONCEPT", badge_fill=CARD_A, badge_color=AMBER_DARK)

    _picture_fit(s, os.path.join(HERE, "db", "er_diagram_slide.png"),
                 Inches(0.6), Inches(1.95), Inches(7.2), Inches(4.35))

    _card(s, Inches(8.0), Inches(1.95), Inches(4.73), Inches(4.35),
          "Constraints that carry requirements",
          ["- experiment.name UNIQUE  ->  FR-02",
           "- EXCLUDE gist (device_id, tstzrange)  ->  FR-03 / FR-09",
           "- measurement UNIQUE (device_id, recorded_at)  ->  FR-11",
           "- experiment_id nullable  ->  FR-10",
           "- new device/experiment: no schema change  ->  FR-12",
           "- one transmission = one row"],
          fill=CARD_B, head_color=BRAND, body_size=11)
    _text(s, Inches(0.6), Inches(6.4), Inches(12.1), Inches(0.4),
          [[("The database enforces the rules - the dashboard does not have to "
             "trust its own code.", 12, True, AMBER_DARK)]])
    _notes(s, "2:00-3:00 | Concept. The database enforces the rules: unique name, "
              "one active experiment, no duplicate rows. A new device or experiment "
              "needs no schema change.")
    _footer(s, n)
    return s


def slide_technology(prs, n):
    s = _blank(prs)
    _title(s, "Technology choice - and why", kicker="1 - CONCEPT",
           badge="1  -  CONCEPT", badge_fill=CARD_A, badge_color=AMBER_DARK)

    data = [
        ["Layer", "Choice", "Why this one", "Alternative rejected"],
        ["Storage", "PostgreSQL 16", "relational batch structure, timestamptz (UTC, DST-safe), exclusion constraints enforce one active experiment", "SQLite / InfluxDB"],
        ["Acquisition", "Python + paho-mqtt", "assembles 7 messages into one row, normalises units, reconnects after outages", "Node-RED / Telegraf"],
        ["Dashboard", "Plotly Dash + Tailwind", "native Plotly charts, callbacks in Python, free responsive layout", "Grafana / Streamlit"],
        ["Broker", "mosquitto", "data stays in the local network; no public broker", "public broker / HiveMQ"],
        ["Web server", "gunicorn", "restart after a power failure, no debugger on 0.0.0.0", "Dash development server"],
        ["Deployment", "Podman / Docker Compose", "the same stack on a laptop and on the Pi - three core containers (db, broker, dashboard) plus optional ingest", "bare-metal install"],
    ]
    _table(s, Inches(0.6), Inches(1.95), Inches(12.13), Inches(4.5), data,
           [Inches(1.35), Inches(2.35), Inches(5.55), Inches(2.88)],
           size=10.5, header_size=10.5, bold_first_col=True)
    _text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.4),
          [[("The full justification, the alternatives and the assumptions "
             "A1-A8 are in the D1 concept.", 12, True, AMBER_DARK)]])
    _notes(s, "3:00-4:00 | Concept. One line per layer: what we picked, why, what "
              "we rejected. The full justification is in D1.")
    _footer(s, n)
    return s


def slide_live_demo_placeholder(prs, n):
    s = _blank(prs)
    _title(s, "Live demo - the web app", kicker="2 - LIVE SYSTEM",
           badge="2  -  LIVE SYSTEM", badge_fill=CARD_B, badge_color=BRAND)

    # The big callout: leave the deck, show the app, come back here.
    _add_box(s, Inches(0.6), Inches(1.95), Inches(12.13), Inches(1.15),
             fill=CARD_B, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(s, Inches(0.9), Inches(2.05), Inches(11.5), Inches(0.5),
          [[("Switch to the web app now  ->  http://[ hostname ]:8080",
             22, True, BRAND)]])
    _text(s, Inches(0.9), Inches(2.55), Inches(11.5), Inches(0.4),
          [[("Show the running system, then return to this slide for the next topic.",
             13, False, MUTED)]])

    _card(s, Inches(0.6), Inches(3.3), Inches(5.95), Inches(3.2),
          "What we will show in the app",
          ["1. Device cards: latest gravity, temperature, tilt, battery (FR-13)",
           "2. Live chart updates within 60 s, no reload (FR-14)",
           "3. Start an experiment with the required fields only (FR-01)",
           "4. Duplicate name -> clear error (FR-02); end the experiment (FR-04)",
           "5. Compare two experiments + relative time axis (FR-17 / FR-18)",
           "6. Export the batch as CSV and open it in Excel (FR-21)"],
          fill=CARD_B, head_color=BRAND, body_size=11.5)

    _card(s, Inches(6.75), Inches(3.3), Inches(5.98), Inches(3.2),
          "If the network fails",
          ["- The same states are in presentation/screenshots/ as backup",
           "- 00_dashboard_overview.png: the whole page",
           "- 07_popup_setup_experiment.png: start an experiment",
           "- 05_tab_devices_brokers.png: devices + brokers",
           "- 03_chart_comparison_2experiments.png: comparison chart",
           "- 14_mobile_responsive.png: the phone view"],
          fill=CARD_A, head_color=AMBER_DARK, body_size=11.5)
    _notes(s, "4:00-8:00 | Oskar. Switch to the web app, show the six functions, "
              "then return to this slide. If the network fails, use the backup "
              "screenshots.")
    _footer(s, n)
    return s


def slide_two_questions(prs, n):
    s = _blank(prs)
    _title(s, "The two brewmaster questions", kicker="3 - INTERPRETATION",
           badge="3  -  INTERPRETATION", badge_fill=CARD_A, badge_color=AMBER_DARK)

    _card(s, Inches(0.6), Inches(1.95), Inches(5.95), Inches(4.55),
          "Question 1 - needs historical data",
          ["\"Is the Mango Maracuya Dream fermentation finished - is the gravity stable over the last 2-3 days?\"",
           "",
           "Why historical: today's value only means something against the last days.",
           "",
           "How the dashboard answers it:",
           "- the whole experiment over its full duration (FR-16)",
           "- the rate in °P/24 h and the target FG (FR-20)",
           "- a stable line at the end = ready for the next step"],
          fill=CARD_A, head_color=AMBER_DARK, body_size=12.5)

    _card(s, Inches(6.75), Inches(1.95), Inches(5.98), Inches(4.55),
          "Question 2 - needs a comparison",
          ["\"Which batch fermented faster - Mango Maracuya Dream or a previous batch?\"",
           "",
           "Why a comparison: two batches only become comparable when they are overlaid.",
           "",
           "How the dashboard answers it:",
           "- two experiments in one chart (FR-17)",
           "- the axis switched to hours since start (FR-18)",
           "- the same gravity and temperature scales for both"],
          fill=CARD_B, head_color=BRAND, body_size=12.5)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("Dark Day has no sensor data, so it is assessed the traditional way "
             "(next slides). The dashboard answers Q1 and Q2 for the logged beer.",
             12, True, AMBER_DARK)]])
    _notes(s, "8:00-9:00 | Interpretation. Read both questions; say which needs "
              "history and which needs a comparison. Note that Dark Day has no "
              "sensor data and is assessed traditionally.")
    _footer(s, n)
    return s


def slide_sketch(prs, n):
    s = _blank(prs)
    _title(s, "The hand sketch vs. the real fermentation",
           kicker="3 - INTERPRETATION", badge="3  -  INTERPRETATION",
           badge_fill=CARD_A, badge_color=AMBER_DARK)

    _card(s, Inches(0.6), Inches(1.95), Inches(5.35), Inches(4.55),
          "What we expected (hand sketch)",
          ["Lag phase: gravity nearly flat, temperature follows the ambient.",
           "",
           "Main fermentation: gravity falls steeply, temperature rises because the yeast is exothermic.",
           "",
           "End of fermentation: gravity stable over 2-3 days - the beer is ready for the next step.",
           "",
           "The sketch is the reference we compare the measured curve against."],
          fill=CARD_A, head_color=AMBER_DARK, body_size=12.5)

    _picture_fit(s, os.path.join(SHOTS, "mango_device_card.png"),
                 Inches(6.15), Inches(1.95), Inches(6.58), Inches(4.55))
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("The measured Mango curve shows the expected steep main phase; the last "
             "MTB9 segment is the device out of the fermenter, not fermentation.",
             12, True, AMBER_DARK)]])
    _notes(s, "9:00-10:00 | Interpretation. Compare the sketch (lag / main / end) "
              "with the Mango curve. Point at the MTB9 artifact honestly.")
    _footer(s, n)
    return s


def slide_mango(prs, n):
    s = _blank(prs)
    _title(s, "Mango Maracuya Dream - the logged beer",
           kicker="3 - INTERPRETATION  -  ANJA", badge="3  -  INTERPRETATION",
           badge_fill=CARD_A, badge_color=AMBER_DARK, size=26)

    _picture_fit(s, os.path.join(SHOTS, "mango_device_card.png"),
                 Inches(0.6), Inches(1.95), Inches(5.6), Inches(4.55))

    _card(s, Inches(6.45), Inches(1.95), Inches(6.28), Inches(2.15),
          "The batch",
          ["- iSpindel MTB9, responsible Anja",
           "- start 29.10. 19:41, end 05.11. 19:32",
           "- 203 measurements, interval 900 s",
           "- original gravity 13.5 °P"],
          fill=CARD_A, head_color=AMBER_DARK, body_size=12)

    _card(s, Inches(6.45), Inches(4.3), Inches(6.28), Inches(2.2),
          "The fermentation",
          ["- 13.5 °P -> about 5 °P by 01.11. - the steep main phase",
           "- the last segment is the device out of the fermenter (artifact), not fermentation",
           "- temperature around 16 °C",
           "- Q1: the stable tail answers \"is it finished?\"; Q2: the overlay answers \"which faster?\""],
          fill=CARD_B, head_color=BRAND, body_size=11.5)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("Only Mango Maracuya Dream was logged with the iSpindel; the other "
             "batches in the system belong to other teams.", 12, True, AMBER_DARK)]])
    _notes(s, "10:00-10:30 | Anja. This is the only beer with iSpindel data: the "
              "batch facts, the curve, and the honest MTB9 artifact. Q1 and Q2 are "
              "answered here.")
    _footer(s, n)
    return s


def slide_real_curve(prs, n):
    s = _blank(prs)
    _title(s, "All four batches - the real curves",
           kicker="3 - INTERPRETATION  -  ANJA",
           badge="3  -  INTERPRETATION", badge_fill=CARD_A,
           badge_color=AMBER_DARK)

    _picture_fit(s, os.path.join(HERE, "plots", "mango_fermentation.png"),
                 Inches(0.6), Inches(1.95), Inches(7.7), Inches(4.55))

    _card(s, Inches(8.5), Inches(1.95), Inches(4.23), Inches(4.55),
          "What the curves say",
          ["- Mango (amber) is highlighted; CoCo, Honig and Lemon are the comparison batches",
           "- all four show the same shape: a steep main phase, then a slow tail",
           "- the X markers are the device-out points (tilt ~90°)",
           "- Mango real end 31.10. 20:27; UI end 05.11. 19:32"],
          fill=CARD_A, head_color=AMBER_DARK, body_size=10.5)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("The gap is not fermentation - it is the iSpindel lying outside the "
             "fermenter.", 12, True, AMBER_DARK)]])
    _notes(s, "10:30-11:30 | Anja. The real curve ends on 31.10.; the 05.11. point "
              "is the device out of the fermenter. This is the honest reading of the "
              "data.")
    _footer(s, n)
    return s


def slide_real_length(prs, n):
    s = _blank(prs)
    _title(s, "The real experiment length",
           kicker="3 - INTERPRETATION  -  ANJA",
           badge="3  -  INTERPRETATION", badge_fill=CARD_A,
           badge_color=AMBER_DARK)

    _picture_fit(s, os.path.join(HERE, "plots", "mango_duration.png"),
                 Inches(0.6), Inches(1.95), Inches(7.7), Inches(4.55))

    _card(s, Inches(8.5), Inches(1.95), Inches(4.23), Inches(4.55),
          "UI end vs. real end",
          ["- UI end: 05.11. 19:32 (button pressed)",
           "- last measurement: 05.11. 13:14 (device out)",
           "- real fermentation end: 31.10. 20:27",
           "- real length: 2.1 days; the UI says 7.0 days",
           "- code fix: ending an experiment now stores the last measurement as `ended_at`"],
          fill=CARD_B, head_color=BRAND, body_size=10.5)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("The stored end time now follows the data, not the click - FR-04.",
             12, True, AMBER_DARK)]])
    _notes(s, "11:30-12:30 | Anja. The UI end is 4.7 days after the last real "
              "measurement. The code now stores the last measurement as the end, so "
              "the dashboard tells the same story as the data.")
    _footer(s, n)
    return s


def slide_dark_doubt(prs, n):
    s = _blank(prs)
    _title(s, "Dark Day - the dark stout (Oskar)",
           kicker="3 - INTERPRETATION", badge="3  -  INTERPRETATION",
           badge_fill=CARD_A, badge_color=AMBER_DARK)

    _card(s, Inches(0.6), Inches(1.95), Inches(5.95), Inches(4.55),
          "Why there is no iSpindel curve",
          ["- Dark Day was brewed by Oskar, but the iSpindel was in the Mango fermenter.",
           "",
           "So the dark stout has no sensor data - no gravity/temperature curve in the dashboard.",
           "",
           "It is assessed the traditional way after fermentation: hydrometer readings and a sensory evaluation.",
           "",
           "This is the honest limitation of the project: not every beer was instrumented."],
          fill=CARD_A, head_color=AMBER_DARK, body_size=12.5)

    _card(s, Inches(6.75), Inches(1.95), Inches(5.98), Inches(4.55),
          "Traditional assessment after fermentation",
          ["- Hydrometer: OG [ ... °P ] -> FG [ ... °P ], ABV [ ... % ]",
           "- Appearance: [ colour, clarity, head ]",
           "- Aroma: [ roast, coffee, chocolate, ... ]",
           "- Flavour: [ bitterness, body, finish ]",
           "- Mouthfeel: [ carbonation, warmth ]",
           "- Overall: [ the brewer's verdict ]"],
          fill=CARD_B, head_color=BRAND, body_size=12.5)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("The traditional method is the reference the dashboard would replace - "
             "for the one beer that was instrumented.", 12, True, AMBER_DARK)]])
    _notes(s, "12:30-13:15 | Oskar. Explain why Dark Day has no curve and how a "
              "dark stout is assessed traditionally. Fill in the hydrometer and "
              "sensory values before the talk.")
    _footer(s, n)
    return s


def slide_tasting(prs, n):
    s = _blank(prs)
    _title(s, "Tasting both beers",
           kicker="3 - INTERPRETATION  -  OSKAR & ANJA",
           badge="3  -  INTERPRETATION",
           badge_fill=CARD_A, badge_color=AMBER_DARK)

    _card(s, Inches(0.6), Inches(1.95), Inches(5.95), Inches(4.55),
          "Dark Day - Oskar",
          ["Appearance: [ ... ]",
           "Aroma: [ ... ]",
           "Flavour: [ ... ]",
           "Mouthfeel: [ ... ]",
           "Overall: [ ... ]"],
          fill=CARD_A, head_color=AMBER_DARK, body_size=13)

    _card(s, Inches(6.75), Inches(1.95), Inches(5.98), Inches(4.55),
          "Mango Maracuya Dream - Anja",
          ["Appearance: [ ... ]",
           "Aroma: [ ... ]",
           "Flavour: [ ... ]",
           "Mouthfeel: [ ... ]",
           "Overall: [ ... ]"],
          fill=CARD_B, head_color=BRAND, body_size=13)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("Taste both beers with the audience - the sensory result is the other "
             "half of the interpretation.", 12, True, AMBER_DARK)]])
    _notes(s, "13:15-14:15 | Oskar & Anja. Taste both beers and describe them: "
              "appearance, aroma, flavour, mouthfeel, overall. Fill in the notes "
              "before the talk.")
    _footer(s, n)
    return s


def slide_outlook(prs, n):
    s = _blank(prs)
    _title(s, "Outlook - the next iteration", kicker="4 - OUTLOOK",
           badge="4  -  OUTLOOK", badge_fill=CARD_B, badge_color=BRAND)

    _card(s, Inches(0.6), Inches(1.95), Inches(5.95), Inches(4.55),
          "Technical improvements",
          ["- MQTT authentication and a device allow-list - today anybody who can publish can inject values",
           "- Per-device calibration instead of trusting the polynomial",
           "- A second iSpindel so every beer is logged, not only the one with the sensor",
           "- A push notification when a fermentation stalls or the battery is low",
           "- A shared naming convention across all course batches",
           "- An ERP / MES hand-off: batch records into quality assurance"],
          fill=CARD_B, head_color=BRAND, body_size=12)

    _card(s, Inches(6.75), Inches(1.95), Inches(5.98), Inches(4.55),
          "User-facing improvements",
          ["- A structured sensory sheet for the traditional assessment",
           "- A mobile-first pass on the experiment dialogs",
           "- Compare batches across cohorts, not only within one semester",
           "- Export templates for QA and a one-click fermentation report",
           "- Keep the Must core stable - Should and Could only add value on top"],
          fill=CARD_A, head_color=AMBER_DARK, body_size=12)
    _text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.35),
          [[("The next iteration starts from a working Must core, not from a "
             "new feature list.", 12, True, AMBER_DARK)]])
    _notes(s, "14:15-14:45 | Outlook. Technical first, then user-facing. Close with: "
              "the next iteration starts from a working Must core.")
    _footer(s, n)
    return s


def slide_thanks(prs, n):
    s = _blank(prs)
    _add_box(s, 0, 0, SW, Inches(0.35), fill=AMBER)
    _add_box(s, 0, Inches(0.35), SW, Inches(0.15), fill=BRAND)
    _text(s, Inches(1.0), Inches(1.9), SW - Inches(2), Inches(1.2),
          [[("Thank you - questions?", 42, True, INK)]])
    _text(s, Inches(1.0), Inches(3.2), SW - Inches(2), Inches(2.4),
          [[("Live dashboard:  http://[ hostname ]:8080", 16, True, BRAND)],
           [("Repository:  [ link ]", 15, False, MUTED)],
           [("D1 concept  -  D2 running system on the Pi  -  D3 source code "
             "with README and config.yml", 15, False, MUTED)],
           [("Oskar  -  Dark Day   |   Anja  -  Mango Maracuya Dream",
             15, True, AMBER_DARK)]],
          space_after=6)
    _badge(s, "D4  -  THANK YOU", fill=CARD, color=MUTED, y=Inches(0.72))
    _notes(s, "14:45-15:00 | Oskar & Anja. Thank you, invite questions. Keep the "
              "live dashboard open for the demo during Q&A.")
    _footer(s, n)
    return s


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build(path):
    prs = Presentation()
    prs.slide_width = SW
    prs.slide_height = SH
    n = 0

    slide_title(prs, n + 1); n += 1
    slide_agenda(prs, n + 1); n += 1
    slide_architecture(prs, n + 1); n += 1
    slide_data_model(prs, n + 1); n += 1
    slide_technology(prs, n + 1); n += 1
    slide_live_demo_placeholder(prs, n + 1); n += 1
    slide_two_questions(prs, n + 1); n += 1
    slide_sketch(prs, n + 1); n += 1
    slide_mango(prs, n + 1); n += 1
    slide_real_curve(prs, n + 1); n += 1
    slide_real_length(prs, n + 1); n += 1
    slide_dark_doubt(prs, n + 1); n += 1
    slide_tasting(prs, n + 1); n += 1
    slide_outlook(prs, n + 1); n += 1
    slide_thanks(prs, n + 1); n += 1

    prs.save(path)
    return n


if __name__ == "__main__":
    out = os.path.join(HERE, "iSpindel_Final_Presentation.pptx")
    count = build(out)
    print(f"Wrote {count} slides -> {out}")
