# Presentation folder (D4)

Everything needed for the final presentation (12.11.2026, 15 min + questions).

| File | What it is |
| --- | --- |
| `iSpindel_Final_Presentation.pptx` | the 20-slide deck - **placeholders** everywhere |
| `build_deck.py` | the generator; edit the text here and re-run to rebuild the deck |
| `templates/` | **6 ready-made presentation templates** (one full deck per theme) |
| `requirements-checklist.md` | the FR/NFR/T fill-in sheet shown on slides 14-18 |
| `screenshots/` | 16 PNGs of every live feature + popup from the Pi, with `INDEX.md` |
| `capture_screenshots.sh` | re-capture the static shots (curl check + headless Chrome) |

Rebuild the deck after editing `build_deck.py`:

```bash
python presentation/build_deck.py            # default template (classic)
python presentation/build_deck.py nordic     # pick any template by name
```

Every run also (re)writes the whole template gallery into `templates/`.

`python-pptx` is only needed to *build* the deck (`pip install python-pptx`); it is
not part of the runtime stack and nothing in the app imports it.

## Presentation templates (6)

The deck is theme-driven: `build_deck.py` holds a `THEMES` table and every slide is
rendered from the active palette + font, so the same 20 slides can be shown in any of
these templates. `templates/` holds one full deck per theme; the presented deck
(`iSpindel_Final_Presentation.pptx`) uses the default (`classic`).

| Template | Look | Font |
| --- | --- | --- |
| `classic` (default) | brand blue + beer amber - matches the app | Calibri |
| `nordic` | deep teal + copper | Segoe UI |
| `midnight` | dark navy + cyan + amber (dark theme) | Segoe UI |
| `mono` | charcoal + grey, minimal | Segoe UI |
| `warm` | burgundy + gold, serif | Georgia |
| `ocean` | royal blue + coral | Segoe UI |

To present a different look, either open the matching file in `templates/`, or rebuild
the main deck with that theme: `python presentation/build_deck.py midnight`.

## The two speakers and their roles

The deck alternates between two speakers. The top-right pill on every slide names
the owner: **amber = Speaker A**, **blue = Speaker B**.

### Speaker A - the brewer / builder

Owns the brew and the build (the person who wrote the code and brewed one beer).

* the two beers and how each recipe is structured (slides 4-5)
* brew day and the fermentation plan (slide 6)
* architecture, data model, technology choice - D1 concept (slides 7-9)
* the live demo of the running system (slide 10)
* the technical half of the outlook (slide 19)

### Speaker B - the brewmaster's voice (the newcomer)

This person **was not involved in development**, so the deck gives them a genuine,
non-developer role instead of pretending they built something:

* the **client / brewmaster perspective**: what a brewer actually needs from the data
* the **two brewmaster questions** and which of them needs historical vs. comparative
  data (slide 11) - this is a required part of D4
* **how the concept and the recipes were structured** - described from the recipe side,
  not the code side (slides 4-6, 12)
* **reading the fermentation curve** as a user (slides 12-13, "interpretation of the data")
* walking the audience through the **requirement checklist and acceptance test**
  (slides 14-18) - checking the system the way the client would, which needs no
  development knowledge at all
* the user-facing half of the outlook (slide 19)

This split is deliberate: it satisfies the assignment's presentation parts
(**concept**, **live system**, **interpretation of the data**, **outlook**) and it
gives the second speaker a credible part that does not require having written code.

## What to fill in

Every piece of content that is project-specific sits inside `[ ... ]`. Replace it with
real values. In particular:

* the two beer names, recipes, gravities, yeast and hops (slide 4-5)
* the two brewmaster questions (slide 11) - these are an open item in the concept
* the actual fermentation numbers of each beer (slide 13)
* the screenshots: concept diagram, ER diagram, hand sketch, demo backup screenshots
  (slides 7, 8, 10, 12) - paste them over the placeholder text boxes
* the host name for the live demo (slide 10, 20)

## Suggested timing (15 minutes)

| Slide | Speaker | ~time |
| --- | --- | --- |
| 1-3 Intro / motivation | both | 1.5 min |
| 4-6 The beers + recipes | A, then B | 3 min |
| 7-9 Concept (D1) | A | 3 min |
| 10 Live demo | A | 4 min |
| 11-13 Interpretation of the data | B | 2 min |
| 14-18 Requirement checklist | B | 1 min |
| 19-20 Outlook + questions | both | 0.5 min |
