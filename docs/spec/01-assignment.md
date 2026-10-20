# 1. The assignment (project brief)

## Background

In the self-study phase the students taught themselves the brewing process and clarified open
questions in an exchange with a beer expert. Later in the semester each student brews their own
beer on a scale of about **20 litres together with a brewmaster**. During fermentation an
**iSpindel floats in each fermenter** and transmits measurement data such as gravity and
temperature at regular intervals.

Measured values are only valuable if they are stored reliably, assigned to the correct batch and
remain accessible later. **Closing exactly this gap is the purpose of this project.**

## What the system is useful for

Without such a system fermentation is usually checked by taking samples and measuring the gravity
by hand. That gives individual values only, takes time, and every sample means opening the
fermenter, which increases the risk of contamination. A monitoring system replaces these spot
checks with a continuous record and creates benefits on several levels:

* **Process control during fermentation.** The course of fermentation can be followed at any time
  without opening the fermenter. Deviations such as a stalled fermentation or an unsuitable
  temperature are noticed early, and the end of fermentation can be determined reliably from a
  stable gravity. This is the basis for deciding when the beer is ready for the next process step.
* **Quality and traceability.** Every batch is documented with its complete fermentation data. In
  the food industry such batch records are the foundation of quality assurance and make it
  possible to trace afterwards what happened in a batch.
* **Learning from comparisons.** Because all experiments are stored in the same structure, the
  influence of recipe, yeast or temperature on the fermentation can be compared. Over several
  semesters a data set grows that can be evaluated systematically.
* **Transfer to industry.** Capturing sensor data, storing it in a structured way and making it
  usable via a dashboard is the same principle as in industrial food production. What is built
  here on a small scale is a building block of a digital production environment.

The software therefore turns individual measured values into usable information: for the brewer
during fermentation, for quality assurance, and for the evaluation afterwards.

## The assignment itself

The client commissions the contractor to develop a **fermentation monitoring system on a Raspberry
Pi**. The system:

* receives the data of the iSpindels **via MQTT**,
* stores it **per experiment in a database**, and
* makes it available **via a web dashboard in the local network**, both live and historically.

**Team size.** Work alone or in a group of two. Each participant receives one iSpindel and one
Raspberry Pi from the start of the project. A group of two develops one common system and submits
its deliverables together; in a group of two everything said about "your beer" and "your iSpindel"
applies to the beers and iSpindels of both members. **During the fermentation phase the system
also integrates the other iSpindels in use**, so that all running fermentations can be followed in
the dashboard.

**Central objective.** A **database that can be used for many different experiments**. It must
make it possible to evaluate and compare fermentations after the fact - for example the beers from
this semester with each other, or with batches brewed by future cohorts.

**Users.** The users of the system, such as brewmasters and students, are **not programmers**. They
need a user-friendly dashboard that they can operate **without any programming knowledge**:
starting and ending experiments, following the fermentation, comparing experiments and
downloading data.

## Learning objectives

After completing the project the student is able to:

* design a data model for process data from several sensors and experiments and justify the design
  decisions,
* implement a data pipeline on a Raspberry Pi that receives sensor data via MQTT and stores it
  persistently and reliably,
* develop a user-friendly web dashboard that visualises live and historical fermentation data and
  allows users to manage, compare and export experiments,
* verify a system systematically against a requirements specification and interpret the data of a
  real fermentation.

## Position in the module

The project builds directly on the self-study of the brewing process and on the expert exchange.

* **On brew day the system goes into operation:** the own iSpindel is placed in the fermenter of
  the own beer and its fermentation is recorded.
* **In the final presentation** the system is shown live and the fermentation of the own beer is
  interpreted.
* **The database remains in use** afterwards, so that later evaluations and future cohorts can
  build on the data.

## Before you start (self-study tasks, about 15 minutes)

Work on the following before looking at the requirements:

1. Sketch **by hand** how gravity (°P) and temperature are likely to develop during a fermentation
   of 7 to 10 days, and mark where the **lag phase**, the **main fermentation** and the **end of
   fermentation** are expected.
2. Write down **two questions that a brewmaster wants to answer with these data**.
3. Consider which of the two questions requires **historical data** and which requires a
   **comparison between experiments**.

These sketches and questions are used again in the presentation ("Interpretation of the data").

## Positioning in the automation pyramid

The automation pyramid describes the hierarchical structure of automation systems in industry. It
ranges from the field level (sensors and actuators) through the control level to the supervisory
level (MES) and the enterprise level (ERP). *Figure 1 in the assignment shows the automation
pyramid (source: Copilot 2025).*

The fermentation monitoring system covers the **lower three levels**:

* **Field level** - the iSpindel acts as a sensor and provides raw data from the fermentation
  process.
* **Control level** - the Raspberry Pi receives the data via MQTT and processes it locally. Since
  the system only monitors and does not control (there are no actuators), this level is limited to
  data acquisition.
* **Supervisory level (MES)** - the database stores the measurement data in a structured way and
  assigns it to experiments (batches). This corresponds to a simplified precursor of a
  Manufacturing Execution System.
* **Enterprise level (ERP)** - an integration into an ERP system is conceivable in future, for
  example for batch management or quality assurance. It is **not part of this project**.

The concept (D1) must assign **each component of the own architecture** to one of these levels.
This shows that the student understands where the solution sits in an industrial data chain.

