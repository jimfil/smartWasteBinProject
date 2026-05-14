import paho.mqtt.client as mqtt
import json
import time
import click
from datetime import datetime, timezone
from queue import Queue, Empty
from threading import Thread, Lock

event_times = Queue()
event_lock = Lock()


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode('utf-8').strip())
        if "motion_state" in data and data["motion_state"] == "detected":
            event_lock.acquire()
            event_times.put(time.time())
            event_lock.release()
    except Exception:
        pass  


def evaluate_usage(windowMinutes=10):
    cutoffTime = time.time() - (windowMinutes * 60)
    event_lock.acquire()
    while not event_times.empty() and event_times.queue[0] < cutoffTime:
        event_times.get()
    count = event_times.qsize() 
    event_lock.release()

    
    if count == 0:
        state = 'idle'
    elif count <=5:
        state = 'low'
    elif count <=15:
        state = 'medium'
    else:
        state = 'high'
        
    return (state,count)

def publish_discovery(client, publish_topic, bin_id):
    print(f"[Virtual Sensor Rules] Publishing HA discovery for bin {bin_id}...")
    
    # Usage Level Sensor
    usage_config = {
        "name": f"Wastebin {bin_id} Usage Level",
        "state_topic": publish_topic,
        "value_template": "{{ value_json.state }}",
        "unique_id": f"{bin_id}_usage_level",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}",
            "model": "Rule-based Virtual Sensor",
            "manufacturer": "IoT Lab"
        },
        "icon": "mdi:gauge"
    }
    client.publish(f"homeassistant/sensor/{bin_id}_usage/config", json.dumps(usage_config), retain=True)

    # Window Event Count Sensor
    count_config = {
        "name": f"Wastebin {bin_id} Window Event Count",
        "state_topic": publish_topic,
        "value_template": "{{ value_json.count }}",
        "unique_id": f"{bin_id}_window_count",
        "device": {
            "identifiers": [bin_id],
            "name": f"Smart Wastebin {bin_id}"
        },
        "unit_of_measurement": "events",
        "icon": "mdi:counter"
    }
    client.publish(f"homeassistant/sensor/{bin_id}_window_count/config", json.dumps(count_config), retain=True)


@click.command()
@click.option("--broker", default="localhost", help="MQTT Broker address")
@click.option("--port", type=int, default=1883, help="MQTT Broker port")
@click.option("--subscribe-topic", default="smartbin/bin-01/pir-01/events", help="MQTT topic to subscribe to")
@click.option("--publish-topic", default="smartbin/bin-01/usage_intensity", help="MQTT topic to publish to")
@click.option("--bin-id", default="bin-01", help="Identifier for the smart bin")
@click.option("--window", type=int, default=10, help="Usage evaluation window in minutes")
@click.option("--interval", type=int, default=30, help="Time between evaluations in seconds")
def main(broker: str, port: int, subscribe_topic: str, publish_topic: str, bin_id: str, window: int, interval: int):
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(broker, port)
    client.subscribe(subscribe_topic)
    client.loop_start()
    
    publish_discovery(client, publish_topic, bin_id)
    
    print(f"[Virtual Sensor Rules] Monitoring {subscribe_topic} for usage evaluation window of {window} minutes")
    try:
        while True:
            state, count = evaluate_usage(window)
            payload = {
                "state": state,
                "count": count,
                "window_minutes": window,
                "timestamp": time.time()
            }
            client.publish(publish_topic, json.dumps(payload), qos=1, retain=True)
            print(f"[Virtual Sensor Rules] State: {state}, Count: {count}")
            time.sleep(interval)
    except KeyboardInterrupt:
        client.disconnect()
        print("[Virtual Sensor Rules] Disconnected from broker.")

if __name__ == "__main__":
    main()