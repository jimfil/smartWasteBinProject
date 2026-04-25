"""
MQTT Consumer: Subscribes to motion events and logs them to a file.

This is the consumer in the pub/sub architecture - it subscribes to MQTT
topics independently and processes events without coupling to the producer.
Multiple consumers can subscribe to the same topics without affecting each other.
"""

import paho.mqtt.client as mqtt
import json
import click
from datetime import datetime, timezone
from paho.mqtt.enums import CallbackAPIVersion

def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_iso_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


BROKER_ADDRESS = "localhost"
BROKER_PORT = 1883

def on_connect(client, userdata, flags, rc, properties):
    """Callback that executes when the client connects to the broker."""
    topic = userdata["topic"]
    status_topic = userdata["status_topic"]
    if rc == 0:
        print(f"[Consumer] Successfully connected to broker at {userdata['broker']}:{userdata['port']}")
        client.subscribe(topic, qos=userdata["qos"])
        print(f"[Consumer] Subscribed to topic: {topic}")
        client.subscribe(status_topic, qos=userdata["qos"])
        print(f"[Consumer] Subscribed to status topic: {status_topic}")
    else:
        print(f"[Consumer] Connection failed with code: {rc}")


def on_message(client, userdata, msg):
    """Callback that executes when a message is received from a topic."""
    metrics = userdata["metrics"]
    out_file = userdata["out_file"]
    verbose = userdata["verbose"]
    
    payload = msg.payload.decode('utf-8')
    
    # Check if this is a status message (retained)
    if msg.topic == userdata["status_topic"]:
        print(f"[Consumer] Producer status: {payload}")
        metrics["status_updates"] += 1
        return
    
    # Handle event messages
    try:
        record = json.loads(payload)
        if verbose:
            print(f"[Consumer] Received message on topic '{msg.topic}': {record}")

        current_utc_iso = utc_now_iso()
        record["ingest_time"] = current_utc_iso
        event_dt  = parse_iso_utc(record["event_time"])
        ingest_dt = parse_iso_utc(current_utc_iso)

        latency_s = (ingest_dt - event_dt).total_seconds()
        record["pipeline_latency_ms"] = round(latency_s * 1000, 3)

        with open(out_file, "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
        
        metrics["consumed"] += 1
        print(f"[Consumer] Latency: {record['pipeline_latency_ms']} ms")
    except Exception as e:
        print(f"[Consumer] Error processing message: {e}")
        metrics["dropped"] += 1
    
    print(f"[Consumer] Stats - Consumed: {metrics['consumed']}, Dropped: {metrics['dropped']}, Status updates: {metrics['status_updates']}")


@click.command()
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--topic", type=str, default="smartbin/bin-01/pir-01/events", help="MQTT topic for events")
@click.option("--status-topic", default="smartbin/bin-01/pir-01/status", help="MQTT topic for sensor status")
@click.option("--qos", type=int, default=1, help="MQTT QoS (0=At most once, 1=At least once, 2=Exactly once)")
@click.option("--out", required=True, help="Path to the output JSONL file")
@click.option("--verbose", is_flag=True, help="Print status messages to the terminal")
def main(broker: str, port: int, topic: str, status_topic: str, qos: int, out: str, verbose: bool):
    """
    MQTT Consumer: subscribes to motion events and logs them to a file.
    """
    # Creating an MQTT client
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    
    # Prepare userdata for callbacks
    metrics = {
        "consumed": 0,
        "dropped": 0,
        "status_updates": 0,
    }
    userdata = {
        "broker": broker,
        "port": port,
        "topic": topic,
        "status_topic": status_topic,
        "qos": qos,
        "metrics": metrics,
        "out_file": out,
        "verbose": verbose,
    }
    client.user_data_set(userdata)
    
    # Set callback functions
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the MQTT broker
    print(f"[Consumer] Connecting to broker at {broker}:{port}...")
    client.connect(broker, port, keepalive=60)
    print("[Consumer] Waiting for messages... Press Ctrl+C to exit.")
    
    # loop_forever keeps the client running, constantly listening for events
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[Consumer] Received Ctrl+C, disconnecting...")
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
