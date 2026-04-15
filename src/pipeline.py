import sys
import os

# Add root folder to sys.path to allow absolute imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import time
import uuid
import click
import threading
from queue import Queue, Full, Empty
from datetime import datetime, timezone
from typing import Dict, Any

from src.pirlib.sampler import PirSampler
from src.pirlib.interpreter import PirInterpreter

SENSOR_ID      = "urn:dev:team05:pir-01"
WASTEBIN_ID    = "urn:wastebin:bin-01"
ENVIRONMENT_ID = "urn:env:kypes-02"

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

# Use a remote context URL to avoid massive inline context dictionaries in the output
JSONLD_CONTEXT = "https://raw.githubusercontent.com/jimfil/smartWasteBinProject/main/src/models/context.jsonld"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_iso_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def producer_loop(
    event_q: Queue,
    sampler: PirSampler,
    interp: PirInterpreter,
    device_id: str,
    sample_interval: float,
    metrics: dict,
    stop_flag: dict,
):
    run_id = str(uuid.uuid4())
    seq = 0

    while not stop_flag["stop"]:
        current_time_s = time.time()
        raw = sampler.read()
        events = interp.update(raw, current_time_s)

        for event in events:
            seq += 1
            record = {
                "@context":        JSONLD_CONTEXT,
                "@type":           "sosa:Observation",

                "device_id":       SENSOR_ID,
                "sensor_ref":      SENSOR_ID,
                "wastebin_ref":    WASTEBIN_ID,
                "environment_ref": ENVIRONMENT_ID,

                "event_time":      utc_now_iso(),
                "event_type":      "motion",
                "motion_state":    "detected",

                "seq":             seq,
                "run_id":          run_id,
            }

            try:
                event_q.put_nowait(record)
                metrics["produced"] += 1
            except Full:
                metrics["dropped"] += 1

        time.sleep(sample_interval)


def consumer_loop(
    event_q: Queue,
    out_file: str,
    consumer_delay: float,
    metrics: dict,
    stop_flag: dict,
):
    path = "data/" + out_file
    
    data_dir = os.path.dirname(path)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)

    with open(path, "a") as f:
        while not stop_flag["stop"] or not event_q.empty():
            try:
                record = event_q.get(timeout=0.5)
            except Empty:
                continue

            current_utc_iso = utc_now_iso()
            record["ingest_time"] = current_utc_iso

            event_dt  = parse_iso_utc(record["event_time"])
            ingest_dt = parse_iso_utc(record["ingest_time"])

            latency_s = (ingest_dt - event_dt).total_seconds()
            record["pipeline_latency_ms"] = round(latency_s * 1000, 3)

            f.write(json.dumps(record) + "\n")
            f.flush()

            metrics["consumed"] += 1
            current_qsize = event_q.qsize()
            if current_qsize > metrics["max_queue"]:
                metrics["max_queue"] = current_qsize

            event_q.task_done()

            if consumer_delay > 0:
                time.sleep(consumer_delay)


@click.command()
@click.option("--device-id", required=True, help="Unique identifier for this device")
@click.option("--pin", type=int, required=True, help="GPIO pin the PIR is connected to")
@click.option("--sample-interval", type=float, required=True, help="Seconds between sensor samples")
@click.option("--cooldown", type=float, required=True, help="Cooldown in seconds between motion events")
@click.option("--min-high", type=float, required=True, help="Minimum high time in seconds to trigger an event")
@click.option("--queue-size", type=int, required=True, help="Maximum number of items the queue can hold")
@click.option("--consumer-delay", type=float, default=0.0, help="Artificial delay in seconds for the consumer")
@click.option("--duration", type=float, required=True, help="How long to run the pipeline in seconds")
@click.option("--out", default="motion_pipeline.log", help="Path to the output JSONL file")
@click.option("--verbose", is_flag=True, help="Print status messages to the terminal")
def main(
    device_id: str,
    pin: int,
    sample_interval: float,
    cooldown: float,
    min_high: float,
    queue_size: int,
    consumer_delay: float,
    duration: float,
    out: str,
    verbose: bool,
):
    metrics = {
        "produced": 0,
        "consumed": 0,
        "dropped": 0,
        "max_queue": 0,
    }
    stop_flag = {"stop": False}
    event_q: Queue[Dict[str, Any]] = Queue(maxsize=queue_size)

    sampler = PirSampler(pin=pin)
    interp = PirInterpreter(cooldown_s=cooldown, min_high_s=min_high)

    producer_t = threading.Thread(
        target=producer_loop,
        args=(event_q, sampler, interp, device_id, sample_interval, metrics, stop_flag),
        daemon=True,
    )
    consumer_t = threading.Thread(
        target=consumer_loop,
        args=(event_q, out, consumer_delay, metrics, stop_flag),
        daemon=True,
    )

    producer_t.start()
    consumer_t.start()

    start_t = time.time()
    try:
        while (time.time() - start_t) < duration:
            if verbose:
                print(
                    f"[status] produced={metrics['produced']} "
                    f"consumed={metrics['consumed']} "
                    f"dropped={metrics['dropped']} "
                    f"queue={event_q.qsize()} "
                    f"max_queue={metrics['max_queue']}",
                    flush=True
                )
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[main] Ctrl-C: stopping...")
    finally:
        stop_flag["stop"] = True
        producer_t.join()
        print("Please wait for the consumer to stop!")
        consumer_t.join()


if __name__ == "__main__":
    main()
