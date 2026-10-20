# iSpindel Project

## 1. Project Brief

#### Background

In the self-study phase you taught yourselves the brewing process, and in the exchange with a beer expert you clarified open questions and collected input. Later in the semester, each of you will brew your own beer on a scale of approx. 20 litres together with a brewmaster. During fermentation, an iSpindel floats in each fermenter and transmits measurement data such as gravity and temperature at regular intervals.

Measured values are only valuable if they are stored reliably, assigned to the correct batch and remain accessible later. Closing exactly this gap is the purpose of this project.

#### What the system is useful for

Without such a system, fermentation is usually checked by taking samples and measuring the gravity by hand. This only provides individual values, takes time, and every sample means opening the fermenter, which increases the risk of contamination. A monitoring system replaces these spot checks with a continuous record and creates benefits on several levels:

- **Process control during fermentation:** The course of fermentation can be followed at any time without opening the fermenter. Deviations such as a stalled fermentation or an unsuitable temperature are noticed early, and the end of fermentation can be determined reliably from a stable gravity. This is the basis for deciding when the beer is ready for the next process step.
- **Quality and traceability:** Every batch is documented with its complete fermentation data. In the food industry, such batch records are the foundation of quality assurance and make it possible to trace afterwards what happened in a batch.
- **Learning from comparisons:** Because all experiments are stored in the same structure, the influence of recipe, yeast or temperature on the fermentation can be compared. Over several semesters, a data set grows that can be evaluated systematically.
- **Transfer to industry:** Capturing sensor data, storing it in a structured way and making it usable via a dashboard is the same principle as in industrial food production. What you build here on a small scale is a building block of a digital production environment.

Your software therefore turns individual measured values into usable information: for the brewer during fermentation, for quality assurance and for the evaluation afterwards.

#### Assignment

The client commissions you, as the contractor, to develop a fermentation monitoring system on a Raspberry Pi. The system receives the data of the iSpindels via MQTT, stores it per experiment in a database and makes it available via a web dashboard in the local network, both live and historically.

You work **alone or in a group of two**. Each participant receives one iSpindel and one Raspberry Pi from the start of the project; a group of two develops one common system and submits its deliverables together. In a group of two, everything said in this assignment about «your beer» and «your iSpindel» applies to the beers and iSpindels of both members. During the fermentation phase, your system also integrates the other iSpindels in use, so that all running fermentations can be followed in your dashboard.

The central objective is a database that can be used for many different experiments. It must make it possible to evaluate and compare fermentations after the fact, for example the beers from this semester with each other or with batches brewed by future cohorts.

The users of the system, such as brewmasters and students, are not programmers. They need a user-friendly dashboard that they can operate without any programming knowledge: starting and ending experiments, following the fermentation, comparing experiments and downloading data.

#### Learning objectives

After completing this project you are able to:

- design a data model for process data from several sensors and experiments and justify your design decisions,
- implement a data pipeline on a Raspberry Pi that receives sensor data via MQTT and stores it persistently and reliably,
- develop a user-friendly web dashboard that visualises live and historical fermentation data and allows users to manage, compare and export experiments,
- verify a system systematically against a requirements specification and interpret the data of a real fermentation.

#### Position in the module

The project builds directly on your self-study of the brewing process and on the expert exchange. On brew day, your system goes into operation: your iSpindel is placed in the fermenter of your beer and its fermentation is recorded. In the final presentation, you show your system live and interpret the fermentation of your own beer. The database you build remains in use, so that later evaluations and future cohorts can build on your data.

#### Before you start

Take about 15 minutes and work on the following, before you look at the requirements:

- Sketch by hand how gravity (°P) and temperature are likely to develop during a fermentation of 7 to 10 days. Mark where you expect the lag phase, the main fermentation and the end of fermentation.
- Write down two questions that a brewmaster wants to answer with these data.
- Consider which of your two questions requires historical data, and which requires a comparison between experiments.

### 1.1. Positioning in the Automation Pyramid

The automation pyramid describes the hierarchical structure of automation systems in industry. It ranges from the field level (sensors and actuators) through the control level to the supervisory level (MES) and the enterprise level (ERP).

*Figure 1: Automation pyramid (Copilot 2025)*

Your fermentation monitoring system covers the lower three levels:

