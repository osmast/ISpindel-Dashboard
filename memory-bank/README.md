# Memory Bank - index

Project: **iSpindel fermentation monitor** (ZHAW *Digital Food Processing HS26 / AD24*).
Read these files at the start of every session; update them after every significant change or on
"update memory bank".

| File | Content |
| --- | --- |
| `projectbrief.md` | assignment, scope, users, deliverables, milestones, acceptance, automation-pyramid mapping |
| `productContext.md` | why the product exists, target users, UX goals, out-of-scope, the two brewmaster questions |
| `systemPatterns.md` | architecture, the 7-message burst pattern, data model + rationale, dashboard patterns, deployment patterns |
| `techContext.md` | stack and versions, environment setup, commands, deployment facts, repository state |
| `activeContext.md` | current focus, open Must gaps, next steps, decisions, open client questions, learnings |
| `progress.md` | what works, what is missing, risks, evolution of decisions |
| `requirements.md` | the requirement specification condensed verbatim: 31 requirements, priorities, acceptance test, deliverables |
| `requirements-traceability.md` | **the design-requirement register**: every FR/NFR with evidence, status, gap, action and verification |
| `acceptance-tests.md` | copy-paste recipes for T-01 to T-08 and the non-functional proofs |

Source documents (not part of the memory bank):

* `docs/spec/` - **the client's specification as prose, no tables, written for agents**: `README.md`
  (index, terms, priorities), `01-assignment.md`, `02-system-context.md`, `03-requirements.md` (all
  31 requirements with priority, text and acceptance criterion), `04-milestones-and-acceptance.md`
  (M1 - M4, brew-day constraint, T-01 - T-08) and `05-deliverables-and-presentation.md` (D1 - D4).
  Read this folder for *what is required*; the two files below remain the original evidence.
* `docs/iSpindel-project.md` - assignment / requirement specification (Markdown copy of the Moodle book)
* `docs/ispindel-project-moodle-print-2026-10-20.txt` - raw text extraction of the PDF print
* `docs/concept.md` - the D1 concept (architecture, automation pyramid, data model, technology choice, assumptions)
* `tools/check_requirements.py` - machine checks of the requirements that need no hardware

Status at a glance (20.10.2026, after the deployment on the Pi): 22 Must / 8 Should / 1 Could.
**19 Must proven, 3 left (FR-15 waits for the other iSpindels, NFR-05 for a test person, NFR-08 for
a second installer), no Must unimplemented.** The system runs on the lab Pi
(`http://clt-lab-n-1298.zhaw.ch:8080`) with a real iSpindel, survives power cycles without data
loss and is closed to the internet. Biggest remaining risks: the FR-15 integration, the
uncommitted repository and the missing D1 polish / D4. Brew day: **29.10.2026**.
