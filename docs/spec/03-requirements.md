# 3. Requirements specification

> "The following chapters contain the requirements the client places on the system. Each
> requirement has an ID, a priority and an acceptance criterion. A requirement counts as fulfilled
> only if its acceptance criterion can be demonstrated."

Every requirement below is stated with its **priority**, its **full text**, and its **acceptance
criterion** (the demonstrable proof).

Priorities: **Must** = mandatory for acceptance, otherwise the system is not accepted.
**Should** = expected by the client, omittable only with a justification in the concept.
**Could** = optional extension that adds value, worth doing only after all Must requirements.

Groups: experiment management (FR-01 to FR-06, chapter 3.1), data acquisition and storage (FR-07
to FR-12, 3.2), dashboard and visualisation (FR-13 to FR-20, 3.3), data access and export (FR-21
and FR-22, 3.4), non-functional requirements (NFR-01 to NFR-09, 3.5).

> Info from the specification: if a requirement is unclear, ask the client before implementing,
> just as you would in industry. Note the answer and any assumptions you make yourself in the
> concept.

## 3.1 Experiment management

Users must be able to manage experiments **entirely via the dashboard**, without access to the
code or the database.

### FR-01 - Must

**Requirement.** A new experiment can be created and started via the dashboard. Required fields:
name, start date and time, and the iSpindel. The form also contains the following fields, which
can be left empty at the start: beer style, original gravity (°P), yeast, responsible person,
notes.

**Acceptance criterion.** An experiment can be started with the required fields only; it is stored
in the database and appears immediately in the experiment overview.

### FR-02 - Must

**Requirement.** The experiment name is unique. The system rejects a duplicate name with a clear
message.

**Acceptance criterion.** Creating a second experiment with an existing name produces an error
message; no second record is created.

### FR-03 - Must

**Requirement.** Exactly one iSpindel is assigned to each experiment. An iSpindel can belong to at
most one active experiment at a time.

**Acceptance criterion.** Assigning an iSpindel that is already in use in an active experiment is
rejected or produces a warning.

### FR-04 - Must

**Requirement.** An active experiment can be ended via the dashboard; the end time is stored.
Measurements received afterwards are no longer assigned to this experiment.

**Acceptance criterion.** After ending, new measurements of the iSpindel no longer appear in the
ended experiment.

### FR-05 - Must

**Requirement.** An overview lists all experiments with name, iSpindel, start, end, status (active
or completed) and number of measurements.

**Acceptance criterion.** The overview is complete and the figures match the database.

### FR-06 - Should

**Requirement.** The fields of an experiment can be completed or edited afterwards, and events
with a timestamp can be recorded (e.g. "dry hopping", "temperature raised").

**Acceptance criterion.** Edited fields are stored; recorded events are shown in the chart of the
experiment, e.g. as markers.

### Example from the specification

Experiment "2026_IPA_Mueller", start 12.11.2026 16:30, iSpindel "iSpindel_03". Beer style and
yeast are entered right away, the original gravity of 14.5 °P is added later the same evening.
After 9 days the gravity is stable at 3.2 °P; the experiment is ended via the dashboard.

### Naming convention

Think about the naming convention for experiments early and agree on it within the course, so that
the data of all beers can be compared later.

## 3.2 Data acquisition and storage

The database is the core of the system. It must be designed so that it can be used for **any
number of experiments and iSpindels over several years**.

### FR-07 - Must

**Requirement.** The system receives the measurements of all iSpindels in use via MQTT,
automatically and without manual intervention.

**Acceptance criterion.** During the fermentation phase, every transmission of all iSpindels in
use is stored.

### FR-08 - Must

