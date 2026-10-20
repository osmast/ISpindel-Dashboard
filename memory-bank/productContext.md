# Product Context

## Why the product exists

Without a monitoring system, fermentation is checked by taking samples and measuring gravity by
hand. That gives individual values only, costs time, and every sample opens the fermenter -
which increases the risk of contamination. The system replaces these spot checks with a
**continuous record**.

Four benefits the assignment names explicitly:

1. **Process control during fermentation** - follow the course at any time without opening the
   fermenter; notice a stalled fermentation or an unsuitable temperature early; determine the
   end of fermentation from a stable gravity (basis for deciding the next process step).
2. **Quality and traceability** - every batch is documented with its complete fermentation data;
   in the food industry such batch records are the foundation of quality assurance.
3. **Learning from comparisons** - the same structure for all experiments makes the influence of
   recipe, yeast or temperature comparable across semesters.
4. **Transfer to industry** - capturing sensor data, storing it structurally and making it usable
   in a dashboard is the same principle as in industrial food production.

## Product idea in one line

Individual measured values become usable information: for the brewer during fermentation, for
quality assurance, and for the evaluation afterwards.

## Target users

| User | Technical skill | Interaction with the system |
| --- | --- | --- |
| brewmaster | none (not a programmer) | follows fermentation, reads values, interprets the batch |
| student / participant | medium | starts and ends own experiment, adds the other iSpindels in use, compares |
| future cohorts / evaluators | medium | reopen old experiments, export data for Excel / Python / R |

The user interface is **English** (NFR-05) and must be operable **without programming knowledge**:
start and end experiments, follow the fermentation, compare experiments, download data.

## Two brewmaster questions this project must answer

The self-study phase requires every student to write down two questions a brewmaster wants to
answer with the data, and to decide which one needs **historical** data and which one needs a
**comparison between experiments**. The dashboard has to answer them (FR-13 - FR-20 are the
technical translation of that, e.g. overlaid experiments + relative time axis for comparison).

The questions are part of the presentation ("Interpretation of the data"): interpret the
fermentation of the own beer with reference to the brewing process, compare it with the hand
sketch (lag phase / main fermentation / end of fermentation) and show how the dashboard answers
the two questions.

> Open item: the repository does not yet document which two questions were chosen. They belong
> in the concept (D1) and in the presentation (D4).

## Expected course of a fermentation (7-10 days, from the self-study sketch)

* **Lag phase:** gravity almost constant, temperature follows the ambient/fermenter temperature
  (no measurement has to be interpreted beyond "nothing happens yet").
* **Main fermentation:** gravity falls steeply (sugar -> alcohol + CO₂), temperature rises above
  ambient because the fermentation is exothermic.
* **End of fermentation:** gravity approaches a stable value; stability over ~2-3 days is the
  signal that the beer is ready for the next process step (e.g. dry hopping, bottling).

## Non-goals / product boundaries

* no actuators, no temperature control, no automatic intervention
* no iSpindel firmware/calibration work - the raw values and the device's polynomial are trusted
* no internet exposure, no login/multi-user accounts, no ERP integration
* no mobile app - a responsive web dashboard is enough (NFR-06)
* the dashboard "does not have to look spectacular, but it must be understandable for someone
  without programming knowledge"

## UX goals that follow from the requirements

| Goal | Requirement |
| --- | --- |
| The current state of every device is visible without any interaction | FR-13 |
| The chart feels live - no manual reload, max 60 s lag | FR-14 |
| Several fermentations side by side without confusion (colour, legend, name) | FR-15 |
| Historical analysis: any experiment, whole duration, selectable time range | FR-16 |
| Comparison is the central analysis: two experiments in one chart, optional relative axis | FR-17, FR-18 |
| The dashboard warns about silence (stale iSpindel) and low battery by itself | FR-19 |
| Data leaves the system in a form a non-programmer can use (Excel) | FR-21 |
| Phones can be used in the cellar (responsive) | NFR-06 |
| A complete experiment renders in < 5 s | NFR-07 |
| Times are always understood correctly, including DST change | NFR-09 |
