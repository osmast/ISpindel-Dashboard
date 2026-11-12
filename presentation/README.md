# Presentation folder (D4)

Everything needed for the final presentation (12.11.2026, 15 min + questions).

The deck follows the four parts the assignment asks for in chapter
**"5. Deliverables and Presentation"**:

1. **Concept** - architecture, data model, technology choice
2. **Live system** - the running web app and its main functions
3. **Interpretation of the data** - Mango Maracuya Dream (logged) and Dark Day
   (traditional), the hand sketch, the two brewmaster questions, and a tasting
4. **Outlook** - what we would improve in a next iteration

| File | What it is |
| --- | --- |
| `iSpindel_Final_Presentation.pptx` | the 15-slide deck (built, with speaker notes) |
| `build_deck.py` | the generator; edit the text here and re-run to rebuild the deck |
| `plot_fermentation.py` | builds the two matplotlib figures from the real CSV |
| `data/mango_maracuya.csv` | the real FR-21 export from the live dashboard (203 rows) |
| `plots/` | `mango_fermentation.png` and `mango_duration.png` |
| `requirements-checklist.md` | separate handout for the acceptance test (not repeated in the deck) |
| `screenshots/` | 16 PNGs of every live feature + popup from the Pi, with `INDEX.md` |
| `capture_screenshots.sh` | re-capture the static shots (curl check + headless Chrome) |
| `db/` | the ER diagrams (Graphviz source + SVG + PNG); `db/er_diagram_views.*` includes both dashboard views, `db/README.md` justifies them |

Rebuild the deck after editing `build_deck.py`:

```bash
python presentation/build_deck.py
```

Rebuild the plots after a new CSV export:

```bash
python presentation/plot_fermentation.py
```

`python-pptx` and `matplotlib` are only needed to *build* the deck and the plots;
they are not part of the runtime stack and nothing in the app imports them.

## The two beers

| Beer | Brewer | Logged with the iSpindel? | How it is assessed |
| --- | --- | --- | --- |
| **Mango Maracuya Dream** | Anja | **yes** - iSpindel MTB9, 203 measurements, OG 13.5 °P | the dashboard curve + the two questions |
| **Dark Day** (dark stout) | Oskar | **no** - the iSpindel was in the Mango fermenter | the traditional way after fermentation: hydrometer + sensory evaluation |

Only Mango Maracuya Dream is "our" logged beer. The other batches in the system
(CoCo Jambo, Honig Bier, Lemon Pale Lager) belong to other teams and are not
presented as ours.

## The real data and the two plots

The CSVs are the real FR-21 exports from `https://beer.chios.ch/` (the production
Pi behind Cloudflare): `mango_maracuya.csv`, `coco_jambo.csv`, `honig_bier.csv`
and `lemon_pale_lager.csv`. The table below is Mango's timeline; the other three
batches are overlaid in the same figure for comparison.

| | time |
| --- | --- |
| first measurement | 29.10. 18:54 |
| **real fermentation end** (last measurement before the 4.7-day gap) | **31.10. 20:27** |
| last measurement (device out of the fermenter, tilt ~90°) | 05.11. 13:14 |
| UI end (the moment "End experiment" was pressed) | 05.11. 19:32 |
| **real fermentation length** | **2.1 days** |
| UI length | 7.0 days |

* `plots/mango_fermentation.png` - **all four batches** overlaid (Mango
  highlighted): gravity on top, temperature below; the Mango real window is
  shaded, the UI end is a dotted line, and every device-out point is an X marker.
* `plots/mango_duration.png` - Mango's three end times as bars: UI end, last
  measurement, real fermentation end.

The app was changed to match the data: `end_experiment()` in
[`main.py`](../main.py:1678) now stores the **last measurement** as `ended_at`
(with `now()` only when the experiment has no measurement at all), so the
dashboard no longer reports the click time as the end of the fermentation.

## The 15 slides