- **Field level:** The iSpindel acts as a sensor and provides raw data from the fermentation process.
- **Control level:** The Raspberry Pi receives the data via MQTT and processes it locally. Since the system only monitors and does not control (no actuators), this level is limited to data acquisition.
- **Supervisory level (MES):** The database stores the measurement data in a structured way and assigns it to experiments (batches). This corresponds to a simplified precursor of a Manufacturing Execution System.
- **Enterprise level (ERP):** An integration into an ERP system is conceivable in future, for example for batch management or quality assurance. It is not part of this project.

In your concept, assign each component of your own architecture to one of these levels. This shows that you understand where your solution sits in an industrial data chain.

## 2. System Context

This chapter describes the environment in which your system operates and the conditions it has to meet. Read it before you start designing.

#### Components and responsibilities

| Component | Provided by | Role in the system |
| --- | --- | --- |
| iSpindel | Client | Sensor in the fermenter. One per participant from the start; during the fermentation phase, the other iSpindels in use are added. |
| Raspberry Pi | Client | One per participant from the start. Hosts your application, the database and the web server for the dashboard. |
| MQTT broker | Part of your concept | Receives the iSpindel data via the internet. It does not have to run on the Raspberry Pi. |
| Network with internet access | Client | Connects the iSpindels, the Raspberry Pi and the users' devices; the iSpindel data is transmitted via the internet. |
| Data acquisition, database, dashboard | You | The subject of this assignment |
| Web browser | User | Access to the dashboard from a laptop or smartphone in the same local network |

#### Data interface

The iSpindels transmit their data via **MQTT**. This is prescribed. How the iSpindel is configured, which data it sends and in which form it arrives is part of your work to find out.

During the fermentation phase, your system must also integrate the other iSpindels in use. The client provides the information required for this on brew day.

#### Network and access

The Raspberry Pi needs internet access at all times, because the iSpindel data is transmitted via the internet.

The dashboard, however, only needs to be accessible within the local network, via **http://hostname:port** (for example http://dfp-pi-01:8080). It must not be published to the internet: no port forwarding, no tunnels, no public hosting.

#### Technology choice

You are free to choose programming languages, frameworks, databases and dashboard tools. Whatever you choose, you justify it in your concept: which alternatives you considered and why your choice fits the requirements best.

#### Scope

##### In scope

- Receiving, storing and assigning the measurement data of all iSpindels in use
- Managing experiments via a user-friendly dashboard
- Live and historical visualisation, comparison and export of the data
- Operation of the application, the database and the dashboard on the Raspberry Pi

##### Out of scope

- Controlling the fermentation (e.g. temperature control, actuators)
- Changes to the iSpindel hardware or firmware and its calibration
- Access to the dashboard from outside the local network and user authentication
- Integration into ERP or other enterprise systems

## 3. Requirements Specification

The following chapters contain the requirements the client places on the system. Each requirement has an ID, a priority and an acceptance criterion. A requirement counts as fulfilled only if its acceptance criterion can be demonstrated.

#### Priorities

| Priority | Meaning |
| --- | --- |
| **Must** | Mandatory for the acceptance of the system. If a Must requirement is not fulfilled, the system is not accepted. |
| **Should** | Expected by the client. Can be omitted only with a justification in the concept. |
| **Could** | Optional extension that adds value. Only worthwhile once all Must requirements are fulfilled. |

#### Requirement groups

| Group | IDs | Chapter |
| --- | --- | --- |
| Experiment management | FR-01 to FR-06 | 3.1 |
| Data acquisition and storage | FR-07 to FR-12 | 3.2 |
| Dashboard and visualisation | FR-13 to FR-20 | 3.3 |
| Data access and export | FR-21 and FR-22 | 3.4 |
| Non-functional requirements | NFR-01 to NFR-09 | 3.5 |

FR stands for functional requirement (what the system does), NFR for non-functional requirement (how well and under which conditions it does it).

#### Terms used in this specification

