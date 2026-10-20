# 4. Milestones, schedule and acceptance test

## The four milestones

The project follows four milestones. **Brew day is the critical date:** from then on the system
must run reliably, because **data from the beginning of fermentation cannot be recorded later**.

* **M1 - Kick-off, 08.10.2026.** Project brief discussed, groups formed, iSpindels and Raspberry
  Pis handed out, questions to the client clarified.
* **M2 - Brew day, 29.10.2026.** The own iSpindel is placed in the fermenter of the own beer and
  the experiment is started in the system.
* **M3 - Fermentation, 29.10.2026 to 05.11.2026.** Operation with real data, integration of the
  other iSpindels in use, self-test according to the acceptance test.
* **M4 - Final presentation, 12.11.2026.** Presentation with live demo, submission of all
  deliverables.

## The brew-day constraint

> Important: on brew day the system must already run reliably with the own iSpindel and fulfil all
> Must requirements of chapters 3.1 and 3.2. Use the time between kick-off and brew day to test it
> with the own iSpindel.

Concretely: the experiment management Must requirements (FR-01 to FR-05) and the acquisition and
storage Must requirements (FR-07, FR-08, FR-09, FR-11, FR-12) must be working before brew day,
because the first days of a fermentation can never be re-recorded.

## 4.1 Acceptance test

At the end of the project the client accepts the system. As in industry, the acceptance is based
on test cases derived from the requirements. Each test names the requirements it covers, the
procedure and the expected result.

**T-01 - Requirements FR-01 to FR-05.**
Procedure: start an experiment with the required fields only, try a duplicate name, assign an
iSpindel that is already in use, end the experiment.
Expected result: behaviour as specified in each acceptance criterion.

**T-02 - Requirements FR-07 to FR-09 and FR-15.**
Procedure: during the fermentation phase, record all iSpindels in use at the same time.
Expected result: all measurements are stored and displayed in the correct experiment.

**T-03 - Requirement FR-11.**
Procedure: set the iSpindel to an interval of 1 minute, then to 30 minutes.
Expected result: exactly one record per transmission, no duplicates.

**T-04 - Requirements FR-13 and FR-14.**
Procedure: wait for a new measurement while the dashboard is open.
Expected result: current value and chart update within 60 seconds.

**T-05 - Requirements FR-16 and FR-17.**
Procedure: display a completed experiment and compare it with a running one.
Expected result: complete course visible, both experiments in one chart.

**T-06 - Requirement FR-21.**
Procedure: export an experiment and open the file in Excel.
Expected result: correct columns, numbers and timestamps.

**T-07 - Requirements NFR-03 and NFR-04.**
Procedure: disconnect the power supply of the Raspberry Pi and reconnect it.
Expected result: system restarts automatically, no data lost, history visible.

**T-08 - Requirement NFR-02.**
Procedure: open the dashboard from another device in the local network via `http://hostname:port`.
Expected result: dashboard accessible.

> Info from the specification: use the test cases as a checklist during development. If you cannot
> describe how you would test a requirement, you have not yet understood it.