| # | Part | Slide | What it says |
| --- | --- | --- | --- |
| 1 | - | Title | Oskar (Dark Day) + Anja (Mango Maracuya Dream), date, live-dashboard host |
| 2 | - | The presentation in four parts | agenda + timing |
| 3 | 1 Concept | Architecture on the automation pyramid | field / control / MES / user level |
| 4 | 1 Concept | Data model | ER diagram + the constraints that carry FRs |
| 5 | 1 Concept | Technology choice - and why | PostgreSQL, paho-mqtt, Dash, mosquitto, gunicorn, Compose + rejected alternatives |
| 6 | 2 Live system | Live demo - the web app | **placeholder**: switch to the app, show the six functions, return |
| 7 | 3 Interpretation | The two brewmaster questions | Q1 needs history, Q2 needs a comparison |
| 8 | 3 Interpretation | The hand sketch vs. the real fermentation | lag / main / end vs. the Mango curve |
| 9 | 3 Interpretation | Mango Maracuya Dream - the logged beer | Anja's batch: MTB9, 203 measurements, OG 13.5 °P |
| 10 | 3 Interpretation | The real fermentation curve | the matplotlib curve + the artifact point |
| 11 | 3 Interpretation | The real experiment length | 2.1 days real vs. 7.0 days in the UI + the code fix |
| 12 | 3 Interpretation | Dark Day - the dark stout | Oskar's beer: no sensor data, assessed traditionally |
| 13 | 3 Interpretation | Tasting both beers | Oskar and Anja describe Dark Day and Mango Maracuya Dream |
| 14 | 4 Outlook | Outlook - the next iteration | technical + user-facing improvements |
| 15 | - | Thank you - questions? | live dashboard, repository, D1-D3 |

Every slide carries **speaker notes** with the timing and the one thing to say out
loud. The notes are the fastest way to rehearse the 15 minutes.

## The web-app placeholder (slide 6)

Slide 6 is deliberately a **placeholder**: it says what will be shown in the app,
then you switch to `http://[ hostname ]:8080`, demonstrate the six functions, and
return to the same slide for the next topic. The right-hand card lists the backup
screenshots in case the network fails.

## What to fill in

The deck is content-complete, but a few values are still placeholders in `[ ... ]`:

* the **host name** of the live dashboard (slides 1, 6, 15)
* the **repository link** (slide 15)
* the exact wording of the **two brewmaster questions** (slide 7) - confirm them
  with the brewmaster before the talk
* the **hand sketch** itself (slide 8) - the deck describes it in text; paste the
  photographed sketch over the left card if you have it
* **Dark Day** hydrometer values (OG, FG, ABV) and sensory notes (slide 12)
* the **tasting notes** for both beers (slide 13)

The Mango numbers on slides 9-11 are real and come from
`data/mango_maracuya.csv`; no placeholder is left there.

## Suggested timing (15 minutes)

| Slide | Part | ~time |
| --- | --- | --- |
| 1-2 | Intro / agenda | 1 min |
| 3-5 | Concept (D1) | 3 min |
| 6 | Live system + web-app demo | 4 min |
| 7-8 | Interpretation: questions + sketch | 2 min |
| 9 | Mango - the logged beer | 0.5 min |
| 10-11 | Real curve + real length | 2 min |
| 12 | Dark Day - traditional | 0.75 min |
| 13 | Tasting | 1 min |
| 14-15 | Outlook + questions | 0.75 min |

The speaker notes on each slide repeat this timing.

## Database drawings (ER diagrams)

The data model is drawn from `sql/schema.sql` with Graphviz. Three versions:

| File | Use |
| --- | --- |
| `db/er_diagram_full.png` / `.svg` | complete ER diagram (all fields + constraints) - the D1 data-model page |
| `db/er_diagram.png` / `.svg` | simple ER diagram (key fields) - handouts / D1 |
| `db/er_diagram_slide.png` / `.svg` | minimal 16:9 version embedded on slide 4 |

Regenerate after a schema change:

```bash
cd presentation/db
dot -Tsvg er_diagram_full.dot -o er_diagram_full.svg
dot -Tpng -Gdpi=200 er_diagram_full.dot -o er_diagram_full.png
dot -Tsvg er_diagram.dot -o er_diagram.svg
dot -Tpng -Gdpi=200 er_diagram.dot -o er_diagram.png
dot -Tsvg er_diagram_slide.dot -o er_diagram_slide.svg
dot -Tpng -Gdpi=220 er_diagram_slide.dot -o er_diagram_slide.png
```

The `.dot` sources are the editable originals; the `.svg` files are vector
(use them in the D1 document), the `.png` files are for the deck.

## Images used in the deck

| Slide | File |
| --- | --- |
| 8 | `screenshots/mango_device_card.png` (cropped from `06_device_card_expanded.png`) |
| 9 | `screenshots/mango_device_card.png` |
| 10 | `plots/mango_fermentation.png` |
| 11 | `plots/mango_duration.png` |
| 6 | backup list only (no image) |

The remaining screenshots in `screenshots/` are the backup for the live demo
(see `screenshots/INDEX.md`).
