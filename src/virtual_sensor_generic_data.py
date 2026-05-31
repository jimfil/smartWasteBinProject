#!/usr/bin/env python3
import json
import os
import signal
import sys
import time
import click
import paho.mqtt.client as mqtt

stop_flag = False

def handle_sigint(sig, frame):
    global stop_flag
    print("\n[HA Generic Data] Ctrl+C detected, terminating...", flush=True)
    stop_flag = True

def publish_discovery(client, bin_id, verbose):
    print(f"[HA Generic Data] Publishing Home Assistant MQTT discovery configs for bin '{bin_id}'...", flush=True)

    # Shared device structure so all entities are grouped into a single device!
    device_config = {
        "identifiers": [bin_id],
        "name": f"Smart Wastebin {bin_id}",
        "model": "Smart Wastebin v1",
        "manufacturer": "Jumbo xoreuo"
    }

    # Configuration definitions for HA discovery
    configs = {
        # Ultrasonic Trash Distance
        "distance": {
            "platform": "sensor",
            "unique_id": f"{bin_id}_distance",
            "name": f"Wastebin {bin_id} Trash Distance",
            "state_topic": f"smartbin/{bin_id}/ultrasonic-01/state",
            "value_template": "{{ value_json.distance_cm }}",
            "unit_of_measurement": "cm",
            "icon": "mdi:arrow-expand-vertical",
            "device": device_config
        },
        # Ultrasonic Fill Percentage
        "fill_pct": {
            "platform": "sensor",
            "unique_id": f"{bin_id}_fill_pct",
            "name": f"Wastebin {bin_id} Fill Percentage",
            "state_topic": f"smartbin/{bin_id}/ultrasonic-01/state",
            "value_template": "{{ value_json.fill_pct }}",
            "unit_of_measurement": "%",
            "icon": "mdi:trash-can-outline",
            "device": device_config
        },
        # Temperature
        "temperature": {
            "platform": "sensor",
            "unique_id": f"{bin_id}_temperature",
            "name": f"Wastebin {bin_id} Temperature",
            "state_topic": f"smartbin/{bin_id}/temp-01/state",
            "value_template": "{{ value_json.temperature }}",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "icon": "mdi:thermometer",
            "device": device_config
        },
        # Weight
        "weight": {
            "platform": "sensor",
            "unique_id": f"{bin_id}_weight_kg",
            "name": f"Wastebin {bin_id} Weight",
            "state_topic": f"smartbin/{bin_id}/weight-01/state",
            "value_template": "{{ value_json.weight_kg }}",
            "unit_of_measurement": "kg",
            "icon": "mdi:weight-kilogram",
            "device": device_config
        },
        # Battery
        "battery": {
            "platform": "sensor",
            "unique_id": f"{bin_id}_battery",
            "name": f"Wastebin {bin_id} Battery",
            "state_topic": f"smartbin/{bin_id}/battery-01/state",
            "value_template": "{{ value_json.battery_pct }}",
            "unit_of_measurement": "%",
            "device_class": "battery",
            "icon": "mdi:battery",
            "device": device_config
        }
    }

    # Publish discovery messages with retain=True
    for key, config in configs.items():
        platform = config.pop("platform")
        discovery_topic = f"homeassistant/{platform}/{config['unique_id']}/config"
        client.publish(discovery_topic, json.dumps(config), qos=1, retain=True)
        if verbose:
            print(f"[HA Generic Data] Registered entity: {config['name']} on topic: {discovery_topic}", flush=True)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[HA Generic Data] Connected to MQTT broker successfully!", flush=True)
        # Subscribe to all mock sensor events
        bin_id = userdata["bin_id"]
        topics = [
            f"smartbin/{bin_id}/ultrasonic-01/events",
            f"smartbin/{bin_id}/temp-01/events",
            f"smartbin/{bin_id}/weight-01/events",
            f"smartbin/{bin_id}/battery-01/events"
        ]
        for topic in topics:
            client.subscribe(topic, qos=1)
            print(f"[HA Generic Data] Subscribed to topic: {topic}", flush=True)
    else:
        print(f"[HA Generic Data] Connection failed with code {rc}", flush=True)

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")
    verbose = userdata["verbose"]
    bin_id = userdata["bin_id"]

    if verbose:
        print(f"[HA Generic Data] Received event on {topic}", flush=True)

    try:
        data = json.loads(payload_str)
        # 1. Ultrasonic Event Handler
        if "ultrasonic-01" in topic:
            distance_cm = data.get("distance_cm")
            fill_pct = data.get("fill_pct")
            if distance_cm is not None and fill_pct is not None:
                state_topic = f"smartbin/{bin_id}/ultrasonic-01/state"
                state_payload = {"distance_cm": distance_cm, "fill_pct": fill_pct}
                client.publish(state_topic, json.dumps(state_payload), qos=1, retain=True)
                if verbose:
                    print(f"  -> Extracted & Published Ultrasonic State: {state_payload} to {state_topic}", flush=True)

        # 2. Temperature Event Handler
        elif "temp-01" in topic:
            temp_c = data.get("temperature_c")
            if temp_c is not None:
                state_topic = f"smartbin/{bin_id}/temp-01/state"
                state_payload = {"temperature": temp_c}
                client.publish(state_topic, json.dumps(state_payload), qos=1, retain=True)
                if verbose:
                    print(f"  -> Extracted & Published Temp State: {state_payload} to {state_topic}", flush=True)

        # 3. Weight Event Handler
        elif "weight-01" in topic:
            weight_kg = data.get("weight_kg")
            weight_g = data.get("weight_g")
            if weight_kg is not None:
                state_topic = f"smartbin/{bin_id}/weight-01/state"
                state_payload = {"weight_kg": weight_kg, "weight_g": weight_g}
                client.publish(state_topic, json.dumps(state_payload), qos=1, retain=True)
                if verbose:
                    print(f"  -> Extracted & Published Weight State: {state_payload} to {state_topic}", flush=True)

        # 4. Battery Event Handler
        elif "battery-01" in topic:
            battery_pct = data.get("battery_pct")
            if battery_pct is not None:
                state_topic = f"smartbin/{bin_id}/battery-01/state"
                state_payload = {"battery_pct": battery_pct}
                client.publish(state_topic, json.dumps(state_payload), qos=1, retain=True)
                if verbose:
                    print(f"  -> Extracted & Published Battery State: {state_payload} to {state_topic}", flush=True)

    except Exception as e:
        print(f"[HA Generic Data] Error parsing telemetry payload on topic {topic}: {e}", file=sys.stderr, flush=True)

@click.command()
@click.option("--bin-id", default="bin-01", help="Identifier of the wastebin")
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--verbose", is_flag=True, help="Print details of incoming events")
def main(bin_id, broker, port, verbose):
    global stop_flag
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    userdata = {
        "bin_id": bin_id,
        "verbose": verbose
    }

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)
    except AttributeError:
        client = mqtt.Client(userdata=userdata)

    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[HA Generic Data] Connecting to broker {broker}:{port}...", flush=True)

    try:
        client.connect(broker, port, keepalive=60)
    except Exception as e:
        print(f"[HA Generic Data] Error connecting to broker: {e}. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)

    client.loop_start()

    # Publish HA configs
    publish_discovery(client, bin_id, verbose)

    print("[HA Generic Data] Bridge is active. Listening for observation events. Press Ctrl+C to stop.", flush=True)

    try:
        while not stop_flag:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("[HA Generic Data] Disconnecting from broker...", flush=True)
    client.loop_stop()
    client.disconnect()
    print("[HA Generic Data] Terminated successfully.", flush=True)

if __name__ == "__main__":
    main()
