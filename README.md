# Smart Waste Bin — ECE CK801

**Advanced Programming Techniques (CK801) · Spring 2026**  
University of Patras · Department of Electrical and Computer Engineering · 8th Semester

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/)
[![Sensor](https://img.shields.io/badge/Sensor-HC--SR501%20PIR-green)](https://www.google.com/search?q=HC-SR501+PIR+sensor)
[![Course](https://img.shields.io/badge/Course-CK801--S26-orange)](https://gbouloukakis.com/courses/ck801-s26/projects/)

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
- **Mock-based testing** using `gpiozero`'s `MockFactory` — no hardware required for development

---

## Repository Structure

```
smartWasteBinProject/
├── src/
│   ├── producer.py           # MQTT Publisher: reads sensor and publishes events
│   ├── consumer.py           # MQTT Subscriber: receives events and logs to file
│   ├── dashboard.py          # MQTT Subscriber: displays real-time events in console
│   ├── Dockerfile            # Container image definition (python:3.11 -slim)
│   ├── docker-compose.yml    # Single-command deployment with volumes & resource limits
│   ├── .dockerignore         # Excludes caches, venvs, and output from build context
│   ├── requirements.txt      # Pinned Python dependencies for reproducible builds
│   ├── pirlib/
│   │   ├── __init__.py
│   │   ├── sampler.py        # PirSampler: reads raw GPIO pin state via gpiozero
│   │   └── interpreter.py    # PirInterpreter: debounce & event detection logic
│   └── models/
│       ├── context.jsonld     # Shared JSON-LD @context (SOSA, SSN, SAREF, BOT, custom)
│       ├── sensor.jsonld      # PIR sensor entity description
│       ├── wastebin.jsonld    # Smart wastebin entity description
│       └── environment.jsonld # Deployment environment (kypes-02) description
├── requirements.txt
└── README.md
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

### Output Record Format (JSONL)

```json
{
  "event_time": "2026-03-30T13:00:00.123Z",
  "device_id": "pir-01",
  "event_type": "motion",
  "motion_state": "detected",
  "seq": 1,
  "run_id": "f1a2b3c4-...",
  "ingest_time": "2026-03-30T13:00:00.131Z",
  "pipeline_latency_ms": 8
}
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Raspberry Pi with a PIR sensor connected to a GPIO pin  
  *(or use the mock mode for development on any machine)*

### Installation

```bash
git clone https://github.com/jimfil/smartWasteBinProject.git
cd smartWasteBinProject
pip install -r requirements.txt
```

### Running the System

You will need an MQTT Broker (like Mosquitto) running. You can start one via Docker or install it locally.

**1. Start the Consumer (Logger)**
```bash
python src/consumer.py \
  --broker localhost \
  --topic "smartbin/bin-01/pir-01/events" \
  --out events.jsonl \
  --verbose
```

**2. Start the Producer (Sensor)**
```bash
python src/producer.py \
  --device-id pir-01 \
  --pin 4 \
  --broker localhost \
  --topic "smartbin/bin-01/pir-01/events" \
  --verbose
```

**3. Start the Dashboard (Optional)**
```bash
python src/dashboard.py --broker localhost --topic "smartbin/#"
```

---

## Project Milestones

### Milestone 1 — Lab 01: Project Foundation

Establish the team's project foundation: GitHub repository, project structure, initial documentation, and a reproducible development workflow.

**Status: Complete**

---

### Milestone 2 — Lab 02: Sensor Integration

Integrate the HC-SR501 PIR motion sensor on the Raspberry Pi. Implement the `pirlib` mini-library (`PirSampler`, `PirInterpreter`) and a JSONL event logger to produce clean, structured motion events.

**Status: Complete**

---

### Milestone 3 — Lab 03: Concurrent Data Pipeline

Restructure the project into a modular, concurrent data pipeline. Separate sensing, buffering, and downstream processing into independent components (producer/consumer threads with a bounded queue) so that each part can be reused, replaced, and extended independently.

**Status: Complete**

---

### Milestone 4 — Lab 04: Containerization

Containerize the Smart Waste Bin into a Docker image (or multiple images) and define its deployment with Docker Compose, so that the full system starts, runs, and persists data with a single `docker compose up`.

**Status: Complete**

---

### Milestone 5 — Lab 05: Context-aware Data Modeling

Model the Smart Waste Bin system using JSON-LD. Describe sensors, the wastebin, and the deployment environment as structured entities with explicit relationships between them. The pipeline now produces self-describing output with inlined `@context` and entity references.

**Status: Complete**

---

### Milestone 6 - Lab 06: Publish/Subscribe Messaging

Replace your in-process producers–consumers (publisher/subscribers) with MQTT-based communication. Set up a Mosquitto broker, split your pipeline into a standalone components, and define a topic structure for your Smart Waste Bin system. Your publishers and subscribers should run as separate processes that communicate only through the broker.

**Status: Ongoing**

## Resources

- [Course Project Page](https://gbouloukakis.com/courses/ck801-s26/projects/)
- [Lab 01 — Getting Started](https://gbouloukakis.com/courses/ck801-s26/labs/getting_started/)
- [Lab 02 — Sensor Integration](https://gbouloukakis.com/courses/ck801-s26/labs/sensor_integration_code/)
- [Lab 03 — Concurrent Data Pipelines](https://gbouloukakis.com/courses/ck801-s26/labs/pipelines/)
- [Lab 04 — Portable Data Pipelines](https://gbouloukakis.com/courses/ck801-s26/labs/containers/)
- [Lab 05 — Context-aware Data Modeling](https://gbouloukakis.com/courses/ck801-s26/labs/data_models/)
- [Lab 06 — Publish/Subscribe Messaging](https://gbouloukakis.com/courses/ck801-s26/labs/pub_sub/)
- [gpiozero Documentation](https://gpiozero.readthedocs.io/)
