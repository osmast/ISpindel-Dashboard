# iSpindel project - the specification, written to be read

This folder is a **complete, faithful copy of the client's project description and requirement
specification** (module *Digital Food Processing HS26 / AD24*, ZHAW). It is written as prose and
bullets on purpose: no tables. Tables are compact for humans who already know the project, but an
agent (or a person) that has to *understand* the rules reads headings, sentences and lists far more
reliably - especially when the table cells wrap and the requirement text is long.

Nothing in here is interpretation, design or status. It is the requirement side only.

## Where the material comes from

* `docs/iSpindel-project.md` - the original Markdown copy of the Moodle book (table-heavy).
* `docs/ispindel-project-moodle-print-2026-10-20.txt` - raw text of the PDF print of the same
  Moodle book. The print was verified against the Markdown copy: **the same text**, no extra or
  newer requirement (only page headers/footers differ).
* This folder - that same text, restructured into prose. It is the **source of truth for what the
  client demands**; the original files stay untouched as the evidence.

Implementation knowledge (how this repository solves the requirements, what is proven, what is
still open, deployment records, gotchas) lives in `memory-bank/` and in `README.md` - not here.
When the two ever disagree about *what is required*, this folder wins.

## How to read it

Read the files in order. Each one is self-contained; the numbering follows the assignment.

1. `01-assignment.md` - why the project exists, what is commissioned, the four learning
   objectives, the position in the automation pyramid and the two self-study tasks.
2. `02-system-context.md` - the environment: components, the MQTT data interface, the network and
   access rules, the freedom of technology choice and the scope boundaries.
3. `03-requirements.md` - **all 31 requirements** (FR-01 to FR-22, NFR-01 to NFR-09), each with
   its priority, its full text and its acceptance criterion, plus the minimum measurement fields.
4. `04-milestones-and-acceptance.md` - the four milestones with dates, the brew-day constraint and
   the eight acceptance tests T-01 to T-08.
5. `05-deliverables-and-presentation.md` - the four deliverables D1 to D4 and the four parts of
   the final presentation.

## The project in one paragraph

Fermentation is normally checked by taking samples and measuring the gravity by hand: single
values, repeated work, and every sample opens the fermenter and increases the risk of
contamination. The client therefore commissions a **fermentation monitoring system on a Raspberry
Pi**. An **iSpindel** floats in each fermenter, measures tilt angle, temperature, battery voltage
and similar values, and transmits them over **MQTT**. The system receives those transmissions,
stores them **per experiment (batch)** in a database, and makes them available in a **web
dashboard inside the local network**, both live and historically. The database is the core of the
deliverable: it has to work for any number of experiments and iSpindels over several years, so
that fermentations can be evaluated and compared afterwards - this semester's beers with each
other and with batches of future cohorts. The users are brewmasters and students who do **not
program**; they start and end experiments, follow the fermentation, compare experiments and
download data entirely through the dashboard.

## Priorities (the vocabulary used all over the specification)

* **Must** - mandatory for acceptance. If a Must requirement is not fulfilled, the system is not
  accepted.
* **Should** - expected by the client. May be omitted, but only with a justification in the
  concept.
* **Could** - optional extension that adds value. Only worth doing once all Must requirements are
  fulfilled.

## The two requirement families

* **FR** = functional requirement: *what* the system does. Groups: experiment management
  (FR-01 to FR-06), data acquisition and storage (FR-07 to FR-12), dashboard and visualisation
  (FR-13 to FR-20), data access and export (FR-21 and FR-22).
* **NFR** = non-functional requirement: *how well* and *under which conditions* the system does
  it (NFR-01 to NFR-09).

Count: 22 Must, 8 Should, 1 Could - 31 requirements in total.

## The vocabulary of the specification

* **Experiment** - one fermentation, e.g. the fermentation of the own beer. Identified by a unique
  name and a start time; exactly one iSpindel is assigned to it.
* **Measurement** - one complete set of values (tilt, temperature, gravity, battery, ...) that an
  iSpindel transmits at one point in time. One transmission = one measurement.
* **Active experiment** - an experiment that has been started and not yet ended. New measurements
  of its iSpindel are assigned to it.
* **Gravity (°P)** - extract content of the wort or beer in degrees Plato. It decreases during
  fermentation as sugar is converted into alcohol and CO₂.
* **Interval** - time between two transmissions of an iSpindel. It is configurable and may vary.

## Three rules that run through the whole specification

1. **A requirement counts as fulfilled only if its acceptance criterion can be demonstrated.**
   Every requirement below therefore carries its acceptance criterion; a demo is part of the
   deliverable, not an optional extra.
2. **Ask the client when something is unclear** - as you would in industry. The answer and every
   assumption you make yourself belong in the concept (D1). This applies in particular to the
   broker/brooding questions and the experiment naming convention.
3. **Must before Should before Could.** Should and Could requirements only add value on top of a
   working core system.
