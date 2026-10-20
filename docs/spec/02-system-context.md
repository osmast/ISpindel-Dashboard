# 2. System context

This chapter describes the environment in which the system operates and the conditions it has to
meet. It is meant to be read **before** designing anything.

## Components and who provides them

* **iSpindel** - provided by the client. Role: sensor in the fermenter. One per participant from
  the start; during the fermentation phase the other iSpindels in use are added.
* **Raspberry Pi** - provided by the client. Role: one per participant from the start. Hosts the
  application, the database and the web server for the dashboard.
* **MQTT broker** - part of the contractor's concept. Role: receives the iSpindel data via the
  internet. It does **not** have to run on the Raspberry Pi.
* **Network with internet access** - provided by the client. Role: connects the iSpindels, the
  Raspberry Pi and the users' devices; the iSpindel data is transmitted via the internet.
* **Data acquisition, database, dashboard** - delivered by the contractor. Role: the subject of
  this assignment.
* **Web browser** - the user's side. Role: access to the dashboard from a laptop or smartphone in
  the same local network.

## The data interface: MQTT

* The iSpindels transmit their data via **MQTT**. This is prescribed.
* **How the iSpindel is configured, which data it sends and in which form it arrives is part of
  the contractor's work to find out.** It is not given in the specification.
* During the fermentation phase the system **must also integrate the other iSpindels in use**. The
  client provides the information required for this on brew day.

## Network and access

* The Raspberry Pi needs **internet access at all times**, because the iSpindel data is
  transmitted via the internet.
* The dashboard only needs to be accessible **within the local network**, via
  **http://hostname:port** (for example `http://dfp-pi-01:8080`).
* The dashboard **must not be published to the internet**: no port forwarding, no tunnels, no
  public hosting.

## Technology choice

The contractor is **free to choose** programming languages, frameworks, databases and dashboard
tools. Whatever the choice is, it has to be **justified in the concept**: which alternatives were
considered and why the chosen technology fits the requirements best.

## Scope

**In scope**

* Receiving, storing and assigning the measurement data of all iSpindels in use.
* Managing experiments via a user-friendly dashboard.
* Live and historical visualisation, comparison and export of the data.
* Operation of the application, the database and the dashboard on the Raspberry Pi.

**Out of scope**

* Controlling the fermentation (e.g. temperature control, actuators).
* Changes to the iSpindel hardware or firmware and its calibration.
* Access to the dashboard from outside the local network and user authentication.
* Integration into ERP or other enterprise systems.