| Term | Meaning |
| --- | --- |
| **Experiment** | One fermentation, e.g. the fermentation of your beer. Identified by a unique name and a start time; exactly one iSpindel is assigned to it. |
| **Measurement** | One complete set of values (tilt, temperature, gravity, battery, …) that an iSpindel transmits at one point in time. |
| **Active experiment** | An experiment that has been started and not yet ended. New measurements of its iSpindel are assigned to it. |
| **Gravity (°P)** | Extract content of the wort or beer in degrees Plato. It decreases during fermentation as sugar is converted into alcohol and CO₂. |
| **Interval** | Time between two transmissions of an iSpindel. It is configurable and may vary. |

> **Info:** If a requirement is unclear to you, ask the client before implementing, just as you would in industry. Note the answer and any assumptions you make yourself in your concept.

### 3.1. Experiment Management

Users must be able to manage experiments entirely via the dashboard, without access to the code or the database.

| ID | Priority | Requirement | Acceptance criterion |
| --- | --- | --- | --- |
| FR-01 | Must | A new experiment can be created and started via the dashboard. Required fields: name, start date and time, and the iSpindel. The form also contains the following fields, which can be left empty at the start: beer style, original gravity (°P), yeast, responsible person, notes. | An experiment can be started with the required fields only; it is stored in the database and appears immediately in the experiment overview. |
| FR-02 | Must | The experiment name is unique. The system rejects a duplicate name with a clear message. | Creating a second experiment with an existing name produces an error message; no second record is created. |
| FR-03 | Must | Exactly one iSpindel is assigned to each experiment. An iSpindel can belong to at most one active experiment at a time. | Assigning an iSpindel that is already in use in an active experiment is rejected or produces a warning. |
| FR-04 | Must | An active experiment can be ended via the dashboard; the end time is stored. Measurements received afterwards are no longer assigned to this experiment. | After ending, new measurements of the iSpindel no longer appear in the ended experiment. |
| FR-05 | Must | An overview lists all experiments with name, iSpindel, start, end, status (active or completed) and number of measurements. | The overview is complete and the figures match the database. |
| FR-06 | Should | The fields of an experiment can be completed or edited afterwards, and events with a timestamp can be recorded (e.g. «dry hopping», «temperature raised»). | Edited fields are stored; recorded events are shown in the chart of the experiment, e.g. as markers. |

> **Example:** Experiment «2026_IPA_Mueller», start 12.11.2026 16:30, iSpindel «iSpindel_03». Beer style and yeast are entered right away, the original gravity of 14.5 °P is added later the same evening. After 9 days the gravity is stable at 3.2 °P; the experiment is ended via the dashboard.

Think about the naming convention for experiments early and agree on it within the course, so that the data of all beers can be compared later.

### 3.2. Data Acquisition and Storage

The database is the core of the system. It must be designed so that it can be used for any number of experiments and iSpindels over several years.

| ID | Priority | Requirement | Acceptance criterion |
| --- | --- | --- | --- |
| FR-07 | Must | The system receives the measurements of all iSpindels in use via MQTT, automatically and without manual intervention. | During the fermentation phase, every transmission of all iSpindels in use is stored. |
| FR-08 | Must | Each measurement is stored with at least the fields listed in the table below. | The database contains all fields with the correct units. |
| FR-09 | Must | A measurement is automatically assigned to the experiment that is active for its iSpindel at the time of receipt. | Measurements appear in the correct experiment; no measurement is assigned to two experiments. |
| FR-10 | Should | Measurements of an iSpindel without an active experiment are stored without assignment instead of being discarded. | Such measurements are present in the database and can be identified as unassigned. |
| FR-11 | Must | The system does not assume a fixed interval and does not create duplicate records for one transmission. | With your iSpindel set to an interval of 1 minute and of 30 minutes, exactly one measurement record per transmission is stored. |
| FR-12 | Must | The data model separates experiments, iSpindels and measurements into linked entities (e.g. tables with keys). New iSpindels and experiments require no change to the schema or the code. | The concept contains a data model diagram; an additional iSpindel is recorded without code changes. |

#### Minimum fields per measurement

| Field | Description | Unit / format |
| --- | --- | --- |
| Experiment | Reference to the experiment (may be empty, see FR-10) | Key |
| iSpindel name | Name of the transmitting iSpindel | Text |
| Timestamp | Time of the measurement | ISO 8601, UTC |
| Tilt | Tilt angle | ° |
| Temperature | Temperature of the beer | °C |
| Gravity | Gravity | °P |
| Battery | Battery voltage | V |
| Interval | Transmission interval of the iSpindel | s |
| RSSI (Should) | Wi-Fi signal strength | dBm |

