import json
import time
import uuid
import os
import signal
from datetime import datetime, timezone

import click
import paho.mqtt.client as mqtt

from pirlib.sampler import PirSampler
from pirlib.interpreter import PirInterpreter

from apiFunc import find_sensor, find_bin

# Constants for default values if not found
DEFAULT_SENSOR_ID      = "urn:dev:team05:pir-01"
DEFAULT_WASTEBIN_ID    = "urn:wastebin:bin-01"
DEFAULT_ENVIRONMENT_ID = "urn:env:kypes-02"

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

def _load_context() -> dict:
    path = os.path.join(_MODELS_DIR, "context.jsonld")
    with open(path) as f:
        ctx = json.load(f)
    return ctx["@context"]

JSONLD_CONTEXT = _load_context()

def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

stop_flag = False

def handle_sigint(sig, frame):
    global stop_flag
    print("\n[Producer] Ctrl+C detected, terminating...")
    stop_flag = True

def publish_discovery(client, bin_id, sensor_id):
    print(f"[Producer] Publishing HA discovery messages for {sensor_id} on {bin_id}...")
    
    motion_config = {
        "name": f"PIR Motion Sensor {sensor_id}", 
        "state_topic": f"smartbin/{bin_id}/{sensor_id}/motion", 
        "value_template": "{{ value_json.state }}",
        "payload_on": "detected", 
        "payload_off": "clear", 
        "device_class": "motion", 
        "unique_id": f"{sensor_id}_motion", 
        "device": { 
            "identifiers": [sensor_id], 
            "name": f"PIR Sensor {sensor_id}", 
            "model": "HC-SR501", 
            "manufacturer": "Generic" 
        } 
    }
    client.publish(f"homeassistant/binary_sensor/{sensor_id}_motion/config", json.dumps(motion_config), retain=True)

    status_config = { 
        "name": f"Wastebin {bin_id} Status", 
        "state_topic": f"smartbin/{bin_id}/status", 
        "value_template": "{{ value_json.state }}", 
        "json_attributes_topic": f"smartbin/{bin_id}/status", 
        "unique_id": f"{bin_id}_status", 
        "device": { 
            "identifiers": [bin_id], 
            "name": f"Smart Wastebin {bin_id}", 
            "model": "Smart Wastebin v1", 
            "manufacturer": "Jumbo xoreuo" 
        } 
    }
    client.publish(f"homeassistant/sensor/{bin_id}_status/config", json.dumps(status_config), retain=True)

    count_config = { 
        "name": f"Motion Event Count {sensor_id}", 
        "state_topic": f"smartbin/{bin_id}/{sensor_id}/event_count", 
        "value_template": "{{ value_json.count }}",
        "unit_of_measurement": "events", 
        "icon": "mdi:motion-sensor", 
        "unique_id": f"{bin_id}_{sensor_id}_motion_count", 
        "device": { 
            "identifiers": [bin_id], 
            "name": f"Smart Wastebin {bin_id}" 
        } 
    }
    client.publish(f"homeassistant/sensor/{bin_id}_{sensor_id}_motion_count/config", json.dumps(count_config), retain=True)

    ack_button_config = {
        "name": f"Acknowledge Alert {bin_id}",
        "command_topic": "smartbin/nodered/alert_ack",
        "payload_press": json.dumps({"bin_id": bin_id, "level": "ACK", "operator": "Home Assistant"}),
        "icon": "mdi:check-circle-outline",
        "unique_id": f"{bin_id}_ack_alert",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        }
    }
    client.publish(f"homeassistant/button/{bin_id}_ack_alert/config", json.dumps(ack_button_config), retain=True)

    ack_button_config = {
        "name": f"Acknowledge Alert {bin_id}",
        "command_topic": "smartbin/nodered/alert_ack",
        "payload_press": json.dumps({
            "bin_id": bin_id,
            "level": "HIGH",  # This will be dynamic later
            "operator": "HomeAssistant"
        }),
        "unique_id": f"{bin_id}_ack_button",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        },
        "icon": "mdi:check-circle"
    }
    client.publish(
        f"homeassistant/button/{bin_id}_ack/config",
        json.dumps(ack_button_config),
        retain=True
    )


    # Alert Status Sensor (shows current alert level)
    alert_status_config = {
        "name": f"Alert Status {bin_id}",
        "state_topic": f"smartbin/{bin_id}/alerts/current_status",
        "value_template": "{{ value_json.level }}",
        "json_attributes_topic": f"smartbin/{bin_id}/alerts/current_status",
        "json_attributes_template": "{{ {'message': value_json.message, 'fill_pct': value_json.fill_pct, 'timestamp': value_json.timestamp} | tojson }}",
        "unique_id": f"{bin_id}_alert_status",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        },
        "icon": "mdi:alert-circle"
    }
    client.publish(
        f"homeassistant/sensor/{bin_id}_alert_status/config",
        json.dumps(alert_status_config),
        retain=True
    )
    print(f"[Producer] Published alert status sensor for {bin_id}")

    # Alert Message Sensor (shows the full alert message)
    alert_message_config = {
        "name": f"Latest Alert {bin_id}",
        "state_topic": f"smartbin/{bin_id}/alerts/current_status",
        "value_template": "{{ value_json.message }}",
        "unique_id": f"{bin_id}_alert_message",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        },
        "icon": "mdi:message-alert"
    }
    client.publish(
        f"homeassistant/sensor/{bin_id}_alert_message/config",
        json.dumps(alert_message_config),
        retain=True
    )
    print(f"[Producer] Published alert message sensor for {bin_id}")


    solved_button_config = {
        "name": f"Mark Alert Solved {bin_id}",
        "command_topic": "smartbin/nodered/alert_solved",
        "payload_press": json.dumps({
            "bin_id": bin_id,
            "operator": "HomeAssistant"
        }),
        "unique_id": f"{bin_id}_solved_button",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        },
        "icon": "mdi:check-all"
    }
    client.publish(
        f"homeassistant/button/{bin_id}_solved/config",
        json.dumps(solved_button_config),
        retain=True
    )