**Requirement.** Each measurement is stored with at least the fields listed below ("minimum fields
per measurement").

**Acceptance criterion.** The database contains all fields with the correct units.

### FR-09 - Must

**Requirement.** A measurement is automatically assigned to the experiment that is active for its
iSpindel at the time of receipt.

**Acceptance criterion.** Measurements appear in the correct experiment; no measurement is
assigned to two experiments.

### FR-10 - Should

**Requirement.** Measurements of an iSpindel without an active experiment are stored without
assignment instead of being discarded.

**Acceptance criterion.** Such measurements are present in the database and can be identified as
unassigned.

### FR-11 - Must

**Requirement.** The system does not assume a fixed interval and does not create duplicate records
for one transmission.

**Acceptance criterion.** With the iSpindel set to an interval of 1 minute and of 30 minutes,
exactly one measurement record per transmission is stored.

### FR-12 - Must

**Requirement.** The data model separates experiments, iSpindels and measurements into linked
entities (e.g. tables with keys). New iSpindels and experiments require no change to the schema or
the code.

**Acceptance criterion.** The concept contains a data model diagram; an additional iSpindel is
recorded without code changes.

### Minimum fields per measurement

* **Experiment** - reference to the experiment (may be empty, see FR-10); stored as a key.
* **iSpindel name** - name of the transmitting iSpindel; text.
* **Timestamp** - time of the measurement; ISO 8601, UTC.
* **Tilt** - tilt angle; in degrees (°).
* **Temperature** - temperature of the beer; in degrees Celsius (°C).
* **Gravity** - gravity; in degrees Plato (°P).
* **Battery** - battery voltage; in volts (V).
* **Interval** - transmission interval of the iSpindel; in seconds (s).
* **RSSI** - Wi-Fi signal strength; in dBm. This field is a **Should**.

For the **experiment** itself, the name, start and end time, the assigned iSpindel and the
additional fields from FR-01 are stored.

> Tip from the specification: design and sketch the data model before writing any code. Ask
> yourselves which query the evaluation will need most often. A typical one is "all measurements
> of experiments A and B, ordered by time since start".

## 3.3 Dashboard and visualisation

The dashboard is the interface for brewmasters and students. It must answer the questions
formulated at the beginning (the two brewmaster questions from the self-study), both during a
running fermentation and afterwards.

### FR-13 - Must

**Requirement.** For each active iSpindel, the dashboard shows the latest values (gravity,
temperature, tilt, battery) and the time of the last measurement.

**Acceptance criterion.** The displayed values match the latest record in the database.

### FR-14 - Must

**Requirement.** A chart shows gravity and temperature over time. It updates automatically,
without manual page reload, no later than 60 seconds after a measurement is received.

**Acceptance criterion.** A new measurement appears in the chart within 60 seconds of its receipt.

### FR-15 - Must

**Requirement.** All iSpindels in use can be displayed at the same time and are clearly
distinguishable (colour, legend, name).

**Acceptance criterion.** During the fermentation phase, all iSpindels in use are visible
simultaneously and can be identified unambiguously.

### FR-16 - Must

**Requirement.** Any experiment, including completed ones, can be selected and displayed over its
entire duration. The time range can be selected (e.g. last 24 hours, last 7 days, entire
experiment).

**Acceptance criterion.** A completed experiment is displayed completely; changing the time range
changes the chart accordingly.

### FR-17 - Must

**Requirement.** At least two experiments can be overlaid in one chart for comparison.

**Acceptance criterion.** Two selected experiments are displayed in one chart.

### FR-18 - Should

**Requirement.** For comparisons, the time axis can be switched to relative time (hours since the
start of the experiment).

**Acceptance criterion.** Two experiments with different start dates start at the same point on
the time axis.

### FR-19 - Should

**Requirement.** The dashboard indicates if an iSpindel has not sent data for more than three
intervals or if its battery voltage falls below a configurable threshold (e.g. 3.5 V).

**Acceptance criterion.** Switching off the iSpindel, or setting the threshold above its current
voltage, triggers the indication.

### FR-20 - Could

**Requirement.** Derived values are displayed, e.g. apparent attenuation, estimated alcohol content
or gravity drop per 24 hours.

**Acceptance criterion.** The calculation is explained in the concept and the values are
plausible.

> Info from the specification: the dashboard does not have to look spectacular, but it must be
> understandable for someone without programming knowledge.

## 3.4 Data access and export

The data is collected so that it can be evaluated later, for example in Excel, Python or R. It must
therefore be retrievable via the dashboard **without any access to the database**.

### FR-21 - Must

**Requirement.** The measurements of a selected experiment can be downloaded via the dashboard as a
CSV file. Experiment name and iSpindel name are included in the data or in the file name.

**Acceptance criterion.** The file opens correctly in Excel: one column per field, correct decimal
values and readable timestamps.

### FR-22 - Should

**Requirement.** Several experiments and/or a selected time range can be exported in one file.

**Acceptance criterion.** The export contains exactly the selected data.

The structure of the export file (columns, units, format) must be described in the README, so that
someone evaluating the data later does not need to ask.

## 3.5 Non-functional requirements

Non-functional requirements describe the conditions under which the system must work. In practice
they often decide whether a system is actually used.

### NFR-01 - Must

**Requirement.** The application, the database and the web server for the dashboard run on the
Raspberry Pi, and all measurement data is stored there. Only the MQTT broker may run elsewhere.

**Acceptance criterion.** Dashboard and data are served directly from the Raspberry Pi; no external
hosting or external database is used.

### NFR-02 - Must

**Requirement.** The dashboard is accessible in the local network via a browser at
`http://hostname:port` and is not published to the internet.

**Acceptance criterion.** Another device in the same local network opens the dashboard via the host
name.

### NFR-03 - Must

**Requirement.** After a restart or power failure, all services start automatically, data
acquisition resumes and the history is displayed again without manual intervention.

**Acceptance criterion.** After disconnecting and reconnecting the power supply, the system runs
again and shows all previous data.

### NFR-04 - Must

**Requirement.** Stored measurements are not lost on restart. A backup procedure for the database
is described in the README (this part is a Should).

**Acceptance criterion.** The number of records before and after the restart is identical.

### NFR-05 - Must

**Requirement.** The dashboard can be operated by a person without programming knowledge after a
short introduction. The user interface is in English.

**Acceptance criterion.** A test person creates, displays and exports an experiment without help.

### NFR-06 - Should

**Requirement.** The dashboard can be used on a smartphone browser.

**Acceptance criterion.** All Must functions can be operated on a smartphone.

### NFR-07 - Should

**Requirement.** Displaying a complete experiment takes less than 5 seconds, also when several
iSpindels are displayed at the same time.

**Acceptance criterion.** Measured with the data of the fermentation phase.

### NFR-08 - Must

**Requirement.** A README describes the installation from a fresh Raspberry Pi OS to the running
system. Settings such as broker address, port and database path are in a configuration file, not in
the code.

**Acceptance criterion.** A third person can install the system with the README.

### NFR-09 - Should

**Requirement.** Timestamps are stored in UTC and displayed in local time (Europe/Zurich),
correctly also across the change from summer to winter time.

**Acceptance criterion.** Measurements around the time change are displayed without gaps or
overlaps.



