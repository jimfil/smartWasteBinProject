"""
MQTT Archiver: Subscribes to all smartbin topics and logs events to a persistent archive.

This demonstrates data logging in a pub/sub system:
- Single subscription to 'smartbin/#' captures all events for archival
- Independent from producers and consumers
- Provides a complete audit trail of all system events
"""

import paho.mqtt.client as mqtt
import json
import click
from datetime import datetime, timezone

def utc_now_iso() -> str:
    """Get current UTC time in ISO format."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

def parse_iso_utc(s: str) -> datetime:
    """Parse ISO UTC string back to datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def on_connect(client, userdata, flags, rc):
    """Callback when client connects to broker."""
    broker = userdata.get("broker", "localhost")
    port = userdata.get("port", 1883)
    
    if rc == 0:
        print(f"[Archiver] Connected to broker at {broker}:{port}")
        topic = userdata.get("topic", "smartbin/#")
        qos = userdata.get("qos", 1)
        client.subscribe(topic, qos=qos)
        print(f"[Archiver] Subscribed to: {topic}")
    else:
        print(f"[Archiver] Connection failed with code: {rc}")

def on_message(client, userdata, msg):
    """Callback when a message is received."""
    out_file = userdata.get("out_file")
    verbose = userdata.get("verbose", False)
    metrics = userdata.get("metrics")
    
    try:
        payload = msg.payload.decode('utf-8')
        
        # Create archive record with metadata
        archive_record = {
            "topic": msg.topic,
            "timestamp": utc_now_iso(),
            "qos": msg.qos,
            "retain": msg.retain,
            "payload": json.loads(payload) if msg.topic != "smartbin/bin-01/pir-01/status" else payload,
        }
        
        # Write to archive file
        with open(out_file, "a") as f:
            f.write(json.dumps(archive_record) + "\n")
            f.flush()
        
        metrics["archived"] += 1
        
        if verbose:
            print(f"[Archiver] Archived message from {msg.topic} (total: {metrics['archived']})")
    
    except Exception as e:
        print(f"[Archiver] Error archiving message: {e}")
        metrics["dropped"] += 1

@click.command()
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--topic", type=str, default="smartbin/#", help="MQTT topic pattern to subscribe to")
@click.option("--qos", type=int, default=1, help="MQTT QoS (0=At most once, 1=At least once, 2=Exactly once)")
@click.option("--out", required=True, help="Path to the archive JSONL file")
@click.option("--verbose", is_flag=True, help="Print archival status messages")
def main(broker: str, port: int, topic: str, qos: int, out: str, verbose: bool):
    """
    MQTT Archiver: Archive all smartbin events for long-term storage.
    
    This demonstrates durable data logging in a pub/sub system:
    - Subscribes to smartbin/# to capture all events
    - Logs complete event history with metadata (topic, timestamp, qos, retain flag)
    - Independent component that doesn't affect producers or other consumers
    - Useful for analytics, auditing, and debugging
    """
    client = mqtt.Client()
    
    # Prepare userdata
    metrics = {"archived": 0, "dropped": 0}
    userdata = {
        "broker": broker,
        "port": port,
        "topic": topic,
        "qos": qos,
        "out_file": out,
        "verbose": verbose,
        "metrics": metrics,
    }
    client.user_data_set(userdata)
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect
    print(f"[Archiver] Connecting to broker at {broker}:{port}...")
    client.connect(broker, port, keepalive=60)
    print(f"[Archiver] Archiving to: {out}")
    print("[Archiver] Listening for events... Press Ctrl+C to exit.\n")
    
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\n[Archiver] Received Ctrl+C, disconnecting...")
        print(f"[Archiver] Final stats - Archived: {metrics['archived']}, Dropped: {metrics['dropped']}")
        client.disconnect()
        client.loop_stop()

if __name__ == "__main__":
    main()