@click.command()
@click.option("--sensor-id", default=DEFAULT_SENSOR_ID, help="URN of the sensor")
@click.option("--pin", type=int, default=4, help="GPIO pin the PIR is connected to")
@click.option("--sample-interval", type=float, default=0.1, help="Seconds between sensor samples")
@click.option("--cooldown", type=float, default=2.0, help="Cooldown in seconds between motion events")
@click.option("--min-high", type=float, default=0.5, help="Minimum high time in seconds to trigger an event")
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--verbose", is_flag=True, help="Print status messages to the terminal")
def main(
    sensor_id: str,
    pin: int,
    sample_interval: float,
    cooldown: float,
    min_high: float,
    broker: str,
    port: int,
    verbose: bool,
):
    global stop_flag
    signal.signal(signal.SIGINT, handle_sigint)

    # Load dynamic configuration
    sensor_data = find_sensor(sensor_id)
    if not sensor_data:
        print(f"Error: Sensor {sensor_id} not found in models.")
        return
    
    bin_urn = sensor_data.get("mounted_on", DEFAULT_WASTEBIN_ID)
    bin_data = find_bin(bin_urn)
    
    sensor_short_id = sensor_id.split(":")[-1]
    bin_short_id = bin_urn.split(":")[-1]
    
    topic = f"smartbin/{bin_short_id}/{sensor_short_id}/events"
    status_topic = f"smartbin/{bin_short_id}/status"
    motion_topic = f"smartbin/{bin_short_id}/{sensor_short_id}/motion"
    count_topic = f"smartbin/{bin_short_id}/{sensor_short_id}/event_count"
    
    environment_id = DEFAULT_ENVIRONMENT_ID # Could also be loaded from models

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    
    client.will_set(status_topic, json.dumps({"state": "offline"}), qos=1, retain=True)
    
    if verbose:
        print(f"[Producer] Connecting to broker {broker}:{port}...")
    client.connect(broker, port, keepalive=60)
    
    client.loop_start()

    publish_discovery(client, bin_short_id, sensor_short_id)

    sampler = PirSampler(pin=pin)
    interp = PirInterpreter(cooldown_s=cooldown, min_high_s=min_high)

    run_id = str(uuid.uuid4())
    seq = 0
    
    event_count = 0
    ha_motion_state = "clear"
    last_event_time_s = 0
    init_status = {
        "state": "active",
        "location": "Lab Room 101",
        "last_motion": "None",
        "total_events_today": event_count
    }
    client.publish(status_topic, json.dumps(init_status), retain=True)
    
    last_motion_iso = None

    print("[Producer] Started reading the sensor (while not stopped). Press Ctrl+C to stop.")
    if verbose:
        print(f"[Producer] Run ID: {run_id}")
        print(f"[Producer] Publishing events to topic: {topic}")
    
    while not stop_flag:
        current_time_s = time.time()
        
        raw = sampler.read()
        
        events = interp.update(raw, current_time_s)

        for event in events:
            seq += 1
            event_count += 1
            last_event_time_s = current_time_s
            ha_motion_state = "detected"
            last_motion_iso = utc_now_iso()
            
            # Publish HA states in JSON format
            client.publish(motion_topic, json.dumps({"state": ha_motion_state}), retain=True)
            client.publish(count_topic, json.dumps({"count": event_count}), retain=True)
            status_payload = {
                "state": "active",
                "location": bin_data.get("location", "Unknown") if bin_data else "Unknown",
                "last_motion": last_motion_iso,
                "total_events_today": event_count
            }
            client.publish(status_topic, json.dumps(status_payload), retain=True)
            
            record = {
                "@context":        JSONLD_CONTEXT,
                "@type":           "sosa:Observation",

                "device_id":       sensor_id,
                "sensor_ref":      sensor_id,
                "wastebin_ref":    bin_urn,
                "environment_ref": environment_id,

                "event_time":      last_motion_iso,
                "event_type":      "motion",
                "motion_state":    "detected",

                "seq":             seq,
                "run_id":          run_id,
            }
            
            payload = json.dumps(record)
            
            client.publish(topic, payload, qos=1)
            
            if verbose:
                print(f"[Producer] Sent event #{seq}")

        if ha_motion_state == "detected" and (current_time_s - last_event_time_s) > cooldown:
            ha_motion_state = "clear"
            client.publish(motion_topic, json.dumps({"state": ha_motion_state}), retain=True)
            if verbose:
                print(f"[Producer] Motion cleared after cooldown.")

        time.sleep(sample_interval)

    if verbose:
        print("[Producer] Terminating...")
    
    end_status = {
        "state": "offline",
        "location": bin_data.get("location", "Unknown") if bin_data else "Unknown",
        "last_motion": last_motion_iso if last_motion_iso is not None else "none",
        "total_events_today": event_count
    }

    client.publish(status_topic, json.dumps(end_status), qos=1, retain=True)
    time.sleep(0.5) 
    
    client.loop_stop()
    client.disconnect()
    
    if verbose:
        print("[Producer] Disconnection successful.")

if __name__ == "__main__":
    main()
