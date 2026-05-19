# Smart Waste Bin — ECE CK801

**Advanced Programming Techniques (CK801) · Spring 2026**  
University of Patras · Department of Electrical and Computer Engineering · 8th Semester

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/)
[![Sensor](https://img.shields.io/badge/Sensor-HC--SR501%20PIR-green)](https://www.google.com/search?q=HC-SR501+PIR+sensor)
[![Course](https://img.shields.io/badge/Course-CK801--S26-orange)](https://gbouloukakis.com/courses/ck801-s26/projects/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff)](https://www.docker.com/)
---

## Overview

This repository contains our team's implementation of a **Smart Waste Bin** system, built as part of the [CK801 Advanced Programming Techniques](https://gbouloukakis.com/courses/ck801-s26/projects/) course project.

The system uses a **Raspberry Pi** with a **PIR motion sensor** to detect when waste is deposited into a bin. Raw sensor readings are processed through a modular data pipeline that filters noise, debounces events, and logs structured motion records — turning a standard bin into an IoT-enabled smart device.

The project is developed incrementally throughout the semester, with each lab introducing a new layer of the system (sensor integration, concurrent pipelines, containerization, visualization).

---

## Features

- **Real-time PIR sensing** via GPIO on Raspberry Pi
- **Noise filtering** with configurable `min_high` duration and `cooldown` debounce
- **Distributed Pub/Sub Architecture** using MQTT protocol (Eclipse Mosquitto)
- **Self-describing JSON-LD output** with inlined `@context`, `@type`, and entity references (sensor, wastebin, environment)
- **Structured JSONL logging** with event timestamps, ingest time, and pipeline latency
- **Live metrics** (produced, consumed, dropped, queue depth) via `--verbose` flag
- **Dockerized deployment** via `Dockerfile` + `docker-compose.yml` with GPIO pass-through, named volumes, and resource limits

---

## Repository Structure

```
smartWasteBinProject/
.
├── docker-compose.yml
├── Dockerfile
├── mosquitto.conf
├── README.md
├── requirements.txt
├── docs/               # Contains the ontology file for our project
├── data/               # Logs will appear here
└── src/                # Python scripts
    ├── archiver.py
    ├── consumer.py
    ├── dashboard.py
    ├── producer.py
    ├── models/         # JSON-LD context and models
    └── pirlib/         # PIR sensor utilities
```

---

## How It Works

The system uses a decentralized **Publish/Subscribe** architecture over MQTT.

1. **`PirSampler`** reads the raw digital value from the GPIO pin at a configurable interval.
2. **`PirInterpreter`** applies two filters:
   - **`min_high`**: the pin must stay HIGH for at least N seconds before an event is emitted.
   - **`cooldown`**: a minimum interval between successive events to avoid re-triggering.
3. **`producer.py`** (Publisher) calls the sampler + interpreter and publishes clean `motion` events to an MQTT broker under a specific topic (e.g., `smartbin/bin-01/pir-01/events`).
4. **`consumer.py`** (Subscriber) listens to the topic, enriches arriving events with an `ingest_time` and `pipeline_latency_ms`, and writes each record as a JSON line to the output file.
5. **`dashboard.py`** (Subscriber) can independently listen to the broker and display real-time events without interfering with the data logging.

---

## Getting Started

### Prerequisites

- Raspberry Pi with a PIR sensor connected to a GPIO pin 
- Verify you have docker and docker compose installed on your machine with:
```bash
docker --version
docker compose version
```
If not install docker and add your user to the docker group:
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```
And then reboot your Pi.

If you can run 
```bash
docker run hello-world
```
then docker is installed correctly.



### Installation

```bash
git clone https://github.com/jimfil/smartWasteBinProject.git
cd smartWasteBinProject
```

### Running the System
To start the system either:
Start the whole system:
```bash
docker compose up -d --build
```

Then view the dashboard logs:
```bash
docker compose logs -f dashboard
```

Or start the system manually:
```bash
docker compose up -d broker producer consumer archiver
```

View live logs and visualizations:
```bash
docker compose up dashboard
```



Stop the system:
```bash
docker compose down
```
---

## Project Milestones

### Milestone 1 — Lab 01: Project Foundation

Establish the team's project foundation: GitHub repository, project structure, initial documentation, and a reproducible development workflow.

**Status: Completed**

---

### Milestone 2 — Lab 02: Sensor Integration

Integrate the HC-SR501 PIR motion sensor on the Raspberry Pi. Implement the `pirlib` mini-library (`PirSampler`, `PirInterpreter`) and a JSONL event logger to produce clean, structured motion events.

**Status: Completed**

---

### Milestone 3 — Lab 03: Concurrent Data Pipeline

Restructure the project into a modular, concurrent data pipeline. Separate sensing, buffering, and downstream processing into independent components (producer/consumer threads with a bounded queue) so that each part can be reused, replaced, and extended independently.

**Status: Completed**

---

### Milestone 4 — Lab 04: Containerization

Containerize the Smart Waste Bin into a Docker image (or multiple images) and define its deployment with Docker Compose, so that the full system starts, runs, and persists data with a single `docker compose up`.

**Status: Completed**

---

### Milestone 5 — Lab 05: Context-aware Data Modeling

Model the Smart Waste Bin system using JSON-LD. Describe sensors, the wastebin, and the deployment environment as structured entities with explicit relationships between them. The pipeline now produces self-describing output with inlined `@context` and entity references.

**Status: Completed**

---

### Milestone 6 - Lab 06: Publish/Subscribe Messaging

Replace your in-process producers–consumers (publisher/subscribers) with MQTT-based communication. Set up a Mosquitto broker, split your pipeline into a standalone components, and define a topic structure for your Smart Waste Bin system. Your publishers and subscribers should run as separate processes that communicate only through the broker.

**Status: Completed**

---

### Milestone 8 - Lab 08: REST API

Add a REST API to your Smart Waste Bin using Flask and Flask-RESTx. Expose endpoints for querying bins, sensors, and events, and include MQTT endpoints that let HTTP clients publish to and read from your broker. Write an AsyncAPI spec documenting your MQTT interface. Your system should now have both a pull-based API (OpenAPI) and a push-based messaging interface (AsyncAPI), both formally documented.

**Status: Completed**

---

### Milestone 9 - Lab 09: Virtual Sensors

Build virtual sensors on top of your Smart Waste Bin pipeline. Implement a rule-based virtual sensor that derives bin usage intensity and an ML-based virtual sensor that predicts busy/quiet periods from historical patterns. Both publish their output to MQTT, appear as entities in Home Assistant, and are queryable through the REST API.

**Status: Completed**

## Resources

- [Course Project Page](https://gbouloukakis.com/courses/ck801-s26/projects/)
- [Lab 01 — Getting Started](https://gbouloukakis.com/courses/ck801-s26/labs/getting_started/)
- [Lab 02 — Sensor Integration](https://gbouloukakis.com/courses/ck801-s26/labs/sensor_integration_code/)
- [Lab 03 — Concurrent Data Pipelines](https://gbouloukakis.com/courses/ck801-s26/labs/pipelines/)
- [Lab 04 — Portable Data Pipelines](https://gbouloukakis.com/courses/ck801-s26/labs/containers/)
- [Lab 05 — Context-aware Data Modeling](https://gbouloukakis.com/courses/ck801-s26/labs/data_models/)
- [Lab 06 — Publish/Subscribe Messaging](https://gbouloukakis.com/courses/ck801-s26/labs/pub_sub/)
- [Lab 07 — Home Assistant Integration](https://gbouloukakis.com/courses/ck801-s26/labs/home_assistant/)
- [Lab 08 — Building a REST API for the Smart Wastebin](https://gbouloukakis.com/courses/ck801-s26/labs/swagger/)
- [Lab 09 — Data Processing on Edge Devices](https://gbouloukakis.com/courses/ck801-s26/labs/virtual_sensors/)
- [Lab 10 — Node-RED LCDP](https://gbouloukakis.com/courses/ck801-s26/labs/node-red/)
- [gpiozero Documentation](https://gpiozero.readthedocs.io/)
