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
- **Concurrent producer/consumer pipeline** using Python threads and a bounded queue
- **Structured JSONL logging** with event timestamps, ingest time, and pipeline latency
- **Live metrics** (produced, consumed, dropped, queue depth) via `--verbose` flag
- **Mock-based testing** using `gpiozero`'s `MockFactory` — no hardware required for development

---

## Repository Structure

```
smartWasteBinProject/
├── src/
│   ├── pipeline.py         # Main entry point — CLI + producer/consumer threads
│   ├── test_mock.py        # Mock hardware test (runs pipeline with simulated GPIO)
│   └── pirlib/
│       ├── __init__.py
│       ├── sampler.py      # PirSampler: reads raw GPIO pin state via gpiozero
│       └── interpreter.py  # PirInterpreter: debounce & event detection logic
├── requirements.txt
└── README.md
```

---

## How It Works

The pipeline consists of two concurrent threads: the producer and the consumer.


1. **`PirSampler`** reads the raw digital value from the GPIO pin at a configurable interval.
2. **`PirInterpreter`** applies two filters:
   - **`min_high`**: the pin must stay HIGH for at least N seconds before an event is emitted.
   - **`cooldown`**: a minimum interval between successive events to avoid re-triggering.
3. **Producer thread** calls sampler + interpreter and pushes `motion` events onto a bounded `Queue`.
4. **Consumer thread** dequeues events, enriches them with an `ingest_time` and `pipeline_latency_ms`, and writes each record as a JSON line to the output file.

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

### Running on Raspberry Pi (real hardware)

```bash
python src/pipeline.py \
  --device-id pir-01 \
  --pin 18 \
  --sample-interval 0.1 \
  --cooldown 2.0 \
  --min-high 0.3 \
  --queue-size 100 \
  --duration 60 \
  --out events.jsonl \
  --verbose
```

### Running with Mock GPIO (no hardware needed)

```bash
cd src
python test_mock.py
```

This simulates two motion pulses on GPIO pin 18 and runs the full pipeline for 5 seconds, writing output to `motion_pipeline.jsonl`.

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

**Status: Pending**

---

## Resources

- [Course Project Page](https://gbouloukakis.com/courses/ck801-s26/projects/)
- [Lab 01 — Getting Started](https://gbouloukakis.com/courses/ck801-s26/labs/getting_started/)
- [Lab 02 — Sensor Integration](https://gbouloukakis.com/courses/ck801-s26/labs/sensor_integration_code/)
- [Lab 03 — Concurrent Data Pipelines](https://gbouloukakis.com/courses/ck801-s26/labs/pipelines/)
- [Lab 04 — Portable Data Pipelines](https://gbouloukakis.com/courses/ck801-s26/labs/containers/)
- [gpiozero Documentation](https://gpiozero.readthedocs.io/)