For the experiment itself, the name, start and end time, the assigned iSpindel and the additional fields from FR-01 are stored.

> **Tip:** Design and sketch the data model before writing any code. Ask yourselves: Which query will the evaluation need most often? A typical one is «all measurements of experiments A and B, ordered by time since start».

### 3.3. Dashboard and Visualisation

The dashboard is the interface for brewmasters and students. It must answer the questions you formulated at the beginning, both during a running fermentation and afterwards.

| ID | Priority | Requirement | Acceptance criterion |
| --- | --- | --- | --- |
| FR-13 | Must | For each active iSpindel, the dashboard shows the latest values (gravity, temperature, tilt, battery) and the time of the last measurement. | The displayed values match the latest record in the database. |
| FR-14 | Must | A chart shows gravity and temperature over time. It updates automatically, without manual page reload, no later than 60 seconds after a measurement is received. | A new measurement appears in the chart within 60 seconds of its receipt. |
| FR-15 | Must | All iSpindels in use can be displayed at the same time and are clearly distinguishable (colour, legend, name). | During the fermentation phase, all iSpindels in use are visible simultaneously and can be identified unambiguously. |
| FR-16 | Must | Any experiment, including completed ones, can be selected and displayed over its entire duration. The time range can be selected (e.g. last 24 hours, last 7 days, entire experiment). | A completed experiment is displayed completely; changing the time range changes the chart accordingly. |
| FR-17 | Must | At least two experiments can be overlaid in one chart for comparison. | Two selected experiments are displayed in one chart. |
| FR-18 | Should | For comparisons, the time axis can be switched to relative time (hours since the start of the experiment). | Two experiments with different start dates start at the same point on the time axis. |
| FR-19 | Should | The dashboard indicates if an iSpindel has not sent data for more than three intervals or if its battery voltage falls below a configurable threshold (e.g. 3.5 V). | Switching off your iSpindel, or setting the threshold above its current voltage, triggers the indication. |
| FR-20 | Could | Derived values are displayed, e.g. apparent attenuation, estimated alcohol content or gravity drop per 24 hours. | The calculation is explained in the concept and the values are plausible. |

> **Info:** The dashboard does not have to look spectacular, but it must be understandable for someone without programming knowledge.

### 3.4. Data Access and Export

The data is collected so that it can be evaluated later, for example in Excel, Python or R. It must therefore be retrievable via the dashboard without any access to the database.

| ID | Priority | Requirement | Acceptance criterion |
| --- | --- | --- | --- |
| FR-21 | Must | The measurements of a selected experiment can be downloaded via the dashboard as a CSV file. Experiment name and iSpindel name are included in the data or in the file name. | The file opens correctly in Excel: one column per field, correct decimal values and readable timestamps. |
| FR-22 | Should | Several experiments and/or a selected time range can be exported in one file. | The export contains exactly the selected data. |

Describe the structure of the export file (columns, units, format) in your README, so that someone evaluating the data later does not need to ask you.

### 3.5. Non-functional Requirements

Non-functional requirements describe the conditions under which the system must work. In practice, they often decide whether a system is actually used.

| ID | Priority | Requirement | Acceptance criterion |
| --- | --- | --- | --- |
| NFR-01 | Must | Your application, the database and the web server for the dashboard run on the Raspberry Pi, and all measurement data is stored there. Only the MQTT broker may run elsewhere. | Dashboard and data are served directly from the Raspberry Pi; no external hosting or external database is used. |
| NFR-02 | Must | The dashboard is accessible in the local network via a browser at http://hostname:port and is not published to the internet. | Another device in the same local network opens the dashboard via the host name. |
| NFR-03 | Must | After a restart or power failure, all services start automatically, data acquisition resumes and the history is displayed again without manual intervention. | After disconnecting and reconnecting the power supply, the system runs again and shows all previous data. |
| NFR-04 | Must | Stored measurements are not lost on restart. A backup procedure for the database is described in the README (Should). | The number of records before and after the restart is identical. |
| NFR-05 | Must | The dashboard can be operated by a person without programming knowledge after a short introduction. The user interface is in English. | A test person creates, displays and exports an experiment without help. |
| NFR-06 | Should | The dashboard can be used on a smartphone browser. | All Must functions can be operated on a smartphone. |
| NFR-07 | Should | Displaying a complete experiment takes less than 5 seconds, also when several iSpindels are displayed at the same time. | Measured with the data of the fermentation phase. |
| NFR-08 | Must | A README describes the installation from a fresh Raspberry Pi OS to the running system. Settings such as broker address, port and database path are in a configuration file, not in the code. | A third person can install the system with the README. |
| NFR-09 | Should | Timestamps are stored in UTC and displayed in local time (Europe/Zurich), correctly also across the change from summer to winter time. | Measurements around the time change are displayed without gaps or overlaps. |

