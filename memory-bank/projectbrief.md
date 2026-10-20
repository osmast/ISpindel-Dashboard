# Project Brief

## What this project is

A **fermentation monitoring system** for the ZHAW module *Digital Food Processing HS26 (AD24)*.
An **iSpindel** floats in each fermenter of a ~20 L beer and publishes gravity/temperature via
**MQTT**. The system receives those values on a **Raspberry Pi**, stores them per **experiment**
(batch) in a database and shows them live and historically in a **web dashboard** in the local
network.

Core sentence from the assignment:

> "Measured values are only valuable if they are stored reliably, assigned to the correct batch
> and remain accessible later. Closing exactly this gap is the purpose of this project."

* **Client:** ZHAW / module lecturer (assignment text), brewmaster + students as end users
* **Contractor:** student(s) - one or a group of two (this repository = one system)
* **Type:** graded semester project; acceptance test plus final presentation

## Sources of truth (in this repository)

| File | What it is |
| --- | --- |
| `docs/iSpindel-project.md` | full assignment / requirement specification (Markdown copy of the Moodle book) |
| `docs/ispindel-project-moodle-print-2026-10-20.txt` | raw text extraction of `iSpindel Project _ Moodle ZHAW.pdf` (printed 20.10.2026) |
| `memory-bank/requirements.md` | the requirement specification condensed, verbatim, with priorities |
| `memory-bank/requirements-traceability.md` | design-requirement register: every FR/NFR/T with status, evidence, gap, action |

Verified: the PDF print and the Markdown copy carry **the same text** (word-set diff only shows
page headers/footers such as `19 von 24` and `20.10.2026, 10:51`). The PDF was printed on
**20.10.2026** and contains no newer requirement than the Markdown copy.

## Scope

**In scope** (from the specification)

* receiving, storing and assigning the measurement data of **all iSpindels in use**
* managing experiments via a **user-friendly dashboard** (non-programmers as users)
* live and historical **visualisation, comparison and export** of the data
* operation of **application, database and dashboard on the Raspberry Pi**

**Out of scope**

* controlling fermentation (temperature control, actuators) - the system only monitors
* changes to iSpindel hardware/firmware/calibration
* dashboard access from outside the local network, user authentication
* ERP or other enterprise-system integration

## Scope of the delivered requirements

* **FR-01 to FR-22** - 22 functional requirements: **16 Must**, 5 Should, 1 Could
* **NFR-01 to NFR-09** - 9 non-functional requirements: **6 Must**, 3 Should
* **Total 31 requirements: 22 Must, 8 Should, 1 Could** (see `requirements.md` for the verbatim
  text and `requirements-traceability.md` for the per-requirement status)
* Priorities: **Must** = mandatory for acceptance, **Should** = expected (omission needs a
  justification in the concept), **Could** = optional, only worth it once all Must are done.

## Users and their job to be done

| User | Wants |
| --- | --- |
| brewer / brewmaster during fermentation | see the course of fermentation without opening the fermenter, notice stalled fermentation or unsuitable temperature early, know when fermentation is finished (stable gravity) |
| quality assurance / traceability | a complete batch record per experiment, retrievable later |
| students & future cohorts | comparable experiments in one structure, export for Excel/Python/R |
| non-programmers | start/end experiments, follow fermentation, compare, download - without touching code or database |

## Deliverables (all due at M4, 12.11.2026)

| ID | Deliverable | Content |
| --- | --- | --- |
| D1 | Concept | 1-2 pages: architecture diagram with the levels of the automation pyramid, data model, technology choice with justification, assumptions and clarifications with the client |
| D2 | Running system | system running on the Raspberry Pi with the data of the fermentation phase |
| D3 | Source code | including README and configuration file |
| D4 | Presentation | 15 minutes plus questions, including live demo |

Presentation parts: **concept**, **live system**, **interpretation of the data** (own beer vs. the
hand sketch from the self-study, and how the dashboard answers the two questions), **outlook**.

## Milestones

| Milestone | Content | Date |
| --- | --- | --- |
| M1 Kick-off | brief discussed, groups formed, hardware handed out | 08.10.2026 |
| M2 Brew day | iSpindel in the fermenter, experiment started in the system | **29.10.2026** |
| M3 Fermentation | operation with real data, integration of the other iSpindels in use, self-test | 29.10.2026 - 05.11.2026 |
| M4 Final presentation | live demo, submission of all deliverables | 12.11.2026 |

Hard constraint: *on brew day the system must already run reliably with the own iSpindel and
fulfil all **Must** requirements of chapters 3.1 and 3.2* (FR-01 to FR-13 minus the dashboard
group; concretely FR-01 - FR-12). Data from the beginning of fermentation can never be
recovered afterwards.

## Acceptance

The client accepts the system on the basis of **T-01 to T-08** (`requirements.md`, section
"Acceptance test"). A requirement counts as fulfilled only if its acceptance criterion can be
demonstrated. Rule of thumb from the assignment: *"if you cannot describe how you would test a
requirement, you have not yet understood it"*.

## Positioning in the automation pyramid (D1 content, mandatory)

| Level | Component in this system |
| --- | --- |
| Field level | iSpindel (sensor in the fermenter, raw data) |
| Control level | Raspberry Pi: MQTT receive + local processing (data acquisition only, no actuators) |
| Supervisory level (MES) | PostgreSQL: structured storage, assignment of measurements to experiments (simplified MES precursor) |
| Enterprise level (ERP) | out of scope (conceivable future: batch management, quality assurance) |
