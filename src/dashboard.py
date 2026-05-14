"""
MQTT Dashboard: Subscribes to all smartbin topics and displays real-time events.

This component demonstrates the power of pub/sub messaging:
- Single subscription to 'smartbin/#' captures all events across all sensors/bins
- No direct coupling to producers (producer doesn't need to know about this)
- Easy to add/remove without modifying existing components
"""

import paho.mqtt.client as mqtt
import json
import click
from datetime import datetime, timezone
from collections import defaultdict
from paho.mqtt.enums import CallbackAPIVersion
# ANSI color codes for terminal output
COLORS = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "RED": "\033[91m",
}

# Track metrics by topic
topic_metrics = defaultdict(lambda: {"count": 0, "last_time": None})

def on_connect(client, userdata, flags, rc):
    """Callback when client connects to broker."""
    broker = userdata.get("broker", "localhost")
    port = userdata.get("port", 1883)
    
    if rc == 0:
        print(f"{COLORS['GREEN']}[Dashboard] Connected to broker at {broker}:{port}{COLORS['RESET']}")
        topic = userdata.get("topic", "smartbin/#")
        qos = userdata.get("qos", 1)
        client.subscribe(topic, qos=qos)
        print(f"{COLORS['GREEN']}[Dashboard] Subscribed to: {topic}{COLORS['RESET']}")
        print(f"{COLORS['CYAN']}{'='*80}{COLORS['RESET']}")
        print(f"{COLORS['BOLD']}Smart Waste Bin — Real-Time Event Dashboard{COLORS['RESET']}")
        print(f"{COLORS['CYAN']}{'='*80}{COLORS['RESET']}\n")
    else:
        print(f"{COLORS['RED']}[Dashboard] Connection failed with code: {rc}{COLORS['RESET']}")

def on_message(client, userdata, msg):
    """Callback when a message is received."""
    verbose = userdata.get("verbose", False)
    
    try:
        # Decode payload
        payload = msg.payload.decode('utf-8')
        topic = msg.topic
        
        # 1. Handle Status messages
        if "status" in topic:
            print(f"{COLORS['YELLOW']}[Status Update]{COLORS['RESET']} {topic}: {COLORS['BOLD']}{payload}{COLORS['RESET']}")
            topic_metrics[topic]["count"] += 1
            topic_metrics[topic]["last_time"] = datetime.now(timezone.utc).isoformat()
            return

        # 2. Handle simple state topics (motion strings, event counts)
        if "motion" in topic or "event_count" in topic:
            print(f"{COLORS['CYAN']}[Sensor State]{COLORS['RESET']} {topic}: {COLORS['BOLD']}{payload}{COLORS['RESET']}")
            topic_metrics[topic]["count"] += 1
            topic_metrics[topic]["last_time"] = datetime.now(timezone.utc).isoformat()
            return

        # 3. Try to parse as JSON
        try:
            record = json.loads(payload)
        except json.JSONDecodeError:
            # Fallback for any other non-JSON messages
            print(f"{COLORS['CYAN']}[Raw Message]{COLORS['RESET']} {topic}: {payload}")
            return

        # If it's a valid JSON but not a dictionary (e.g. just a number or string), handle it
        if not isinstance(record, dict):
            print(f"{COLORS['CYAN']}[Value]{COLORS['RESET']} {topic}: {record}")
            return

        # 4. Handle Analytics topics (usage_intensity, usage_prediction)
        if "usage_" in topic:
            # Usage intensity uses 'state', ML prediction uses 'prediction' (which is a list)
            state = record.get("state") or record.get("prediction")
            if isinstance(state, list) and len(state) > 0:
                state = state[0]
            
            timestamp = record.get("timestamp") or record.get("utc_prediction_timestamp")
            time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S') if timestamp else "now"

            print(f"{COLORS['BLUE']}[{time_str}]{COLORS['RESET']} "
                  f"{COLORS['YELLOW']}ANALYTICS{COLORS['RESET']} on {COLORS['BOLD']}{topic}{COLORS['RESET']}: "
                  f"{COLORS['GREEN']}{str(state).upper() if state else 'N/A'}{COLORS['RESET']}")
            
            if verbose:
                for k, v in record.items():
                    print(f"  • {k}: {v}")
            return

        # 5. Handle standard SOSA/Observation events
        event_type = record.get("event_type", "observation")
        device_id = record.get("device_id", "unknown")
        timestamp = record.get("event_time", "unknown")
        
        # Format and display event
        print(f"{COLORS['BLUE']}[{timestamp}]{COLORS['RESET']} "
              f"{COLORS['GREEN']}{event_type.upper()}{COLORS['RESET']} "
              f"from {COLORS['CYAN']}{device_id}{COLORS['RESET']} "
              f"on {COLORS['BOLD']}{topic}{COLORS['RESET']}")
        
        # Display additional details if verbose
        if verbose:
            for key, value in record.items():
                if key not in ["@context", "@type", "device_id", "event_type", "event_time"]:
                    print(f"  • {key}: {value}")
        
        # Update metrics
        topic_metrics[topic]["count"] += 1
        topic_metrics[topic]["last_time"] = timestamp
        
    except Exception as e:
        print(f"{COLORS['RED']}[Dashboard] Error processing message: {e}{COLORS['RESET']}")

def print_metrics():
    """Print summary metrics."""
    if topic_metrics:
        print(f"\n{COLORS['CYAN']}{'='*80}{COLORS['RESET']}")
        print(f"{COLORS['BOLD']}Topic Metrics:{COLORS['RESET']}")
        for topic, metrics in sorted(topic_metrics.items()):
            print(f"  {topic}: {metrics['count']} events (last: {metrics['last_time']})")

@click.command()
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--topic", type=str, default="smartbin/#", help="MQTT topic pattern to subscribe to")
@click.option("--qos", type=int, default=1, help="MQTT QoS (0=At most once, 1=At least once, 2=Exactly once)")
@click.option("--verbose", is_flag=True, help="Print detailed event information")
def main(broker: str, port: int, topic: str, qos: int, verbose: bool):
    """
    MQTT Dashboard: Display real-time events from all smartbin topics.
    
    This demonstrates pub/sub architecture:
    - Subscribes to smartbin/# to receive all events from all sensors/bins
    - Independently displays information without coupling to producers
    - Easy to add visualization, alerting, or other logic
    """
    print("test1")
    client = mqtt.Client()
    print("test2")
    # Prepare userdata
    userdata = {
        "broker": broker,
        "port": port,
        "topic": topic,
        "qos": qos,
        "verbose": verbose,
    }
    client.user_data_set(userdata)
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect
    print(f"[Dashboard] Connecting to broker at {broker}:{port}...")
    client.connect(broker, port, keepalive=60)
    
    print("[Dashboard] Listening for events... Press Ctrl+C to exit.\n")
    
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\n{COLORS['YELLOW']}[Dashboard] Received Ctrl+C, disconnecting...{COLORS['RESET']}")
        print_metrics()
        client.disconnect()
        client.loop_stop()

if __name__ == "__main__":
    main()