## 4. Milestones and Schedule

The project follows four milestones. Brew day is the critical date: from then on, your system must run reliably, because data from the beginning of fermentation cannot be recorded later.

| Milestone | Content | Date |
| --- | --- | --- |
| M1 Kick-off | Project brief discussed, groups formed, iSpindels and Raspberry Pis handed out, questions to the client clarified | 08.10.2026 |
| M2 Brew day | Your iSpindel is placed in the fermenter of your beer, your experiment is started in your system | 29.10.2026 |
| M3 Fermentation | Operation with real data, integration of the other iSpindels in use, self-test according to the acceptance test | 29.10.2026 to 05.11.2026 |
| M4 Final presentation | Presentation with live demo, submission of all deliverables | 12.11.2026 |

> **Important:** On brew day, your system must already run reliably with your own iSpindel and fulfil all Must requirements of chapters 3.1 and 3.2. Use the time between kick-off and brew day to test it with your iSpindel.

### 4.1. Acceptance Test

At the end of the project, the client accepts the system. As in industry, the acceptance is based on test cases derived from the requirements.

| Test | Requirements | Procedure | Expected result |
| --- | --- | --- | --- |
| T-01 | FR-01 to FR-05 | Start an experiment with the required fields only, try a duplicate name, assign an iSpindel that is already in use, end the experiment | Behaviour as specified in each acceptance criterion |
| T-02 | FR-07 to FR-09, FR-15 | During the fermentation phase, record all iSpindels in use at the same time | All measurements are stored and displayed in the correct experiment |
| T-03 | FR-11 | Set your iSpindel to an interval of 1 minute, then to 30 minutes | Exactly one record per transmission, no duplicates |
| T-04 | FR-13, FR-14 | Wait for a new measurement while the dashboard is open | Current value and chart update within 60 seconds |
| T-05 | FR-16, FR-17 | Display a completed experiment and compare it with a running one | Complete course visible, both experiments in one chart |
| T-06 | FR-21 | Export an experiment and open the file in Excel | Correct columns, numbers and timestamps |
| T-07 | NFR-03, NFR-04 | Disconnect the power supply of the Raspberry Pi and reconnect it | System restarts automatically, no data lost, history visible |
| T-08 | NFR-02 | Open the dashboard from another device in the local network via http://hostname:port | Dashboard accessible |

> **Info:** Use the test cases as a checklist during development: if you cannot describe how you would test a requirement, you have not yet understood it.

## 5. Deliverables and Presentation

#### Deliverables

All deliverables are due at the final presentation (M4).

| ID | Deliverable | Content |
| --- | --- | --- |
| D1 | Concept | 1 to 2 pages: architecture diagram with assignment to the levels of the automation pyramid, data model, technology choice with justification, assumptions and clarifications with the client |
| D2 | Running system | System running on the Raspberry Pi with the data of the fermentation phase |
| D3 | Source code | Including README and configuration file |
| D4 | Presentation | 15 minutes plus questions, including live demo |

#### Presentation

Your presentation covers four parts:

- **Concept:** Explain your architecture, your data model and your technology choice.
- **Live system:** Demonstrate the running system and its main functions in the dashboard.
- **Interpretation of the data:** Interpret the fermentation of your own beer with reference to the brewing process. Compare it with the sketch you made at the beginning, and show how your dashboard answers your two questions.
- **Outlook:** Show what you would improve in a next iteration.

> **Info:** Should and Could requirements only add value on top of a working core system. Focus first on fulfilling all Must requirements.
